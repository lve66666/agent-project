"""Read-only project exploration followed by a user-reviewable implementation plan."""

from __future__ import annotations

from threading import Event
from typing import Any, Callable

from .agent_loop import AgentLoop
from .model_client import ModelClient
from .protocol import RunResult
from .tool_registry import build_read_only_registry
from .trace import TraceWriter
from .workspace import Workspace

PLANNING_SYSTEM_PROMPT = """You are Pine's read-only planning mode for a local coding task.
Use the available read-only tools to inspect the relevant project files before planning.
You may list files, search text, and read files. You cannot modify files or run commands.
After sufficient inspection, return a concise numbered implementation plan that names the
relevant files, describes the intended change, and states how execution should verify it.
Do not claim the task is complete. The user must approve or edit your plan before execution."""
EventCallback = Callable[[str, dict[str, Any]], None]


def run_read_only_plan(client: ModelClient, workspace: Workspace, task: str, *, max_turns: int, max_seconds: int, cancelled: Event | None = None, trace: TraceWriter | None = None, on_event: EventCallback | None = None) -> RunResult:
    """Explore through read-only tools, then return the model's final plan text."""
    planner = AgentLoop(
        client,
        build_read_only_registry(workspace),
        max_turns=max_turns,
        max_seconds=max_seconds,
        cancelled=cancelled,
        trace=trace,
        on_event=on_event,
        system_prompt=PLANNING_SYSTEM_PROMPT,
    )
    return planner.run(task)
