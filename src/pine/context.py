"""Protocol-aware context trimming before each model request."""

from __future__ import annotations

import json
from typing import Any

from .protocol import Message


class ContextWindow:
    """Keeps complete assistant/tool groups so tool call IDs never become orphaned."""

    def __init__(self, max_chars: int = 24_000, max_tool_chars: int = 8_000) -> None:
        if max_chars < 1_000:
            raise ValueError("max context budget must be at least 1000 characters")
        if max_tool_chars < 256:
            raise ValueError("max tool output budget must be at least 256 characters")
        self.max_chars = max_chars
        self.max_tool_chars = max_tool_chars

    def prepare(self, messages: list[Message]) -> list[Message]:
        prepared = [self._compact_tool_message(message) for message in messages]
        if self._size(prepared) <= self.max_chars:
            return prepared
        pinned_indices = self._pinned_indices(prepared)
        pinned = [prepared[index] for index in pinned_indices]
        remaining = [message for index, message in enumerate(prepared) if index not in pinned_indices]
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

    def _compact_tool_message(self, message: Message) -> Message:
        """Return a copy with oversized tool output shortened at the middle."""
        compacted = dict(message)
        if compacted.get("role") != "tool":
            return compacted
        content = compacted.get("content")
        if not isinstance(content, str) or len(content) <= self.max_tool_chars:
            return compacted
        original_size = len(content)
        marker = f"\n... tool output truncated: {original_size} -> {self.max_tool_chars} chars ...\n"
        available = self.max_tool_chars - len(marker)
        head_size = max(1, available // 2)
        tail_size = max(1, available - head_size)
        compacted["content"] = content[:head_size] + marker + content[-tail_size:]
        return compacted

    @staticmethod
    def _pinned_indices(messages: list[Message]) -> list[int]:
        indices: list[int] = []
        system_index = next((index for index, message in enumerate(messages) if message.get("role") == "system"), None)
        user_indices = [index for index, message in enumerate(messages) if message.get("role") == "user"]
        if system_index is not None:
            indices.append(system_index)
        if user_indices:
            latest_user = user_indices[-1]
            if latest_user not in indices:
                indices.append(latest_user)
        return indices

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
