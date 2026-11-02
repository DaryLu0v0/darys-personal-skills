---
name: hikari-meeting
description: Join a Zoom meeting with Hikari's live voice and a reusable local project agent that can inspect files, use project skills, edit code, and run checks. Use when the user asks to bring a project-aware AI agent into a meeting or switch Hikari to another project.
---

# Hikari project meeting

Use an already provisioned local Windows/WSL installation. Locate the user's
chosen Hikari checkout; in this monorepo it is the `hikari/` subfolder, with launcher
`inference/zoom/windows_launcher.py`. This is a launcher, not an installer.
Confirm the intended host configuration before running it. Do not assume that
cloning this code migrated existing services or credentials.

Infer the project folder from the user's request or current project. Ask only
for an ambiguous project or a missing Zoom invitation. Do not reuse a meeting
link from a different task. Any valid `https://*.zoom.us/j/MEETING_ID` invitation
can be supplied, including its passcode query. Admission still depends on Zoom.

From the Hikari checkout, run with literal arguments:

```powershell
python inference/zoom/windows_launcher.py check
python inference/zoom/windows_launcher.py prepare --project "C:\path\to\project"
python inference/zoom/windows_launcher.py join "ZOOM_INVITATION" --project "C:\path\to\project"
python inference/zoom/windows_launcher.py status
```

Preparation creates or reuses a stable agent for that canonical folder. The
agent's private state and history live in Hikari WSL; its workspace and working
directory are the selected project. Automatic OpenClaw template creation is
disabled. Preparation does not copy or edit the project's files.
The voice agent delegates project questions and work to this project agent.
Project `skills/` and `.agents/skills/` are discoverable by OpenClaw, along with
the installed `project-work` skill. Codex's own skills and connector tools are
not automatically available inside OpenClaw; inspect dependencies before
adapting a requested skill.

This local profile supports one selected project and meeting at a time.
Changing the project replaces the voice session. If another project is active,
leave that meeting first. When the user requests switching the current meeting
to a new project, that request authorizes `--switch-project` on the join command;
do not ask again. Never silently replace an unrelated active meeting.

Zoom may require the user to complete a security check or admit Hikari. Keep
Hikari as a guest and the user as host with this pinned plugin. After admission:

```powershell
python inference/zoom/windows_launcher.py voice SESSION_ID
```

Verify `agentId`, `inCall`, `speechReady`, and the audio bridge from the returned
status. An allocated session or a spoken claim does not prove tool use. For a
new project, verify a concrete file lookup with a result not supplied in the
prompt. For coding tasks, inspect the actual changes and check results. Ask the
user to address Hikari normally for the final conversational check.

The project agent uses native OpenClaw tools and its automatic command approval
reviewer. Honor pending approvals. Never broaden permissions to make a test
pass. Never install, run, expose, or proxy OpenClaw on restricted institutional compute systems.

To leave, use `python inference/zoom/windows_launcher.py leave SESSION_ID`.
Closing the launcher leaves the meeting running.

Read `inference/zoom/docs/LOCAL_WINDOWS.md` in the checkout for audio repair,
agent-history inspection, and the version-pinned upstream consultation fix.
Do not reapply the repository's generic configuration patch: it would replace
the local working voice model. Do not modify official plugin trust metadata.
