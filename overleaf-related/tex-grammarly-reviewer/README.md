# TeX Grammarly Reviewer

A conservative, comment-first reviewer for English prose inside a single `.tex` file. It:

1. extracts reviewable prose without executing LaTeX or following `\input` files;
2. obtains Grammarly's official writing-quality scores and contextual AI estimate;
3. lets a humanization reviewer interpret Grammarly measurements and validated UI observations;
4. generates anchored humanization, grammar, concept, citation/evidence, and scientific-overview comments without editing the source;
5. validates every proposed Overleaf comment against the exact source and its SHA-256.

An optional bounded copyedit mode can propose replacements, but the default outputs remain comments. Grammarly's AI estimate is reported rather than optimized.

The default output is a `.review-comments.tex` file. It contains the original LaTeX unchanged plus `% TEX-REVIEW ...` comments with proposed replacements and explanations. Applying edits requires the explicit `--apply` option. Every candidate, accepted revision, score, and stop reason is saved under `.tex-reviewer/` beside the input file.

## What “Grammarly issues” means

Grammarly's official Writing Score API returns category scores, not the individual suggestion cards shown in Grammarly's editor. This tool defines:

```text
issue_level = 1 - correctness_score
```

Thus, lowering `issue_level` means raising Grammarly's correctness score. The tool reports the other writing scores as well. Grammarly's API supplies aggregate measurements, not passage-level explanations. Explanations in the comment report are explicitly labeled as reviewer inference. When an already signed-in Grammarly document is available, the companion Codex skill can supervise a read-only pass over Grammarly's UI-only strong/moderate/weak pattern highlights and explanations. Those observations remain distinct from reviewer inference and can be supplied to the humanization reviewer. The tool never treats an AI-detection percentage as proof, an acceptance gate, or a revision target.

## Scientific-writing preference

`scientific` is the default editor preference. It favors:

- precise, falsifiable statements and calibrated uncertainty;
- concise logical transitions and consistent technical terminology;
- appropriate passive voice when the actor is unimportant;
- preservation of qualified claims and the author's scientific interpretation;
- avoidance of promotional language, unnecessary intensifiers, and stock academic phrases.

Use `--preference general` for ordinary formal prose, or add an author-controlled requirement with `--style-note`, for example `--style-note "Use IEEE terminology and retain first-person plural."`

## Requirements

- Python 3.11 or newer.
- Grammarly Enterprise or Grammarly for Education organization-admin OAuth credentials with Writing Score and AI Detection access.
- An OpenAI API key for automatic editing. The model is configurable; the default is `gpt-6-astra`.

Documents are transmitted to Grammarly for scoring and to OpenAI for revision. Do not use this tool with confidential material unless your organization's policies permit both services.

## Install

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
```

Set credentials in the current shell (do not put secrets in the repository):

```powershell
$env:GRAMMARLY_CLIENT_ID = "..."
$env:GRAMMARLY_CLIENT_SECRET = "..."
$env:OPENAI_API_KEY = "..."
```

## Use

Score only:

```powershell
tex-review score .\paper.tex
```

Generate the multi-reviewer panel without changing the manuscript or publishing anything:

```powershell
tex-review panel .\paper.tex
```

The default panel contains:

- `humanize`: natural scientific voice, specificity, and flow informed by Grammarly measurements and validated observations;
- `grammar`: minimal grammar and scientific-clarity corrections;
- `concept`: assumptions, units, claim/evidence alignment, methods, controls, and reproducibility;
- `citation`: citation coverage, placement, integrity, and source support without invented references;
- `overview`: a venue-agnostic author pre-review covering motivation, novelty, evidence, rigor, significance, limitations, clarity, and reproducibility.

The command creates `overleaf-comments.json` and `review-panel.md` inside a timestamped audit directory. Each proposed thread is bound to an exact unique source substring and the complete source SHA-256. It is marked `not-published` until a supervised Overleaf publisher verifies and posts it.

Select roles or cap comment volume:

```powershell
tex-review panel .\paper.tex `
  --reviewers humanize grammar concept citation overview `
  --max-comments-per-reviewer 8
```

The overview remains general unless current official venue criteria are supplied:

```powershell
tex-review panel .\paper.tex `
  --venue "Target Venue and Year" `
  --venue-guidance .\official-review-guide.txt
```

This keeps ICLR, NeurIPS, AAAI, IEEE, ACM, and journal requirements as optional profiles rather than hard-coded defaults.

Use passage-level feedback copied during a supervised Grammarly UI pass:

```powershell
tex-review panel .\paper.tex `
  --reviewers humanize `
  --grammarly-observations .\grammarly-observations.json
```

The observation file is a JSON list, or an object with an `observations` list. Each item contains an exact unique `anchor_text`, `category`, displayed `explanation`, and optional `pattern_class`. The object can also record `document_title` and `observed_at`. Grammarly observations are preserved separately from the reviewer's inference.

Request bounded copyedit suggestions with the conservative defaults (scientific preference, comment-only output, at most five candidates, and stop after two consecutive rejections):

```powershell
tex-review review .\paper.tex
```

This creates `paper.review-comments.tex`. Suggested replacement lines are comments, so compiling it still compiles the original prose.

Set thresholds and output explicitly:

```powershell
tex-review review .\paper.tex `
  --output .\paper.review-comments.tex `
  --preference scientific `
  --target-issue-level 0.05 `
  --max-attempts 5 `
  --patience 2
```

Apply the accepted candidate only when desired:

```powershell
tex-review review .\paper.tex --apply --output .\paper.reviewed.tex
```

Use `--apply --in-place` only when you intentionally want to overwrite the input. A pre-overwrite backup is saved in that run's audit directory. `--in-place` is rejected in comment mode.

## Acceptance and stopping rules

A candidate must preserve the preamble, braces, ordered environment inventory, citations, references, labels, URLs, includes, image paths, mathematical content, and numeric tokens. It is accepted only if:

- Grammarly's correctness deficit improves; and
- all LaTeX safety checks pass.

The AI percentage remains in the audit record for context but never controls acceptance. The run stops when the correctness target is met, the attempt limit is reached, or `--patience` consecutive candidates are rejected. `--tolerance` can accommodate small score variance, but the safest default is zero.

## Current scope

- Reviews one UTF-8 `.tex` file at a time.
- Does not execute TeX, compile the document, or recursively read `\input`/`\include` files.
- Protects structural tokens, but a final human review and normal LaTeX compilation remain required.
- The CLI does not automate Grammarly's website or browser extension. The companion Codex skill can inspect an already open Grammarly editor under user supervision, without accepting rewrites or changing the document.
- Cannot retrieve Grammarly's UI-only highlighted passages or AI Rewriter suggestions through the public score APIs.
- Native Overleaf publishing is deliberately a supervised browser step because Overleaf does not expose a documented public bulk-comment API. See [the native review-panel design](docs/OVERLEAF_REVIEW_PANEL.md).
- Native comments are authored by the signed-in Overleaf account. Reviewer roles are visible labels, not impersonated user identities.

## Test

```powershell
python -m pytest -q
```
