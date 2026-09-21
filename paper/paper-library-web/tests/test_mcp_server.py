from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server" / "paper_library_mcp.py"


class PaperLibraryMcpTests(unittest.TestCase):
    def test_stdio_tools_end_to_end(self) -> None:
        asyncio.run(self._exercise_stdio_server())

    async def _exercise_stdio_server(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "Vault"
            vault.mkdir()
            config = root / ".paper-library.json"
            config.write_text(
                json.dumps(
                    {
                        "vault_path": str(vault),
                        "notes_folder": "Literature/Papers",
                        "attachments_folder": "Literature/PDFs",
                        "index_note": "Literature/Paper Library.md",
                    }
                ),
                encoding="utf-8",
            )
            env = dict(os.environ)
            env["PAPER_LIBRARY_CONFIG"] = str(config)
            params = StdioServerParameters(
                command=sys.executable,
                args=[str(SERVER)],
                cwd=str(ROOT),
                env=env,
                encoding="utf-8",
                encoding_error_handler="replace",
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    names = {tool.name for tool in tools.tools}
                    self.assertEqual(
                        names,
                        {
                            "library_status",
                            "search_papers",
                            "get_paper",
                            "add_paper",
                            "update_paper",
                            "export_context",
                            "rebuild_index",
                        },
                    )
                    added = await session.call_tool(
                        "add_paper",
                        {
                            "title": "A Web Paper",
                            "doi": "10.1000/web",
                            "source_url": "https://doi.org/10.1000/web",
                            "status": "reading",
                            "fields": ["Electromagnetics"],
                            "topics": ["Metasurface"],
                            "reading_notes": "# A Web Paper\n\n## Summary\n\nCoupling matters.\n",
                        },
                    )
                    self.assertFalse(added.isError)
                    self.assertEqual(added.structuredContent["paper_id"], "doi:10.1000/web")
                    found = await session.call_tool("search_papers", {"query": "coupling"})
                    self.assertFalse(found.isError)
                    self.assertEqual(found.structuredContent["count"], 1)
                    fetched = await session.call_tool("get_paper", {"identifier": "10.1000/web"})
                    self.assertIn("Coupling matters", fetched.structuredContent["note_markdown"])
                    updated = await session.call_tool(
                        "update_paper",
                        {
                            "identifier": "10.1000/web",
                            "status": "read",
                            "reading_log": "Completed discussion with the user.",
                        },
                    )
                    self.assertEqual(updated.structuredContent["status"], "read")
                    context = await session.call_tool(
                        "export_context",
                        {"field": "electromagnetics", "limit": 10},
                    )
                    self.assertEqual(context.structuredContent["count"], 1)
                    indexed = await session.call_tool("rebuild_index", {})
                    self.assertFalse(indexed.isError)
                    self.assertTrue((vault / "Literature" / "Paper Library.md").exists())
                    status = await session.call_tool("library_status", {})
                    self.assertTrue(status.structuredContent["healthy"])
                    self.assertEqual(status.structuredContent["papers"], 1)


if __name__ == "__main__":
    unittest.main()
