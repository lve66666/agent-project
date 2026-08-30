from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pine.context import ContextWindow
from pine.trace import TraceWriter, redact


class ContextTraceTests(unittest.TestCase):
    def test_oversized_tool_output_is_compacted_without_mutating_history(self) -> None:
        tool_message = {
            "role": "tool",
            "tool_call_id": "call-1",
            "name": "read_file",
            "content": "BEGIN\n" + ("x" * 2_000) + "\nEND",
        }
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "task"},
            {"role": "assistant", "content": None, "tool_calls": []},
            tool_message,
        ]
        original_content = tool_message["content"]
        prepared = ContextWindow(max_chars=4_000, max_tool_chars=300).prepare(messages)
        compacted_tool = prepared[-1]
        self.assertLessEqual(len(compacted_tool["content"]), 300)
        self.assertIn("tool output truncated", compacted_tool["content"])
        self.assertTrue(compacted_tool["content"].startswith("BEGIN"))
        self.assertTrue(compacted_tool["content"].endswith("END"))
        self.assertEqual(compacted_tool["tool_call_id"], "call-1")
        self.assertEqual(tool_message["content"], original_content)

    def test_small_tool_output_is_unchanged(self) -> None:
        messages = [{"role": "tool", "tool_call_id": "call-1", "name": "list_files", "content": "ok"}]
        prepared = ContextWindow(max_chars=1_000, max_tool_chars=300).prepare(messages)
        self.assertEqual(prepared, messages)

    def test_context_rejects_invalid_tool_budget(self) -> None:
        with self.assertRaises(ValueError):
            ContextWindow(max_tool_chars=255)

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
