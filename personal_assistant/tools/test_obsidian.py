from sample_data import prepare
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from library import ROOT, load_library, load_papers
from obsidian_vault import FIELDS, attach_existing_pdf, contained, make_note, migrate, open_uri, read_note


class ObsidianTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / '.local/test-temp'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.temp.name)
        prepare(self.root, migrate_notes=False)
        # New post-migration references also need legacy fixtures; no live note is changed.
        for paper in load_papers(self.root).values():
            legacy = {k:v for k,v in paper.items() if k not in {'storage_version','note_path','obsidian','note_body','reading_notes','relevance_notes','pdf'}}
            (self.root / 'library/papers' / (paper['id']+'.json')).write_text(json.dumps(legacy,ensure_ascii=False),encoding='utf-8')
        # Reconstruct the pre-migration fixture from the versioned exact-byte backup.
        recovery = self.root / 'library/migrations/obsidian-v1-original-papers.json'
        if recovery.exists():
            originals = json.loads(recovery.read_text(encoding='utf-8'))['originals']
            for name, record in originals.items():
                (self.root / 'library/papers' / name).write_bytes(record['content'].encode('utf-8'))
            recovery.unlink()
            (self.root / 'library/vault.json').unlink()
        self.before = load_library(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_migrate_preserves_papers_provenance_graph_and_second_run(self):
        project = (self.root / 'library/projects/sample-research.json').read_bytes()
        self.assertEqual(migrate(self.root)['status'], 'migrated')
        after = load_library(self.root)
        for old, new in zip(self.before['papers'], after['papers']):
            for key, value in old.items():
                self.assertEqual(new[key], value, key)
        self.assertEqual((self.root / 'library/projects/sample-research.json').read_bytes(), project)
        snapshot = {p:p.read_bytes() for p in (self.root / 'Hikari Research/Papers').glob('*.md')}
        self.assertEqual(migrate(self.root)['status'], 'unchanged')
        self.assertTrue(all(p.read_bytes() == raw for p, raw in snapshot.items()))

    def test_roundtrip_block_yaml_and_hand_edit_projection_no_writeback(self):
        migrate(self.root)
        path = self.root / 'Hikari Research/Papers/sample-paper-a.md'
        raw = path.read_text(encoding='utf-8').replace('reading_status: "metadata_only"', 'reading_status: reading')
        raw = raw.replace('authors: ["Example, Alex", "Example, Blair", "Example, Casey", "Example, Devon"]', 'authors:\n  - Example, Alex\n  - Example, Blair\n  - Example, Casey\n  - Example, Devon')
        raw = raw.replace('## Reading notes\n', '## Reading notes\n\n手写记录 · <script>alert(1)</script>\n')
        path.write_text(raw, encoding='utf-8')
        original = path.read_bytes()
        paper = load_papers(self.root)['sample-paper-a']
        self.assertEqual(paper['reading_status'], 'reading')
        self.assertIn('手写记录', paper['reading_notes'])
        self.assertEqual(len(paper['authors']), 4)
        migrate(self.root)
        self.assertEqual(path.read_bytes(), original)

    def test_existing_folder_never_overwritten(self):
        vault = self.root / 'Hikari Research'
        vault.mkdir(); (vault / 'human.md').write_text('keep me', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            migrate(self.root)
        self.assertEqual((vault / 'human.md').read_text(), 'keep me')

    def test_duplicate_yaml_aliases_and_unsafe_tags_rejected(self):
        note = self.root / 'note.md'
        for header in ['id: one\nid: two', 'id: &a one\ntitle: *a', 'id: !!python/object/apply:os.system [echo unsafe]']:
            note.write_text('---\n' + header + '\n---\n## General summary\nA summary', encoding='utf-8')
            with self.assertRaises(ValueError):
                read_note(note)

    def test_missing_note_invalid_id_and_competing_json_fields(self):
        migrate(self.root)
        manifest_path = self.root / 'library/papers/sample-paper-a.json'
        original = json.loads(manifest_path.read_text())
        for changes in [{'title':'competing'}, {'note_path':'../outside.md'}, {'note_path':'Papers/missing.md'}]:
            manifest_path.write_text(json.dumps({**original, **changes}), encoding='utf-8')
            with self.assertRaises(ValueError): load_papers(self.root)
        manifest_path.write_text(json.dumps(original), encoding='utf-8')
        path = self.root / 'Hikari Research' / original['note_path']
        path.write_text(path.read_text(encoding='utf-8').replace('id: "sample-paper-a"', 'id: different'), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'ID'): load_papers(self.root)

    def test_known_note_uri_unicode_spaces_and_path_safety(self):
        vault = self.root / '研究 Vault'; vault.mkdir()
        note = vault / '模式 #1 & 2.md'; note.write_text('note', encoding='utf-8')
        uri = open_uri(note)
        parsed = urlsplit(uri)
        self.assertEqual(parsed.netloc, 'open')
        self.assertEqual(parse_qs(parsed.query), {'path':[str(note.resolve())]})
        for path in ['../outside.md', '/outside.md', 'C:/outside.md', 'Papers/../outside.md']:
            with self.assertRaises(ValueError): contained(vault, path, must_exist=False)

    def test_attachment_copy_integrity_idempotence_and_missing_file(self):
        source = self.root / 'existing.pdf'; source.write_bytes(b'%PDF-1.7\nlocal test fixture\n')
        path = self.root / 'library/papers/sample-paper-b.json'
        paper = json.loads(path.read_text(encoding='utf-8')); paper['local_path'] = str(source)
        path.write_text(json.dumps(paper), encoding='utf-8')
        migrate(self.root)
        self.assertEqual(attach_existing_pdf(self.root, paper['id'])['status'], 'attached')
        attached = load_papers(self.root)[paper['id']]
        self.assertTrue(attached['pdf']['available'])
        self.assertEqual(attached['reading_status'], 'metadata_only')
        self.assertEqual(attach_existing_pdf(self.root, paper['id'])['status'], 'unchanged')
        destination = self.root / 'Hikari Research' / attached['pdf']['path']
        self.assertEqual(destination.read_bytes(), source.read_bytes())
        destination.unlink()
        self.assertFalse(load_papers(self.root)[paper['id']]['pdf']['available'])

    def test_duplicate_identity_after_note_edit_rejected(self):
        migrate(self.root)
        note = self.root / 'Hikari Research/Papers/sample-paper-c.md'
        raw = note.read_text(encoding='utf-8').replace('10.0000/sample-c', '10.0000/sample-a')
        note.write_text(raw, encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'duplicate paper identity'):
            load_papers(self.root)


if __name__ == '__main__':
    unittest.main()
