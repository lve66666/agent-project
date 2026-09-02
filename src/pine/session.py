"""Small, redacted, workspace-scoped conversation history store."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .protocol import Message
from .trace import redact


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    timestamp: str
    task: str
    summary: str
    reason: str
    transcript: tuple[Message, ...]
    modified_files: tuple[str, ...] = ()
    commands: tuple[str, ...] = ()
    tests_passed: bool | None = None


class SessionStore:
    """Persist a bounded list of sessions separately for each workspace."""

    def __init__(self, directory: Path | None = None, *, max_sessions: int = 30,
                 max_transcript_chars: int = 20_000) -> None:
        if max_sessions < 1 or max_transcript_chars < 1_000:
            raise ValueError("session limits are too small")
        self.directory = (directory or Path("sessions")).expanduser()
        self.max_sessions = max_sessions
        self.max_transcript_chars = max_transcript_chars

    def _path(self, workspace: Path) -> Path:
        resolved = str(workspace.expanduser().resolve()).encode("utf-8")
        digest = hashlib.sha256(resolved).hexdigest()[:16]
        return self.directory / f"{digest}.jsonl"

    def load(self, workspace: Path) -> list[SessionRecord]:
        path = self._path(workspace)
        if not path.exists():
            return []
        records: list[SessionRecord] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    value = json.loads(line)
                    if isinstance(value, dict):
                        records.append(self._from_dict(value))
                except (ValueError, TypeError):
                    continue
        except OSError:
            return []
        return records[-self.max_sessions :]

    def get(self, workspace: Path, session_id: str) -> SessionRecord | None:
        return next((item for item in self.load(workspace) if item.session_id == session_id), None)

    def record(self, workspace: Path, *, task: str, summary: str, reason: str,
               transcript: Iterable[Message], modified_files: Iterable[str] = (),
               commands: Iterable[str] = (), tests_passed: bool | None = None,
               session_id: str | None = None) -> SessionRecord:
        clean_transcript = self._limit_transcript(tuple(redact(dict(message)) for message in transcript))
        records = self.load(workspace)
        existing = next((item for item in records if item.session_id == session_id), None) if session_id else None
        item = SessionRecord(
            existing.session_id if existing else uuid.uuid4().hex,
            datetime.now(UTC).isoformat(),
            existing.task if existing else task[:2_000],
            summary[:4_000], reason, clean_transcript,
            tuple(dict.fromkeys((*existing.modified_files, *modified_files))) if existing else tuple(modified_files),
            tuple(dict.fromkeys((*existing.commands, *commands))) if existing else tuple(commands),
            tests_passed,
        )
        if existing:
            records[records.index(existing)] = item
        else:
            records.append(item)
        self._write(workspace, records[-self.max_sessions :])
        return item

    def clear(self, workspace: Path) -> None:
        try:
            self._path(workspace).unlink()
        except FileNotFoundError:
            pass

    def continue_messages(self, workspace: Path, session_id: str) -> list[Message]:
        item = self.get(workspace, session_id)
        if not item:
            return []
        return [dict(message) for message in item.transcript if message.get("role") != "system"]

    def _limit_transcript(self, messages: tuple[Message, ...]) -> tuple[Message, ...]:
        encoded = [json.dumps(message, ensure_ascii=False, separators=(",", ":")) for message in messages]
        total = sum(len(value) for value in encoded)
        if total <= self.max_transcript_chars:
            return messages
        kept: list[Message] = []
        used = 0
        for message, value in reversed(list(zip(messages, encoded))):
            if used + len(value) > self.max_transcript_chars:
                break
            kept.append(message)
            used += len(value)
        if not kept and messages:
            # Keep a small, valid message instead of dropping the whole session.
            last = dict(messages[-1])
            content = last.get("content")
            if isinstance(content, str):
                last["content"] = content[: max(1, self.max_transcript_chars // 2)]
            kept.append(last)
        return tuple(reversed(kept))

    def _write(self, workspace: Path, records: list[SessionRecord]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(workspace)
        fd, temporary = tempfile.mkstemp(prefix=path.name, dir=str(self.directory), text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
                for item in records:
                    output.write(json.dumps(self._to_dict(item), ensure_ascii=False, separators=(",", ":")) + "\n")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _to_dict(item: SessionRecord) -> dict[str, Any]:
        return {"session_id": item.session_id, "timestamp": item.timestamp, "task": item.task,
                "summary": item.summary, "reason": item.reason, "transcript": list(item.transcript),
                "modified_files": list(item.modified_files), "commands": list(item.commands),
                "tests_passed": item.tests_passed}

    @staticmethod
    def _from_dict(value: dict[str, Any]) -> SessionRecord:
        transcript = value.get("transcript", [])
        if not isinstance(transcript, list):
            transcript = []
        return SessionRecord(str(value.get("session_id", "")), str(value.get("timestamp", "")),
                             str(value.get("task", "")), str(value.get("summary", "")),
                             str(value.get("reason", "")), tuple(item for item in transcript if isinstance(item, dict)),
                             tuple(str(item) for item in value.get("modified_files", []) if isinstance(item, str)),
                             tuple(str(item) for item in value.get("commands", []) if isinstance(item, str)),
                             value.get("tests_passed") if isinstance(value.get("tests_passed"), bool) else None)
