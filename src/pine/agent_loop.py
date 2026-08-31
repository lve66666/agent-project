"""The local, bounded control loop that turns model suggestions into tool results."""

from __future__ import annotations

import time
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
    def __init__(self, client: ModelClient, tools: ToolRegistry, *, max_turns: int, max_seconds: int, cancelled: Event | None = None, context: ContextWindow | None = None, trace: TraceWriter | None = None, on_event: EventCallback | None = None, system_prompt: str = SYSTEM_PROMPT, memory: list[Message] | tuple[Message, ...] | None = None) -> None:
        self.client = client
        self.tools = tools
        self.max_turns = max_turns
        self.max_seconds = max_seconds
        self.cancelled = cancelled or Event()
        self.context = context or ContextWindow()
        self.trace = trace
        self.on_event = on_event
        self.system_prompt = system_prompt
        self.memory = tuple(dict(message) for message in (memory or ()))

    def _emit(self, event: str, **payload: Any) -> None:
        if self.on_event:
            self.on_event(event, payload)

    def run(self, task: str) -> RunResult:
        messages: list[Message] = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": task}, *self.memory]
        results: list[ToolResult] = []
        deadline = time.monotonic() + self.max_seconds
        for turn in range(1, self.max_turns + 1):
            if self.cancelled.is_set():
                self._emit("run_finished", reason=StopReason.CANCELLED.value, turns=turn - 1)
                return RunResult(StopReason.CANCELLED, "Run cancelled by user.", turn - 1, tuple(results))
            if time.monotonic() >= deadline:
                self._emit("run_finished", reason=StopReason.TIMEOUT.value, turns=turn - 1)
                return RunResult(StopReason.TIMEOUT, "Run exceeded its total time budget.", turn - 1, tuple(results))
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
                return RunResult(StopReason.PROTOCOL_ERROR, f"Model protocol error: {error}", turn - 1, tuple(results))
            except ModelError as error:
                self._emit("model_error", turn=turn, error=str(error))
                if self.trace:
                    self.trace.record("model_error", turn=turn, error=str(error))
                return RunResult(StopReason.MODEL_ERROR, f"Model error: {error}", turn - 1, tuple(results))
            except Exception as error:
                self._emit("protocol_error", turn=turn, error=str(error))
                return RunResult(StopReason.PROTOCOL_ERROR, f"Unexpected model client error: {error}", turn - 1, tuple(results))
            messages.append(_assistant_message(reply))
            self._emit("assistant_reply", turn=turn, content=reply.content, tools=[call.name for call in reply.tool_calls])
            if self.trace:
                self.trace.record("assistant_reply", turn=turn, content=reply.content, tool_calls=[call.name for call in reply.tool_calls])
            if not reply.tool_calls:
                self._emit("run_finished", reason=StopReason.COMPLETED.value, turns=turn)
                if self.trace:
                    self.trace.record("run_finished", reason=StopReason.COMPLETED.value, turns=turn)
                return RunResult(StopReason.COMPLETED, reply.content or "Task completed.", turn, tuple(results))
            for call in reply.tool_calls:
                result = self.tools.execute(call)
                results.append(result)
                self._emit("tool_result", turn=turn, tool=call.name, ok=result.ok, content=result.content)
                if self.trace:
                    self.trace.record("tool_result", turn=turn, tool=call.name, ok=result.ok, content=result.content)
                messages.append({"role": "tool", "tool_call_id": call.id, "name": call.name, "content": result.content})
        if self.trace:
            self.trace.record("run_finished", reason=StopReason.MAX_TURNS.value, turns=self.max_turns)
        self._emit("run_finished", reason=StopReason.MAX_TURNS.value, turns=self.max_turns)
        return RunResult(StopReason.MAX_TURNS, "Run reached the maximum number of model turns.", self.max_turns, tuple(results))


def _assistant_message(reply: AssistantReply) -> Message:
    message: Message = {"role": "assistant", "content": reply.content}
    if reply.tool_calls:
        message["tool_calls"] = [{"id": call.id, "type": "function", "function": {"name": call.name, "arguments": call.arguments}} for call in reply.tool_calls]
    return message
