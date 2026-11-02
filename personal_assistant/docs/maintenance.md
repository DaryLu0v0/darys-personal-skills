# Incremental conversation maintenance

This repository does not create a scheduler or read a chat client by itself.
Use authorized native Claude Code / Codex app tools when available, or an approved
handoff/export. Client capabilities and permissions vary. Never read protected
raw session stores, transcript databases or credentials, or bypass a denial.

Collect only the project scope approved by the owner. Exclude unrelated personal
chats and unnecessary sensitive content. Use stable source identities and actual
returned pagination cursors. Preserve user decisions separately from assistant
proposals, code evidence and reported/independently checked experiments.

## Collection

`examples/conversation-batch.json` illustrates the schema. Put real batches in
`library/inbox/codex-desktop/` or `library/inbox/claude-desktop/`. Inventory entries
retain provider-scoped project keys and observed working directories. Sessions
record source revision/update time, read status, actual returned message refs,
next cursor and gaps. Events are concise, selected provenance, not full chat logs.

Use `listed` or `unavailable` with no read-message claims for unread sessions.
`window_complete` means a specified window, not all historical conversations.
Record caps and truncated outputs. Do not advance unread watermarks or treat
missing messages as no activity. Rotate bounded reads between projects.

```powershell
python -B tools/maintenance.py validate-batch library/inbox/codex-desktop/BATCH.json
python -B tools/maintenance.py ingest --date YYYY-MM-DD
python -B tools/maintenance.py status
```

Ingestion archives exact submission bytes and deduplicates provider/session/message
identity. One atomic state document contains inventory, observations, conflicts,
plan receipts and an append-only journal. A missing Claude batch stays pending
instead of silently being treated as an empty day.

## Reconciliation

Create a reviewed plan under `library/maintenance/plans/` with `schema_version`,
stable `id`, `kind`, `reviewed_at`, `reviewed_by`, `review_note`, `submission_ids`
and `source_refs`. Kinds:

- `create_project`: validated new project, revision zero and no update receipts.
- `map_project`: one provider inventory key to a confirmed canonical project.
- `handoff`: append-only update plus the expected target-file digest.
- `defer`: explicit uncertainty, pending input or unresolved conflict.

Creation/mapping can cite checked document `identity_evidence` tied to an existing
inventory key and its original submission. This does not let documents bypass
the source-message requirements for scientific handoff updates. A workspace with
several repositories should remain pending until messages can be attributed
correctly. Never overwrite an existing conflicting mapping.

```powershell
python -B tools/maintenance.py apply-plan library/maintenance/plans/PLAN.json
python -B tools/library.py validate
```

Plans are archived before application. Repeating the same plan makes no duplicate
writes. Changed payloads need a new reviewed plan; stale/identity conflicts remain
pending. A crash after a canonical write but before its maintenance receipt is
recoverable by replay. A lock requires checking for an active writer, not automatic
deletion. Paper-note edits are a separate reviewed workflow, not a side effect of
conversation ingestion.

## Optional scheduling

Before creating native tasks, confirm exact daily times, the owner's IANA timezone,
source scope, destination paths and current app authorization. Verify a bounded
manual run and its receipt first. A two-stage design can collect Claude handoffs
before a later Codex/Hikari reconciliation, but no times or tasks are shipped here.
Local tasks can require the app running and the host awake; manual permission
prompts can pause them. Verify the saved schedule and next execution in the actual
app. Success means checked run receipts and reconciled outputs, not merely an
enabled task. No unattended completeness guarantee is made.
