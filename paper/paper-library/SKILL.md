---
name: paper-library
description: Build and use a durable personal library of academic papers from links or local files. Use when saving an interesting paper, reading a paper with the user, finding or revisiting prior papers, auditing labels, reviewing a field from the saved corpus, or brainstorming from the user's literature. Do not use for editing the user's own manuscript.
---

# Paper Library

Maintain one evidence-linked note per paper and make the saved corpus useful in
later conversations. The deterministic helper is
[`scripts/paper_library.py`](scripts/paper_library.py); it works without the
Obsidian CLI or third-party Python packages.

## Locate the library

Prefer an explicit `--config` path. Otherwise the helper checks
`PAPER_LIBRARY_CONFIG`, then searches the current directory and its parents for
`.paper-library.json` or the legacy `.paper-obsidian.json`.

If no configuration exists, initialize one only after the user has selected a
vault directory:

```powershell
python <skill-dir>\scripts\paper_library.py init --vault "E:\paper_vault"
```

Configuration and vault locations are machine-local. Do not commit a populated
configuration, PDFs, or reading notes into the skill repository.

For a vault created by the earlier paper-Obsidian bridge, preview the metadata
upgrade with `migrate`, then use `migrate --apply` after reviewing the reported
conflicts. Migration preserves note bodies and filenames.

## Save or read a paper

1. Resolve the supplied source. For a local PDF, inspect the PDF. For a link,
   open the linked paper or landing page and retain its canonical URL. If the
   source cannot be read, save only known metadata and explain that no reading
   summary was produced.
2. Extract stable metadata from the source itself: exact title, author list,
   year, venue, DOI or arXiv identifier, and URL. Never invent missing metadata.
3. Choose labels using [the library schema](references/library-schema.md).
   Fields are broad disciplines, topics are paper-specific subjects, and
   methods name techniques actually used in the paper.
4. Run `add`. The helper de-duplicates by stable ID, DOI, canonical URL, and as
   a fallback normalized title plus year. An existing result means update that
   note; do not create a second note.
5. When reading with the user, write source-grounded notes under the generated
   headings. Record page, section, figure, or table locations for important
   claims. Separate the paper's claims from the user's interpretation and from
   new ideas.
6. Set `status: read` only after a substantive read. Use `reading` for an
   in-progress discussion and `interested` or `to-read` when merely saving it.
   Refresh the index after changes.

Typical commands:

```powershell
python <skill-dir>\scripts\paper_library.py add "C:\papers\paper.pdf" --title "Exact title" --author "First Author" --year 2026 --field electromagnetics --topic metasurface
python <skill-dir>\scripts\paper_library.py add "https://doi.org/10.xxxx/example" --title "Exact title" --doi "10.xxxx/example" --status interested
python <skill-dir>\scripts\paper_library.py update "10.xxxx/example" --status reading --reading-log "Discussed the experimental controls with the user."
python <skill-dir>\scripts\paper_library.py index
```

Use `update --reading-notes <markdown-file>` when replacing the note body with
a completed structured reading note. The file must not contain YAML
frontmatter; the helper preserves the paper's identity and library metadata.

## Retrieve papers

Search before answering from memory:

```powershell
python <skill-dir>\scripts\paper_library.py find "nonlocal metasurface" --field electromagnetics
python <skill-dir>\scripts\paper_library.py labels
python <skill-dir>\scripts\paper_library.py context --topic inverse-design --output corpus.json
```

`find` returns ranked metadata and note paths. Read the most relevant notes and
their linked sources when claim-level accuracy matters. `context` produces a
bounded JSON bundle containing the selected notes for synthesis; do not treat
it as proof that the library covers the whole field.

## Field review and brainstorming

Begin with a coverage statement: active filters, number of matching papers, and
whether the answer uses only the saved library or also a fresh external search.
Organize a field review around consensus, disagreements, method families,
evidence quality, limitations, and missing areas. Cite saved notes by paper
title and DOI/URL, and include source locations where the note records them.

For brainstorming, label statements as one of:

- **Library-backed:** directly supported by one or more saved papers.
- **Synthesis:** a connection inferred across saved papers.
- **Hypothesis:** a new, unvalidated research idea.

Do not write a synthesis or brainstorm back into the library unless the user
asks. Never present a small or selectively collected personal library as an
exhaustive literature review.

## Maintenance

Run `doctor` after configuration or migration, `labels` when taxonomy begins to
drift, and `index` after imports or metadata updates. `doctor` reports duplicate
IDs and incomplete records but does not delete or merge anything.
