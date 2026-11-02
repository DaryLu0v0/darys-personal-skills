"""Private local attention snapshots and durable user decisions; no mailbox access."""
import argparse
import copy
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import os
import re

from library import ROOT, canonical, digest, identity, require, timestamp, url
from maintenance import atomic, bounded

STATES = {'active', 'resolved', 'snoozed', 'not_relevant'}
EVIDENCE = {'needs_verification', 'course_deadline_role_unverified', 'confirmed_upcoming', 'fyi'}

def private(root):
    return root / '.local/attention'

def read(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def aware(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.tzinfo is not None, 'time zone required')
    return parsed

def validate(snapshot):
    require(snapshot.get('schema_version') == 1, 'unsupported attention schema')
    identity(snapshot.get('id')); timestamp(snapshot.get('checked_at'), 'checked_at')
    aware(snapshot['checked_at'])
    bounded(snapshot.get('coverage'), 'coverage', 4000)
    accounts = snapshot.get('accounts')
    require(isinstance(accounts, list), 'accounts required')
    known = set()
    for account in accounts:
        require({'id','label'} <= set(account) <= {'id','label','email'}, 'unexpected account fields')
        if 'email' in account:
            require(isinstance(account['email'],str) and re.fullmatch(r'[^\s<>"@?&#]+@[^\s<>"@?&#]+',account['email']), 'invalid account email')
        identity(account['id']); bounded(account['label'], 'account label', 200)
        require(account['id'] not in known, 'duplicate account')
        known.add(account['id'])
    require(isinstance(snapshot.get('items'), list), 'items required')
    seen, source_ids = set(), set()
    allowed = {'id','title','section','priority','evidence_status','summary','action','source','dates','links','project_refs'}
    for item in snapshot['items']:
        require(set(item) <= allowed, 'unexpected attention fields; do not store email bodies or secrets')
        identity(item.get('id')); require(item['id'] not in seen, 'duplicate attention ID'); seen.add(item['id'])
        for key in ('title', 'summary', 'action'):
            bounded(item.get(key), key, 1500)
        require(item.get('section') in {'life','research'}, 'invalid section')
        require(item.get('priority') in {'high','medium','low'}, 'invalid priority')
        require(item.get('evidence_status') in EVIDENCE, 'invalid evidence status')
        source = item.get('source', {})
        require({'account_id','date','url'} <= set(source) <= {'account_id','date','url','rfc822_message_id','gmail_message_id','gmail_thread_id','message_id_checked_at'}, 'unexpected email source fields')
        if 'rfc822_message_id' in source:
            value=source['rfc822_message_id']
            require(isinstance(value,str) and len(value)<=1000, 'invalid RFC822 Message-ID')
            value=value.strip()
            if value.startswith('<') and value.endswith('>'): value=value[1:-1]
            require(re.fullmatch(r'[^\s<>"@]+@[^\s<>"@]+',value) is not None, 'invalid RFC822 Message-ID; API IDs are different')
        for field in ('gmail_message_id','gmail_thread_id'):
            if field in source: require(isinstance(source[field],str) and re.fullmatch(r'[0-9a-fA-F]{1,64}',source[field]), 'invalid Gmail API ID')
        if 'message_id_checked_at' in source: timestamp(source['message_id_checked_at'],'message ID checked_at')
        require(source['account_id'] in known, 'unknown source account')
        bounded(source['date'], 'source date', 80); url(source['url'])
        key = (source['account_id'], source['url'])
        require(key not in source_ids, 'duplicate source; use one canonical attention record')
        source_ids.add(key)
        for link in item.get('links', []):
            require(set(link) == {'title','url'}, 'invalid supporting link')
            bounded(link['title'], 'link title', 120); url(link['url'])
        for d in item.get('dates', []):
            require(set(d) == {'label','local','timezone'}, 'date must preserve timezone uncertainty')
            for field in d: bounded(d[field], 'date '+field, 160)
        require(isinstance(item.get('project_refs'), list), 'project_refs required')
        for ref in item['project_refs']: identity(ref)
    require(set(snapshot) == {'schema_version','id','checked_at','coverage','accounts','items'}, 'unexpected snapshot fields')
    return snapshot

@contextmanager
def locked(root):
    folder = private(root); folder.mkdir(parents=True, exist_ok=True)
    lock = folder / '.lock'
    try: fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error: raise ValueError('Attention writer active; retry after reviewing lock') from error
    try:
        with os.fdopen(fd, 'w') as f: f.write(str(os.getpid()))
        yield
    finally: lock.unlink(missing_ok=True)

def import_snapshot(root, path):
    path = Path(path).resolve()
    require(path.is_relative_to((root / '.local').resolve()), 'real snapshots must stay in ignored .local storage')
    raw = path.read_bytes(); require(len(raw) < 200_000, 'snapshot too large')
    incoming = validate(json.loads(raw.decode('utf-8-sig')))
    for item in incoming['items']:
        for ref in item['project_refs']:
            require((root / 'library/projects' / (ref+'.json')).is_file(), 'unconfirmed project reference')
    with locked(root):
        folder = private(root); archive = folder / 'snapshots' / (digest(raw)+'.json')
        if not archive.exists(): atomic(archive, raw, create_only=True)
        target = folder / 'records.json'
        previous_raw = target.read_bytes() if target.exists() else None
        current = read(target, {'schema_version':1,'accounts':{},'items':{},'receipts':{}})
        prior = current['receipts'].get(incoming['id'])
        if prior:
            require(prior == digest(raw), 'snapshot ID changed; original archive retained, use a reconciled ID')
            return {'status':'unchanged','items':len(current['items'])}
        if current.get('checked_at'):
            require(aware(incoming['checked_at']) >= aware(current['checked_at']), 'stale snapshot; review before merging')
        for account in incoming['accounts']:
            prior_account = current['accounts'].get(account['id'])
            require(prior_account is None or all(prior_account[k] == v for k,v in account.items() if k in prior_account), 'account identity changed')
            # Adding a verified email is enrichment. Older snapshots may omit it,
            # but cannot change an already recorded account identity.
            current['accounts'][account['id']] = {**(prior_account or {}), **account}
        for item in incoming['items']:
            prior_item = current['items'].get(item['id'])
            require(not prior_item or prior_item['source']['account_id'] == item['source']['account_id'], 'source account changed for same item')
            require(not any(k != item['id'] and (v['source']['account_id'], v['source']['url']) == (item['source']['account_id'], item['source']['url']) for k,v in current['items'].items()), 'source already indexed under another ID')
            current['items'][item['id']] = {**item, 'checked_at':incoming['checked_at']}
        current.update(checked_at=incoming['checked_at'], coverage=incoming['coverage'])
        current['receipts'][incoming['id']] = digest(raw)
        atomic(target, (json.dumps(current,ensure_ascii=False,indent=2)+'\n').encode(), expected=previous_raw, create_only=previous_raw is None)
        return {'status':'updated','items':len(current['items'])}

def decisions(root):
    return read(private(root)/'decisions.json', {'schema_version':1,'items':{},'journal':[]})

def projection(root):
    records = read(private(root)/'records.json', {'accounts':{},'items':{},'checked_at':None,'coverage':'No private attention snapshot imported yet.'})
    state = decisions(root)
    return {'schema_version':1,'checked_at':records['checked_at'],'coverage':records['coverage'],
            'accounts':list(records['accounts'].values()), 'items':[dict(copy.deepcopy(i),decision=state['items'].get(i['id'],{'status':'active'})) for i in records['items'].values()],
            'decision_revision':digest(canonical(state)), 'mode':'snapshot'}

def decide(root, request):
    require(set(request) == {'id','status','snooze_until','expected_revision'}, 'unexpected decision fields')
    identity(request['id']); require(request['status'] in STATES, 'invalid decision')
    until = request['snooze_until']
    if request['status'] == 'snoozed':
        require(isinstance(until,str) and aware(until) > datetime.now(timezone.utc), 'snooze must end in the future')
    else: require(until is None, 'only snoozed decisions have a wake time')
    with locked(root):
        require(request['id'] in read(private(root)/'records.json',{'items':{}})['items'], 'unknown attention item')
        path = private(root)/'decisions.json'; original = path.read_bytes() if path.exists() else None
        state = decisions(root)
        require(request['expected_revision'] == digest(canonical(state)), 'decision changed elsewhere; refresh before saving')
        old = state['items'].get(request['id'],{'status':'active','snooze_until':None})
        value = {'status':request['status'],'snooze_until':until}
        if all(old.get(k)==v for k,v in value.items()): return projection(root)
        value['updated_at'] = datetime.now(timezone.utc).isoformat()
        state['items'][request['id']] = value
        state['journal'].append({'id':request['id'],**value})
        atomic(path,(json.dumps(state,ensure_ascii=False,indent=2)+'\n').encode(),expected=original,create_only=original is None)
    return projection(root)

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('snapshot')
    args=parser.parse_args()
    try: print(json.dumps(import_snapshot(ROOT,Path(args.snapshot)),ensure_ascii=False))
    except (ValueError,KeyError,TypeError,OSError) as e: parser.exit(1,str(e)+'\n')
