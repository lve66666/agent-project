"""Local tool definitions, argument validation, and deterministic dispatch."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from .command_runner import CommandRunner
from .diff import make_unified_diff
from .protocol import ToolCall, ToolResult
from .workspace import Workspace
from .search import search_text


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    schema: dict[str, Any]
    required: frozenset[str]
    argument_types: dict[str, type]
    handler: Callable[..., str]

    def as_openai_tool(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.schema}}


class ToolRegistry:
    def __init__(self, definitions: list[ToolDefinition]) -> None:
        self._definitions = {definition.name: definition for definition in definitions}
        if len(self._definitions) != len(definitions):
            raise ValueError("tool names must be unique")

    def schemas(self) -> list[dict[str, Any]]:
        return [definition.as_openai_tool() for definition in self._definitions.values()]

    def execute(self, call: ToolCall) -> ToolResult:
        definition = self._definitions.get(call.name)
        if definition is None:
            return ToolResult(call.id, call.name, False, f"unknown tool: {call.name}")
        try:
            arguments = json.loads(call.arguments)
            if not isinstance(arguments, dict):
                raise ValueError("arguments must decode to a JSON object")
            _validate_arguments(definition, arguments)
            content = definition.handler(**arguments)
            return ToolResult(call.id, call.name, True, content)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            return ToolResult(call.id, call.name, False, f"invalid arguments: {error}")
        except Exception as error:
            return ToolResult(call.id, call.name, False, f"tool failed: {type(error).__name__}: {error}")


def _validate_arguments(definition: ToolDefinition, arguments: dict[str, Any]) -> None:
    unknown = set(arguments) - set(definition.argument_types)
    missing = definition.required - set(arguments)
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"missing required fields: {', '.join(sorted(missing))}")
    for name, value in arguments.items():
        expected_type = definition.argument_types[name]
        if type(value) is not expected_type:
            raise ValueError(f"{name} must be {expected_type.__name__}")


def build_default_registry(workspace: Workspace, runner: CommandRunner) -> ToolRegistry:
    def list_files(path: str = ".", depth: int = 2) -> str:
        return workspace.list_files(path, depth)

    def read_file(path: str, start_line: int = 1, end_line: int | None = None) -> str:
        return workspace.read_file(path, start_line, end_line)

    def write_file(path: str, content: str) -> str:
        target = workspace.resolve_path(path)
        before: str | None = None
        if target.exists():
            raw = target.read_bytes()
            if b"\x00" in raw:
                raise ValueError("cannot diff binary files")
            before = raw.decode("utf-8")
        message = workspace.write_file(path, content)
        relative = target.relative_to(workspace.root).as_posix()
        return json.dumps(
            {"path": relative, "message": message, "diff": make_unified_diff(before, content, relative)},
            ensure_ascii=False,
        )

    def run_command(command: str, cwd: str = ".", timeout_seconds: int = 30) -> str:
        result = runner.run(command, cwd, timeout_seconds)
        return json.dumps({"approved": result.approved, "returncode": result.returncode, "timed_out": result.timed_out, "truncated": result.truncated, "output": result.output}, ensure_ascii=False)

    def search_workspace(query: str, path: str = ".", max_results: int = 50, use_regex: bool = False) -> str:
        return search_text(workspace, query, path, max_results, use_regex)

    return ToolRegistry([
        ToolDefinition("list_files", "List files below a directory in the workspace.", _object_schema({"path": {"type": "string"}, "depth": {"type": "integer"}}), frozenset(), {"path": str, "depth": int}, list_files),
        ToolDefinition("read_file", "Read a UTF-8 text file with line numbers.", _object_schema({"path": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}}, ["path"]), frozenset({"path"}), {"path": str, "start_line": int, "end_line": int}, read_file),
        ToolDefinition("write_file", "Atomically write UTF-8 text to a workspace file.", _object_schema({"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]), frozenset({"path", "content"}), {"path": str, "content": str}, write_file),
        ToolDefinition("run_command", "Run a shell command in the workspace with a time limit.", _object_schema({"command": {"type": "string"}, "cwd": {"type": "string"}, "timeout_seconds": {"type": "integer"}}, ["command"]), frozenset({"command"}), {"command": str, "cwd": str, "timeout_seconds": int}, run_command),
        ToolDefinition("search_text", "Search workspace UTF-8 source files by literal text or regular expression.", _object_schema({"query": {"type": "string"}, "path": {"type": "string"}, "max_results": {"type": "integer"}, "use_regex": {"type": "boolean"}}, ["query"]), frozenset({"query"}), {"query": str, "path": str, "max_results": int, "use_regex": bool}, search_workspace),
    ])


def build_read_only_registry(workspace: Workspace) -> ToolRegistry:
    """Expose project-inspection tools only; no mutation or shell execution."""
    def list_files(path: str = ".", depth: int = 2) -> str:
        return workspace.list_files(path, depth)

    def read_file(path: str, start_line: int = 1, end_line: int | None = None) -> str:
        return workspace.read_file(path, start_line, end_line)

    def search_workspace(query: str, path: str = ".", max_results: int = 50, use_regex: bool = False) -> str:
        return search_text(workspace, query, path, max_results, use_regex)

    return ToolRegistry([
        ToolDefinition("list_files", "List files below a directory in the workspace.", _object_schema({"path": {"type": "string"}, "depth": {"type": "integer"}}), frozenset(), {"path": str, "depth": int}, list_files),
        ToolDefinition("read_file", "Read a UTF-8 text file with line numbers.", _object_schema({"path": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}}, ["path"]), frozenset({"path"}), {"path": str, "start_line": int, "end_line": int}, read_file),
        ToolDefinition("search_text", "Search workspace UTF-8 source files by literal text or regular expression.", _object_schema({"query": {"type": "string"}, "path": {"type": "string"}, "max_results": {"type": "integer"}, "use_regex": {"type": "boolean"}}, ["query"]), frozenset({"query"}), {"query": str, "path": str, "max_results": int, "use_regex": bool}, search_workspace),
    ])


def _object_schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        schema["required"] = required
    return schema
