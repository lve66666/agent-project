from __future__ import annotations

import unittest

from pine.diff import make_unified_diff


class DiffTests(unittest.TestCase):
    def test_existing_file_diff_contains_removed_and_added_lines(self) -> None:
        diff = make_unified_diff("old\nkeep\n", "new\nkeep\n", "calculator.py")
        self.assertIn("--- a/calculator.py", diff)
        self.assertIn("-old", diff)
        self.assertIn("+new", diff)

    def test_new_file_diff_uses_dev_null(self) -> None:
        diff = make_unified_diff(None, "created\n", "new.txt")
        self.assertIn("--- /dev/null", diff)
        self.assertIn("+created", diff)
