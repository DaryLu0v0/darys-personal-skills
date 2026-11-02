# Source and consolidation

This folder contains reusable meeting code from the Hikari repository at commit
`45b3a6628612326765eb6f015c2ac28f264833b4`, retrieved through the authorized GitHub
connection on 2026-11-02. Its tracked blobs were checked against Git blob hashes.

The sibling personal assistant package derives from the local research-library
development revision `662cf9f2a01f27e20e3bb0475a83884ad3c0a46d`. Its source data was
replaced by synthetic examples and isolated test fixtures. The meeting integration
uses its separately verified newer source, rather than the older meeting snapshot
in that dashboard development branch.

Publication adaptations:

- Separate the dashboard/library into `../personal_assistant/`; retain meeting code here.
- Replace personal filesystem paths, operator-specific prompts and domain examples
  with generic configuration/examples. Retain normal tool reviews and restrictions.
- Replace machine-specific setup receipts with prerequisites and verification limits.
- Keep the upstream plugin manifest and MIT license unchanged.
- Bind the dashboard's library HTTP projection to the configured root explicitly;
  its isolation test verifies that it cannot accidentally read the installed library.
- Preserve the original repository, live checkouts, private data and configured schedules.

The separate live meeting checkout could not be inspected because filesystem access
was denied. This copy makes no claim to include its possible uncommitted changes.
No history was rewritten or original repository removed. Future updates should
compare the appropriate component with its source and repeat the privacy audit.

Portable validation at consolidation is recorded in the root publication report.
Installed OpenClaw integration, meetings, audio, credentials and schedules require
separate host-specific verification.
