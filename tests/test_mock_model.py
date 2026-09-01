from __future__ import annotations

import unittest

from pine.mock_model import MockModelExhausted, ScriptedMockModel
from pine.protocol import AssistantReply


class ScriptedMockModelTests(unittest.TestCase):
    def test_returns_scripted_replies_and_records_context(self) -> None:
        model = ScriptedMockModel([AssistantReply("one"), AssistantReply("two")])
        self.assertEqual(model.complete([{"role": "user", "content": "task"}], []).content, "one")
        self.assertEqual(model.complete([{"role": "tool", "content": "failed"}], []).content, "two")
        self.assertEqual(model.requests[1][0]["content"], "failed")

    def test_exhaustion_is_explicit(self) -> None:
        model = ScriptedMockModel([])
        with self.assertRaises(MockModelExhausted):
            model.complete([], [])
