"""Canonical records, validation and atomic, append-only handoff reconciliation."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {'completed', 'active', 'possible', 'parked', 'closed', 'superseded'}
BASES = {'documented_implementation', 'reported_check', 'inspected_saved_result',
         'user_decision', 'user_correction', 'proposal', 'observed_record'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value, label):
    require(isinstance(value, str) and bool(value.strip()), f'{label}: required text')


def identity(value):
    require(isinstance(value, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', value), 'invalid stable ID')
    return value


def timestamp(value, label, optional=False):
    if value is None and optional:
        return
    text(value, label)
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        require(parsed.tzinfo is not None, f'{label}: timezone required')
    except (TypeError, ValueError) as error:
        raise ValueError(f'{label}: invalid timestamp') from error


def url(value):
    text(value, 'URL')
    require(not any(ord(c) < 33 for c in value) and '\\' not in value, 'unsafe URL')
    p = urlsplit(value)
    require(p.scheme == 'https' and bool(p.hostname) and not p.username and not p.password, 'only HTTPS evidence links allowed')


def indexed(items, label):
    require(isinstance(items, list), f'{label}: list required')
    result = {}
    for item in items:
        require(isinstance(item, dict), f'{label}: object required')
        key = identity(item.get('id'))
        require(key not in result, f'duplicate {label} ID: {key}')
        result[key] = item
    return result


def validate_evidence(e):
    for key in ('title', 'summary', 'access_note'):
        text(e.get(key), key)
    require(e.get('kind') in {'code', 'document', 'experiment', 'conversation'}, 'invalid evidence kind')
    require(e.get('basis') in BASES, 'invalid evidence basis')
    require(e.get('access') in {'checked', 'reported', 'unavailable'}, 'invalid evidence access')
    timestamp(e.get('checked_at'), 'checked_at')
    timestamp(e.get('occurred_at'), 'occurred_at', optional=True)
    require(bool(e.get('url') or e.get('local_path') or e.get('native_reference')), 'evidence location required')
    if e.get('url'):
        url(e['url'])
    if e.get('local_path'):
        text(e['local_path'], 'local_path')
    if e['kind'] == 'conversation':
        for key in ('conversation_id', 'message_id', 'excerpt', 'retrieval'):
            text(e.get(key), key)
        require(e.get('speaker') in {'user', 'assistant', 'worker'}, 'conversation speaker required')
        if e.get('provider') in {'claude-desktop', 'codex-desktop'}:
            text(e.get('native_reference'), 'native tool/session/message reference')
            text(e.get('message_reference_kind'), 'native message ID or observed tool position')
            # A native reference is displayed as text, never executed as a URI.
            # No invented public message link is required for local desktop chats.
        else:
            require(e.get('provider') in {None, 'chatgpt'}, 'unsupported conversation provider')
            p = urlsplit(e.get('url', ''))
            require(p.hostname == 'chatgpt.com' and p.path == '/c/' + e['conversation_id'], 'conversation link mismatch')
            require(p.query == 'messageId=' + e['message_id'], 'message link mismatch')
        if e['basis'] in {'user_decision', 'user_correction'}:
            require(e['speaker'] == 'user', 'user provenance requires user message')


def validate_project(project, papers):
    require(project.get('schema_version') == 1, 'unsupported project schema')
    identity(project.get('id'))
    for key in ('title', 'summary', 'coverage'):
        text(project.get(key), key)
    require(type(project.get('revision')) is int and project['revision'] >= 0, 'invalid revision')
    sources = indexed(project.get('sources'), 'source')
    for s in sources.values():
        for key in ('title', 'branch', 'revision', 'role', 'mapping_note'):
            text(s.get(key), key)
        url(s.get('url'))
        require(s.get('mapping_status') in {'confirmed', 'candidate'}, 'invalid mapping status')
        timestamp(s.get('checked_at'), 'source checked_at')
    evidence = indexed(project.get('evidence'), 'evidence')
    for e in evidence.values():
        validate_evidence(e)
        if e.get('source_id'):
            require(e['source_id'] in sources, 'unknown evidence source')
            text(e.get('source_revision'), 'source_revision')
    nodes = indexed(project.get('checkpoints'), 'checkpoint')
    for c in nodes.values():
        for key in ('title', 'goal', 'status_note'):
            text(c.get(key), key)
        require(c.get('status') in STATUSES, 'invalid checkpoint status')
        timestamp(c.get('recorded_at'), 'recorded_at')
        timestamp(c.get('occurred_at'), 'occurred_at', optional=True)
        require(isinstance(c.get('evidence_ids'), list) and c['evidence_ids'], 'checkpoint evidence required')
        require(all(x in evidence for x in c['evidence_ids']), 'unknown checkpoint evidence')
        for section in ('done', 'next'):
            require(isinstance(c.get(section), list) and c[section], f'{section}: entries required')
            for claim in c[section]:
                require(isinstance(claim, dict), 'claim must be an object')
                text(claim.get('text'), section)
                require(claim.get('basis') in BASES, 'invalid claim basis')
                require(isinstance(claim.get('evidence_ids'), list) and claim['evidence_ids'], 'claim evidence required')
                require(all(x in evidence for x in claim['evidence_ids']), 'unknown claim evidence')
        for p in c.get('papers', []):
            require(p.get('paper_id') in papers, 'unknown paper reference')
            text(p.get('relevance'), 'paper relevance')
    edges = project.get('relationships')
    require(isinstance(edges, list), 'relationships required')
    seen, children = set(), {n: [] for n in nodes}
    incoming = {n: 0 for n in nodes}
    for edge in edges:
        a, b = edge.get('from'), edge.get('to')
        require(a in nodes and b in nodes, 'unknown relationship endpoint')
        require(a != b, 'self-link')
        require(edge.get('kind') == 'progression', 'only progression edges; references belong in evidence/papers')
        require((a, b) not in seen, 'duplicate relationship')
        text(edge.get('rationale'), 'relationship rationale')
        seen.add((a, b)); children[a].append(b); incoming[b] += 1
    ready = [n for n, count in incoming.items() if count == 0]
    visited = 0
    while ready:
        n = ready.pop(); visited += 1
        for child in children[n]:
            incoming[child] -= 1
            if incoming[child] == 0:
                ready.append(child)
    require(visited == len(nodes), 'progression cycle')
    receipts = indexed(project.get('applied_updates'), 'update receipt')
    require(len({r.get('source_revision_key') for r in receipts.values()}) == len(receipts), 'duplicate source update')
    for r in receipts.values():
        for key in ('digest', 'semantic_digest', 'source_revision_key', 'summary'):
            text(r.get(key), key)
        timestamp(r.get('applied_at'), 'applied_at')
    return project


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def normalized_doi(value):
    if value is None or value == '':
        return None
    text(value, 'DOI')
    value = value.strip().casefold()
    for prefix in ('https://doi.org/', 'http://doi.org/', 'https://dx.doi.org/', 'doi:'):
        if value.startswith(prefix):
            value = value[len(prefix):].strip()
            break
    require(bool(re.fullmatch(r'10\.\d{4,9}/[^\s<>]+', value)), 'invalid DOI')
    return value


def paper_identity_keys(item):
    """Strong identifiers plus a conservative exact metadata fingerprint."""
    keys = []
    doi = normalized_doi(item.get('doi'))
    if doi:
        keys.append(('doi', doi))
    for origin in item.get('origins', []):
        keys.append(('origin', origin['source_id'], origin['record_id']))
    if item.get('year') and item.get('authors'):
        normalize = lambda value: ''.join(c for c in value.casefold() if c.isalnum())
        keys.append(('metadata', normalize(item['title']), item['year'], tuple(normalize(a) for a in item['authors'])))
    return keys


def load_papers(root):
    from obsidian_vault import project_paper
    papers, identities = {}, {}
    for p in sorted((root / 'library/papers').glob('*.json')):
        item = read_json(p)
        identity(item.get('id'))
        require(item['id'] == p.stem and item['id'] not in papers, 'paper identity mismatch')
        item = project_paper(root, item)
        for key in ('title', 'summary', 'access_note'):
            text(item.get(key), key)
        timestamp(item.get('checked_at'), 'paper checked_at')
        require(item.get('access') in {'checked', 'reference_only', 'unavailable'}, 'paper access required')
        require(bool(item.get('url') or item.get('local_path')), 'paper location required')
        if item.get('url'):
            url(item['url'])
        if item.get('source_url'):
            url(item['source_url'])
        require(isinstance(item.get('authors', []), list), 'paper authors must be a list')
        for author in item.get('authors', []):
            text(author, 'paper author')
        year = item.get('year')
        require(year is None or (type(year) is int and 1000 <= year <= 3000), 'invalid paper year')
        require(item.get('reading_status', 'metadata_only') in {'metadata_only', 'queued', 'reading', 'reviewed'}, 'invalid reading status')
        require(isinstance(item.get('origins', []), list), 'paper origins must be a list')
        for origin in item.get('origins', []):
            identity(origin.get('source_id')); text(origin.get('record_id'), 'origin record ID')
            url(origin.get('url')); timestamp(origin.get('checked_at'), 'origin checked_at')
        for key in paper_identity_keys(item):
            require(key not in identities or identities[key] == item['id'], f'duplicate paper identity: {item["id"]} and {identities.get(key)}')
            identities[key] = item['id']
        papers[item['id']] = item
    return papers


def paper_backlinks(papers, projects, links):
    """Derive reverse links, retaining context separately from paper summaries."""
    result = {p: {} for p in papers}
    by_project = {p['id']: p for p in projects}

    def add(paper_id, project_id, checkpoint_id, relevance, evidence_url=None):
        require(paper_id in papers, 'unknown linked paper')
        require(project_id in by_project, 'unknown paper-link project')
        project = by_project[project_id]
        checkpoint = None
        if checkpoint_id is not None:
            checkpoint = next((c for c in project['checkpoints'] if c['id'] == checkpoint_id), None)
            require(checkpoint is not None, 'unknown paper-link checkpoint')
        text(relevance, 'paper-link relevance')
        if evidence_url:
            url(evidence_url)
        key = (project_id, checkpoint_id)
        entry = result[paper_id].setdefault(key, {
            'project_id': project_id, 'project_title': project['title'],
            'checkpoint_id': checkpoint_id, 'checkpoint_title': checkpoint['title'] if checkpoint else None,
            'relevance': [], 'evidence_urls': []})
        if relevance not in entry['relevance']:
            entry['relevance'].append(relevance)
        if evidence_url and evidence_url not in entry['evidence_urls']:
            entry['evidence_urls'].append(evidence_url)

    for project in projects:
        for checkpoint in project['checkpoints']:
            for ref in checkpoint.get('papers', []):
                add(ref['paper_id'], project['id'], checkpoint['id'], ref['relevance'])
    for link in indexed(links, 'paper link').values():
        add(link.get('paper_id'), link.get('project_id'), link.get('checkpoint_id'), link.get('relevance'), link.get('evidence_url'))
    return {paper: list(contexts.values()) for paper, contexts in result.items()}


def load_library(root=ROOT):
    from obsidian_vault import vault_info
    from maintenance import dashboard_status
    papers = load_papers(root)
    projects = []
    for p in sorted((root / 'library/projects').glob('*.json')):
        item = validate_project(read_json(p), papers)
        require(item['id'] == p.stem, 'project filename/identity mismatch')
        projects.append(item)
    candidates = read_json(root / 'library/source-candidates.json')
    for item in indexed(candidates, 'source candidate').values():
        url(item.get('url')); text(item.get('note'), 'candidate note')
    workflow = read_json(root / 'library/workflow.json')
    for item in indexed(workflow.get('evidence'), 'workflow evidence').values():
        validate_evidence(item)
    source_file, link_file = root / 'library/paper-sources.json', root / 'library/paper-links.json'
    paper_sources = read_json(source_file) if source_file.exists() else []
    source_index = indexed(paper_sources, 'paper source')
    for source in source_index.values():
        text(source.get('title'), 'paper source title'); text(source.get('note'), 'paper source note')
        require(source.get('status') in {'available', 'unavailable', 'incomplete'}, 'invalid paper source status')
        timestamp(source.get('checked_at'), 'paper source checked_at')
        if source.get('url'):
            url(source['url'])
    for paper in papers.values():
        for origin in paper.get('origins', []):
            require(origin['source_id'] in source_index, 'unknown paper origin source')
    backlinks = paper_backlinks(papers, projects, read_json(link_file) if link_file.exists() else [])
    enriched = [{**paper, 'doi': normalized_doi(paper.get('doi')), 'backlinks': backlinks[paper['id']]} for paper in papers.values()]
    return {'projects': projects, 'papers': enriched, 'paper_sources': paper_sources, 'candidates': candidates, 'workflow': workflow, 'vault': vault_info(root), 'maintenance': dashboard_status(root)}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def apply_handoff(root, handoff, expected_digest):
    identity(handoff.get('id')); identity(handoff.get('project_id'))
    require(handoff.get('schema_version') == 1, 'unsupported handoff schema')
    for key in ('goal', 'completed', 'source_revision_key'):
        text(handoff.get(key), key)
    for key in ('findings', 'uncertainties', 'verification', 'next_actions', 'source_revisions'):
        require(isinstance(handoff.get(key), list) and handoff[key], f'{key} required')
    timestamp(handoff.get('recorded_at'), 'handoff recorded_at')
    timestamp(handoff.get('occurred_at'), 'handoff occurred_at', optional=True)
    path = root / 'library/projects' / (handoff['project_id'] + '.json')
    lock = root / 'library/.update.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise ValueError('update lock exists; inspect running writer before removing stale lock') from error
    temporary = None
    try:
        os.close(fd)
        original = path.read_bytes()
        project = validate_project(json.loads(original), load_papers(root))
        require(project['id'] == handoff['project_id'], 'project identity mismatch')
        hd = digest(canonical(handoff))
        semantic = {k: v for k, v in handoff.items() if k not in {'id', 'recorded_at', 'base_revision'}}
        sd = digest(canonical(semantic))
        for receipt in project['applied_updates']:
            if receipt['id'] == handoff['id']:
                require(receipt['digest'] == hd, 'same handoff ID has different content')
                return {'status': 'unchanged', 'revision': project['revision']}
            if receipt['source_revision_key'] == handoff['source_revision_key']:
                require(receipt['semantic_digest'] == sd, 'source update conflicts with applied content')
                return {'status': 'unchanged', 'revision': project['revision']}
        require(digest(original) == expected_digest, 'stale file digest; reread and reconcile human edits')
        require(project['revision'] == handoff.get('base_revision'), 'stale project revision')
        updated = copy.deepcopy(project)
        for key in ('evidence', 'checkpoints', 'relationships'):
            require(isinstance(handoff.get(key), list), f'handoff {key} required')
            updated[key].extend(handoff[key])
        updated['revision'] += 1
        updated['applied_updates'].append({
            'id': handoff['id'], 'digest': hd, 'semantic_digest': sd,
            'source_revision_key': handoff['source_revision_key'],
            'applied_at': datetime.now().astimezone().isoformat(),
            'summary': handoff['completed'], 'revision': updated['revision']})
        validate_project(updated, load_papers(root))
        with tempfile.NamedTemporaryFile(mode='wb', prefix='.' + path.stem, suffix='.tmp', dir=path.parent, delete=False) as f:
            temporary = Path(f.name)
            f.write((json.dumps(updated, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
            f.flush(); os.fsync(f.fileno())
        require(path.read_bytes() == original, 'concurrent file edit; update not applied')
        os.replace(temporary, path)
        return {'status': 'applied', 'revision': updated['revision'], 'digest': digest(path.read_bytes())}
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['validate', 'digest', 'apply'])
    parser.add_argument('file', nargs='?')
    parser.add_argument('--expected', help='SHA256 of the canonical project bytes previously read')
    args = parser.parse_args()
    try:
        if args.command == 'validate':
            data = load_library()
            print(json.dumps({'valid': True, 'projects': len(data['projects']), 'checkpoints': sum(len(p['checkpoints']) for p in data['projects']), 'papers': len(data['papers'])}))
        elif args.command == 'digest':
            require(args.file is not None, 'file required')
            print(digest(Path(args.file).read_bytes()))
        else:
            require(args.file is not None and args.expected is not None, 'file and --expected required')
            print(json.dumps(apply_handoff(ROOT, read_json(Path(args.file)), args.expected)))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'Library error: {error}\n')


if __name__ == '__main__':
    main()
