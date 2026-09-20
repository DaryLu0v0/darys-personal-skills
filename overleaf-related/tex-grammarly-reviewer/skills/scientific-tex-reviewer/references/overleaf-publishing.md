# Native Overleaf publication

Use this workflow only when the user wants findings posted as Overleaf Review-panel threads and provides or opens the target project.

## Preconditions

1. Generate `overleaf-comments.json` and review `review-panel.md`.
2. Run `scripts/validate_manifest.py` against the exact local `.tex` file.
3. Read the manifest's role counts, severities, warnings, source filename, and SHA-256.
4. Open the user-specified Overleaf project with computer control. If Overleaf requires login, ask the user to take over and sign in; never automate authentication or a password manager.
5. Open the matching source file in the Code Editor. Do not upload, replace, or edit manuscript files unless separately requested.

## Preflight

Verify that the Overleaf source matches the manifest before any comment is posted. Prefer an exact source export or another deterministic comparison. If only the UI is available, locate every exact anchor and ensure each is unique; this is weaker than a full hash check and must be disclosed.

Present the exact batch to the user: project, source file, total threads, counts by reviewer and severity, and any warnings. Obtain confirmation immediately before clicking the first **Comment** submission button. Confirmation covers only that fixed batch; regenerate the preflight if anything changes.

## Publish loop

For each confirmed manifest item:

1. Reobserve the Overleaf window and active file.
2. Locate the exact `anchor_text`; stop if missing or ambiguous.
3. Select precisely that source span.
4. Choose **Add comment** and verify the Review panel is attached to the intended selection.
5. Enter the exact `overleaf_comment` body.
6. Submit the comment and verify the new thread is visible on the intended anchor.
7. Append a receipt entry containing manifest comment ID, reviewer ID, anchor hash, observed file, timestamp, and outcome.

Reobserve after every UI mutation. Never reuse stale coordinates or element indexes. Stop rather than guessing if the editor layout, file, selection, or comment state is uncertain.

## Identity and mutations

Overleaf attributes every thread to the signed-in account. Role prefixes distinguish `[AI-pattern reviewer]`, `[Grammar and clarity reviewer]`, `[Scientific concept reviewer]`, and `[ICLR overview reviewer]`; they are not separate human identities.

Do not resolve, delete, reply to, or edit existing comments unless the user explicitly requests that separate action. Do not switch collaborators or sharing permissions. Never attempt multiple-account impersonation.

## Receipt

Write a separate `overleaf-publication-receipt.json`; do not modify the review manifest. Include completed, skipped, failed, and unattempted comment IDs. A partial run is not complete and should be reported as partial.
