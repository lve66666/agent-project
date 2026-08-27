"""The local, bounded control loop that turns model suggestions into tool results."""

from __future__ import annotations

import time
from threading import Event

from .model_client import ModelClient, ModelError
from .protocol import AssistantReply, Message, RunResult, StopReason, ToolResult
from .tool_registry import ToolRegistry

SYSTEM_PROMPT = "You are Pine, a coding agent. Use tools to inspect and modify only the assigned workspace. Explain the completed work concisely after verification."


class AgentLoop:
    def __init__(self, client: ModelClient, tools: ToolRegistry, *, max_turns: int, max_seconds: int, cancelled: Event | None = None) -> None:
        self.client = client
        self.tools = tools
        self.max_turns = max_turns
        self.max_seconds = max_seconds
        self.cancelled = cancelled or Event()

    def run(self, task: str) -> RunResult:
        messages: list[Message] = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": task}]
        results: list[ToolResult] = []
        deadline = time.monotonic() + self.max_seconds
        for turn in range(1, self.max_turns + 1):
            if self.cancelled.is_set():
                return RunResult(StopReason.CANCELLED, "Run cancelled by user.", turn - 1, tuple(results))
            if time.monotonic() >= deadline:
                return RunResult(StopReason.TIMEOUT, "Run exceeded its total time budget.", turn - 1, tuple(results))
            try:
                reply = self.client.complete(messages, self.tools.schemas())
            except ModelError as error:
                return RunResult(StopReason.MODEL_ERROR, f"Model error: {error}", turn - 1, tuple(results))
            except Exception as error:
                return RunResult(StopReason.PROTOCOL_ERROR, f"Unexpected model client error: {error}", turn - 1, tuple(results))
            messages.append(_assistant_message(reply))
            if not reply.tool_calls:
                return RunResult(StopReason.COMPLETED, reply.content or "Task completed.", turn, tuple(results))
            for call in reply.tool_calls:
                result = self.tools.execute(call)
                results.append(result)
                messages.append({"role": "tool", "tool_call_id": call.id, "name": call.name, "content": result.content})
        return RunResult(StopReason.MAX_TURNS, "Run reached the maximum number of model turns.", self.max_turns, tuple(results))


def _assistant_message(reply: AssistantReply) -> Message:
    message: Message = {"role": "assistant", "content": reply.content}
    if reply.tool_calls:
        message["tool_calls"] = [{"id": call.id, "type": "function", "function": {"name": call.name, "arguments": call.arguments}} for call in reply.tool_calls]
    return message
