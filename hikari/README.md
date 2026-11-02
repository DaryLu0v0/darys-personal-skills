# Hikari meeting assistant

A named Zoom voice participant with a reusable project agent. The wrapper uses
OpenClaw's official Zoom plugin; the project agent can inspect a selected workspace,
use available skills and complete authorized coding work under its configured review
policy. No meeting is joined merely by cloning this repository.

The research dashboard, canonical library tools, Obsidian notes and maintenance
workflow now live in the sibling [personal_assistant/](../personal_assistant/) package.
There is one library implementation. Hikari may contribute evidence-backed handoffs;
a meeting does not automatically connect all projects or publish its conversation.

## Layout

- `Start-Hikari.cmd`: Windows launcher entry point.
- `inference/zoom/zoom_assistant.py`: standard-library CLI for scoped configuration,
  validation and live meeting controls.
- `inference/zoom/windows_launcher.py`, `local_runtime.sh`, `local_session.mjs`:
  launcher and persistent controller for a separately provisioned Windows/WSL host.
- `inference/zoom/project_agent.py`: stable project identity and explicit selection.
- `inference/zoom/skills/`: optional skill sources; copying this folder does not install them.
- `inference/zoom/tests/`: offline tests and an explicitly separate installed-runtime check.
- `inference/zoom/vendor/openclaw/`: upstream manifest, pin and MIT license.
- [Manager workflow](docs/hikari-research-library-manager.md): points to the sibling
  library's canonical instructions rather than duplicating them.

## Setup and use

The [Zoom guide](inference/zoom/README.md) describes the pinned OpenClaw/plugin
`2026.10.9` workflow, prerequisites, scoped configuration and manual Zoom admission.
Python 3.10+ is sufficient for offline wrapper use. Node.js is needed for controller
tests and the installed meeting runtime. OpenClaw, Chrome, native audio and model
credentials are separately configured dependencies; none are installed by these tests.

Run these commands from `hikari/` for an offline configuration check:

```console
python -B inference/zoom/zoom_assistant.py prepare --brief inference/zoom/MEETING_BRIEF.example.md --agent EXAMPLE_AGENT --output inference/zoom/.local/example.patch.json
python -B inference/zoom/zoom_assistant.py validate --patch inference/zoom/.local/example.patch.json
```

The example does not establish that EXAMPLE_AGENT exists. Preparation refuses an
existing output unless explicitly told otherwise; keep real briefs and generated
patches ignored.

For the Windows launcher, first read [Windows/WSL prerequisites](inference/zoom/docs/LOCAL_WINDOWS.md).
It expects provisioned services and a Linux desktop/audio environment. It is not an
installer. Use `Start-Hikari.cmd` only after that setup. Opening the launcher may
start/check local services; joining, speaking and selecting a project are explicit
operations with effects described in the guide.

## Tests

From `hikari/`:

```console
python -B -m unittest discover -s inference/zoom/tests -p "test_*.py" -v
node --test inference/zoom/tests/test_local_session.mjs
node --check inference/zoom/local_session.mjs
node --check inference/zoom/local_consult_patch.mjs
```

These offline tests mock live calls. They do not use credentials, start a project
agent, join Zoom or run a research experiment.

`tests/test_local_consult_patch.mjs` is a separate integration test against the
exact provisioned OpenClaw lifecycle artifacts. Run it only in that intended host
after verifying the pin; it is not part of the portable suite and is not replaced by
a mock claim of live success. [Validation boundaries](inference/zoom/docs/VALIDATION.md)
describe the additional manual admission, audio and delegation checks.

## Migration and privacy

This code copy preserves the original Hikari repository and running checkouts.
Existing shortcuts, service files and scheduled paths are not rewritten. A future
host migration needs an explicit path/configuration review; do not run two meeting
controllers against the same live session.

No private research library, emails, transcripts, credentials, meeting history or
local verification receipts are included. Source versions and adaptations are
documented in [SOURCE.md](SOURCE.md); upstream attribution is in
[THIRD_PARTY.md](THIRD_PARTY.md). A clone grants no new source access or authorization.
