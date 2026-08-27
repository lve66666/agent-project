"""Command-line entry point. The loop is deliberately assembled here, not hidden by a framework."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigurationError, load_settings


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

    # The remaining runtime is wired in P4; retaining these values makes P1 executable and inspectable.
    print(f"Pine configured for {workspace} with model {settings.model}.")
    print("Agent runtime is being assembled; complete P4 before executing tasks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
