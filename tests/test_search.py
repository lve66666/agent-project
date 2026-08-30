from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pine.search import SearchError, search_text
from pine.workspace import Workspace, WorkspaceError


class SearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace = Workspace(self.root)
        (self.root / "src").mkdir()
        (self.root / "src" / "a.py").write_text("TODO: first\ndef divide(a, b):\n    return a / b\n", encoding="utf-8")
        (self.root / "src" / "b.py").write_text("# TODO: second\n", encoding="utf-8")
        (self.root / ".git").mkdir()
        (self.root / ".git" / "hidden.py").write_text("TODO hidden\n", encoding="utf-8")
        (self.root / "binary.bin").write_bytes(b"TODO\x00hidden")
        (self.root / "large.py").write_bytes(b"TODO\n" + b"x" * Workspace.MAX_FILE_BYTES)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_literal_search_skips_hidden_binary_and_large_files(self) -> None:
        result = search_text(self.workspace, "TODO", max_results=10)
        self.assertIn("src/a.py:1", result)
        self.assertIn("src/b.py:1", result)
        self.assertNotIn("hidden.py", result)
        self.assertIn("skipped", result)

    def test_regex_and_result_limit(self) -> None:
        result = search_text(self.workspace, r"def\s+divide", use_regex=True)
        self.assertIn("src/a.py:2", result)
        limited = search_text(self.workspace, "TODO", max_results=1)
        self.assertIn("results limited to 1", limited)

    def test_invalid_regex_and_escape_are_rejected(self) -> None:
        with self.assertRaisesRegex(SearchError, "regular expression"):
            search_text(self.workspace, "[", use_regex=True)
        with self.assertRaisesRegex(WorkspaceError, "escapes"):
            search_text(self.workspace, "TODO", path="..")
