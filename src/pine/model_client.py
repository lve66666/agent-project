"""Minimal OpenAI-compatible chat-completions client, without an Agent SDK."""

from __future__ import annotations

import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .protocol import AssistantReply, Message, ToolCall


class ModelError(RuntimeError):
    pass


class ModelProtocolError(ModelError):
    pass


class ModelClient(Protocol):
    def complete(self, messages: list[Message], tools: list[dict]) -> AssistantReply: ...


class OpenAICompatibleClient:
    def __init__(self, *, api_key: str, base_url: str, model: str, timeout_seconds: int = 60) -> None:
        self.api_key = api_key
        self.endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self.model = model
        self.timeout_seconds = timeout_seconds

    def complete(self, messages: list[Message], tools: list[dict]) -> AssistantReply:
        payload = json.dumps({"model": self.model, "messages": messages, "tools": tools}).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            raise ModelError(f"model HTTP {error.code}: {detail}") from error
        except (URLError, TimeoutError) as error:
            raise ModelError(f"model request failed: {error}") from error
        try:
            decoded = json.loads(body)
        except json.JSONDecodeError as error:
            raise ModelProtocolError("model returned invalid JSON") from error
        return parse_chat_completion(decoded)


def parse_chat_completion(payload: object) -> AssistantReply:
    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as error:
        raise ModelProtocolError("model response has no choices[0].message") from error
    content = message.get("content")
    if content is not None and not isinstance(content, str):
        raise ModelProtocolError("assistant content must be a string or null")
    calls: list[ToolCall] = []
    raw_calls = message.get("tool_calls", [])
    if raw_calls is None:
        raw_calls = []
    if not isinstance(raw_calls, list):
        raise ModelProtocolError("tool_calls must be a list")
    for raw_call in raw_calls:
        try:
            call_id = raw_call["id"]
            function = raw_call["function"]
            name = function["name"]
            arguments = function["arguments"]
        except (KeyError, TypeError) as error:
            raise ModelProtocolError("malformed tool call") from error
        if not all(isinstance(value, str) and value for value in (call_id, name)):
            raise ModelProtocolError("tool call id and name must be non-empty strings")
        if isinstance(arguments, dict):
            arguments = json.dumps(arguments)
        if not isinstance(arguments, str):
            raise ModelProtocolError("tool call arguments must be JSON text")
        calls.append(ToolCall(call_id, name, arguments))
    if content is None and not calls:
        raise ModelProtocolError("assistant response has neither content nor tool calls")
    return AssistantReply(content=content, tool_calls=tuple(calls))
