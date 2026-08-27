"""Guarded local command execution for the agent."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .workspace import Workspace, WorkspaceError


@dataclass(frozen=True)
class CommandResult:
    command: str
    cwd: str
    returncode: int | None
    output: str
    timed_out: bool = False
    truncated: bool = False
    approved: bool = True


class CommandRunner:
    MAX_OUTPUT_CHARS = 12_000
    MAX_TIMEOUT_SECONDS = 120

    def __init__(self, workspace: Workspace, *, approve_all: bool = False, confirmer=None) -> None:
        self.workspace = workspace
        self.approve_all = approve_all
        self.confirmer = confirmer or (lambda command: False)

    def run(self, command: str, cwd: str = ".", timeout_seconds: int = 30) -> CommandResult:
        if not isinstance(command, str) or not command.strip():
            raise WorkspaceError("command must be a non-empty string")
        if timeout_seconds < 1 or timeout_seconds > self.MAX_TIMEOUT_SECONDS:
            raise WorkspaceError(f"timeout must be between 1 and {self.MAX_TIMEOUT_SECONDS} seconds")
        directory = self.workspace.resolve_path(cwd, must_exist=True)
        if not directory.is_dir():
            raise WorkspaceError("cwd must be a directory")
        approved = self.approve_all or bool(self.confirmer(command))
        if not approved:
            return CommandResult(command, str(directory), None, "command not approved", approved=False)
        try:
            completed = subprocess.run(
                command,
                cwd=directory,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
            output = _limit_output(completed.stdout + completed.stderr, self.MAX_OUTPUT_CHARS)
            return CommandResult(command, str(directory), completed.returncode, output, truncated=len(output) < len(completed.stdout + completed.stderr))
        except subprocess.TimeoutExpired as error:
            output = _limit_output(_as_text(error.stdout) + _as_text(error.stderr), self.MAX_OUTPUT_CHARS)
            return CommandResult(command, str(directory), None, output, timed_out=True, truncated=False)


def _as_text(value) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)


def _limit_output(output: str, limit: int) -> str:
    if len(output) <= limit:
        return output
    return output[:limit] + f"\n... output truncated at {limit} characters ..."
