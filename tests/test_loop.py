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
        self.assertEqual(result.modified_files, ("answer.txt",))
        self.assertEqual(result.commands, ())
        self.assertIsNone(result.tests_passed)
        self.assertEqual(result.failure_count, 0)
        self.assertGreaterEqual(len(result.transcript), 5)

    def test_initial_messages_are_injected(self) -> None:
        model = FakeModel([AssistantReply("continued")])
        history = [{"role": "user", "content": "previous"}, {"role": "assistant", "content": "answer"}]
        result = AgentLoop(model, self.registry, max_turns=1, max_seconds=30).run("follow up", initial_messages=history)
        self.assertEqual(result.reason, StopReason.COMPLETED)
        self.assertEqual([m["role"] for m in model.requests[0][0]], ["system", "user", "assistant", "user"])

    def test_run_summary_tracks_commands_and_test_outcome(self) -> None:
        (self.root / "test_sample.py").write_text(
            "import unittest\n\nclass Sample(unittest.TestCase):\n    def test_placeholder(self):\n        pass\n",
            encoding="utf-8",
        )
        model = FakeModel([
            AssistantReply(None, (ToolCall("call-1", "run_command", json.dumps({"command": "python -m unittest discover -s ."})),)),
            AssistantReply("Tests completed."),
        ])
        result = AgentLoop(model, self.registry, max_turns=2, max_seconds=30).run("run tests")
        self.assertEqual(result.commands, ("python -m unittest discover -s .",))
        self.assertTrue(result.tests_passed)
        self.assertEqual(result.failure_count, 0)
        self.assertEqual(json.loads(result.tool_results[0].content)["returncode"], 0)

    def test_mutation_confirmation_happens_before_write(self) -> None:
        approvals: list[tuple[str, str, str]] = []

        def deny(tool: str, path: str, diff: str) -> bool:
            approvals.append((tool, path, diff))
            return False

        denied_registry = build_default_registry(
            Workspace(self.root),
            CommandRunner(Workspace(self.root), approve_all=True),
            mutation_confirmer=deny,
        )
        model = FakeModel([
            AssistantReply(None, (ToolCall("call-1", "write_file", json.dumps({"path": "blocked.txt", "content": "no\n"})),)),
            AssistantReply("Change was rejected."),
        ])
        result = AgentLoop(model, denied_registry, max_turns=2, max_seconds=30).run("write a file")
        self.assertFalse((self.root / "blocked.txt").exists())
        self.assertEqual(approvals[0][0:2], ("write_file", "blocked.txt"))
        self.assertIn("+no", approvals[0][2])
        self.assertEqual(result.failure_count, 1)

    def test_loop_emits_observable_local_events(self) -> None:
        events = []
        model = FakeModel([
            AssistantReply(None, (ToolCall("call-1", "list_files", "{}"),)),
            AssistantReply("Finished."),
        ])
        result = AgentLoop(
            model,
            self.registry,
            max_turns=2,
            max_seconds=30,
            on_event=lambda name, payload: events.append((name, payload)),
        ).run("inspect files")
        self.assertEqual(result.reason, StopReason.COMPLETED)
        self.assertEqual(
            [name for name, _ in events],
            ["model_request", "assistant_reply", "tool_result", "model_request", "assistant_reply", "run_finished"],
        )
        self.assertEqual(events[2][1]["tool"], "list_files")

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
