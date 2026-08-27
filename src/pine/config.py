"""Runtime configuration read only from environment variables and CLI arguments."""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    max_turns: int
    max_seconds: int


def load_settings(*, max_turns: int, max_seconds: int) -> Settings:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ConfigurationError(
            "OPENAI_API_KEY is not set. Set it in your shell; do not put it in source files."
        )
    if max_turns < 1 or max_seconds < 1:
        raise ConfigurationError("--max-turns and --max-seconds must both be positive.")
    return Settings(
        api_key=api_key,
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini",
        max_turns=max_turns,
        max_seconds=max_seconds,
    )
