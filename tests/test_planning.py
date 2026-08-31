from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pine.planning import PLANNING_SYSTEM_PROMPT, run_read_only_plan
from pine.protocol import AssistantReply, StopReason, ToolCall
from pine.workspace import Workspace


class FakePlanModel:
    def __init__(self, replies: list[AssistantReply]) -> None:
        self.replies = iter(replies)
        self.requests = []

    def complete(self, messages, tools):
        self.requests.append((messages, tools))
        return next(self.replies)


class PlanningTests(unittest.TestCase):
    def test_plan_can_read_project_files_but_not_modify_or_run_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.js").write_text("function calculate() {}\n", encoding="utf-8")
            workspace = Workspace(root)
            model = FakePlanModel([
                AssistantReply(None, (ToolCall("call-1", "read_file", '{"path":"app.js"}'),)),
                AssistantReply("1. Add empty-input validation in app.js\n2. Run the existing tests after approval."),
            ])
            result = run_read_only_plan(model, workspace, "Fix the empty input bug", max_turns=3, max_seconds=30)
        self.assertEqual(result.reason, StopReason.COMPLETED)
        self.assertEqual(result.turns, 2)
        self.assertEqual(result.tool_results[0].name, "read_file")
        first_messages, first_tools = model.requests[0]
        tool_names = {tool["function"]["name"] for tool in first_tools}
        self.assertEqual(tool_names, {"list_files", "read_file", "search_text"})
        self.assertNotIn("write_file", tool_names)
        self.assertNotIn("run_command", tool_names)
        self.assertEqual(first_messages[0]["content"], PLANNING_SYSTEM_PROMPT)
        self.assertEqual(first_messages[1]["content"], "Fix the empty input bug")
        second_messages, _ = model.requests[1]
        self.assertEqual(second_messages[-1]["role"], "tool")
        self.assertIn("function calculate", second_messages[-1]["content"])

    def test_custom_planning_prompt_reaches_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = FakePlanModel([AssistantReply("1. Inspect the project")])
            run_read_only_plan(model, Workspace(Path(directory)), "Inspect the project", max_turns=1, max_seconds=30)
        self.assertEqual(model.requests[0][0][0]["content"], PLANNING_SYSTEM_PROMPT)

    def test_forged_write_call_cannot_create_a_file_during_planning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = FakePlanModel([
                AssistantReply(None, (ToolCall("call-1", "write_file", '{"path":"changed.txt","content":"no"}'),)),
                AssistantReply("1. Review the existing files"),
            ])
            result = run_read_only_plan(model, Workspace(root), "Review the project", max_turns=3, max_seconds=30)
            self.assertFalse((root / "changed.txt").exists())
        self.assertEqual(result.reason, StopReason.COMPLETED)
        self.assertFalse(result.tool_results[0].ok)
        self.assertIn("unknown tool: write_file", result.tool_results[0].content)
