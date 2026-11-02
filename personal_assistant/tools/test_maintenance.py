from sample_data import prepare
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from library import ROOT, digest, read_json, validate_evidence, load_library
from maintenance import (apply_plan, empty_state, event_key, ingest, load_state,
                         state_path, validate_batch)


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        (ROOT / '.local/test-temp').mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.local/test-temp')
        self.root = Path(self.temp.name)
        prepare(self.root)
        state_path(self.root).parent.mkdir(parents=True, exist_ok=True)
        self.write(state_path(self.root), empty_state())
        self.project_path = self.root / 'library/projects/sample-research.json'
        self.batch = {
            'schema_version': 1, 'id': 'test-batch', 'provider': 'claude-desktop',
            'scope': 'all-projects', 'report_date': '2026-11-02', 'recorded_at': '2026-11-03T03:00:00Z',
            'coverage': {'listing_complete': False, 'note': 'Fixture, bounded page.', 'gaps': ['More pages unknown.']},
            'projects': [{'project_key': 'claude-desktop:local:fixture', 'title': 'Research 研究',
                'host': 'local', 'working_directory': 'D:/fixture', 'identity_basis': 'Native fixture metadata'}],
            'sessions': [{'session_id': 'native-fixture', 'project_key': 'claude-desktop:local:fixture',
                'title': 'Fixture session', 'source_revision': 'turn-1', 'source_updated_at': None,
                'native_reference': 'native read_session native-fixture',
                'read': {'status': 'partial', 'message_refs': ['msg-1'], 'next_cursor': 'opaque/2',
                         'note': 'One message returned.', 'gaps': ['Older history not covered.']},
                'events': [{'message_ref': 'msg-1', 'speaker': 'user', 'basis': 'user_decision',
                    'occurred_at': None, 'summary': 'Fixture confirms project identity.',
                    'verification': 'Fixture user message only.', 'evidence_urls': []}]}]}
        self.ref = event_key('claude-desktop', 'native-fixture', 'msg-1')

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return path

    def submit(self, batch=None):
        b = batch or self.batch
        return self.write(self.root / 'library/inbox' / b['provider'] / (b['id'] + '.json'), b)

    def plan(self, kind, pid, **extra):
        return self.write(self.root / 'library/maintenance/plans' / (pid + '.json'), {
            'schema_version': 1, 'id': pid, 'kind': kind, 'reviewed_at': '2026-11-03T04:00:00Z',
            'reviewed_by': 'test reviewer', 'review_note': 'Reviewed fixture evidence; no scientific claim.',
            'submission_ids': ['test-batch'], 'source_refs': [self.ref], **extra})

    def prepared(self):
        self.submit(); ingest(self.root, '2026-11-02')
        mapping = self.plan('map_project', 'map-fixture', project_key='claude-desktop:local:fixture', canonical_project_id='sample-research')
        self.assertEqual(apply_plan(self.root, mapping)['status'], 'mapped')

    def handoff(self):
        p = read_json(self.project_path)
        e = copy.deepcopy(p['evidence'][0]); e['id'] = 'fixture-evidence'
        c = copy.deepcopy(p['checkpoints'][0]); c['id'] = 'fixture-checkpoint'
        c['evidence_ids'] = [e['id']]
        for field in ('done', 'next'):
            for claim in c[field]:
                claim['evidence_ids'] = [e['id']]
        return {'schema_version': 1, 'id': 'fixture-update', 'project_id': p['id'], 'base_revision': p['revision'],
            'source_revision_key': 'fixture-source-one', 'recorded_at': '2026-11-03T04:00:00Z', 'occurred_at': None,
            'goal': 'Fixture goal', 'completed': 'Fixture result', 'findings': ['fixture'], 'uncertainties': ['fixture'],
            'verification': ['fixture'], 'next_actions': ['fixture'], 'source_revisions': ['turn-1'],
            'evidence': [e], 'checkpoints': [c], 'relationships': []}

    def test_intake_replay_zero_writes_and_no_false_history_completion(self):
        self.submit()
        result = ingest(self.root, '2026-11-02')
        self.assertEqual(result['projects_indexed'], 1)
        self.assertEqual(result['projects_pending_mapping'], 1)
        raw = state_path(self.root).read_bytes()
        second = ingest(self.root, '2026-11-02')
        self.assertFalse(second['state_written'])
        self.assertEqual(raw, state_path(self.root).read_bytes())
        observation = next(iter(load_state(self.root)['observations'].values()))
        self.assertEqual(observation['read']['message_refs'], ['msg-1'])
        self.assertEqual(observation['read']['status'], 'partial')

    def test_end_to_end_append_and_replay_preserve_notes_and_old_nodes(self):
        notes = {p: p.read_bytes() for p in (self.root / 'Hikari Research').rglob('*.md')}
        self.prepared()
        old = read_json(self.project_path)
        plan = self.plan('handoff', 'apply-fixture', handoff=self.handoff(), expected_digest=digest(self.project_path.read_bytes()))
        self.assertEqual(apply_plan(self.root, plan)['status'], 'applied')
        updated = read_json(self.project_path)
        self.assertEqual(updated['checkpoints'][:-1], old['checkpoints'])
        self.assertEqual(len(updated['checkpoints']), len(old['checkpoints']) + 1)
        snapshot = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(apply_plan(self.root, plan)['status'], 'unchanged')
        self.assertFalse(ingest(self.root, '2026-11-02')['state_written'])
        self.assertEqual(snapshot, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertEqual(notes, {p: p.read_bytes() for p in notes})
        load_library(self.root)

    def test_new_project_creation_is_explicit_and_replay_safe(self):
        self.submit(); ingest(self.root, '2026-11-02')
        project = copy.deepcopy(read_json(self.project_path))
        project.update(id='new-project', title='New project', revision=0, sources=[], checkpoints=[], relationships=[], applied_updates=[])
        for e in project['evidence']:
            e.pop('source_id', None); e.pop('source_revision', None)
        plan = self.plan('create_project', 'create-fixture', project=project)
        self.assertEqual(apply_plan(self.root, plan)['status'], 'created')
        self.assertEqual(apply_plan(self.root, plan)['status'], 'unchanged')
        other = self.plan('create_project', 'collision-fixture', project=project)
        self.assertEqual(apply_plan(self.root, other)['status'], 'pending')
        self.assertEqual(len(load_library(self.root)['projects']), 3)

    def identity_document(self):
        return {'project_key': self.batch['projects'][0]['project_key'], 'evidence': {
            'id': 'fixture-identity', 'title': 'Checked repository identity',
            'summary': 'Fixture configuration matches this inventory directory.',
            'access_note': 'Synthetic fixture; no network or source project access.',
            'kind': 'document', 'basis': 'observed_record', 'access': 'checked',
            'checked_at': '2026-11-03T04:00:00Z', 'occurred_at': None,
            'local_path': 'D:/fixture/README.md'}}

    def test_document_identity_mapping_and_creation_replay(self):
        self.submit(); ingest(self.root, '2026-11-02')
        evidence = self.identity_document()
        mapping = self.plan('map_project', 'document-map', source_refs=[],
            identity_evidence=[evidence], project_key=evidence['project_key'], canonical_project_id='sample-research')
        self.assertEqual(apply_plan(self.root, mapping)['status'], 'mapped')
        before = state_path(self.root).read_bytes()
        self.assertEqual(apply_plan(self.root, mapping)['status'], 'unchanged')
        self.assertEqual(before, state_path(self.root).read_bytes())
        project = copy.deepcopy(read_json(self.project_path))
        project.update(id='document-project', revision=0, sources=[], evidence=[evidence['evidence']],
                       checkpoints=[], relationships=[], applied_updates=[])
        create = self.plan('create_project', 'document-create', source_refs=[],
            identity_evidence=[evidence], project=project)
        self.assertEqual(apply_plan(self.root, create)['status'], 'created')
        self.assertEqual(apply_plan(self.root, create)['status'], 'unchanged')

    def test_document_identity_rejects_wrong_project_unchecked_and_handoff_bypass(self):
        self.submit(); ingest(self.root, '2026-11-02')
        for name, change in [('unknown', {'project_key': 'unknown'}),
                             ('reported', {'evidence': dict(self.identity_document()['evidence'], access='reported')})]:
            evidence = dict(self.identity_document(), **change)
            plan = self.plan('map_project', 'bad-'+name, source_refs=[], identity_evidence=[evidence],
                project_key=self.batch['projects'][0]['project_key'], canonical_project_id='sample-research')
            self.assertEqual(apply_plan(self.root, plan)['status'], 'pending')
        handoff = self.plan('handoff', 'no-message-bypass', source_refs=[],
            identity_evidence=[self.identity_document()], handoff=self.handoff(), expected_digest=digest(self.project_path.read_bytes()))
        self.assertEqual(apply_plan(self.root, handoff)['status'], 'pending')

    def test_crash_after_canonical_write_recovers_without_duplicate(self):
        self.prepared()
        plan = self.plan('handoff', 'recover-fixture', handoff=self.handoff(), expected_digest=digest(self.project_path.read_bytes()))
        with patch('maintenance.write_state', side_effect=OSError('simulated crash after project write')):
            with self.assertRaises(OSError):
                apply_plan(self.root, plan)
        raw = self.project_path.read_bytes()
        self.assertEqual(apply_plan(self.root, plan)['status'], 'unchanged')
        self.assertEqual(raw, self.project_path.read_bytes())
        self.assertIn('recover-fixture', load_state(self.root)['plans'])

    def test_rejected_plan_identity_is_immutable(self):
        self.prepared()
        file = self.plan('handoff', 'rejected-fixture', handoff=self.handoff(), expected_digest='stale')
        self.assertEqual(apply_plan(self.root, file)['status'], 'pending')
        before = state_path(self.root).read_bytes()
        self.assertFalse(apply_plan(self.root, file)['state_written'])
        self.assertEqual(before, state_path(self.root).read_bytes())
        plan = read_json(file); plan['expected_digest'] = digest(self.project_path.read_bytes())
        self.write(file, plan)
        with self.assertRaisesRegex(ValueError, 'plan ID changed'):
            apply_plan(self.root, file)

    def test_crash_before_state_replace_keeps_receipt_retryable(self):
        self.submit(); before = state_path(self.root).read_bytes()
        import maintenance
        real_replace = maintenance.os.replace
        def fail_state(src, dst):
            if Path(dst) == state_path(self.root):
                raise OSError('full disk')
            return real_replace(src, dst)
        with patch('maintenance.os.replace', side_effect=fail_state):
            with self.assertRaises(OSError): ingest(self.root, '2026-11-02')
        self.assertEqual(before, state_path(self.root).read_bytes())
        self.assertEqual(ingest(self.root, '2026-11-02')['accepted'], 1)

    def test_stale_digest_preserves_human_edit_and_is_pending(self):
        self.prepared(); h = self.handoff(); expected = digest(self.project_path.read_bytes())
        project = read_json(self.project_path); project['summary'] = 'Human edited this summary.'
        self.write(self.project_path, project); raw = self.project_path.read_bytes()
        result = apply_plan(self.root, self.plan('handoff', 'stale-fixture', handoff=h, expected_digest=expected))
        self.assertEqual(result['status'], 'pending'); self.assertIn('stale file', result['reason'])
        self.assertEqual(raw, self.project_path.read_bytes())

    def test_mapping_and_message_conflicts_do_not_apply(self):
        self.prepared()
        changed = copy.deepcopy(self.batch); changed['id'] = 'changed-message'
        changed['sessions'][0]['events'][0]['summary'] = 'Conflicting scientific interpretation'
        self.submit(changed); ingest(self.root, '2026-11-02')
        plan = self.plan('handoff', 'conflict-fixture', handoff=self.handoff(), expected_digest=digest(self.project_path.read_bytes()))
        raw = self.project_path.read_bytes()
        self.assertEqual(apply_plan(self.root, plan)['status'], 'pending')
        self.assertEqual(raw, self.project_path.read_bytes())

    def test_mutated_submission_preserves_original_archive(self):
        file = self.submit(); initial = file.read_bytes(); ingest(self.root, '2026-11-02')
        self.batch['coverage']['note'] = 'Changed same ID'
        self.submit(); ingest(self.root, '2026-11-02')
        state = load_state(self.root)
        self.assertEqual((self.root / state['submissions']['test-batch']['archive']).read_bytes(), initial)
        self.assertIn('submission-conflict:test-batch', state['pending'])
        self.assertFalse(ingest(self.root, '2026-11-02')['state_written'])

    def test_missing_claude_resolves_on_late_arrival(self):
        self.assertTrue(ingest(self.root, '2026-11-02')['missing_claude'])
        self.assertFalse(ingest(self.root, '2026-11-02')['state_written'])
        self.submit(); self.assertFalse(ingest(self.root, '2026-11-02')['missing_claude'])
        self.assertEqual(load_state(self.root)['pending']['missing-claude:2026-11-02']['status'], 'resolved')

    def test_lock_is_not_removed_by_contender(self):
        lock = self.root / 'library/.maintenance.lock'; lock.write_text('active writer')
        with self.assertRaisesRegex(ValueError, 'inspect active writer'):
            ingest(self.root, '2026-11-02')
        self.assertEqual(lock.read_text(), 'active writer')

    def test_batch_rejects_unread_provenance_personal_scope_and_unsafe_urls(self):
        mutations = [lambda b: b.update(scope='all-personal-chats'),
            lambda b: b['sessions'][0].update(project_key='unknown'),
            lambda b: b['sessions'][0]['read'].update(status='listed'),
            lambda b: b['sessions'][0]['events'][0].update(speaker='assistant'),
            lambda b: b['sessions'][0]['events'][0].update(evidence_urls=['javascript:alert(1)']),
            lambda b: b['sessions'][0]['events'][0].update(message_ref='unread'),
            lambda b: b['projects'][0].update(canonical_project_id='guessed'),
            lambda b: b['projects'].append(b['projects'][0])]
        for mutation in mutations:
            b = copy.deepcopy(self.batch); mutation(b)
            with self.assertRaises((ValueError, KeyError, TypeError)):
                validate_batch(b)

    def test_invalid_input_stays_pending_and_repeated_read_is_noop(self):
        b = copy.deepcopy(self.batch); b['sessions'][0]['read']['message_refs'] = []
        self.submit(b)
        self.assertEqual(ingest(self.root, '2026-11-02')['accepted'], 0)
        self.assertFalse(ingest(self.root, '2026-11-02')['state_written'])

    def test_same_message_new_delivery_deduplicates_and_unicode_is_literal(self):
        self.batch['sessions'][0]['events'][0]['summary'] = '研究 <script>alert(1)</script>'
        self.submit(); ingest(self.root, '2026-11-02')
        self.batch['id'] = 'second-delivery'; self.submit()
        self.assertEqual(ingest(self.root, '2026-11-02')['source_messages_indexed'], 1)

    def test_native_conversation_evidence_and_legacy_url_safety(self):
        e = {'id': 'native-evidence', 'kind': 'conversation', 'provider': 'codex-desktop',
            'title': 'A returned message', 'summary': 'A proposal', 'basis': 'proposal',
            'access': 'checked', 'access_note': 'Message inspected, experiment not executed.',
            'checked_at': '2026-11-02T18:00:00Z', 'occurred_at': None, 'conversation_id': 'thread-native',
            'message_id': 'turn-2/message-1', 'message_reference_kind': 'native tool message ID',
            'native_reference': 'read_thread thread-native / turn-2/message-1',
            'speaker': 'assistant', 'excerpt': 'Try another design.', 'retrieval': 'One bounded message.'}
        validate_evidence(e)
        e['url'] = 'file:///private'
        with self.assertRaises(ValueError): validate_evidence(e)


if __name__ == '__main__':
    unittest.main()
