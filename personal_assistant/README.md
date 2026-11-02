# Personal assistant

A local Hikari dashboard for daily attention, research paths and literature.
Today combines items that need review; Life contains personal administration;
Research preserves completed, active, possible and unsuccessful branches;
Literature presents canonical paper notes with project and checkpoint backlinks.

This package contains reusable code and **synthetic examples only**. It does not
include anyone's research records, conversations, emails, account identifiers,
PDFs, credentials, schedules or runtime state. Installing the code does not grant
access to Claude, Codex, Gmail or Obsidian, or create any scheduled task.

## Start locally

Use Python 3.11+ and PyYAML 6.x. Node.js with `node:test` is needed only for the
JavaScript tests. Run these commands from `personal_assistant/`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r tools/requirements.txt
python -B tools/initialize.py --demo
python -B tools/library.py validate
python -B tools/serve_library.py --port 8767
```

On macOS/Linux, activate with `source .venv/bin/activate`. Open
http://127.0.0.1:8767/. If that port is already occupied, choose another, such as
`--port 8769`; leave the existing server alone. The server binds only to loopback.

For a fresh empty library, omit `--demo`. Initialization refuses to overwrite an
existing `library/` or `Hikari Research/` directory. It never imports personal data
or schedules work. The demo has two fictional projects, six checkpoints and three
fictional references; all evidence is visibly marked synthetic.

## Layout and ownership

| Path | Purpose | Publication policy |
| --- | --- | --- |
| `dashboard/` | Today / Life / Research / Literature UI | Reusable code |
| `tools/` | Validators, importer, maintenance, server, tests | Reusable code |
| `examples/` | Synthetic handoff, project, batch, paper and attention shapes | Safe examples |
| `library/projects/` | Local canonical research graph | Generated; Git-ignored |
| `library/papers/` | Stable paper IDs, origin metadata and note manifests | Generated; Git-ignored |
| `Hikari Research/Papers/` | Authoritative editable Markdown paper notes | Generated; Git-ignored |
| `Hikari Research/Attachments/` | Locally registered PDFs | Git-ignored |
| `library/inbox/` | Deliberately supplied native-app collection handoffs | Git-ignored |
| `library/maintenance/` | Immutable submissions/plans, state and journal | Git-ignored |
| `.local/attention/` | Email-derived snapshots and durable user decisions | Git-ignored |

Research JSON uses stable identities, evidence references and an acyclic graph
with multiple parents. Every checkpoint includes **Goal / Done and learned /
Next**. Historical next steps remain part of history. Code implementation,
reported execution, inspected artifacts and scientific qualification are separate
evidence states. A proposed branch is not a completed experiment.

Paper summaries and reading notes live in one Markdown note per paper. The
dashboard reads those notes; it does not write a second editable copy. DOI/origin
identity deduplication and backlinks allow one paper to support several nodes.
PDF registration does not mark a paper read. Obsidian is optional; no application
or community plugin is installed. Only known `obsidian://open` note links are
generated, with no URI write actions.

Attention snapshots are **not live monitoring**. The local controls persist
handled, snoozed and irrelevant decisions across source refreshes. Gmail links
use account-aware `rfc822msgid:` searches when a verified Message-ID is supplied;
API message/thread IDs are not browser permalinks. Missing metadata has an explicit
date-search or unavailable fallback. A signed-in browser is required to verify
the actual message destination. The dashboard never sends or modifies email.

## Updates and verification

See [the data model](docs/data-model.md), [maintenance](docs/maintenance.md),
[attention inputs](docs/attention.md), and [the manager guide](docs/manager.md).

```powershell
python -B tools/maintenance.py validate-batch library/inbox/codex-desktop/BATCH.json
python -B tools/maintenance.py ingest --date 2026-01-01
python -B tools/maintenance.py status
python -B tools/maintenance.py apply-plan library/maintenance/plans/PLAN.json
python -B tools/library.py validate
python -B -m unittest discover -s tools -p "test_*.py"
node --test tools/test_literature.js tools/test_attention.js
node --check dashboard/app.js
```

Replace example filenames and date with the intended local review inputs. Tests
generate isolated synthetic fixtures; they do not copy the user's active library
or call a mailbox, research solver or agent. The HTTP tests use temporary loopback
servers and may require the execution environment to allow local socket access.

Native-app collection and scheduling are **separate setup steps**. Supported
conversation interfaces must be available and authorized in the executing client.
Otherwise use deliberately generated handoffs or approved exports. Never scan
protected session directories, raw transcript databases or credentials. Schedule
times, personal timezone, scope and permissions must be confirmed in the actual
app; schedules do not transfer with this repository. A local app may need to be
running and the host awake, and manual permission prompts can stop unattended
work. Partial listing/reading, missing inputs and conflicts remain visible.

## Privacy and deployment

Keep generated data ignored. Back it up separately in a destination appropriate
for its sensitivity; this code repository is not a personal-data backup. Do not
force-add local folders or copy raw chat histories, large research artifacts,
email bodies, credentials or account configuration into examples. The server
exposes only allowlisted assets and projections, with origin checks and an
ephemeral token for local decision writes. There is no public hosting or cloud
sync configuration. Public deployment would require a separate access/privacy
design and authorization.

## Related meeting assistant

The sibling [Hikari package](../hikari/README.md) contains the Zoom/project meeting
agent. It can contribute deliberately prepared handoffs to this library; it does
not contain a second dashboard or automatically ingest meeting transcripts.
See [source and migration notes](../hikari/SOURCE.md) for the additive consolidation.
