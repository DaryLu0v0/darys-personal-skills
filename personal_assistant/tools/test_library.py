from sample_data import prepare
import copy
import json
import random
import shutil
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

from library import ROOT, apply_handoff, digest, load_library, load_papers, read_json, validate_project, normalized_doi, paper_backlinks
from serve_library import Handler, ThreadingHTTPServer


class LibraryTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / '.local/test-temp'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.temp.name)
        prepare(self.root)
        self.path = self.root / 'library/projects/sample-research.json'
        self.project = read_json(self.path)
        self.handoff = read_json(self.root / 'library/handoffs/sample-initial-update.json')
        self.papers = load_papers(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def reset(self):
        base = copy.deepcopy(self.project)
        for key in ('evidence', 'checkpoints', 'relationships', 'applied_updates'):
            base[key] = []
        base['revision'] = 0
        self.path.write_text(json.dumps(base), encoding='utf-8')
        return digest(self.path.read_bytes())

    def test_current_library(self):
        result = load_library(self.root)
        projects = {p['id']: p for p in result['projects']}
        self.assertEqual(projects['sample-research'], self.project)
        self.assertTrue({c['id'] for c in self.handoff['checkpoints']} <= {c['id'] for c in self.project['checkpoints']})

    def test_end_to_end_replay_and_preservation(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file() and p != self.path}
        expected = self.reset()
        self.assertEqual(apply_handoff(self.root, self.handoff, expected)['status'], 'applied')
        stored = self.path.read_bytes()
        self.assertEqual(apply_handoff(self.root, self.handoff, expected)['status'], 'unchanged')
        self.assertEqual(self.path.read_bytes(), stored)
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file() and p != self.path})

    def test_same_source_under_another_update_id(self):
        self.handoff['id'] = 'same-source-new-delivery'
        self.handoff['recorded_at'] = '2026-11-01T00:00:00Z'
        self.handoff['base_revision'] = 1
        before = self.path.read_bytes()
        self.assertEqual(apply_handoff(self.root, self.handoff, 'old-digest')['status'], 'unchanged')
        self.assertEqual(self.path.read_bytes(), before)
        self.handoff['checkpoints'][0]['goal'] = 'conflicting reinterpretation'
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            apply_handoff(self.root, self.handoff, digest(before))

    def test_mutated_duplicate_rejected(self):
        self.handoff['goal'] = 'different goal'
        with self.assertRaisesRegex(ValueError, 'different content'):
            apply_handoff(self.root, self.handoff, digest(self.path.read_bytes()))

    def test_stale_revision_and_human_edits(self):
        expected = self.reset()
        self.handoff['base_revision'] = 9
        with self.assertRaisesRegex(ValueError, 'stale project'):
            apply_handoff(self.root, self.handoff, expected)
        self.handoff['base_revision'] = 0
        p = read_json(self.path); p['summary'] = 'A human edited this summary.'
        self.path.write_text(json.dumps(p), encoding='utf-8')
        human = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'stale file'):
            apply_handoff(self.root, self.handoff, expected)
        self.assertEqual(human, self.path.read_bytes())

    def test_partial_write_failure_is_atomic(self):
        expected = self.reset(); before = self.path.read_bytes()
        with patch('library.os.replace', side_effect=OSError('simulated full disk')):
            with self.assertRaises(OSError):
                apply_handoff(self.root, self.handoff, expected)
        self.assertEqual(before, self.path.read_bytes())
        self.assertFalse((self.root / 'library/.update.lock').exists())
        self.assertFalse(list(self.path.parent.glob('.*.tmp')))

    def test_lock_prevents_concurrent_writer(self):
        expected = self.reset()
        (self.root / 'library/.update.lock').write_text('another writer')
        with self.assertRaisesRegex(ValueError, 'lock exists'):
            apply_handoff(self.root, self.handoff, expected)

    def test_required_fields_and_references(self):
        for mutate in [lambda p: p['checkpoints'][0].pop('goal'),
                       lambda p: p['checkpoints'][0].update(status='finished-maybe'),
                       lambda p: p['checkpoints'][0].update(evidence_ids=['missing']),
                       lambda p: p['checkpoints'][0].update(papers=[{'paper_id':'missing','relevance':'test'}]),
                       lambda p: p['relationships'][0].update(to='missing'),
                       lambda p: p['checkpoints'].append(p['checkpoints'][0])]:
            p = copy.deepcopy(self.project); mutate(p)
            with self.assertRaises(ValueError):
                validate_project(p, self.papers)

    def test_cycles_self_links_and_valid_merge(self):
        validate_project(self.project, self.papers)
        for a, b in [('synthesis','foundation'),('foundation','foundation')]:
            p = copy.deepcopy(self.project)
            p['relationships'].append({'from':a,'to':b,'kind':'progression','rationale':'test'})
            with self.assertRaises(ValueError):
                validate_project(p, self.papers)

    def test_unsafe_links_and_conversation_provenance(self):
        for u in ['javascript:alert(1)', 'data:text/html,test', '//evil.test', 'file:///private', 'https://x.test\\@evil.test', 'https://x.test\n', 'https://user:pass@x.test']:
            p = copy.deepcopy(self.project); p['evidence'][0]['url'] = u
            with self.assertRaises(ValueError):
                validate_project(p, self.papers)
        p = copy.deepcopy(self.project)
        e = next(e for e in p['evidence'] if e['kind'] == 'conversation')
        e['speaker'] = 'assistant'
        with self.assertRaisesRegex(ValueError, 'user provenance'):
            validate_project(p, self.papers)

    def test_inaccessible_source_retained(self):
        p = copy.deepcopy(self.project)
        p['evidence'][0]['access'] = 'unavailable'
        p['evidence'][0]['access_note'] = 'Previously cited; remote inaccessible at this check.'
        validate_project(p, self.papers)
        self.assertEqual(p['checkpoints'], self.project['checkpoints'])

    def test_long_unicode_and_literal_markup(self):
        p = copy.deepcopy(self.project)
        p['checkpoints'][0]['goal'] = '研究路径 → λ <script>alert(1)</script> ' * 300
        validate_project(p, self.papers)
        self.assertIn('研究路径', json.dumps(p, ensure_ascii=False))

    def test_bounded_random_dags_deep_and_wide(self):
        rng = random.Random(418)
        for count in (20, 150, 400):
            p = copy.deepcopy(self.project); p['checkpoints'] = []; p['relationships'] = []
            for i in range(count):
                c = copy.deepcopy(self.project['checkpoints'][0]); c['id'] = f'node-{i}'; p['checkpoints'].append(c)
                parents = {i-1} if i else set()
                if i > 1: parents.add(rng.randrange(i-1))
                for parent in parents:
                    p['relationships'].append({'from':f'node-{parent}','to':f'node-{i}','kind':'progression','rationale':'bounded test'})
            validate_project(p, self.papers)
            p['relationships'].append({'from':f'node-{count-1}','to':'node-0','kind':'progression','rationale':'cycle test'})
            with self.assertRaisesRegex(ValueError, 'cycle'):
                validate_project(p, self.papers)

    def test_http_read_only_and_restricted_files(self):
        self.project['summary'] = 'HTTP fixture only; never use the installed library.'
        self.path.write_text(json.dumps(self.project), encoding='utf-8')
        with patch('serve_library.ROOT', self.root):
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                for method, path, headers, expected in [('GET','/api/library',{},200),('GET','/',{},200),('GET','/../.git/config',{},404),('POST','/api/library',{},501),('GET','/',{'Host':'untrusted.test'},403)]:
                    c = HTTPConnection('127.0.0.1', server.server_port)
                    try:
                        c.request(method, path, headers=headers); r = c.getresponse()
                        raw = r.read()
                    finally:
                        c.close()
                    self.assertEqual(r.status, expected, raw.decode('utf-8'))
                    if expected == 200:
                        self.assertIn("frame-ancestors 'none'", r.getheader('Content-Security-Policy'))
                    if path == '/api/library' and expected == 200:
                        projects = {p['id']: p for p in json.loads(raw)['projects']}
                        self.assertEqual(projects['sample-research']['summary'], self.project['summary'])
            finally:
                server.shutdown(); server.server_close(); thread.join()

    def write_paper(self, paper):
        paper = {k:v for k,v in paper.items() if k not in {'storage_version','note_path','obsidian','note_body','reading_notes','relevance_notes','pdf'}}
        path = self.root / 'library/papers' / (paper['id'] + '.json')
        path.write_text(json.dumps(paper, ensure_ascii=False), encoding='utf-8')

    def test_paper_dedup_normalizes_doi(self):
        original = next(p for p in self.papers.values() if p.get('doi'))
        self.assertEqual(normalized_doi('HTTPS://DOI.ORG/' + original['doi'].upper()), original['doi'].lower())
        duplicate = copy.deepcopy(original)
        duplicate.update(id='duplicate-doi', doi='https://doi.org/' + original['doi'].upper(), origins=[])
        self.write_paper(duplicate)
        with self.assertRaisesRegex(ValueError, 'duplicate paper identity'):
            load_papers(self.root)

    def test_paper_dedup_preserves_origin_identity(self):
        original = next(p for p in self.papers.values() if p.get('doi'))
        duplicate = copy.deepcopy(original)
        duplicate.update(id='duplicate-origin', doi=None, year=None, authors=[])
        self.write_paper(duplicate)
        with self.assertRaisesRegex(ValueError, 'duplicate paper identity'):
            load_papers(self.root)

    def test_paper_optional_metadata_and_unknown_reading_state(self):
        paper = copy.deepcopy(self.papers['sample-paper-b'])
        paper.update(id='minimal-paper', title='A reference with incomplete metadata')
        for key in ('authors', 'year', 'doi', 'origins', 'reading_status', 'venue', 'type'):
            paper.pop(key, None)
        self.write_paper(paper)
        self.assertIn('minimal-paper', load_papers(self.root))
        paper['reading_status'] = 'probably-read'
        self.write_paper(paper)
        with self.assertRaisesRegex(ValueError, 'reading status'):
            load_papers(self.root)

    def test_paper_multi_project_backlinks_and_context_dedup(self):
        paper_id = 'sample-paper-b'
        second = copy.deepcopy(self.project)
        second.update(id='second-project', title='Second project')
        links = [{'id':'extra-link', 'paper_id':paper_id, 'project_id':self.project['id'],
                  'checkpoint_id':'synthesis', 'relevance':'An additional context note.'}]
        before = copy.deepcopy(self.papers)
        index = paper_backlinks(self.papers, [self.project, second], links)
        self.assertEqual(len(index[paper_id]), 2)
        self.assertEqual(len(index[paper_id][0]['relevance']), 2)
        self.assertEqual(self.papers, before)

    def test_paper_link_invalid_endpoints(self):
        link = {'id':'bad-link', 'paper_id':'sample-paper-b',
                'project_id':self.project['id'], 'checkpoint_id':None, 'relevance':'test'}
        for key, value in [('paper_id','missing'),('project_id','missing'),('checkpoint_id','missing')]:
            invalid = {**link, key:value}
            with self.assertRaises(ValueError):
                paper_backlinks(self.papers, [self.project], [invalid])

    def test_paper_unsafe_origin_and_doi(self):
        paper = copy.deepcopy(next(p for p in self.papers.values() if p.get('doi')))
        paper['source_url'] = 'javascript:alert(1)'
        self.write_paper(paper)
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            load_papers(self.root)
        paper.pop('source_url')
        paper['origins'][0]['url'] = 'file:///private'
        self.write_paper(paper)
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            load_papers(self.root)
        with self.assertRaisesRegex(ValueError, 'DOI'):
            normalized_doi('javascript:alert(1)')

    def test_empty_paper_index(self):
        for path in (self.root / 'library/papers').glob('*.json'):
            path.unlink()
        self.assertEqual(load_papers(self.root), {})
        self.assertEqual(paper_backlinks({}, [], []), {})

    def test_index_coverage_and_existing_checkpoint_unchanged(self):
        data = load_library(self.root)
        self.assertEqual({p['id'] for p in data['papers']}, set(self.papers))
        sources = {s['id']: s for s in data['paper_sources']}
        self.assertTrue(all(s['status'] in {'available','unavailable','incomplete'} for s in sources.values()))
        self.assertEqual(next(p for p in data['projects'] if p['id']=='sample-research'), self.project)
        self.assertTrue(all(p['reading_status'] in {'metadata_only','queued','reading','reviewed'} for p in data['papers']))


if __name__ == '__main__':
    unittest.main()
