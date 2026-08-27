from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pine.workspace import Workspace, WorkspaceError


class WorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace = Workspace(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_write_then_read_numbered_lines(self) -> None:
        self.workspace.write_file("package/example.py", "one\ntwo\nthree\n")
        self.assertEqual(self.workspace.read_file("package/example.py", 2, 3), "    2: two\n    3: three")
        self.assertIn("package/", self.workspace.list_files(".", depth=2))

    def test_parent_traversal_is_rejected(self) -> None:
        with self.assertRaisesRegex(WorkspaceError, "escapes"):
            self.workspace.read_file("../secret.txt")

    def test_git_directory_is_rejected(self) -> None:
        with self.assertRaisesRegex(WorkspaceError, ".git"):
            self.workspace.write_file(".git/config", "bad")

    def test_binary_and_large_files_are_rejected(self) -> None:
        (self.root / "binary.bin").write_bytes(b"before\x00after")
        (self.root / "large.txt").write_bytes(b"x" * (Workspace.MAX_FILE_BYTES + 1))
        with self.assertRaisesRegex(WorkspaceError, "binary"):
            self.workspace.read_file("binary.bin")
        with self.assertRaisesRegex(WorkspaceError, "exceeds"):
            self.workspace.read_file("large.txt")

    def test_symlink_escape_is_rejected_when_supported(self) -> None:
        outside = self.root.parent / "pine-outside.txt"
        outside.write_text("private", encoding="utf-8")
        link = self.root / "link.txt"
        try:
            link.symlink_to(outside)
        except OSError as error:
            self.skipTest(f"symbolic links unavailable: {error}")
        try:
            with self.assertRaisesRegex(WorkspaceError, "escapes"):
                self.workspace.read_file("link.txt")
        finally:
            outside.unlink(missing_ok=True)
