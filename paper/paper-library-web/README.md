# Paper Library Web

This plugin exposes the existing private, Obsidian-compatible paper library to
ChatGPT and Codex through a focused MCP server. The vault stays on the user's
machine; OpenAI Secure MCP Tunnel can provide outbound-only access for ChatGPT
developer-mode testing without opening an inbound port.

## Local prerequisites

- Python 3.11 or newer.
- `mcp>=1.9,<2` (`python -m pip install -r requirements.txt`).
- The sibling `../paper-library/scripts/paper_library.py` engine.
- `PAPER_LIBRARY_CONFIG` pointing to `.paper-library.json` or the legacy
  `.paper-obsidian.json`. The established `E:\paper` configuration is detected
  automatically on this machine.

## Test

```powershell
python -m unittest discover -s .\tests -v
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\skills\paper-library-web
python "$env:USERPROFILE\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" .
```

## Run locally

Codex can launch the stdio server through `.mcp.json`. For direct HTTP testing:

```powershell
$env:PAPER_LIBRARY_CONFIG = "E:\paper\.paper-obsidian.json"
$env:PAPER_LIBRARY_MCP_TRANSPORT = "streamable-http"
python .\server\paper_library_mcp.py
```

The Streamable HTTP endpoint is `http://127.0.0.1:8000/mcp`.

## Connect ChatGPT on the web

The private-vault route uses OpenAI Secure MCP Tunnel:

1. Create a tunnel in Platform tunnel settings and associate it with the target
   ChatGPT workspace.
2. Download `tunnel-client` from that settings page and keep the runtime API key
   outside this repository.
3. Initialize a named stdio profile whose MCP command runs
   `server/paper_library_mcp.py`, then run `tunnel-client doctor` and
   `tunnel-client run`.
4. In ChatGPT developer mode, create a plugin using **Tunnel** as the connection
   and select the tunnel ID. Install it, start a new Work chat, and invoke it
   with `@paper-library-web`.

The tunnel client and this MCP server must remain running while the web plugin
uses the private vault. Public distribution instead requires a stable public
HTTPS MCP endpoint plus appropriate user authentication.
