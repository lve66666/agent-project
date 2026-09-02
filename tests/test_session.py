from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pine.session import SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_workspace_isolation_and_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            store = SessionStore(base / "sessions", max_sessions=3)
            one, two = base / "one", base / "two"
            one.mkdir(); two.mkdir()
            item = store.record(one, task="first", summary="done", reason="completed",
                                transcript=[{"role": "user", "content": "hello"}])
            self.assertEqual(store.get(one, item.session_id).task, "first")
            self.assertEqual(store.load(two), [])

    def test_limit_and_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            workspace = Path(root) / "workspace"; workspace.mkdir()
            store = SessionStore(Path(root) / "sessions", max_sessions=2, max_transcript_chars=1_000)
            for index in range(4):
                store.record(workspace, task=str(index), summary="ok", reason="completed",
                             transcript=[{"role": "user", "content": "sk-abcdefgh12345678 " + ("x" * 400)}])
            records = store.load(workspace)
            self.assertEqual(len(records), 2)
            self.assertNotIn("sk-abcdefgh12345678", str(records[-1].transcript))
            self.assertLessEqual(len(str(records[-1].transcript)), 1_500)

    def test_continue_messages_excludes_system_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            workspace = Path(root) / "workspace"; workspace.mkdir()
            store = SessionStore(Path(root) / "sessions")
            item = store.record(workspace, task="old", summary="done", reason="completed", transcript=[
                {"role": "system", "content": "secret system"},
                {"role": "user", "content": "old"},
                {"role": "assistant", "content": "answer"},
            ])
            messages = store.continue_messages(workspace, item.session_id)
            self.assertEqual([message["role"] for message in messages], ["user", "assistant"])

    def test_corrupt_line_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            workspace = Path(root) / "workspace"; workspace.mkdir()
            store = SessionStore(Path(root) / "sessions")
            path = store._path(workspace)
            path.parent.mkdir()
            path.write_text("not json\n", encoding="utf-8")
            self.assertEqual(store.load(workspace), [])

    def test_continuation_updates_the_same_session(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            workspace = Path(root) / "workspace"; workspace.mkdir()
            store = SessionStore(Path(root) / "sessions")
            first = store.record(workspace, task="first", summary="one", reason="completed",
                                 transcript=[{"role": "user", "content": "first"}])
            updated = store.record(workspace, task="follow up", summary="two", reason="completed",
                                   transcript=[{"role": "user", "content": "first"}, {"role": "user", "content": "follow up"}],
                                   session_id=first.session_id)
            records = store.load(workspace)
            self.assertEqual(len(records), 1)
            self.assertEqual(updated.session_id, first.session_id)
            self.assertEqual(records[0].task, "first")
            self.assertEqual(records[0].summary, "two")


if __name__ == "__main__":
    unittest.main()
