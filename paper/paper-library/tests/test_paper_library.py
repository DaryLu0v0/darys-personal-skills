from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "paper_library.py"
SPEC = importlib.util.spec_from_file_location("paper_library", SCRIPT)
paper_library = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["paper_library"] = paper_library
SPEC.loader.exec_module(paper_library)


class PaperLibraryTests(unittest.TestCase):
    def run_cli(self, *argv: str) -> int:
        return paper_library.main(list(argv))

    def make_library(self, root: Path) -> tuple[Path, Path]:
        vault = root / "Vault"
        vault.mkdir()
        config = root / ".paper-library.json"
        self.assertEqual(self.run_cli("--config", str(config), "init", "--vault", str(vault)), 0)
        return vault, config

    def test_stable_id_prefers_doi_and_normalizes_it(self) -> None:
        paper_id = paper_library.stable_paper_id(
            doi="https://doi.org/10.1000/Example.",
            url="https://example.org/paper",
            title="Different title",
            year="2026",
        )
        self.assertEqual(paper_id, "doi:10.1000/example")
        self.assertEqual(
            paper_library.doi_from_url("https://doi.org/10.1000/Example"),
            "10.1000/example",
        )

    def test_add_pdf_copies_file_and_prevents_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault, config = self.make_library(root)
            pdf = root / "source.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")
            base = (
                "--config",
                str(config),
                "add",
                str(pdf),
                "--title",
                "A Useful Paper",
                "--year",
                "2026",
                "--doi",
                "10.1000/useful",
                "--field",
                "Electromagnetics",
            )
            self.assertEqual(self.run_cli(*base), 0)
            self.assertEqual(self.run_cli(*base), 0)
            notes = list((vault / "Literature" / "Papers").glob("*.md"))
            self.assertEqual(len(notes), 1)
            self.assertTrue((vault / "Literature" / "PDFs" / "source.pdf").exists())
            metadata, body = paper_library.split_note(notes[0].read_text(encoding="utf-8"))
            self.assertEqual(metadata["paper_id"], "doi:10.1000/useful")
            self.assertEqual(metadata["fields"], ["electromagnetics"])
            self.assertIn("## Claims and Evidence", body)

    def test_find_labels_context_update_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault, config = self.make_library(root)
            self.assertEqual(
                self.run_cli(
                    "--config",
                    str(config),
                    "add",
                    "https://doi.org/10.1000/meta",
                    "--title",
                    "Nonlocal Metasurface Model",
                    "--doi",
                    "10.1000/meta",
                    "--status",
                    "to-read",
                    "--field",
                    "Electromagnetics",
                    "--topic",
                    "Nonlocal Metasurface",
                    "--method",
                    "Foldy Lax",
                ),
                0,
            )
            notes_body = root / "reading.md"
            notes_body.write_text(
                "# Nonlocal Metasurface Model\n\n## Summary\n\nCoupling matters.\n\n## Reading Log\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.run_cli(
                    "--config",
                    str(config),
                    "update",
                    "10.1000/meta",
                    "--status",
                    "read",
                    "--reading-notes",
                    str(notes_body),
                    "--reading-log",
                    "Completed evidence review.",
                ),
                0,
            )
            output = root / "context.json"
            self.assertEqual(
                self.run_cli(
                    "--config",
                    str(config),
                    "context",
                    "coupling",
                    "--field",
                    "electromagnetics",
                    "--output",
                    str(output),
                ),
                0,
            )
            bundle = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(bundle["count"], 1)
            self.assertIn("Coupling matters", bundle["papers"][0]["note_markdown"])
            self.assertEqual(self.run_cli("--config", str(config), "index"), 0)
            index = vault / "Literature" / "Paper Library.md"
            self.assertIn("Nonlocal Metasurface Model", index.read_text(encoding="utf-8"))

    def test_legacy_config_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "Vault"
            vault.mkdir()
            config = root / ".paper-obsidian.json"
            config.write_text(
                json.dumps(
                    {
                        "vault_path": str(vault),
                        "notes_folder": "Literature/Papers",
                        "attachments_folder": "Literature/PDFs",
                    }
                ),
                encoding="utf-8",
            )
            previous = Path.cwd()
            try:
                os_module = __import__("os")
                os_module.chdir(root)
                resolved = paper_library.resolve_config_path(None)
            finally:
                os_module.chdir(previous)
            self.assertEqual(resolved, config)
            loaded = paper_library.load_config(config)
            self.assertEqual(loaded["reviews_folder"], "Literature/Reviews")

            notes_dir = vault / "Literature" / "Papers"
            notes_dir.mkdir(parents=True)
            note = notes_dir / "legacy.md"
            note.write_text(
                "---\ntype: paper\ntitle: \"Legacy Paper\"\nyear: \"2025\"\n"
                "doi: \"10.1000/legacy\"\nstatus: to-read\nauthors: []\ntags:\n"
                "  - \"paper\"\nsource_pdf: \"C:/papers/legacy.pdf\"\n---\n\n"
                "# Legacy Paper\n\n## Summary\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.run_cli("--config", str(config), "migrate"),
                0,
            )
            before, _ = paper_library.split_note(note.read_text(encoding="utf-8"))
            self.assertNotIn("paper_id", before)
            self.assertEqual(
                self.run_cli("--config", str(config), "migrate", "--apply"),
                0,
            )
            after, body = paper_library.split_note(note.read_text(encoding="utf-8"))
            self.assertEqual(after["paper_id"], "doi:10.1000/legacy")
            self.assertEqual(after["schema_version"], 1)
            self.assertEqual(after["source_type"], "pdf")
            self.assertIn("## Summary", body)
            self.assertEqual(paper_library.upgraded_metadata(after), after)


if __name__ == "__main__":
    unittest.main()
