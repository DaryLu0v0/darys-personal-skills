# Windows and WSL setup boundary

The Windows launcher is a bridge to an **already provisioned** WSL installation,
not a general-purpose installer. This public package contains code and generic
instructions; it contains no configured distribution, services, credentials,
desktop shortcuts or personal setup receipts.

From the repository's `hikari/` subfolder, `Start-Hikari.cmd` opens the launcher.
The launcher can start/check the configured services. Only an explicit Join
operation requests meeting participation. Closing the window does not leave.

## Required local configuration

Verify these prerequisites on the intended host before use:

| Component | Expected interface |
| --- | --- |
| WSL | Distribution `Hikari` by default, or `HIKARI_WSL_DISTRO`; Linux user `hikari` |
| OpenClaw and official Zoom plugin | Pinned `2026.10.9`; separately installed and configured |
| Browser/audio | Chrome, Linux desktop session, PipeWire-Pulse and required virtual audio |
| Gateway | Authenticated loopback service on port 18989; `hikari-gateway.service` |
| Controller | `hikari-session.service`, private user-only Unix socket |
| Model access | Credentials available to the Gateway through the user's approved provider setup |
| Project agent | Explicitly selected project; normal command review, no elevated execution |

The scripts derive their code location from their own files. Update any existing
host-specific service paths only during an authorized migration. This repository
does not install or rewrite those services. Do not point a second controller at an
active meeting.

The launcher inherits an existing `OPENAI_API_KEY` through WSLENV when configured.
It does not write that key into source or command arguments. Provider usage can
incur charges. Never commit credentials, gateway tokens or real meeting invitations.

## Selecting a project and joining

Run from `hikari/`, replacing the example path and invitation:

```console
python inference/zoom/windows_launcher.py check
python inference/zoom/windows_launcher.py prepare --project "C:\path\to\project"
python inference/zoom/windows_launcher.py join "YOUR_ZOOM_INVITE_URL" --project "C:\path\to\project"
python inference/zoom/windows_launcher.py status
python inference/zoom/windows_launcher.py voice SESSION_ID
python inference/zoom/windows_launcher.py leave SESSION_ID
```

Preparation creates or reuses a stable agent for the canonical folder and preserves
its project files. Per-agent metadata is kept in the private OpenClaw state directory.
The selected folder is the agent workspace; it does not connect every local folder.
The project profile permits coding under OpenClaw's normal tool policy and reviewer.
File tools are scoped to the workspace, but shell execution is not an OS sandbox.
Read the generated profile before using it with sensitive projects.

One meeting/project is selected at a time. Leave an unrelated meeting first.
Explicit `--switch-project` replaces the voice session for the requested project
in the current meeting. Do not silently replace active work.

Zoom may require sign-in, security verification, a passcode or host admission in
the configured Chrome profile. Those steps remain manual. After admission, Connect
voice requests a greeting. Confirm the intended agent, in-call status, speech
readiness, audio bridge and actual audibility; an allocated session is insufficient.
Keep Hikari as a guest for this pinned plugin. If a request times out, inspect
status before retrying because a join may already have succeeded.

## Skills, evidence and restrictions

The optional `hikari-meeting` skill source is in `../skills/hikari-meeting/`.
Cloning does not install it. Project `skills/` and `.agents/skills/` are discoverable
by the configured OpenClaw runtime, but Codex connectors and personal skills do not
automatically transfer. Use only tools and permissions actually available.

For a new project, check actual tool results against a known file or a requested
code change. A spoken summary is not proof of execution. Do not read raw protected
session stores or publish private meeting content. Honor approval requests; do not
disable reviews, alter trust settings or invent approval commands.

## Version-specific compatibility

The optional `local_consult_patch.mjs` backport targets one exact OpenClaw artifact
and references upstream PR 142692. It preserves gateway-drain refusal and tool
policy, checks the original hash, and keeps rollback material. Its upstream status
was recorded at the source revision; verify current compatibility before any use.
Applying/restoring it changes the installed runtime and may require restarting the
Gateway and obtaining admission again. It is never run by portable tests.

The generic configuration generator's voice route can differ from a working local
installation. Do not reapply it over host configuration without reviewing the change.
No live meeting, model invocation or native audio verification was performed for this
consolidation. Use [the controlled check](VALIDATION.md#controlled-meeting-check)
on the actual host before claiming readiness.
