"""A compact desktop interface for Pine Agent, built with the Python standard library."""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any

from .agent_loop import AgentLoop
from .command_runner import CommandRunner
from .config import ConfigurationError, load_settings
from .model_client import OpenAICompatibleClient
from .tool_registry import build_default_registry
from .trace import TraceWriter
from .workspace import Workspace, WorkspaceError


@dataclass(frozen=True)
class GuiRunConfig:
    task: str
    workspace: Path
    api_key: str
    base_url: str
    model: str
    max_turns: int
    max_seconds: int
    trace_dir: Path
    approve_all: bool


class PineGui(ttk.Frame):
    """Runs the existing AgentLoop on a worker thread and renders its local events."""

    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=16)
        self.master = master
        self.events: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        self.cancelled = threading.Event()
        self.running = False
        self._build_variables()
        self._build_layout()
        self.after(100, self._drain_events)

    def _build_variables(self) -> None:
        root = Path.cwd()
        self.workspace_var = tk.StringVar(value=str(root / "demo_project" if (root / "demo_project").is_dir() else root))
        self.api_key_var = tk.StringVar(value=os.environ.get("OPENAI_API_KEY", ""))
        self.base_url_var = tk.StringVar(value=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
        self.model_var = tk.StringVar(value=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"))
        self.turns_var = tk.StringVar(value="10")
        self.seconds_var = tk.StringVar(value="180")
        self.trace_var = tk.StringVar(value=str(root / "runs"))
        self.approve_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready")

    def _build_layout(self) -> None:
        self.master.title("Pine Agent")
        self.master.minsize(980, 680)
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.grid(sticky="nsew")
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        ttk.Label(self, text="Pine Agent", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(self, text="Local tools, visible execution, bounded runs", style="Subtitle.TLabel").grid(row=0, column=1, sticky="e")

        settings = ttk.LabelFrame(self, text="Run Settings", padding=12)
        settings.grid(row=1, column=0, sticky="nsw", padx=(0, 14), pady=(14, 0))
        self._setting_row(settings, 0, "Workspace", self.workspace_var, self._choose_workspace)
        self._setting_row(settings, 1, "API key", self.api_key_var, None, show="*")
        self._setting_row(settings, 2, "Base URL", self.base_url_var)
        self._setting_row(settings, 3, "Model", self.model_var)
        self._setting_row(settings, 4, "Max turns", self.turns_var)
        self._setting_row(settings, 5, "Max seconds", self.seconds_var)
        self._setting_row(settings, 6, "Trace directory", self.trace_var, self._choose_trace_dir)
        ttk.Checkbutton(settings, text="Auto-approve commands", variable=self.approve_var).grid(row=7, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(settings, text="Without auto-approve, every command opens a confirmation dialog.", wraplength=270, style="Hint.TLabel").grid(row=8, column=0, columnspan=3, sticky="w", pady=(4, 0))

        content = ttk.Frame(self)
        content.grid(row=1, column=1, sticky="nsew", pady=(14, 0))
        content.columnconfigure(0, weight=1)
        content.rowconfigure(2, weight=1)
        ttk.Label(content, text="Task", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.task_box = scrolledtext.ScrolledText(content, height=7, wrap=tk.WORD, font=("Consolas", 11), relief="solid", borderwidth=1)
        self.task_box.grid(row=1, column=0, sticky="ew", pady=(6, 10))
        self.task_box.insert("1.0", "Read the relevant files, implement the requested change, run tests, and report the verification result.")
        controls = ttk.Frame(content)
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        controls.columnconfigure(2, weight=1)
        self.run_button = ttk.Button(controls, text="Run Task", command=self._start_run, style="Accent.TButton")
        self.run_button.grid(row=0, column=0, sticky="w")
        self.stop_button = ttk.Button(controls, text="Stop", command=self._stop_run, state="disabled")
        self.stop_button.grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Label(controls, textvariable=self.status_var, style="Status.TLabel").grid(row=0, column=2, sticky="e")
        ttk.Label(content, text="Execution", style="Section.TLabel").grid(row=3, column=0, sticky="w")
        self.log_box = scrolledtext.ScrolledText(content, wrap=tk.WORD, font=("Consolas", 10), state="disabled", relief="solid", borderwidth=1)
        self.log_box.grid(row=4, column=0, sticky="nsew", pady=(6, 0))
        content.rowconfigure(4, weight=1)

    def _setting_row(self, parent: ttk.LabelFrame, row: int, label: str, variable: tk.StringVar, command=None, show: str | None = None) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        entry = ttk.Entry(parent, textvariable=variable, width=31, show=show)
        entry.grid(row=row, column=1, sticky="ew", pady=4, padx=(8, 4))
        if command:
            ttk.Button(parent, text="Browse", command=command).grid(row=row, column=2, pady=4)

    def _choose_workspace(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.workspace_var.get() or str(Path.cwd()))
        if selected:
            self.workspace_var.set(selected)

    def _choose_trace_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.trace_var.get() or str(Path.cwd()))
        if selected:
            self.trace_var.set(selected)

    def _read_config(self) -> GuiRunConfig | None:
        task = self.task_box.get("1.0", tk.END).strip()
        if not task:
            messagebox.showerror("Missing task", "Enter a programming task before running.")
            return None
        try:
            max_turns = int(self.turns_var.get())
            max_seconds = int(self.seconds_var.get())
        except ValueError:
            messagebox.showerror("Invalid budget", "Max turns and max seconds must be integers.")
            return None
        workspace = Path(self.workspace_var.get()).expanduser().resolve()
        if not workspace.is_dir():
            messagebox.showerror("Invalid workspace", f"Workspace is not a directory:\n{workspace}")
            return None
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showerror("Missing API key", "Enter an API key. It is held only in this process and is not written to the trace.")
            return None
        return GuiRunConfig(task, workspace, api_key, self.base_url_var.get().strip(), self.model_var.get().strip(), max_turns, max_seconds, Path(self.trace_var.get()).expanduser(), self.approve_var.get())

    def _start_run(self) -> None:
        config = self._read_config()
        if not config:
            return
        self.running = True
        self.cancelled.clear()
        self.run_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set("Running")
        self._clear_log()
        self._append("Run started. The API key is never displayed or logged.\n")
        threading.Thread(target=self._run_agent, args=(config,), daemon=True).start()

    def _run_agent(self, config: GuiRunConfig) -> None:
        try:
            previous = {name: os.environ.get(name) for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL")}
            os.environ["OPENAI_API_KEY"] = config.api_key
            os.environ["OPENAI_BASE_URL"] = config.base_url
            os.environ["OPENAI_MODEL"] = config.model
            settings = load_settings(max_turns=config.max_turns, max_seconds=config.max_seconds)
            workspace = Workspace(config.workspace)
            runner = CommandRunner(workspace, approve_all=config.approve_all, confirmer=self._confirm_command)
            trace = TraceWriter(config.trace_dir)
            trace.record("run_started", task=config.task, workspace=str(config.workspace), model=settings.model)
            client = OpenAICompatibleClient(api_key=settings.api_key, base_url=settings.base_url, model=settings.model)
            result = AgentLoop(client, build_default_registry(workspace, runner), max_turns=settings.max_turns, max_seconds=settings.max_seconds, cancelled=self.cancelled, trace=trace, on_event=self._on_agent_event).run(config.task)
            self.events.put(("result", {"result": result, "trace": trace.path}))
        except (ConfigurationError, WorkspaceError, OSError, ValueError) as error:
            self.events.put(("fatal", {"error": str(error)}))
        finally:
            for name, value in previous.items() if "previous" in locals() else ():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def _on_agent_event(self, event: str, payload: dict[str, Any]) -> None:
        self.events.put(("agent", {"event": event, **payload}))

    def _confirm_command(self, command: str) -> bool:
        reply: queue.Queue[bool] = queue.Queue(maxsize=1)
        self.events.put(("confirm", {"command": command, "reply": reply}))
        try:
            return reply.get(timeout=300)
        except queue.Empty:
            return False

    def _stop_run(self) -> None:
        self.cancelled.set()
        self.status_var.set("Stopping after the current request")
        self.stop_button.configure(state="disabled")

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "confirm":
                    allowed = messagebox.askyesno("Allow command?", f"Run this command in the selected workspace?\n\n{payload['command']}", parent=self.master)
                    payload["reply"].put(allowed)
                elif kind == "agent":
                    self._render_agent_event(payload)
                elif kind == "result":
                    result = payload["result"]
                    self._append(f"\nResult: {result.summary}\n")
                    self._append(f"Stop reason: {result.reason.value}; turns: {result.turns}; tool calls: {len(result.tool_results)}\n")
                    self._append(f"Trace: {payload['trace']}\n")
                    self._finish_run(result.reason.value)
                elif kind == "fatal":
                    self._append(f"\nError: {payload['error']}\n")
                    self._finish_run("error")
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _render_agent_event(self, event: dict[str, Any]) -> None:
        name = event["event"]
        if name == "model_request":
            self._append(f"[Turn {event['turn']}] Requesting model with {event['message_count']} messages.\n")
        elif name == "assistant_reply":
            tools = event["tools"]
            self._append(f"[Turn {event['turn']}] Model requested: {', '.join(tools) if tools else 'final response'}.\n")
        elif name == "tool_result":
            state = "ok" if event["ok"] else "failed"
            preview = str(event["content"]).replace("\n", " ")[:180]
            self._append(f"[Turn {event['turn']}] {event['tool']}: {state}. {preview}\n")
        elif name in {"model_error", "protocol_error"}:
            self._append(f"[Turn {event['turn']}] {name}: {event['error']}\n")
        elif name == "run_finished":
            self._append(f"Run finished: {event['reason']} after {event['turns']} turn(s).\n")

    def _finish_run(self, reason: str) -> None:
        self.running = False
        self.run_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status_var.set(f"Finished: {reason}")

    def _append(self, text: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert(tk.END, text)
        self.log_box.see(tk.END)
        self.log_box.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", tk.END)
        self.log_box.configure(state="disabled")


def main() -> int:
    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
    style.configure("Subtitle.TLabel", foreground="#55606e")
    style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"))
    style.configure("Hint.TLabel", foreground="#55606e", font=("Segoe UI", 9))
    style.configure("Status.TLabel", foreground="#0e7490", font=("Segoe UI", 10, "bold"))
    style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
    PineGui(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
