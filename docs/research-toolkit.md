# Scientific review, Hikari and the research library

One repository contains three components with separate responsibilities. The
scientific reviewer was already present before the Hikari consolidation, so its
established directory and APIs are retained. There is no second reviewer copy.

## Canonical locations and entry points

| Component | Location | Entry points |
| --- | --- | --- |
| Scientific review | [overleaf-related/tex-grammarly-reviewer/](../overleaf-related/tex-grammarly-reviewer/) | `tex-review score`, `review`, `panel`; Python package `tex_reviewer`; `scientific-tex-reviewer` skill |
| Project meetings | [hikari/](../hikari/) | `Start-Hikari.cmd`; `inference/zoom/zoom_assistant.py`; `windows_launcher.py`; optional `hikari-meeting` skill |
| Research records and attention | [personal_assistant/](../personal_assistant/) | `tools/serve_library.py`, `library.py`, `maintenance.py`; local Obsidian notes |

The reviewer implementation is under `src/tex_reviewer/`, and its skill is under
`skills/scientific-tex-reviewer/`. Its existing version and package/command names
remain unchanged. Hikari's meeting skills stay under `inference/zoom/skills/`.
Use each component README for installation and its actual runtime prerequisites.

## How they can work together

1. Use the reviewer on an authorized manuscript to prepare source-anchored feedback.
   Keep the original source, review manifest, hashes and audit trail in appropriate
   private storage. Default review outputs are comments, not manuscript edits.
2. When requested, use Hikari to discuss a selected project and approved review
   material. Verify that the project agent can access that material; a repository
   path or spoken claim does not prove retrieval or runtime capability.
3. Reconcile selected findings or decisions into the personal assistant through
   its [handoff workflow](../personal_assistant/docs/maintenance.md). Preserve
   Goal / Done and learned / Next and link the precise source revision. Distinguish
   reviewer suggestions, user decisions and independently checked research evidence.

These are explicit workflows, not automatic cross-service ingestion. Repo
co-location does not give OpenClaw the Codex tool surface or install a skill.
Grammarly/OpenAI manuscript transmission and supervised Overleaf publishing retain
their existing authorization requirements. Meeting participation and coding retain
Hikari's configured permissions. No runtime interfaces were merged or rewritten.

## Offline verification

Use Python 3.11+, pytest, PyYAML 6.x and Node.js with `node:test`. See the component
READMEs for optional environment setup; these commands do not install dependencies.
Start in the repository root and run the following in order:

```powershell
cd overleaf-related/tex-grammarly-reviewer
python -B -m pytest -q -o pythonpath=src
cd ../../hikari
python -B -m unittest discover -s inference/zoom/tests -p "test_*.py"
node --test inference/zoom/tests/test_local_session.mjs
cd ../personal_assistant
python -B -m unittest discover -s tools -p "test_*.py"
node --test tools/test_literature.js tools/test_attention.js
cd ..
```

The reviewer tests import this checkout's `src` directly. All three suites use
synthetic inputs and mocked live services. Dashboard HTTP tests open temporary
loopback listeners. In restricted Windows environments, select a writable test
temporary directory within the workspace if the default temporary directory is
inaccessible; do not change trust or security settings.

The installed-OpenClaw lifecycle integration test is separate and requires the
exact provisioned runtime. No real manuscripts, external scoring calls, meetings,
audio, experiments or schedule changes are part of these offline tests.

## Data and maintenance boundaries

Do not commit manuscripts, private review outputs, conversations, emails, PDFs,
credentials or runtime logs. Existing review outputs and the assistant's local
data remain ignored. Private content still needs an appropriate separate backup.
Public source code and synthetic tests are the shared artifacts in this repository.

The reviewer keeps its existing license metadata; Hikari keeps its OpenClaw
attribution. This organizational change does not impose a new blanket license or
alter unrelated components. Live local checkouts, source repositories, services
and schedules are unchanged. Future source updates belong in these canonical
component directories rather than new duplicate copies.

## Verification recorded on 2026-11-02

- Scientific review: 28 Python tests passed.
- Hikari: 34 Python tests and 4 JavaScript controller tests passed.
- Personal assistant: 59 Python tests and 17 JavaScript tests passed.
- No external scoring, manuscript publication or live meeting checks were run.

The scientific test process exited successfully; the host's existing `pyreadline3`
emitted a console cleanup warning after pytest completed. No environment packages
or permissions were changed to suppress it.
