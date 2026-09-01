from __future__ import annotations

import json
import unittest
from io import BytesIO
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from pine.model_client import ModelError, OpenAICompatibleClient


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class ModelClientRetryTests(unittest.TestCase):
    def test_retries_rate_limit_then_succeeds_with_backoff(self) -> None:
        error = HTTPError("https://example.test", 429, "rate limited", {}, BytesIO(b"busy"))
        sleeps: list[float] = []
        client = OpenAICompatibleClient(api_key="key", base_url="https://example.test", model="demo", max_retries=2, backoff_seconds=0.25, sleeper=sleeps.append)
        success = FakeResponse({"choices": [{"message": {"content": "ok"}}]})
        with patch("pine.model_client.urlopen", side_effect=[error, success]):
            reply = client.complete([], [])
        self.assertEqual(reply.content, "ok")
        self.assertEqual(sleeps, [0.25])

    def test_retries_network_error_until_limit(self) -> None:
        sleeps: list[float] = []
        client = OpenAICompatibleClient(api_key="key", base_url="https://example.test", model="demo", max_retries=2, backoff_seconds=0.1, sleeper=sleeps.append)
        with patch("pine.model_client.urlopen", side_effect=URLError("offline")):
            with self.assertRaisesRegex(ModelError, "offline"):
                client.complete([], [])
        self.assertEqual(sleeps, [0.1, 0.2])

    def test_does_not_retry_authentication_error(self) -> None:
        error = HTTPError("https://example.test", 401, "unauthorized", {}, BytesIO(b"bad key"))
        client = OpenAICompatibleClient(api_key="key", base_url="https://example.test", model="demo", max_retries=2, sleeper=lambda _: self.fail("unexpected retry"))
        with patch("pine.model_client.urlopen", side_effect=error) as request:
            with self.assertRaisesRegex(ModelError, "HTTP 401"):
                client.complete([], [])
        self.assertEqual(request.call_count, 1)
