# Reviewer panel

## Default roles

| ID | Focus | Important boundary |
|---|---|---|
| `humanize` | Natural scientific voice, specificity, flow, and formulaic phrasing informed by Grammarly measurements and validated UI observations | Comment only; never treat an AI estimate as proof or optimize for detector evasion |
| `grammar` | Grammar, punctuation, terminology consistency, antecedents, and local scientific clarity | Prefer minimal edits; retain appropriate passive voice and technical meaning |
| `concept` | Definitions, assumptions, units, claim/evidence alignment, controls, uncertainty, methods, and reproducibility | Use manuscript evidence only; phrase uncertain points as author questions |
| `citation` | Claim-to-citation coverage, citation placement, bibliographic integrity, and source support | Never invent sources; specific additions require independent verification |
| `overview` | Venue-agnostic assessment of motivation, novelty, evidence, rigor, significance, limitations, clarity, and reproducibility | Apply venue criteria only from a supplied current profile; never issue an authoritative accept/reject decision |

The default overview is deliberately venue-agnostic. ICLR, NeurIPS, AAAI, IEEE, ACM, Nature Portfolio, Elsevier journals, and other venues are optional profiles, not separate core reviewers.

## Commands

All roles:

```powershell
tex-review panel .\paper.tex
```

Selected roles and bounded volume:

```powershell
tex-review panel .\paper.tex `
  --reviewers humanize grammar concept citation overview `
  --max-comments-per-reviewer 8
```

Apply a venue-specific rubric only from current official guidance:

```powershell
tex-review panel .\paper.tex `
  --venue "Target Venue and Year" `
  --venue-guidance .\official-review-guide.txt
```

When a supervised Grammarly UI pass produced passage-level observations, provide them to the humanization reviewer:

```powershell
tex-review panel .\paper.tex `
  --reviewers humanize `
  --grammarly-observations .\grammarly-observations.json
```

The JSON can be a list or an object with an `observations` list. Each observation needs an exact unique `anchor_text`, a `category`, Grammarly's displayed `explanation`, and an optional `pattern_class`. The object may also record `document_title` and `observed_at`. Invalid or ambiguous anchors stop the run.

The command creates `overleaf-comments.json` and `review-panel.md` in a timestamped audit directory. It does not contact Overleaf.

## Manifest contract

Each publishable finding must contain:

- a reviewer ID and visible label;
- an exact, unique, contiguous source substring;
- source offsets and one-based line/column coordinates;
- category, severity, comment body, rationale, and suggested action;
- confidence and an explicit author-check flag;
- a role-prefixed `overleaf_comment` body.

The manifest also records validated Grammarly UI observations, including available document title and observation time, separately from reviewer inference.

The manifest is bound to the complete UTF-8 source SHA-256. Reject missing and nonunique anchors. Do not repair invalid anchors by fuzzy matching because the comment could attach to the wrong scientific claim.

## Interpretation

Reviewers are deliberately independent and can comment on the same passage for different reasons. The humanization reviewer reads Grammarly evidence but does not attempt to lower its AI estimate. The citation reviewer may flag missing support without naming a paper; specific sources require the separate verified citation workflow. Do not collapse comments from different roles merely because their anchors overlap. Deduplicate only identical findings from the same role.

The panel is advisory. Summarize accepted/rejected anchor counts and validation warnings. Never convert its output into a claim of scientific correctness or publication eligibility.
