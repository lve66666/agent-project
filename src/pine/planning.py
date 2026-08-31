"""Local plan drafting that deliberately has no access to agent tools."""

from __future__ import annotations

from .model_client import ModelClient, ModelProtocolError
from .protocol import Message

PLANNING_SYSTEM_PROMPT = """You are Pine's planning mode for a local coding task.
Create a concise, numbered implementation plan. Explain which files should be inspected,
what change is expected, and how it will be verified. Do not claim that work is complete.
Do not call tools, run commands, or modify files. The user must approve or edit this plan
before execution begins."""


def draft_plan(client: ModelClient, task: str) -> str:
    """Ask for a tool-free plan and reject responses that violate planning mode."""
    messages: list[Message] = [
        {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]
    reply = client.complete(messages, tools=[])
    if reply.tool_calls:
        raise ModelProtocolError("planning response requested tools; no work was executed")
    if not reply.content or not reply.content.strip():
        raise ModelProtocolError("planning response did not include a plan")
    return reply.content.strip()
