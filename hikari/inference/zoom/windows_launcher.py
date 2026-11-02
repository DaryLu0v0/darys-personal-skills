"""Local Windows control window for Hikari's WSL Zoom assistant.

Opening the window checks setup. Only Join sends a meeting invitation to OpenClaw.
The API key is inherited through WSLENV, never placed in command arguments.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading

from zoom_assistant import checked_id, checked_zoom_url

HERE = Path(__file__).resolve().parent


def linux_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    if not re.match(r"^[A-Za-z]:/", value):
        raise ValueError("Keep the local Hikari checkout on a Windows drive.")
    return "/mnt/" + value[0].lower() + value[2:]


def build_command(action: str, value: str | None = None, *,
                  project: str | None = None, switch_project: bool = False) -> list[str]:
    if action not in {"check", "status", "join", "voice", "leave", "prepare"}:
        raise ValueError("Choose check, status, join, voice, leave, or prepare.")
    if project and action not in {"join", "prepare"}:
        raise ValueError("Select a project when preparing or joining a meeting.")
    if switch_project and (action != "join" or not project):
        raise ValueError("Switching projects requires Join and a project folder.")
    project_path = None
    if project:
        folder = Path(project).expanduser().resolve()
        if not folder.is_dir() or folder == Path(folder.anchor):
            raise ValueError("Choose an existing project folder, not a file or drive root.")
        project_path = linux_path(folder)
    tail = [action]
    if action == "join":
        tail.append(checked_zoom_url(value or ""))
        if project_path:
            tail = ["join-project", project_path, tail[-1]]
            if switch_project:
                tail.append("--switch")
    elif action == "prepare":
        if not project_path:
            raise ValueError("Prepare requires a project folder.")
        tail = ["project-prepare", project_path]
    elif action == "voice":
        tail = ["speak", checked_id(value or "", "Meeting session ID"),
                "Say briefly: Hikari's voice is connected. I am ready to listen."]
    elif action == "leave":
        tail.append(checked_id(value or "", "Meeting session ID"))
    elif action == "status" and value:
        tail.append(checked_id(value, "Meeting session ID"))
    return ["wsl.exe", "-d", os.environ.get("HIKARI_WSL_DISTRO", "Hikari"),
            "-u", "hikari", "--exec", "bash", linux_path(HERE / "local_runtime.sh"), *tail]


def child_environment() -> dict[str, str]:
    env = os.environ.copy()
    entries = [part for part in env.get("WSLENV", "").split(":")
               if part and part.split("/")[0] != "OPENAI_API_KEY"]
    if env.get("OPENAI_API_KEY"):
        entries.append("OPENAI_API_KEY/u")
    env["WSLENV"] = ":".join(entries)
    return env


def run_action(action: str, value: str | None = None, *,
               project: str | None = None, switch_project: bool = False) -> tuple[int, str]:
    result = subprocess.run(build_command(action, value, project=project,
                                          switch_project=switch_project), env=child_environment(),
                            capture_output=True, encoding="utf-8", errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                            timeout=260, shell=False)
    output = result.stdout + ("\n" + result.stderr if result.stderr else "")
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        output = output.replace(key, "[redacted]")
    return result.returncode, output.strip()


def result_objects(text: str) -> list[dict]:
    decoder = json.JSONDecoder()
    objects = []
    consumed = 0
    for match in re.finditer(r"(?m)^\s*\{", text):
        if match.start() < consumed:
            continue
        try:
            start = match.start() + len(match.group()) - 1
            obj, length = decoder.raw_decode(text[start:])
            consumed = start + length
            if isinstance(obj, dict):
                objects.append(obj)
        except ValueError:
            continue
    return objects


def returned_session(text: str) -> str | None:
    for obj in result_objects(text):
        session = obj.get("session")
        if not isinstance(session, dict):
            active = [s for s in obj.get("sessions", [])
                      if isinstance(s, dict) and s.get("state") == "active"]
            session = active[0] if len(active) == 1 else None
        candidate = session.get("id") if isinstance(session, dict) else None
        candidate = candidate or obj.get("sessionId")
        if isinstance(candidate, str):
            try:
                return checked_id(candidate, "Meeting session ID")
            except ValueError:
                pass
    return None


def readable_result(action: str, code: int, text: str) -> str:
    objects = result_objects(text)
    if action == "check":
        checks = next((obj["checks"] for obj in objects if isinstance(obj.get("checks"), list)), [])
        if checks:
            lines = [("OK: " if item.get("ok") else "Needs attention: ") + item.get("message", item.get("id", "Check")) for item in checks]
            return "\n".join(lines)
    if code:
        return "The request did not complete. Open Details for the error. Check meeting status before retrying a join."
    if action in {"join", "status", "voice"}:
        if any(obj.get("sessions") == [] for obj in objects):
            return "Hikari is not in a meeting. Paste an invitation above to join."
        sessions = [obj["session"] for obj in objects if isinstance(obj.get("session"), dict)]
        sessions += [s for obj in objects for s in obj.get("sessions", [])
                     if isinstance(s, dict) and s.get("state") == "active"]
        for session in sessions:
            if isinstance(session, dict):
                chrome = session.get("chrome") or {}
                health = chrome.get("health") or {}
                if session.get("state") == "ended":
                    return "This Hikari session has ended. Join again to reconnect."
                if health.get("inCall") is True:
                    if health.get("speechReady") is True and chrome.get("audioBridge"):
                        return "Hikari is in the meeting and its voice connection is ready. Say 'Hikari' followed by your question from your own Zoom participant."
                    reason = health.get("speechBlockedMessage")
                    if health.get("speechBlockedReason") == "audio-bridge-unavailable":
                        reason = "Choose Connect voice after Zoom admits Hikari."
                    return "Hikari is in the meeting, but its voice is not ready. " + (reason or "Choose Connect voice, then check Meeting status.")
                manual = health.get("manualAction")
                if manual:
                    return "Zoom needs your attention in Hikari's Chrome window (for example, sign-in or host admission)."
        return "Request completed. Check Hikari's Chrome window for meeting admission, then refresh Meeting status."
    if action == "leave":
        if any(obj.get("browserLeft") is True for obj in objects):
            return "The browser confirms Hikari left the meeting."
        return "Departure requested. Confirm Hikari has disappeared from the meeting's participant list."
    return "Request completed."


def launch_window() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk

    root = tk.Tk()
    root.title("Hikari · Zoom assistant")
    root.geometry("820x690")
    root.minsize(780, 640)
    style = ttk.Style(root)
    style.theme_use("vista")
    style.configure("TLabel", font=("Segoe UI", 10))
    style.configure("TButton", font=("Segoe UI", 10), padding=7)
    frame = ttk.Frame(root, padding=22)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Hikari", font=("Segoe UI", 24, "bold")).pack(anchor="w")
    ttk.Label(frame, text="Choose a project and invite Hikari to your meeting.").pack(anchor="w", pady=(2, 16))
    project = tk.StringVar()
    ttk.Label(frame, text="Project folder (optional; blank keeps the selected agent)").pack(anchor="w")
    project_row = ttk.Frame(frame)
    project_row.pack(fill="x", pady=(4, 6))
    ttk.Entry(project_row, textvariable=project, font=("Segoe UI", 11)).pack(side="left", fill="x", expand=True)

    def browse_project() -> None:
        chosen = filedialog.askdirectory(title="Choose Hikari's project", parent=root)
        if chosen:
            project.set(chosen)

    ttk.Button(project_row, text="Browse…", command=browse_project).pack(side="left", padx=(8, 0))
    switch_project = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame, text="Replace the current meeting voice when switching projects",
                    variable=switch_project).pack(anchor="w", pady=(0, 12))
    url = tk.StringVar()
    ttk.Label(frame, text="Meeting link").pack(anchor="w")
    invite = ttk.Entry(frame, textvariable=url, font=("Segoe UI", 11))
    invite.pack(fill="x", pady=(4, 12))
    invite.focus_set()
    actions = ttk.Frame(frame)
    actions.pack(fill="x")
    state = tk.StringVar(value="Checking local setup…")
    session_id = tk.StringVar()
    events: queue.Queue = queue.Queue()
    buttons = []
    latest_details = {"text": "No checks have completed yet."}
    startup = {"discover": True}

    def perform(action: str) -> None:
        value = url.get().strip() if action == "join" else session_id.get().strip()
        selected_project = project.get().strip() if action == "join" else None
        switching = switch_project.get() if action == "join" else False
        if action == "status":
            value = ""  # Rediscover sessions after a service/plugin reconnect.
        try:
            build_command(action, value or None, project=selected_project or None, switch_project=switching)
        except ValueError as exc:
            messagebox.showerror("Hikari", str(exc), parent=root)
            return
        for button in buttons:
            button.configure(state="disabled")
        state.set({"check": "Checking browser, audio, and model setup…",
                   "join": "Joining… Zoom may ask you to sign in or wait for the host.",
                   "status": "Checking meeting status…", "voice": "Connecting voice and requesting a short greeting…",
                   "leave": "Leaving the meeting…"}[action])

        def worker() -> None:
            try:
                code, text = run_action(action, value or None, project=selected_project or None,
                                         switch_project=switching)
            except subprocess.TimeoutExpired:
                code, text = 1, "The request timed out. Check status before retrying; a join may still be active."
            except Exception as exc:
                code, text = 1, str(exc)
            events.put((action, code, text))

        threading.Thread(target=worker, daemon=True).start()

    for label, action in [("Join meeting", "join"), ("Connect voice", "voice"), ("Check setup", "check"), ("Meeting status", "status"), ("Leave meeting", "leave")]:
        button = ttk.Button(actions, text=label, command=lambda action=action: perform(action))
        button.pack(side="left", padx=(0, 6))
        buttons.append(button)
    ttk.Label(frame, textvariable=state, wraplength=720).pack(anchor="w", pady=(16, 10))
    session_row = ttk.Frame(frame)
    session_row.pack(fill="x", pady=(0, 8))
    ttk.Label(session_row, text="Session").pack(side="left", padx=(0, 8))
    ttk.Entry(session_row, textvariable=session_id).pack(side="left", fill="x", expand=True)
    output = scrolledtext.ScrolledText(frame, height=12, wrap="word", font=("Consolas", 9), state="disabled")
    output.pack(fill="both", expand=True)
    ttk.Label(frame, text="Voice uses your configured OpenAI API account. Closing this window does not leave a meeting.",
              wraplength=720).pack(anchor="w", pady=(10, 0))

    def show_details() -> None:
        details = tk.Toplevel(root)
        details.title("Hikari · Check details")
        details.geometry("760x520")
        box = scrolledtext.ScrolledText(details, wrap="word", font=("Consolas", 9))
        box.pack(fill="both", expand=True, padx=12, pady=12)
        box.insert("1.0", latest_details["text"])
        box.configure(state="disabled")

    ttk.Button(frame, text="Details", command=show_details).pack(anchor="e", pady=(6, 0))

    def poll() -> None:
        try:
            while True:
                action, code, text = events.get_nowait()
                latest_details["text"] = text
                for button in buttons:
                    button.configure(state="normal")
                found = returned_session(text)
                if found:
                    session_id.set(found)
                if code:
                    state.set("Needs attention — see the details below.")
                else:
                    state.set({"check": "Local setup is ready. Paste a Zoom invite above.",
                               "join": "Join requested. Check admission in the browser and meeting status.",
                               "voice": "Voice request finished. Check the connection result below.",
                               "status": "Meeting status updated below.",
                               "leave": "Leave requested. Confirm departure below."}[action])
                output.configure(state="normal")
                output.insert("end", f"{action.upper()}\n{readable_result(action, code, text)}\n\n")
                output.see("end")
                output.configure(state="disabled")
                if action == "check" and startup["discover"]:
                    startup["discover"] = False
                    if not code:
                        root.after(200, lambda: perform("status"))
        except queue.Empty:
            pass
        root.after(150, poll)

    root.after(150, poll)
    root.after(250, lambda: perform("check"))
    root.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", default="ui", choices=["ui", "check", "status", "join", "voice", "leave", "prepare"])
    parser.add_argument("value", nargs="?")
    parser.add_argument("--project", help="Local Windows project folder for the meeting agent")
    parser.add_argument("--switch-project", action="store_true", help="Explicitly replace an active voice session belonging to another project")
    args = parser.parse_args()
    if args.action == "ui":
        launch_window()
        return 0
    try:
        code, output = run_action(args.action, args.value, project=args.project,
                                  switch_project=args.switch_project)
        print(output)
        return code
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
