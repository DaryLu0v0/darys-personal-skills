# Hikari research-library manager

The canonical manager workflow is now
[personal_assistant/docs/manager.md](../../personal_assistant/docs/manager.md).
Read it together with the [data model](../../personal_assistant/docs/data-model.md)
and [maintenance guide](../../personal_assistant/docs/maintenance.md).

The library and dashboard have one implementation in `personal_assistant/`.
Keep stable project/checkpoint identities, Goal / Done and learned / Next, source
provenance and original handoffs. Distinguish user decisions, assistant proposals,
reported execution and checked evidence. Preserve partial coverage and conflicts.

A meeting can produce a deliberate handoff; this does not authorize automatic
ingestion of raw transcripts, unrelated personal chats or credentials. Native app
access and any schedules are configured separately with the user. Private research
records and runtime state remain local and ignored.
