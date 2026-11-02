# Records and updates

Run initialization before using the tools. Local data is ignored by Git; the
schemas are enforced by `tools/library.py`, `tools/maintenance.py` and
`tools/attention.py`. `examples/` contains fictional inputs, not a user archive.

## Research graph

A project contains `schema_version: 1`, stable `id`, `title`, `summary`, `coverage`,
`revision`, `sources`, `evidence`, `checkpoints`, `relationships` and
`applied_updates`. Sources record confirmed/candidate mapping, HTTPS repository,
branch/revision, role, check date and mapping rationale. Never infer a repository
from a folder label alone. A mixed workspace may contain several projects.

Each checkpoint records `goal`, `done[]`, `next[]`, `status`, `status_note`,
`evidence_ids`, `recorded_at`, optional `occurred_at`, and optional `papers[]`.
Claims carry text, evidence IDs and an explicit basis. States are `completed`,
`active`, `possible`, `parked`, `closed` and `superseded`. Progression edges have
`from`, `to`, `kind: progression` and a rationale; cycles and missing endpoints
are rejected. Paper and source references are not progression edges.

Evidence is code, document, experiment or conversation material, with an access
state, summary, check date and source location. A native conversation citation
retains provider, thread and actual message reference, speaker, selected excerpt,
retrieval limits and observed-position status where no message ID exists. Use
null for unknown original times. Never invent native IDs or public chat URLs.
Reading a worker's report does not independently verify the reported result.

## Append-only handoffs

`examples/handoff.json` shows a complete synthetic update. Required fields include
update/project IDs, base revision, source revision key, goal, completed scope,
findings, uncertainties, verification, next actions, dates, source revisions and
the proposed evidence/checkpoints/edges. Review the target bytes before applying:

```powershell
python -B tools/library.py digest library/projects/PROJECT.json
python -B tools/library.py apply library/handoffs/UPDATE.json --expected SHA256_FROM_REVIEW
```

For conversation maintenance, prefer a reviewed `handoff` plan so source-message
and project-mapping checks also run. Duplicate update IDs, source revision keys,
stale revisions and concurrent human edits are checked. Writes use a lock and an
atomic replacement; failed validation does not partially replace the project.
Preserve rejected inputs and write a newly identified reconciled update. Do not
reset revisions, erase historical Next entries or blindly remove active locks.

## Literature

`library/papers/ID.json` retains stable identity/origins and points to
`Hikari Research/Papers/ID.md`. The note owns title/authors/year/DOI, reading state,
general summary, reading notes and context-specific relevance. Use
`library/paper-links.json` or checkpoint paper references for graph relationships.
Do not create one duplicate paper per checkpoint. The generated dashboard
projection is read-only. Migration preserves original JSON in a local recovery
snapshot and refuses an existing destination vault.

Only register PDFs that actually exist and whose identity has been checked.
`python -B tools/obsidian_vault.py attach-pdf --paper PAPER_ID` copies an already
indexed local PDF; it does not download or read it. Notes, PDFs, manifests and
recovery snapshots remain local and ignored by this package.
