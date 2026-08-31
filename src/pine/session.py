"""Small, workspace-isolated persistent summaries for the GUI."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .trace import redact
from .workspace import Workspace


class SessionStore:
    """Stores bounded task summaries, never the full tool conversation."""

    def __init__(self, directory: Path, *, max_entries: int = 20, max_entry_chars: int = 2_000, max_memory_chars: int = 8_000) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        if max_entry_chars < 256 or max_memory_chars < 256:
            raise ValueError("session character limits must be at least 256")
        self.directory = directory
        self.max_entries = max_entries
        self.max_entry_chars = max_entry_chars
        self.max_memory_chars = max_memory_chars
        self._lock = threading.RLock()

    def path_for(self, workspace: Workspace | Path) -> Path:
        root = workspace.root if isinstance(workspace, Workspace) else workspace.expanduser().resolve()
        key = hashlib.sha256(str(root).casefold().encode("utf-8")).hexdigest()[:24]
        return self.directory / f"{key}.jsonl"

    def load(self, workspace: Workspace | Path) -> list[dict[str, str]]:
        path = self.path_for(workspace)
        with self._lock:
            if not path.is_file():
                return []
            entries: list[dict[str, str]] = []
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                return []
            for line in lines:
                try:
                    decoded = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(decoded, dict):
                    continue
                values = {name: decoded.get(name) for name in ("timestamp", "task", "summary", "reason")}
                if all(isinstance(value, str) and value for value in values.values()):
                    entries.append(values)
            return entries[-self.max_entries :]

    def record(self, workspace: Workspace | Path, *, task: str, summary: str, reason: str) -> Path:
        if not all(isinstance(value, str) and value.strip() for value in (task, summary, reason)):
            raise ValueError("session task, summary, and reason must be non-empty strings")
        entry = redact({
            "timestamp": datetime.now(UTC).isoformat(),
            "task": self._clip(task.strip()),
            "summary": self._clip(summary.strip()),
            "reason": self._clip(reason.strip(), 80),
        })
        path = self.path_for(workspace)
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            entries = self.load(workspace)
            entries.append({name: str(entry[name]) for name in ("timestamp", "task", "summary", "reason")})
            entries = entries[-self.max_entries :]
            self._write(path, entries)
        return path

    def clear(self, workspace: Workspace | Path) -> None:
        path = self.path_for(workspace)
        with self._lock:
            path.unlink(missing_ok=True)

    def memory_messages(self, workspace: Workspace | Path) -> list[dict[str, str]]:
        entries = self.load(workspace)
        if not entries:
            return []
        prefix = "Project memory from prior runs. Verify it against the current files:\n"
        selected: list[str] = []
        used = len(prefix)
        for entry in reversed(entries):
            line = f"- {entry['task']} -> {entry['summary']} (stop: {entry['reason']})\n"
            if used + len(line) > self.max_memory_chars:
                break
            selected.append(line)
            used += len(line)
        if not selected:
            return []
        content = prefix + "".join(reversed(selected)).rstrip()
        return [{"role": "system", "content": content}]

    def display_text(self, workspace: Workspace | Path) -> str:
        entries = self.load(workspace)
        if not entries:
            return "No previous task summaries for this workspace."
        lines: list[str] = []
        for entry in reversed(entries):
            lines.append(f"[{entry['timestamp']}] {entry['reason']}\nTask: {entry['task']}\nAgent: {entry['summary']}\n")
        return "\n".join(lines).rstrip()

    def _clip(self, value: str, limit: int | None = None) -> str:
        max_chars = limit or self.max_entry_chars
        if len(value) <= max_chars:
            return value
        marker = " ...[truncated]"
        return value[: max_chars - len(marker)] + marker

    @staticmethod
    def _write(path: Path, entries: list[dict[str, str]]) -> None:
        descriptor, temporary_name = tempfile.mkstemp(prefix=".pine-session-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
                for entry in entries:
                    output.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
                output.flush()
                os.fsync(output.fileno())
            Path(temporary_name).replace(path)
        except BaseException:
            Path(temporary_name).unlink(missing_ok=True)
            raise
