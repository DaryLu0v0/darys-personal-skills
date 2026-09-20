# Overleaf native review-panel design

## Goal

Publish AI-assisted scientific-review findings as native Overleaf threads attached to exact selected source spans, matching the Review-panel interaction rather than adding `%` comments to a `.tex` file.

## Stable boundary

`tex-review panel paper.tex` generates two artifacts without touching Overleaf:

- `overleaf-comments.json`: a machine-readable, source-hash-bound publication manifest;
- `review-panel.md`: a human-readable preflight review.

Every publishable comment contains the source filename, exact anchor text, character offsets, line and column coordinates, role, severity, rationale, suggested action, confidence, and whether author verification is required. Nonexistent or ambiguous anchors are rejected before publication.

## Reviewer roles

| Role | Primary focus |
|---|---|
| Humanization reviewer | Grammarly-informed natural scientific voice, specificity, flow, and formulaic phrasing; comments only and never detector evasion |
| Grammar and clarity reviewer | Minimal grammar, punctuation, terminology, and sentence-level clarity corrections |
| Scientific concept reviewer | Definitions, assumptions, units, claim/evidence alignment, methods, controls, uncertainty, and reproducibility |
| ICLR overview reviewer | Problem, motivation, literature placement, claim support, rigor, significance, clarity, and reproducibility using the ICLR 2027 reviewer guide |

Roles are independent prompts and remain visibly prefixed in every Overleaf comment. Their findings may overlap intentionally; the author decides which comments to resolve.

## Native publication workflow

Native Overleaf comments are not stored in `.tex` source and are not created through a documented public bulk-comment API. Publication therefore uses a supervised browser session:

1. Generate and inspect the manifest.
2. Open the matching Overleaf project and source file while signed in.
3. Verify that the current source SHA-256 matches the manifest.
4. For each approved item, select the exact anchor in the Code Editor.
5. Choose **Add comment**, insert the role-prefixed `overleaf_comment`, and submit it.
6. Record the published thread outcome in a separate receipt; never mutate the review manifest.

Posting comments represents the user to collaborators. The publisher must show a final preflight and obtain confirmation immediately before submission. It must stop on any source-hash mismatch, missing anchor, ambiguous anchor, authentication prompt, or changed Overleaf layout.

## Reviewer identity limitation

Overleaf attributes a native comment to the account currently signed in. A single logged-in account cannot honestly appear as four different human authors. This design uses clear role labels—`[Humanization reviewer]`, `[Grammar and clarity reviewer]`, and so on—inside comments. Truly different author identities require separate named Overleaf collaborators and deliberate account ownership; the tool does not create or impersonate those accounts.
