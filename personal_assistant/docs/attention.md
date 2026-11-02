# Private attention snapshots

The dashboard reads deliberately supplied local snapshots. It has no Gmail API
credentials and never sends, labels, archives or deletes messages. Check the
actual source account through an authorized connector before preparing an input.

Copy the synthetic shape in `examples/attention-snapshot.json` into an ignored
`.local/` input and replace it with reviewed, minimal evidence. Do not put real
data back into `examples/`. Include a unique snapshot ID, content check time,
coverage/limitations, account labels, stable item IDs and minimal source links.
Do not store full mail bodies, credentials, balances, private identifiers or
unnecessary personal details. A source assertion is not proof that an action is
still outstanding. Preserve unknown roles, timezones, ownership and current state.

```powershell
python -B tools/attention.py .local/attention-input.json
```

Records and exact input snapshots remain in `.local/attention/`; user decisions
are stored separately with optimistic revision checks. Reimporting a snapshot is
idempotent and refreshing sources does not reset handled/snoozed/irrelevant choices.
An omitted item does not erase its earlier decision. Changing an existing account
identity requires explicit reconciliation instead of silent reassignment.

For Gmail, retain the verified account email and `source.rfc822_message_id`
(the actual RFC822 Message-ID header), separately from optional API message/thread
IDs. `message_id_checked_at` records that identity check without pretending the
item's current task state was freshly verified. The UI URL-encodes the whole
`in:anywhere rfc822msgid:` query, including `+` and `=`. This is an exact-message
search, not a direct-permalink guarantee; a conversation or results list may
appear. Gmail must be signed into the selected account. A copyable query supports
manual search after sign-in. See [Gmail search operators](https://support.google.com/mail/answer/7190).

Missing Message-ID gets an explicitly labeled date search; missing account/date
gets an unavailable state. API hex IDs are never used as web permalinks. All link
tests use synthetic addresses and identifiers.
