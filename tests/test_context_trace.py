from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pine.context import ContextWindow
from pine.trace import TraceWriter, redact


class ContextTraceTests(unittest.TestCase):
    def test_context_compacts_complete_groups(self) -> None:
        messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}]
        for index in range(8):
            messages.extend([
                {"role": "assistant", "content": None, "tool_calls": [{"id": f"c{index}", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}]},
                {"role": "tool", "tool_call_id": f"c{index}", "name": "read_file", "content": "x" * 300},
            ])
        compacted = ContextWindow(max_chars=1_200).prepare(messages)
        self.assertLess(len(compacted), len(messages))
        self.assertEqual(compacted[0]["role"], "system")
        self.assertEqual(compacted[1]["role"], "user")
        self.assertTrue(any("compacted" in str(message.get("content")) for message in compacted))

    def test_trace_redacts_secret_fields_and_values(self) -> None:
        self.assertEqual(redact({"api_key": "sk-secret-value"})["api_key"], "[REDACTED]")
        self.assertEqual(redact("token sk-secret-value"), "token [REDACTED]")
        with tempfile.TemporaryDirectory() as directory:
            writer = TraceWriter(Path(directory))
            writer.record("test", api_key="sk-secret-value", detail="ok")
            entry = json.loads(writer.path.read_text(encoding="utf-8"))
            self.assertEqual(entry["api_key"], "[REDACTED]")
            self.assertEqual(entry["detail"], "ok")
