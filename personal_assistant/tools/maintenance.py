"""Local project-conversation inbox, immutable receipts and reviewed reconciliation.

This command never fetches conversations, runs agents, schedules work or edits notes.
The single atomic state document includes its journal. Canonical project writes use
the library lock; replay recovers a crash between that write and the state receipt.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from library import (ROOT, BASES, apply_handoff, canonical, digest, identity,
                     load_papers, read_json, require, text, timestamp, url,
                     validate_project, validate_evidence)

PROVIDERS = {'claude-desktop', 'codex-desktop'}
MAX_BYTES = 2_000_000


def now():
    return datetime.now(timezone.utc).isoformat()


def bounded(value, label, limit=2000):
    text(value, label)
    require(len(value) <= limit, f'{label}: too long; submit concise evidence, not transcripts')


def inside(root, path, folder):
    path = Path(path).resolve()
    require(path.is_relative_to((root / folder).resolve()), f'path must be inside {folder}')
    require(path.suffix == '.json', 'JSON file required')
    return path


def read_bounded(path):
    raw = path.read_bytes()
    require(len(raw) <= MAX_BYTES, 'submission too large')
    return raw, json.loads(raw.decode('utf-8-sig'))


def validate_batch(batch):
    require(isinstance(batch, dict) and batch.get('schema_version') == 1, 'unsupported batch schema')
    identity(batch.get('id'))
    require(batch.get('provider') in PROVIDERS, 'unsupported provider')
    require(batch.get('scope') == 'all-projects', 'all-projects scope required')
    date.fromisoformat(batch['report_date'])
    timestamp(batch.get('recorded_at'), 'recorded_at')
    coverage = batch.get('coverage')
    require(isinstance(coverage, dict), 'coverage object required')
    require(type(coverage.get('listing_complete')) is bool, 'explicit listing coverage required')
    bounded(coverage.get('note'), 'coverage note', 4000)
    require(isinstance(coverage.get('gaps'), list), 'coverage gaps required')
    if not coverage['listing_complete']:
        require(bool(coverage['gaps']), 'partial listing needs a gap')
    for gap in coverage['gaps']:
        bounded(gap, 'coverage gap')
    require(isinstance(batch.get('projects'), list), 'projects required')
    projects = {}
    for p in batch['projects']:
        for field in ('project_key', 'title', 'host', 'working_directory', 'identity_basis'):
            bounded(p.get(field), field)
        require(p['project_key'].startswith(batch['provider'] + ':'), 'project key provider mismatch')
        require(p['project_key'] not in projects, 'duplicate project key')
        require('canonical_project_id' not in p, 'worker cannot assign canonical project mappings')
        projects[p['project_key']] = p
    require(isinstance(batch.get('sessions'), list), 'sessions required')
    seen = set()
    for s in batch['sessions']:
        for field in ('session_id', 'title', 'source_revision', 'native_reference'):
            bounded(s.get(field), field)
        require(s['session_id'] not in seen, 'duplicate session')
        seen.add(s['session_id'])
        require(s.get('project_key') in projects, 'session needs a known project; personal chats are excluded')
        timestamp(s.get('source_updated_at'), 'source_updated_at', optional=True)
        r = s.get('read')
        require(isinstance(r, dict), 'read receipt required')
        require(r.get('status') in {'listed', 'partial', 'window_complete', 'unavailable'}, 'invalid read status')
        bounded(r.get('note'), 'read note', 4000)
        require(isinstance(r.get('message_refs'), list), 'message_refs required')
        require(len(set(r['message_refs'])) == len(r['message_refs']), 'duplicate message reference')
        for ref in r['message_refs']:
            bounded(ref, 'actual returned message reference')
        require(isinstance(r.get('gaps'), list), 'read gaps required')
        for gap in r['gaps']:
            bounded(gap, 'read gap')
        if r['status'] in {'partial', 'unavailable'}:
            require(bool(r['gaps']), 'partial/unavailable read needs a gap')
        if r['status'] in {'partial', 'window_complete'}:
            require(bool(r['message_refs']), 'successful read needs actual message references')
        else:
            require(not r['message_refs'], 'unread session cannot claim processed messages')
        # Cursors are opaque tool values; never increment one or infer coverage.
        require(r.get('next_cursor') is None or isinstance(r['next_cursor'], (str, dict)), 'invalid cursor')
        require(isinstance(s.get('events'), list), 'events required')
        event_refs = set()
        for e in s['events']:
            require(e.get('message_ref') in r['message_refs'], 'event not in actually returned messages')
            require(e['message_ref'] not in event_refs, 'one concise event per message reference')
            event_refs.add(e['message_ref'])
            require(e.get('speaker') in {'user', 'assistant', 'worker'}, 'speaker required')
            require(e.get('basis') in BASES, 'invalid event basis')
            if e['basis'] in {'user_decision', 'user_correction'}:
                require(e['speaker'] == 'user', 'user decision requires user message')
            for field in ('summary', 'verification'):
                bounded(e.get(field), field)
            if e.get('excerpt'):
                bounded(e['excerpt'], 'excerpt', 1000)
            timestamp(e.get('occurred_at'), 'event occurred_at', optional=True)
            require(isinstance(e.get('evidence_urls'), list), 'evidence_urls required')
            for u in e['evidence_urls']:
                url(u)
    return batch


def empty_state():
    return {'schema_version': 1, 'inventory': {}, 'submissions': {}, 'messages': {},
            'observations': {}, 'plans': {}, 'pending': {}, 'journal': []}


def state_path(root):
    return root / 'library/maintenance/state.json'


def load_state(root):
    path = state_path(root)
    state = read_json(path) if path.exists() else empty_state()
    require(state.get('schema_version') == 1, 'unsupported maintenance state')
    for key in empty_state():
        require(key in state, f'missing state field: {key}')
    return state


@contextmanager
def locked(root, name='.maintenance.lock'):
    path = root / 'library' / name
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise ValueError(f'{name} exists; inspect active writer before stale-lock recovery') from error
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump({'pid': os.getpid(), 'started_at': now()}, handle)
            handle.flush(); os.fsync(handle.fileno())
        yield
    finally:
        path.unlink(missing_ok=True)


def atomic(path, raw, expected=None, create_only=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.', suffix='.tmp', delete=False) as handle:
            tmp = Path(handle.name)
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        if create_only:
            require(not path.exists(), 'destination already exists; reconcile instead of overwriting')
        elif expected is not None:
            require(path.read_bytes() == expected, 'concurrent state edit; retry after review')
        os.replace(tmp, path)
    finally:
        if tmp and tmp.exists():
            tmp.unlink()


def write_state(root, state, original):
    path = state_path(root)
    raw = (json.dumps(state, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if original is not None and json.loads(original) == state:
        return False
    atomic(path, raw, expected=original, create_only=original is None)
    return True


def archive(root, category, raw):
    sha = digest(raw)
    path = root / 'library/maintenance' / category / (sha + '.json')
    if path.exists():
        require(path.read_bytes() == raw, 'archive digest collision')
    else:
        atomic(path, raw, create_only=True)
    return str(path.relative_to(root)).replace('\\', '/')


def journal(state, kind, key, details):
    state['journal'].append({'sequence': len(state['journal']) + 1, 'at': now(),
                             'kind': kind, 'key': key, 'details': details})


def pending(state, key, reason, refs=None):
    value = {'reason': reason, 'references': refs or [], 'status': 'pending'}
    if state['pending'].get(key) != value:
        state['pending'][key] = value
        journal(state, 'pending', key, value)


def event_key(provider, session_id, message_ref):
    return digest(canonical([provider, session_id, message_ref]))


def ingest(root, report_date):
    date.fromisoformat(report_date)
    with locked(root):
        path = state_path(root)
        original = path.read_bytes() if path.exists() else None
        state = load_state(root)
        accepted = duplicates = 0
        for provider in sorted(PROVIDERS):
            for file in sorted((root / 'library/inbox' / provider).glob('*.json')):
                inside(root, file, 'library/inbox/' + provider)
                try:
                    raw, batch = read_bounded(file)
                    validate_batch(batch)
                    require(file.stem == batch['id'] and batch['provider'] == provider, 'inbox identity mismatch')
                except (ValueError, KeyError, TypeError, OSError) as error:
                    pending(state, 'invalid:' + str(file.relative_to(root)), str(error))
                    continue
                sha = digest(raw)
                old = state['submissions'].get(batch['id'])
                if old and old['digest'] == sha:
                    duplicates += 1
                    continue
                saved = archive(root, 'submissions', raw)
                if old:
                    pending(state, 'submission-conflict:' + batch['id'],
                            'Same submission ID has different content; original retained.', [old['archive'], saved])
                    continue
                for p in batch['projects']:
                    key = p['project_key']
                    existing = state['inventory'].get(key)
                    if existing and any(existing['source'][f] != p[f] for f in ('host', 'working_directory')):
                        pending(state, 'project-identity:' + key, 'Project identity changed; retain both observations.', [saved])
                    elif not existing:
                        state['inventory'][key] = {'source': p, 'provider': provider,
                            'canonical_project_id': None, 'mapping_status': 'pending', 'first_submission': batch['id']}
                conflicts = []
                for s in batch['sessions']:
                    for e in s['events']:
                        key = event_key(provider, s['session_id'], e['message_ref'])
                        value = {'project_key': s['project_key'], 'event': e}
                        if key in state['messages'] and state['messages'][key]['content'] != value:
                            pending(state, 'message-conflict:' + key,
                                    'Same source message has changed interpretation/content; manual reconciliation required.',
                                    [state['messages'][key]['submission_id'], batch['id']])
                            conflicts.append(key)
                        elif key not in state['messages']:
                            state['messages'][key] = {'content': value, 'provider': provider,
                                'session_id': s['session_id'], 'native_reference': s['native_reference'],
                                'submission_id': batch['id']}
                    observation_id = digest(canonical([provider, s]))
                    state['observations'].setdefault(observation_id, {
                        'provider': provider, 'session_id': s['session_id'], 'project_key': s['project_key'],
                        'source_revision': s['source_revision'], 'source_updated_at': s.get('source_updated_at'),
                        'read': s['read'], 'submission_id': batch['id'],
                        'note': 'Returned-message coverage only; ingestion is not scientific verification or full-history completion.'})
                state['submissions'][batch['id']] = {'digest': sha, 'archive': saved,
                    'provider': provider, 'report_date': batch['report_date'], 'recorded_at': batch['recorded_at'],
                    'coverage': batch['coverage'], 'conflicts': conflicts, 'status': 'received'}
                journal(state, 'received', batch['id'], {'archive': saved, 'conflicts': conflicts})
                accepted += 1
        missing_key = 'missing-claude:' + report_date
        has_claude = any(s['provider'] == 'claude-desktop' and s['report_date'] == report_date
                         for s in state['submissions'].values())
        if not has_claude:
            pending(state, missing_key, 'No valid Claude handoff for this date; do not infer no activity.')
        elif missing_key in state['pending'] and state['pending'][missing_key]['status'] == 'pending':
            state['pending'][missing_key]['status'] = 'resolved'
            journal(state, 'resolved', missing_key, 'Claude input arrived; coverage may still be partial.')
        wrote = write_state(root, state, original)
        return {'accepted': accepted, 'duplicate_deliveries': duplicates, 'state_written': wrote,
                'missing_claude': not has_claude, **summary(state)}


def summary(state):
    return {'projects_indexed': len(state['inventory']),
            'projects_pending_mapping': sum(p['mapping_status'] == 'pending' for p in state['inventory'].values()),
            'source_messages_indexed': len(state['messages']), 'submissions': len(state['submissions']),
            'pending': sum(p['status'] == 'pending' for p in state['pending'].values()),
            'journal_entries': len(state['journal'])}


def apply_plan(root, file):
    file = inside(root, file, 'library/maintenance/plans')
    raw, plan = read_bounded(file)
    require(plan.get('schema_version') == 1, 'unsupported plan schema')
    pid = identity(plan.get('id'))
    require(file.stem == pid, 'plan filename mismatch')
    require(plan.get('kind') in {'handoff', 'create_project', 'map_project', 'defer'}, 'unsupported plan kind')
    for field in ('review_note', 'reviewed_by'):
        bounded(plan.get(field), field, 4000)
    timestamp(plan.get('reviewed_at'), 'reviewed_at')
    with locked(root):
        original = state_path(root).read_bytes()
        state = load_state(root)
        require(isinstance(plan.get('submission_ids'), list) and plan['submission_ids'], 'source submissions required')
        require(all(s in state['submissions'] for s in plan['submission_ids']), 'unknown submission')
        require(isinstance(plan.get('source_refs'), list), 'source_refs required')
        require(all(r in state['messages'] and state['messages'][r]['submission_id'] in plan['submission_ids']
                    for r in plan['source_refs']), 'source reference absent from submitted messages')
        sha = digest(canonical(plan))
        prior = state['plans'].get(pid)
        if prior:
            require(prior['digest'] == sha, 'plan ID changed; retain original and create a new reconciled plan')
            return {'status': 'pending' if prior['result']['status'] == 'pending' else 'unchanged',
                    'plan': pid, 'state_written': False, 'previous_result': prior['result']}
        saved = archive(root, 'reviewed-plans', raw)
        try:
            identities = plan.get('identity_evidence', [])
            require(isinstance(identities, list), 'identity_evidence must be a list')
            require(not identities or plan['kind'] in {'create_project', 'map_project'},
                    'document identity evidence is only for project creation or mapping')
            for item in identities:
                key = item['project_key']
                require(key in state['inventory'], 'unknown identity inventory project')
                require(state['inventory'][key]['first_submission'] in plan['submission_ids'],
                        'identity inventory submission must be cited')
                e = item['evidence']
                validate_evidence(e)
                require(e['kind'] in {'document', 'code'} and e['access'] == 'checked'
                        and e['basis'] in {'observed_record', 'documented_implementation'},
                        'identity document must be checked; reports or proposals do not confirm identity')
                require(state['pending'].get('project-identity:' + key, {}).get('status') != 'pending',
                        'project identity conflict pending')
            require(not any(state['pending'].get('message-conflict:' + r, {}).get('status') == 'pending'
                            for r in plan['source_refs']), 'source-message conflict pending')
            if plan['kind'] == 'handoff':
                require(plan['source_refs'], 'handoff needs cited source messages')
                handoff = plan['handoff']
                for ref in plan['source_refs']:
                    project_key = state['messages'][ref]['content']['project_key']
                    mapping = state['inventory'][project_key]
                    require(mapping['canonical_project_id'] == handoff.get('project_id') and mapping['mapping_status'] == 'confirmed',
                            'source message canonical project mapping not confirmed')
                    require(state['pending'].get('project-identity:' + project_key, {}).get('status') != 'pending',
                            'project identity conflict pending')
                result = apply_handoff(root, handoff, plan.get('expected_digest'))
            elif plan['kind'] == 'create_project':
                require(plan['source_refs'] or identities, 'new project needs cited identity evidence')
                project = copy.deepcopy(plan['project'])
                validate_project(project, load_papers(root))
                require(project['revision'] == 0 and not project['applied_updates'], 'new project starts at revision zero')
                require(project['evidence'], 'new project requires identity evidence')
                project['initialization'] = {'plan_id': pid, 'plan_digest': sha}
                path = root / 'library/projects' / (project['id'] + '.json')
                with locked(root, '.update.lock'):
                    if path.exists():
                        require(read_json(path).get('initialization') == project['initialization'],
                                'project already exists; reconcile instead of replacing')
                        result = {'status': 'unchanged', 'recovered': True}
                    else:
                        atomic(path, (json.dumps(project, ensure_ascii=False, indent=2) + '\n').encode('utf-8'), create_only=True)
                        result = {'status': 'created', 'project_id': project['id']}
            elif plan['kind'] == 'map_project':
                key = plan['project_key']; identity(plan['canonical_project_id'])
                require(key in state['inventory'], 'unknown inventory project')
                require(plan['source_refs'] or identities, 'mapping requires submitted identity evidence')
                require(all(i['project_key'] == key for i in identities),
                        'identity document belongs to another project')
                require(all(state['messages'][r]['content']['project_key'] == key for r in plan['source_refs']),
                        'mapping evidence belongs to another project')
                require(state['pending'].get('project-identity:' + key, {}).get('status') != 'pending',
                        'project identity conflict pending')
                path = root / 'library/projects' / (plan['canonical_project_id'] + '.json')
                validate_project(read_json(path), load_papers(root))
                existing = state['inventory'][key]
                require(existing['canonical_project_id'] in {None, plan['canonical_project_id']}, 'mapping conflicts with confirmed identity')
                existing.update(canonical_project_id=plan['canonical_project_id'], mapping_status='confirmed', mapping_plan=pid)
                result = {'status': 'mapped', 'project_key': key}
            else:
                pending(state, 'review:' + pid, plan['review_note'], plan['submission_ids'])
                result = {'status': 'pending'}
        except (ValueError, KeyError, TypeError, OSError) as error:
            pending(state, 'plan:' + pid, str(error), [saved])
            state['plans'][pid] = {'digest': sha, 'archive': saved,
                'result': {'status': 'pending', 'reason': str(error)},
                'submission_ids': plan['submission_ids'], 'source_refs': plan['source_refs']}
            write_state(root, state, original)
            return {'status': 'pending', 'plan': pid, 'reason': str(error)}
        state['plans'][pid] = {'digest': sha, 'archive': saved, 'result': result,
                               'submission_ids': plan['submission_ids'], 'source_refs': plan['source_refs']}
        if 'plan:' + pid in state['pending']:
            state['pending']['plan:' + pid]['status'] = 'resolved'
        # Supersession preserves the original failure and never changes its payload.
        for superseded in plan.get('supersedes', []):
            if 'plan:' + superseded in state['pending']:
                state['pending']['plan:' + superseded]['status'] = 'resolved'
        journal(state, 'plan-' + result['status'], pid, state['plans'][pid])
        write_state(root, state, original)
        return {**result, 'plan': pid, 'state_written': True}


def dashboard_status(root):
    state = load_state(root)
    return {**summary(state), 'projects': [
        {'title': p['source']['title'], 'provider': p['provider'],
         'mapping_status': p['mapping_status'], 'canonical_project_id': p['canonical_project_id']}
        for p in state['inventory'].values()],
        'pending_items': [{'key': k, **v} for k, v in state['pending'].items() if v['status'] == 'pending'],
        'coverage': [s['coverage'] for s in state['submissions'].values()],
        'note': 'Indexed projects and received handoffs are not complete conversation coverage.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['validate-batch', 'ingest', 'status', 'apply-plan'])
    p.add_argument('file', nargs='?')
    p.add_argument('--date', help='Requested report date in America/New_York, YYYY-MM-DD')
    args = p.parse_args()
    try:
        if args.command == 'validate-batch':
            require(args.file is not None, 'batch path required')
            _, batch = read_bounded(inside(ROOT, Path(args.file), 'library/inbox'))
            validate_batch(batch); result = {'valid': True, 'id': batch['id']}
        elif args.command == 'ingest':
            require(args.date is not None, '--date required; do not infer report date from UTC')
            result = ingest(ROOT, args.date)
        elif args.command == 'apply-plan':
            require(args.file is not None, 'plan path required')
            result = apply_plan(ROOT, Path(args.file))
        else:
            result = dashboard_status(ROOT)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, TypeError, OSError) as error:
        p.exit(1, f'Maintenance error: {error}\n')


if __name__ == '__main__':
    main()
