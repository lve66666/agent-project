"""Workspace-confined file operations used by the agent's file tools."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


class WorkspaceError(ValueError):
    pass


class Workspace:
    MAX_FILE_BYTES = 64 * 1024
    MAX_LIST_ENTRIES = 500
    SKIPPED_DIRECTORY_NAMES = {".git", ".venv", "venv", "__pycache__", "node_modules"}

    def __init__(self, root: Path) -> None:
        resolved = root.resolve()
        if not resolved.is_dir():
            raise WorkspaceError(f"workspace is not a directory: {resolved}")
        self.root = resolved

    def resolve_path(self, raw_path: str, *, must_exist: bool = False) -> Path:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise WorkspaceError("path must be a non-empty string")
        candidate = (self.root / raw_path).resolve(strict=False)
        try:
            relative = candidate.relative_to(self.root)
        except ValueError as error:
            raise WorkspaceError("path escapes the workspace") from error
        if ".git" in relative.parts:
            raise WorkspaceError("access to .git is not allowed")
        if must_exist and not candidate.exists():
            raise WorkspaceError(f"path does not exist: {raw_path}")
        return candidate

    def list_files(self, path: str = ".", depth: int = 2) -> str:
        if not isinstance(depth, int) or depth < 0 or depth > 8:
            raise WorkspaceError("depth must be an integer between 0 and 8")
        directory = self.resolve_path(path, must_exist=True)
        if not directory.is_dir():
            raise WorkspaceError("list_files requires a directory")
        entries: list[str] = []
        for candidate in directory.rglob("*"):
            try:
                resolved = candidate.resolve(strict=False)
                relative = resolved.relative_to(directory)
                relative_to_root = resolved.relative_to(self.root)
            except ValueError:
                continue
            if any(part in self.SKIPPED_DIRECTORY_NAMES for part in relative_to_root.parts):
                continue
            if len(relative.parts) > depth:
                continue
            suffix = "/" if candidate.is_dir() else ""
            entries.append(f"{relative.as_posix()}{suffix}")
            if len(entries) >= self.MAX_LIST_ENTRIES:
                entries.append("... output truncated ...")
                break
        return "\n".join(sorted(entries)) or "(empty)"

    def read_file(self, path: str, start_line: int = 1, end_line: int | None = None) -> str:
        if start_line < 1 or (end_line is not None and end_line < start_line):
            raise WorkspaceError("invalid line range")
        target = self.resolve_path(path, must_exist=True)
        if not target.is_file():
            raise WorkspaceError("read_file requires a regular file")
        if target.stat().st_size > self.MAX_FILE_BYTES:
            raise WorkspaceError(f"file exceeds {self.MAX_FILE_BYTES} byte limit")
        raw = target.read_bytes()
        if b"\x00" in raw:
            raise WorkspaceError("binary files cannot be read")
        try:
            lines = raw.decode("utf-8").splitlines()
        except UnicodeDecodeError as error:
            raise WorkspaceError("file is not valid UTF-8 text") from error
        selected = lines[start_line - 1 : end_line]
        first_line = start_line
        return "\n".join(f"{number:>5}: {line}" for number, line in enumerate(selected, first_line))

    def write_file(self, path: str, content: str) -> str:
        if not isinstance(content, str):
            raise WorkspaceError("content must be a string")
        encoded = content.encode("utf-8")
        if len(encoded) > self.MAX_FILE_BYTES:
            raise WorkspaceError(f"content exceeds {self.MAX_FILE_BYTES} byte limit")
        target = self.resolve_path(path)
        if target.exists() and target.is_dir():
            raise WorkspaceError("cannot overwrite a directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".pine-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            Path(temporary_name).replace(target)
        except BaseException:
            Path(temporary_name).unlink(missing_ok=True)
            raise
        return f"wrote {len(encoded)} bytes to {target.relative_to(self.root).as_posix()}"
