"""Run a deterministic multi-turn harness demo without a network or API key."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pine.agent_loop import AgentLoop
from pine.command_runner import CommandRunner
from pine.mock_model import ScriptedMockModel
from pine.protocol import AssistantReply, StopReason, ToolCall
from pine.tool_registry import build_default_registry
from pine.workspace import Workspace


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pine-mock-demo-") as directory:
        workspace = Workspace(Path(directory))
        workspace.write_file("status.txt", "bad\n")
        model = ScriptedMockModel([
            AssistantReply(None, (ToolCall("call-1", "run_command", json.dumps({
                "command": "python -c \"import sys; print('intentional failure'); sys.exit(1)\"",
            })),)),
            AssistantReply(None, (ToolCall("call-2", "edit_file", json.dumps({
                "path": "status.txt", "old_text": "bad", "new_text": "good",
            })),)),
            AssistantReply(None, (ToolCall("call-3", "run_command", json.dumps({
                "command": "python -c \"print('verification passed')\"",
            })),)),
            AssistantReply("Recovered after the failed command and verified the fix."),
        ])
        registry = build_default_registry(workspace, CommandRunner(workspace, approve_all=True))
        result = AgentLoop(model, registry, max_turns=6, max_seconds=30).run("repair the status and verify it")
        feedback = model.requests[1][-1]["content"]
        print(f"stop_reason={result.reason.value}")
        print(f"turns={result.turns}; tool_calls={len(result.tool_results)}")
        print(f"changed_next_action={'intentional failure' in feedback and model.requests[1][-1]['role'] == 'tool'}")
        print(f"status={ (Path(directory) / 'status.txt').read_text(encoding='utf-8').strip() }")
        return 0 if result.reason is StopReason.COMPLETED else 1


if __name__ == "__main__":
    raise SystemExit(main())
