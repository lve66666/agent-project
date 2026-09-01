"""Data objects exchanged between the model, tools, and agent loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StopReason(str, Enum):
    COMPLETED = "completed"
    MAX_TURNS = "max_turns"
    TIMEOUT = "timeout"
    MODEL_ERROR = "model_error"
    PROTOCOL_ERROR = "protocol_error"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class AssistantReply:
    content: str | None
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True)
class ToolResult:
    tool_call_id: str
    name: str
    ok: bool
    content: str


@dataclass(frozen=True)
class RunResult:
    reason: StopReason
    summary: str
    turns: int
    tool_results: tuple[ToolResult, ...] = field(default_factory=tuple)
    modified_files: tuple[str, ...] = field(default_factory=tuple)
    commands: tuple[str, ...] = field(default_factory=tuple)
    tests_passed: bool | None = None
    failure_count: int = 0


Message = dict[str, Any]
