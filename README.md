# Dary's Personal Skills

Reusable Codex skills, assistant tools, and validation suites. This repository is
public; personal records and runtime configuration belong in private local storage.

## Components

| Folder | Purpose | Start here |
| --- | --- | --- |
| [personal_assistant/](personal_assistant/) | Today, Life, Research and Literature dashboard; research handoffs, Obsidian notes and private attention support | [Setup and tests](personal_assistant/README.md) |
| [hikari/](hikari/) | Zoom voice participant and reusable project meeting agent | [Setup and tests](hikari/README.md) |
| [Scientific review tool](overleaf-related/tex-grammarly-reviewer/) | `scientific-tex-reviewer` skill and `tex-review` CLI for source-preserving manuscript review | [Setup and tests](overleaf-related/tex-grammarly-reviewer/README.md) |
| [overleaf-related/](overleaf-related/) | Scientific LaTeX review, Grammarly-assisted analysis and supervised Overleaf review-panel workflows | [Guide](overleaf-related/README.md) |
| [codex-pet-ping/](codex-pet-ping/) | Windows Need Vision questions answered by the desktop pet; built on [lolPing](https://github.com/darrenprx/lolPing), with inspiration from [super-ping](https://github.com/norvancc/super-ping) | [Guide](codex-pet-ping/README.md) |
| [paper/](paper/) | Existing paper-library tooling | [Guide](paper/README.md) |

Each component keeps its instructions, references, implementation and tests together
so it can be audited before installation. Follow that component's prerequisites;
cloning this repository does not install applications, skills, integrations or tasks.

## Scientific review and Hikari: one repository

Both tools are maintained here. The scientific reviewer already occupied
`overleaf-related/tex-grammarly-reviewer/` before Hikari was added; that remains its
canonical location. Hikari remains in `hikari/`. Existing import paths, CLI names
and skill locations are preserved, with no duplicate reviewer package.

The [shared research-toolkit guide](docs/research-toolkit.md) maps their entry
points, setup, offline tests and optional handoff to the personal assistant.
Repository consolidation does not automatically install the reviewer into Hikari's
runtime or authorize manuscript uploads, Overleaf comments or meeting participation.

## Personal assistant quick start

From `personal_assistant/`, with Python 3.11+ and PyYAML 6.x installed:

```console
python -B tools/initialize.py --demo
python -B tools/library.py validate
python -B tools/serve_library.py --port 8767
```

Open http://127.0.0.1:8767/. Use another port if an existing dashboard is running.
Omit `--demo` for an empty library. Initialization refuses to overwrite local data.
The examples are fictional. See the component README for dependency installation,
the complete test commands, data ownership and supported collection methods.

## Hikari and the dashboard

`personal_assistant/` is the sole dashboard/library implementation in this repository.
`hikari/` contains the meeting integration and points to the same manager workflow;
it does not maintain a second copy of research data. Meetings can contribute
deliberately prepared, source-linked handoffs through the documented library workflow.

This is an additive code consolidation. Existing live checkouts, local data, original
repositories and scheduled paths are preserved. No running service is moved by a
clone or pull. See [Hikari provenance and migration](hikari/SOURCE.md).

## Privacy and local setup

Do not commit research conversations, private research records, email bodies or
account IDs, reminder choices, PDFs, credentials, meeting invitations or runtime logs.
The assistant's generated library, Obsidian vault and local state are Git-ignored.
Use a separate appropriate backup for those records.

Conversation collection requires an authorized native app interface or approved
handoff/export. Raw protected session stores are not an ingestion interface.
Schedules require separate local configuration, explicit scope, timezone and source
access. App availability, an awake host and permission prompts can limit unattended
coverage; installing this code does not transfer or guarantee a schedule.

Hikari requires separately provisioned OpenClaw, browser/audio and model access.
Offline tests do not join meetings or establish live audio readiness. Third-party
notices remain with their components, including [OpenClaw attribution](hikari/THIRD_PARTY.md).
