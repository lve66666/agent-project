"""Minimal OpenAI-compatible chat-completions client, without an Agent SDK."""

from __future__ import annotations

import json
import time
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
    def __init__(self, *, api_key: str, base_url: str, model: str, timeout_seconds: int = 60, max_retries: int = 2, backoff_seconds: float = 0.5, sleeper=time.sleep) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if backoff_seconds < 0:
            raise ValueError("backoff_seconds must be non-negative")
        self.api_key = api_key
        self.endpoint = f"{base_url.rstrip('/')}/chat/completions"
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._sleeper = sleeper

    def complete(self, messages: list[Message], tools: list[dict]) -> AssistantReply:
        payload = json.dumps({"model": self.model, "messages": messages, "tools": tools}).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        body: str | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    body = response.read().decode("utf-8")
                break
            except HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")[:500]
                if not _is_retryable_status(error.code) or attempt >= self.max_retries:
                    raise ModelError(f"model HTTP {error.code}: {detail}") from error
                self._wait_before_retry(attempt, error.headers.get("Retry-After"))
            except (URLError, TimeoutError) as error:
                if attempt >= self.max_retries:
                    raise ModelError(f"model request failed: {error}") from error
                self._wait_before_retry(attempt)
        if body is None:
            raise ModelError("model request failed without a response")
        try:
            decoded = json.loads(body)
        except json.JSONDecodeError as error:
            raise ModelProtocolError("model returned invalid JSON") from error
        return parse_chat_completion(decoded)

    def _wait_before_retry(self, attempt: int, retry_after: str | None = None) -> None:
        delay = self.backoff_seconds * (2 ** attempt)
        if retry_after:
            try:
                delay = max(0.0, min(float(retry_after), 30.0))
            except ValueError:
                pass
        self._sleeper(delay)


def _is_retryable_status(status: int) -> bool:
    return status in {408, 425, 429} or 500 <= status <= 599


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
