"""Command-line entry point. The loop is deliberately assembled here, not hidden by a framework."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .agent_loop import AgentLoop
from .command_runner import CommandRunner
from .config import ConfigurationError, load_settings
from .model_client import OpenAICompatibleClient
from .tool_registry import build_default_registry
from .workspace import Workspace, WorkspaceError
from .trace import TraceWriter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pine",
        description="A small local coding agent with auditable tool execution.",
    )
    parser.add_argument("task", help="Programming task for the agent")
    parser.add_argument("--workspace", type=Path, default=Path.cwd(), help="Directory the agent may access")
    parser.add_argument("--max-turns", type=int, default=12)
    parser.add_argument("--max-seconds", type=int, default=300)
    parser.add_argument("--yes", action="store_true", help="Approve all command tool calls")
    parser.add_argument("--trace-dir", type=Path, default=Path("runs"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = load_settings(max_turns=args.max_turns, max_seconds=args.max_seconds)
    except ConfigurationError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"Configuration error: workspace is not a directory: {workspace}", file=sys.stderr)
        return 2

    def confirm(command: str) -> bool:
        try:
            return input(f"Allow command in {workspace}? {command}\n[y/N] ").strip().lower() in {"y", "yes"}
        except EOFError:
            return False

    try:
        confined_workspace = Workspace(workspace)
        runner = CommandRunner(confined_workspace, approve_all=args.yes, confirmer=confirm)
        registry = build_default_registry(confined_workspace, runner)
    except WorkspaceError as error:
        print(f"Workspace error: {error}", file=sys.stderr)
        return 2
    client = OpenAICompatibleClient(api_key=settings.api_key, base_url=settings.base_url, model=settings.model)
    trace = TraceWriter(args.trace_dir)
    trace.record("run_started", task=args.task, workspace=str(workspace), model=settings.model)
    result = AgentLoop(client, registry, max_turns=settings.max_turns, max_seconds=settings.max_seconds, trace=trace).run(args.task)
    print(result.summary)
    print(f"Stop reason: {result.reason.value}; turns: {result.turns}; tool calls: {len(result.tool_results)}")
    return 0 if result.reason.value == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
