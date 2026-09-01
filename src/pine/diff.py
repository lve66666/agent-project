"""Small, deterministic unified-diff helpers for workspace file changes."""

from __future__ import annotations

from difflib import unified_diff


def make_unified_diff(before: str | None, after: str, path: str, *, context_lines: int = 3) -> str:
    """Return a human-readable diff; ``before=None`` represents a new file."""
    old_lines = [] if before is None else before.splitlines(keepends=True)
    new_lines = after.splitlines(keepends=True)
    diff = unified_diff(old_lines, new_lines, fromfile=f"a/{path}" if before is not None else "/dev/null", tofile=f"b/{path}", n=context_lines)
    return "".join(diff).rstrip("\n")
