from __future__ import annotations

import unittest

from pine.model_client import ModelProtocolError
from pine.planning import PLANNING_SYSTEM_PROMPT, draft_plan
from pine.protocol import AssistantReply, ToolCall


class FakePlanModel:
    def __init__(self, reply: AssistantReply) -> None:
        self.reply = reply
        self.requests = []

    def complete(self, messages, tools):
        self.requests.append((messages, tools))
        return self.reply


class PlanningTests(unittest.TestCase):
    def test_plan_is_requested_without_tools(self) -> None:
        model = FakePlanModel(AssistantReply("1. Inspect app.js\n2. Run tests"))
        plan = draft_plan(model, "Fix the empty input bug")
        self.assertEqual(plan, "1. Inspect app.js\n2. Run tests")
        messages, tools = model.requests[0]
        self.assertEqual(tools, [])
        self.assertEqual(messages[0]["content"], PLANNING_SYSTEM_PROMPT)
        self.assertEqual(messages[1]["content"], "Fix the empty input bug")

    def test_plan_rejects_tool_call(self) -> None:
        model = FakePlanModel(AssistantReply(None, (ToolCall("call-1", "read_file", "{}"),)))
        with self.assertRaisesRegex(ModelProtocolError, "requested tools"):
            draft_plan(model, "Fix the bug")

    def test_plan_requires_text(self) -> None:
        model = FakePlanModel(AssistantReply("   "))
        with self.assertRaisesRegex(ModelProtocolError, "did not include a plan"):
            draft_plan(model, "Fix the bug")
