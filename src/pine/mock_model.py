"""Deterministic scripted model used for offline harness demonstrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .protocol import AssistantReply, Message


class MockModelExhausted(RuntimeError):
    """Raised when a scripted model receives more requests than expected."""


@dataclass
class ScriptedMockModel:
    """A dependency-free ModelClient replacement with observable requests."""

    replies: Iterable[AssistantReply]
    requests: list[list[Message]] = field(default_factory=list, init=False)
    tool_schemas: list[list[dict[str, Any]]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self._replies = iter(self.replies)

    def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> AssistantReply:
        self.requests.append([dict(message) for message in messages])
        self.tool_schemas.append(list(tools))
        try:
            return next(self._replies)
        except StopIteration as error:
            raise MockModelExhausted("scripted mock model has no reply for this request") from error
