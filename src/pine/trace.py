"""Append-only, redacted JSONL trace for one agent run."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SECRET_KEY = re.compile(r"(api[_-]?key|authorization|token|password|secret)", re.IGNORECASE)
_OPENAI_LIKE_KEY = re.compile(r"\b(?:sk|rk)-[A-Za-z0-9_-]{8,}\b")


class TraceWriter:
    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.run_id = uuid.uuid4().hex
        self.path = directory / f"{self.run_id}.jsonl"

    def record(self, event: str, **payload: Any) -> None:
        entry = {"timestamp": datetime.now(UTC).isoformat(), "run_id": self.run_id, "event": event, **redact(payload)}
        with self.path.open("a", encoding="utf-8", newline="\n") as output:
            output.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def redact(value: Any, key: str = "") -> Any:
    if _SECRET_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(child_key): redact(child_value, str(child_key)) for child_key, child_value in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _OPENAI_LIKE_KEY.sub("[REDACTED]", value)
    return value
