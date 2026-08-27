"""Protocol-aware context trimming before each model request."""

from __future__ import annotations

import json
from typing import Any

from .protocol import Message


class ContextWindow:
    """Keeps complete assistant/tool groups so tool call IDs never become orphaned."""

    def __init__(self, max_chars: int = 24_000) -> None:
        if max_chars < 1_000:
            raise ValueError("max context budget must be at least 1000 characters")
        self.max_chars = max_chars

    def prepare(self, messages: list[Message]) -> list[Message]:
        if self._size(messages) <= self.max_chars:
            return messages
        pinned = self._pinned(messages)
        remaining = messages[len(pinned) :]
        groups = _group_turns(remaining)
        kept: list[list[Message]] = []
        budget_used = self._size(pinned)
        for group in reversed(groups):
            group_size = self._size(group)
            if budget_used + group_size > self.max_chars:
                break
            kept.append(group)
            budget_used += group_size
        omitted = len(groups) - len(kept)
        if omitted <= 0:
            return messages
        summary: Message = {
            "role": "system",
            "content": f"Earlier history was compacted locally: {omitted} complete turn group(s) omitted. Continue from the retained recent tool results.",
        }
        return [*pinned, summary, *[message for group in reversed(kept) for message in group]]

    @staticmethod
    def _pinned(messages: list[Message]) -> list[Message]:
        system = next((message for message in messages if message.get("role") == "system"), None)
        user = next((message for message in messages if message.get("role") == "user"), None)
        return [message for message in (system, user) if message is not None]

    @staticmethod
    def _size(messages: list[Message]) -> int:
        return sum(len(json.dumps(message, ensure_ascii=False, separators=(",", ":"))) for message in messages)


def _group_turns(messages: list[Message]) -> list[list[Message]]:
    groups: list[list[Message]] = []
    current: list[Message] = []
    for message in messages:
        if message.get("role") == "assistant" and current:
            groups.append(current)
            current = []
        current.append(message)
    if current:
        groups.append(current)
    return groups
