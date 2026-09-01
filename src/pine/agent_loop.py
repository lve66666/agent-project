"""The local, bounded control loop that turns model suggestions into tool results."""

from __future__ import annotations

import time
import json
from threading import Event
from typing import Any, Callable

from .model_client import ModelClient, ModelError, ModelProtocolError
from .protocol import AssistantReply, Message, RunResult, StopReason, ToolResult
from .tool_registry import ToolRegistry
from .context import ContextWindow
from .trace import TraceWriter

SYSTEM_PROMPT = "You are Pine, a coding agent. Use tools to inspect and modify only the assigned workspace. Explain the completed work concisely after verification."
EventCallback = Callable[[str, dict[str, Any]], None]


class AgentLoop:
    def __init__(self, client: ModelClient, tools: ToolRegistry, *, max_turns: int, max_seconds: int, cancelled: Event | None = None, context: ContextWindow | None = None, trace: TraceWriter | None = None, on_event: EventCallback | None = None, system_prompt: str = SYSTEM_PROMPT) -> None:
        self.client = client
        self.tools = tools
        self.max_turns = max_turns
        self.max_seconds = max_seconds
        self.cancelled = cancelled or Event()
        self.context = context or ContextWindow()
        self.trace = trace
        self.on_event = on_event
        self.system_prompt = system_prompt

    def _emit(self, event: str, **payload: Any) -> None:
        if self.on_event:
            self.on_event(event, payload)

    def run(self, task: str) -> RunResult:
        messages: list[Message] = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": task}]
        results: list[ToolResult] = []
        modified_files: list[str] = []
        commands: list[str] = []
        test_outcomes: list[bool] = []
        failure_count = 0
        deadline = time.monotonic() + self.max_seconds
        for turn in range(1, self.max_turns + 1):
            if self.cancelled.is_set():
                self._emit("run_finished", reason=StopReason.CANCELLED.value, turns=turn - 1)
                return _run_result(StopReason.CANCELLED, "Run cancelled by user.", turn - 1, results, modified_files, commands, test_outcomes, failure_count)
            if time.monotonic() >= deadline:
                self._emit("run_finished", reason=StopReason.TIMEOUT.value, turns=turn - 1)
                return _run_result(StopReason.TIMEOUT, "Run exceeded its total time budget.", turn - 1, results, modified_files, commands, test_outcomes, failure_count)
            try:
                request_messages = self.context.prepare(messages)
                self._emit("model_request", turn=turn, message_count=len(request_messages))
                if self.trace:
                    self.trace.record("model_request", turn=turn, message_count=len(request_messages))
                reply = self.client.complete(request_messages, self.tools.schemas())
            except ModelProtocolError as error:
                self._emit("protocol_error", turn=turn, error=str(error))
                if self.trace:
                    self.trace.record("protocol_error", turn=turn, error=str(error))
                return _run_result(StopReason.PROTOCOL_ERROR, f"Model protocol error: {error}", turn - 1, results, modified_files, commands, test_outcomes, failure_count)
            except ModelError as error:
                self._emit("model_error", turn=turn, error=str(error))
                if self.trace:
                    self.trace.record("model_error", turn=turn, error=str(error))
                return _run_result(StopReason.MODEL_ERROR, f"Model error: {error}", turn - 1, results, modified_files, commands, test_outcomes, failure_count)
            except Exception as error:
                self._emit("protocol_error", turn=turn, error=str(error))
                return _run_result(StopReason.PROTOCOL_ERROR, f"Unexpected model client error: {error}", turn - 1, results, modified_files, commands, test_outcomes, failure_count)
            messages.append(_assistant_message(reply))
            self._emit("assistant_reply", turn=turn, content=reply.content, tools=[call.name for call in reply.tool_calls])
            if self.trace:
                self.trace.record("assistant_reply", turn=turn, content=reply.content, tool_calls=[call.name for call in reply.tool_calls])
            if not reply.tool_calls:
                self._emit("run_finished", reason=StopReason.COMPLETED.value, turns=turn)
                if self.trace:
                    self.trace.record("run_finished", reason=StopReason.COMPLETED.value, turns=turn)
                return _run_result(StopReason.COMPLETED, reply.content or "Task completed.", turn, results, modified_files, commands, test_outcomes, failure_count)
            for call in reply.tool_calls:
                result = self.tools.execute(call)
                results.append(result)
                metadata = _record_tool_outcome(call.name, call.arguments, result)
                if metadata["modified_file"] and result.ok:
                    modified_files.append(metadata["modified_file"])
                if metadata["command"]:
                    commands.append(metadata["command"])
                if metadata["test_outcome"] is not None:
                    test_outcomes.append(metadata["test_outcome"])
                if metadata["failed"]:
                    failure_count += 1
                self._emit("tool_result", turn=turn, tool=call.name, ok=result.ok, content=result.content)
                if self.trace:
                    self.trace.record("tool_result", turn=turn, tool=call.name, ok=result.ok, content=result.content)
                messages.append({"role": "tool", "tool_call_id": call.id, "name": call.name, "content": result.content})
        if self.trace:
            self.trace.record("run_finished", reason=StopReason.MAX_TURNS.value, turns=self.max_turns)
        self._emit("run_finished", reason=StopReason.MAX_TURNS.value, turns=self.max_turns)
        return _run_result(StopReason.MAX_TURNS, "Run reached the maximum number of model turns.", self.max_turns, results, modified_files, commands, test_outcomes, failure_count)


def _assistant_message(reply: AssistantReply) -> Message:
    message: Message = {"role": "assistant", "content": reply.content}
    if reply.tool_calls:
        message["tool_calls"] = [{"id": call.id, "type": "function", "function": {"name": call.name, "arguments": call.arguments}} for call in reply.tool_calls]
    return message


def _run_result(reason: StopReason, summary: str, turns: int, results: list[ToolResult], modified_files: list[str], commands: list[str], test_outcomes: list[bool], failure_count: int) -> RunResult:
    return RunResult(reason, summary, turns, tuple(results), tuple(dict.fromkeys(modified_files)), tuple(commands), (all(test_outcomes) if test_outcomes else None), failure_count)


def _record_tool_outcome(name: str, arguments_text: str, result: ToolResult) -> dict[str, Any]:
    try:
        arguments = json.loads(arguments_text)
    except (TypeError, json.JSONDecodeError):
        arguments = {}
    if not isinstance(arguments, dict):
        arguments = {}
    if name in {"write_file", "edit_file"}:
        return {"modified_file": arguments.get("path") if isinstance(arguments.get("path"), str) else None, "command": None, "test_outcome": None, "failed": not result.ok}
    if name != "run_command":
        return {"modified_file": None, "command": None, "test_outcome": None, "failed": not result.ok}
    command = arguments.get("command") if isinstance(arguments.get("command"), str) else None
    outcome: dict[str, Any] = {}
    try:
        decoded = json.loads(result.content)
        if isinstance(decoded, dict):
            outcome = decoded
    except (TypeError, json.JSONDecodeError):
        pass
    failed = (not result.ok) or outcome.get("approved") is False or outcome.get("timed_out") is True or outcome.get("returncode") not in (None, 0)
    lowered = (command or "").lower()
    is_test = any(marker in lowered for marker in ("pytest", "unittest", "npm test", "node --test", "go test", "cargo test"))
    return {"modified_file": None, "command": command, "test_outcome": (not failed) if is_test else None, "failed": failed}
