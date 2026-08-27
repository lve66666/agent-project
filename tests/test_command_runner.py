from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pine.command_runner import CommandRunner
from pine.workspace import Workspace, WorkspaceError


class CommandRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Workspace(Path(self.temporary.name))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_command_success_and_failure_are_structured(self) -> None:
        runner = CommandRunner(self.workspace, approve_all=True)
        success = runner.run("python -c \"print('ok')\"")
        self.assertEqual(success.returncode, 0)
        self.assertIn("ok", success.output)
        failure = runner.run("python -c \"import sys; print('bad'); sys.exit(3)\"")
        self.assertEqual(failure.returncode, 3)
        self.assertIn("bad", failure.output)

    def test_timeout_and_output_limit(self) -> None:
        runner = CommandRunner(self.workspace, approve_all=True)
        timed_out = runner.run("python -c \"import time; time.sleep(2)\"", timeout_seconds=1)
        self.assertTrue(timed_out.timed_out)
        noisy = runner.run("python -c \"print('x' * 20000)\"")
        self.assertTrue(noisy.truncated)
        self.assertIn("output truncated", noisy.output)

    def test_confirmation_and_workspace_cwd(self) -> None:
        runner = CommandRunner(self.workspace, approve_all=False, confirmer=lambda command: False)
        result = runner.run("echo no")
        self.assertFalse(result.approved)
        with self.assertRaises(WorkspaceError):
            runner.run("echo no", cwd="..")
