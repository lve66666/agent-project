from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pine.agent_loop import AgentLoop
from pine.command_runner import CommandRunner
from pine.model_client import ModelError, ModelProtocolError, parse_chat_completion
from pine.protocol import AssistantReply, StopReason, ToolCall
from pine.tool_registry import build_default_registry
from pine.workspace import Workspace


class FakeModel:
    def __init__(self, replies: list[AssistantReply]) -> None:
        self.replies = iter(replies)
        self.requests = []

    def complete(self, messages, tools):
        self.requests.append(([dict(message) for message in messages], list(tools)))
        return next(self.replies)


class BrokenModel:
    def complete(self, messages, tools):
        raise ModelError("network unavailable")


class MalformedModel:
    def complete(self, messages, tools):
        raise ModelProtocolError("malformed response")


class AgentLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        workspace = Workspace(Path(self.temporary.name))
        self.registry = build_default_registry(workspace, CommandRunner(workspace, approve_all=True))
        self.root = workspace.root

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_model_drives_multi_turn_write_read_and_completion(self) -> None:
        model = FakeModel([
            AssistantReply(None, (ToolCall("call-1", "write_file", json.dumps({"path": "answer.txt", "content": "42\n"})),)),
            AssistantReply(None, (ToolCall("call-2", "read_file", json.dumps({"path": "answer.txt"})),)),
            AssistantReply("Created and checked answer.txt."),
        ])
        result = AgentLoop(model, self.registry, max_turns=4, max_seconds=30).run("create the answer")
        self.assertEqual(result.reason, StopReason.COMPLETED)
        self.assertEqual(result.turns, 3)
        self.assertEqual((self.root / "answer.txt").read_text(encoding="utf-8"), "42\n")
        self.assertEqual([request[0][-1]["role"] for request in model.requests[1:]], ["tool", "tool"])

    def test_unknown_tool_is_returned_to_model(self) -> None:
        model = FakeModel([
            AssistantReply(None, (ToolCall("call-1", "erase_disk", "{}"),)),
            AssistantReply("I could not use that tool."),
        ])
        result = AgentLoop(model, self.registry, max_turns=2, max_seconds=30).run("bad request")
        self.assertTrue(result.tool_results[0].content.startswith("unknown tool"))
        self.assertEqual(result.reason, StopReason.COMPLETED)

    def test_loop_budget_and_model_error_are_explicit(self) -> None:
        looping = FakeModel([AssistantReply(None, (ToolCall("x", "list_files", "{}"),))])
        result = AgentLoop(looping, self.registry, max_turns=1, max_seconds=30).run("loop")
        self.assertEqual(result.reason, StopReason.MAX_TURNS)
        error = AgentLoop(BrokenModel(), self.registry, max_turns=1, max_seconds=30).run("error")
        self.assertEqual(error.reason, StopReason.MODEL_ERROR)
        protocol = AgentLoop(MalformedModel(), self.registry, max_turns=1, max_seconds=30).run("protocol")
        self.assertEqual(protocol.reason, StopReason.PROTOCOL_ERROR)

    def test_openai_response_parser_validates_protocol(self) -> None:
        reply = parse_chat_completion({"choices": [{"message": {"content": "ok"}}]})
        self.assertEqual(reply.content, "ok")
        with self.assertRaises(ModelProtocolError):
            parse_chat_completion({"choices": []})
