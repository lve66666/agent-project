from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from pine.cli import main
from pine.config import ConfigurationError, load_settings
from pine.protocol import AssistantReply


class ConfigAndCliTests(unittest.TestCase):
    def test_missing_key_has_clear_error(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "OPENAI_API_KEY"):
                load_settings(max_turns=1, max_seconds=1)

    def test_cli_returns_configuration_error_without_key(self) -> None:
        stderr = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), redirect_stderr(stderr):
            code = main(["inspect files"])
        self.assertEqual(code, 2)
        self.assertIn("OPENAI_API_KEY", stderr.getvalue())

    def test_cli_accepts_valid_configuration(self) -> None:
        stdout = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), patch(
                "pine.cli.OpenAICompatibleClient"
            ) as client_class, redirect_stdout(stdout):
                client_class.return_value.complete.return_value = AssistantReply("finished")
                code = main(["inspect files", "--workspace", directory])
        self.assertEqual(code, 0)
        self.assertIn("finished", stdout.getvalue())
