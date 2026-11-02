"""Explicitly synthetic examples; never reads a user's research or mailbox data."""
from pathlib import Path
import copy
import json
import shutil

STAMP = '2026-01-01T00:00:00Z'
CODE_ROOT = Path(__file__).resolve().parents[1]

def write(root, name, data):
    p = root / name; p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def evidence(id, kind='document', basis='observed_record'):
    e = dict(id=id, title='Synthetic example evidence', kind=kind, basis=basis,
        summary='Fictional example for demonstrating provenance; no real result or conversation.',
        access='checked', access_note='Synthetic fixture only; nothing was fetched or executed.',
        checked_at=STAMP, occurred_at=None, url='https://example.test/evidence/'+id)
    if kind == 'conversation':
        e.pop('url'); e.update(provider='codex-desktop', conversation_id='synthetic-thread',
            message_id='synthetic-message', message_reference_kind='synthetic fixture, not a real native ID',
            native_reference='Synthetic native-interface example; not a real session', speaker='user',
            excerpt='Fictional user decision: compare both sample approaches.', retrieval='Generated fixture, not a transcript.')
    return e

def node(id, title, status, evidence_ids):
    return dict(id=id,title=title,status=status,status_note='Synthetic demonstration checkpoint.',
        goal='Illustrate a research checkpoint with explicit evidence and next steps.',
        done=[dict(text='This fictional example demonstrates the record format; it is not a research claim.',basis='observed_record',evidence_ids=evidence_ids)],
        next=[dict(text='Replace the example with a reviewed source-backed handoff in your local data.',basis='proposal',evidence_ids=evidence_ids)],
        evidence_ids=evidence_ids,occurred_at=None,recorded_at=STAMP,papers=[])

def blank_project(id='sample-research', title='Sample research — synthetic demo'):
    return dict(schema_version=1,id=id,title=title,summary='Fictional branching research example.',
        coverage='Synthetic example only. No real project, paper or conversation is represented.',
        revision=0,sources=[],evidence=[],checkpoints=[],relationships=[],applied_updates=[])

def sample_handoff():
    nodes=[node('foundation','Example foundation','completed',['sample-document']),
           node('prototype','Example prototype','completed',['sample-document']),
           node('evaluation','Example evaluation','active',['sample-document']),
           node('synthesis','Combine both branches','possible',['sample-document','sample-user']),
           node('parked-idea','Parked alternative','parked',['sample-document'])]
    nodes[3]['papers']=[dict(paper_id='sample-paper-b',relevance='Synthetic context-specific relevance, separate from the general paper summary.')]
    edges=[dict(**{'from':a,'to':b},kind='progression',rationale='Synthetic progression example.')
        for a,b in [('foundation','prototype'),('foundation','evaluation'),('prototype','synthesis'),('evaluation','synthesis'),('foundation','parked-idea')]]
    return dict(schema_version=1,id='sample-initial-update',project_id='sample-research',base_revision=0,
        source_revision_key='synthetic-version-one',recorded_at=STAMP,occurred_at=None,
        goal='Demonstrate a safe end-to-end update.',completed='Synthetic graph example added.',
        findings=['Fictional example only.'],uncertainties=['No real research is represented.'],
        verification=['Schema and replay tests only.'],next_actions=['Review actual source evidence before making claims.'],
        source_revisions=['synthetic-version-one'],evidence=[evidence('sample-document'),evidence('sample-user','conversation','user_decision')],checkpoints=nodes,relationships=edges)

def paper(suffix):
    id='sample-paper-'+suffix
    return dict(id=id,title='Synthetic reference '+suffix.upper()+' — not a real paper',
        authors=['Example, Alex','Example, Blair','Example, Casey','Example, Devon'],year=2026,
        doi='10.0000/sample-'+suffix,type='article',url='https://example.test/papers/'+suffix,
        access='reference_only',access_note='Synthetic metadata. No PDF was fetched or read.',
        summary='Fictional reference used to demonstrate one canonical note with several research links.',
        reading_status='metadata_only',checked_at=STAMP,
        origins=[dict(source_id='synthetic-bibliography',record_id=id,url='https://example.test/bibliography/'+suffix,checked_at=STAMP)])

def batch():
    return dict(schema_version=1,id='synthetic-batch',provider='codex-desktop',scope='all-projects',
        report_date='2026-01-01',recorded_at=STAMP,
        coverage=dict(listing_complete=False,note='Synthetic example, not a real read.',gaps=['No real sessions were inspected.']),
        projects=[dict(project_key='codex-desktop:local:synthetic-project',title='Synthetic project',host='local',working_directory='SYNTHETIC_WORKSPACE',identity_basis='Synthetic fixture, not a discovered folder.')],
        sessions=[dict(session_id='synthetic-thread',project_key='codex-desktop:local:synthetic-project',title='Synthetic conversation',source_revision='synthetic-turn',source_updated_at=None,native_reference='Synthetic native-interface example',
            read=dict(status='partial',message_refs=['synthetic-message'],next_cursor=None,note='Synthetic bounded-read shape.',gaps=['No real history was read.']),
            events=[dict(message_ref='synthetic-message',speaker='user',basis='user_decision',occurred_at=None,summary='Fictional user requested comparing sample approaches.',verification='Synthetic fixture; not an actual user message.',evidence_urls=[])] )])

def prepare(root, *, demo=True, migrate_notes=True, assets=True):
    """Create a new isolated dataset, refusing any existing data or vault directory."""
    from library import apply_handoff, digest, load_library
    from maintenance import empty_state
    from obsidian_vault import migrate
    root=Path(root)
    if any((root/p).exists() for p in ['library','Hikari Research']):
        raise ValueError('Data or vault already exists; preserve it and reconcile manually.')
    for name in ['projects','papers','handoffs','inbox/codex-desktop','inbox/claude-desktop','maintenance/plans','migrations']:
        (root/'library'/name).mkdir(parents=True,exist_ok=True)
    write(root,'library/source-candidates.json',[])
    write(root,'library/workflow.json',dict(schema_version=1,operation='Local records; no schedules or source connections configured.',evidence=[]))
    write(root,'library/paper-links.json',[])
    write(root,'library/paper-sources.json',[dict(id='synthetic-bibliography',title='Synthetic example bibliography',status='incomplete',note='Fictional metadata, not a real bibliography or read paper.',checked_at=STAMP)] if demo else [])
    write(root,'library/maintenance/state.json',empty_state())
    if demo:
        for suffix in 'abc':write(root,'library/papers/sample-paper-'+suffix+'.json',paper(suffix))
        write(root,'library/projects/sample-research.json',blank_project())
        second=blank_project('sample-secondary','Secondary path — synthetic demo')
        second['evidence']=[evidence('secondary-document')]
        second['checkpoints']=[node('secondary-idea','Possible investigation','possible',['secondary-document'])]
        write(root,'library/projects/sample-secondary.json',second)
        update=sample_handoff();write(root,'library/handoffs/sample-initial-update.json',update)
        path=root/'library/projects/sample-research.json';apply_handoff(root,update,digest(path.read_bytes()))
    if migrate_notes:
        migrate(root)
        (root/'Hikari Research/Welcome.md').write_text('# Research vault\n\nMarkdown notes are authoritative; the dashboard projects them read-only.\n\n'+('This vault contains synthetic examples, not real research.\n' if demo else 'Add paper notes with validated metadata and stable IDs.\n'),encoding='utf8')
    if assets and root.resolve()!=CODE_ROOT.resolve():shutil.copytree(CODE_ROOT/'dashboard',root/'dashboard')
    return load_library(root)
