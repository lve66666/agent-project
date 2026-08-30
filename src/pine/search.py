"""Workspace-confined text and regular-expression search."""

from __future__ import annotations

import re
from pathlib import Path

from .workspace import Workspace, WorkspaceError


class SearchError(WorkspaceError):
    pass


def search_text(
    workspace: Workspace,
    query: str,
    path: str = ".",
    max_results: int = 50,
    use_regex: bool = False,
) -> str:
    """Search UTF-8 text files and return ``path:line: text`` matches.

    Files larger than the workspace read limit, binary files, and invalid UTF-8 files
    are skipped rather than uploaded to the model or causing the whole search to fail.
    """
    if not isinstance(query, str) or not query:
        raise SearchError("query must be a non-empty string")
    if type(max_results) is not int or not 1 <= max_results <= 200:
        raise SearchError("max_results must be an integer between 1 and 200")
    if type(use_regex) is not bool:
        raise SearchError("use_regex must be a boolean")
    matcher = _build_matcher(query, use_regex)
    start = workspace.resolve_path(path, must_exist=True)
    candidates = [start] if start.is_file() else list(start.rglob("*"))
    matches: list[str] = []
    skipped = 0
    for candidate in candidates:
        if len(matches) >= max_results:
            break
        try:
            resolved = candidate.resolve(strict=False)
            relative = resolved.relative_to(workspace.root)
        except ValueError:
            skipped += 1
            continue
        if any(part in workspace.SKIPPED_DIRECTORY_NAMES for part in relative.parts):
            continue
        if not candidate.is_file():
            continue
        try:
            raw = candidate.read_bytes()
        except OSError:
            skipped += 1
            continue
        if len(raw) > workspace.MAX_FILE_BYTES or b"\x00" in raw:
            skipped += 1
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            skipped += 1
            continue
        relative_name = resolved.relative_to(workspace.root).as_posix()
        for line_number, line in enumerate(text.splitlines(), 1):
            if matcher.search(line):
                matches.append(f"{relative_name}:{line_number}: {line}")
                if len(matches) >= max_results:
                    break
    if not matches:
        result = "(no matches)"
    else:
        result = "\n".join(matches)
    if len(matches) >= max_results:
        result += f"\n... results limited to {max_results} matches ..."
    if skipped:
        result += f"\n(skipped {skipped} unreadable, binary, or oversized file(s))"
    return result


def _build_matcher(query: str, use_regex: bool):
    if not use_regex:
        return re.compile(re.escape(query))
    try:
        return re.compile(query)
    except re.error as error:
        raise SearchError(f"invalid regular expression: {error}") from error
