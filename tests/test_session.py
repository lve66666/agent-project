from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pine.session import SessionStore
from pine.workspace import Workspace


class SessionStoreTests(unittest.TestCase):
    def test_workspace_histories_are_isolated_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            store = SessionStore(root / "sessions", max_entries=2, max_entry_chars=300, max_memory_chars=500)
            store.record(first, task="first task", summary="first summary", reason="completed")
            store.record(first, task="second task", summary="second summary", reason="completed")
            store.record(first, task="third task", summary="third summary", reason="max_turns")
            store.record(second, task="other task", summary="other summary", reason="completed")

            first_entries = store.load(Workspace(first))
            self.assertEqual(len(first_entries), 2)
            self.assertEqual(first_entries[-1]["task"], "third task")
            self.assertEqual(store.load(Workspace(second))[-1]["task"], "other task")
            self.assertNotEqual(store.path_for(first).name, store.path_for(second).name)
            memory = store.memory_messages(first)
            self.assertEqual(len(memory), 1)
            self.assertIn("third task", memory[0]["content"])
            self.assertNotIn("first task", memory[0]["content"])

    def test_records_are_redacted_and_clipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "project").mkdir(exist_ok=True)
            workspace = Workspace(root / "project")
            store = SessionStore(root / "sessions", max_entry_chars=256)
            store.record(workspace, task="token sk-secret-value " + "x" * 500, summary="ok", reason="completed")
            entry = store.load(workspace)[0]
            self.assertNotIn("sk-secret-value", entry["task"])
            self.assertLessEqual(len(entry["task"]), 256)
            raw = store.path_for(workspace).read_text(encoding="utf-8")
            self.assertNotIn("sk-secret-value", raw)
            json.loads(raw)

    def test_clear_removes_only_selected_workspace_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            store = SessionStore(root / "sessions")
            store.record(first, task="one", summary="one", reason="completed")
            store.record(second, task="two", summary="two", reason="completed")
            store.clear(first)
            self.assertEqual(store.load(first), [])
            self.assertEqual(len(store.load(second)), 1)
