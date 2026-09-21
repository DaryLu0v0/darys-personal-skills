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

## Paper Library Web

[`paper-library-web/`](paper-library-web/) packages the workflow as a ChatGPT
and Codex plugin. Its MCP server exposes bounded search, retrieval, save, update,
context-export, and index tools while keeping the configured vault private. It
supports local Codex stdio use and ChatGPT web access through OpenAI Secure MCP
Tunnel.

Validate it from the repository root:

```powershell
python -m unittest discover -s .\paper\paper-library\tests -v
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\paper\paper-library
```
