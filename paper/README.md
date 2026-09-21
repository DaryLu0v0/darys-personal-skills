# Paper skills

## Paper Library

[`paper-library/`](paper-library/) is a self-contained Codex skill for building a
durable personal literature library. It stores paper files and structured
reading notes in an Obsidian-compatible vault, prevents common duplicates,
keeps a controlled label taxonomy, and supplies deterministic search and corpus
exports for later field reviews and brainstorming.

The helper is Python-standard-library only. It can reuse the earlier
`.paper-obsidian.json` configuration, while new installations use
`.paper-library.json`.

Validate it from the repository root:

```powershell
python -m unittest discover -s .\paper\paper-library\tests -v
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\paper\paper-library
```
