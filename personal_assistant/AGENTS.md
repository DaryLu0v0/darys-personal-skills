# Working on this package

Preserve human edits and follow the owner's scope. Read README.md and
docs/manager.md before modifying data workflows. Test using generated synthetic
fixtures; never use active personal records as test inputs.

`library/`, `Hikari Research/` and `.local/` are local user data and intentionally
ignored. Do not force-add them or copy their contents into tracked examples.
Do not read raw protected session stores or credentials. Use authorized native
app tools or approved handoffs; retain incomplete coverage and conflicts.

Run the Python suite and JavaScript tests described in README.md for relevant code
changes. Do not start research experiments or change app permissions/schedules as
part of routine tests. Verify loopback-only serving and strict source-link handling.

No schedules, integrations or user authorizations are installed by this package.
