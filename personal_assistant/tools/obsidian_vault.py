"""Read-only Obsidian note projection and conservative, one-way JSON migration."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote

try:
    import yaml
except ImportError as error:
    raise ImportError('Obsidian notes require PyYAML 6.x; see tools/requirements.txt') from error

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {'title', 'authors', 'year', 'doi', 'venue', 'type', 'isbn', 'tags', 'url',
          'source_url', 'local_path', 'access', 'access_note', 'checked_at',
          'summary_basis', 'reading_status'}


class NoteLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise ValueError('note frontmatter keys must be unique text')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


NoteLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def contained(base, relative, *, must_exist=True):
    if not isinstance(relative, str) or '\\' in relative or ':' in relative:
        raise ValueError('invalid vault-relative path')
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in {'.', '..'} for part in relative.split('/')):
        raise ValueError('vault path escapes its root')
    target = (base / relative).resolve()
    if not target.is_relative_to(base.resolve()):
        raise ValueError('vault path escapes its root')
    if must_exist and not target.is_file():
        raise ValueError(f'vault file missing: {relative}')
    return target


def vault_config(root):
    config = json.loads((root / 'library/vault.json').read_text(encoding='utf-8'))
    if config.get('schema_version') != 1:
        raise ValueError('unsupported vault configuration')
    vault = contained(root, config.get('path'), must_exist=False)
    if not vault.is_dir():
        raise ValueError('configured vault directory is missing')
    return config, vault


def open_uri(path):
    """Only the open action and one absolute known-file path; no write parameters."""
    if not path.is_file():
        raise ValueError('cannot link to a missing note')
    return 'obsidian://open?path=' + quote(str(path.resolve()), safe='')


def sections(body):
    result, current, fenced = {}, None, None
    for line in body.splitlines():
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            token = marker.group(1)[0]
            fenced = None if fenced == token else token if fenced is None else fenced
        match = re.match(r'^## (.+?)\s*$', line) if fenced is None else None
        if match:
            current = match.group(1)
            if current in result:
                raise ValueError(f'duplicate note section: {current}')
            result[current] = []
        elif current is not None:
            result[current].append(line)
    return {key: '\n'.join(lines).strip() for key, lines in result.items()}


def read_note(path):
    raw = path.read_text(encoding='utf-8-sig')
    if len(raw) > 1_000_000:
        raise ValueError('paper note exceeds the 1 MB text limit')
    match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)(.*)\Z', raw, re.S)
    if not match:
        raise ValueError(f'{path.name}: YAML frontmatter required')
    header, body = match.groups()
    try:
        if len(header) > 64_000 or any(isinstance(t, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken)) for t in yaml.scan(header)):
            raise ValueError('oversized frontmatter or YAML aliases are unsupported')
        metadata = yaml.load(header, Loader=NoteLoader)
    except yaml.YAMLError as error:
        raise ValueError(f'{path.name}: invalid YAML frontmatter') from error
    if not isinstance(metadata, dict):
        raise ValueError('note frontmatter must be an object')
    for key, value in metadata.items():
        if isinstance(value, dict) or (isinstance(value, list) and any(isinstance(v, (dict, list)) for v in value)):
            raise ValueError('use flat Obsidian properties, not nested metadata')
        if isinstance(value, (datetime, date)):
            metadata[key] = value.isoformat()
    parts = sections(body)
    if not parts.get('General summary'):
        raise ValueError(f'{path.name}: keep a nonempty ## General summary section')
    return metadata, body, parts


def vault_info(root):
    if not (root / 'library/vault.json').exists():
        return None
    config, vault = vault_config(root)
    home = vault / 'Welcome.md'
    return {'name': config['path'], 'absolute_path': str(vault),
            'home': {'absolute_path': str(home), 'uri': open_uri(home)} if home.is_file() else None}


def project_paper(root, manifest):
    if manifest.get('storage_version') != 2:
        return manifest
    if FIELDS.intersection(manifest) or 'summary' in manifest:
        raise ValueError('note-backed paper contains competing editable JSON fields')
    config, vault = vault_config(root)
    note = contained(vault, manifest.get('note_path'))
    if note.suffix.lower() != '.md':
        raise ValueError('paper note must be Markdown')
    metadata, body, parts = read_note(note)
    if metadata.get('id') != manifest['id']:
        raise ValueError('paper note ID does not match its stable manifest ID')
    # Arbitrary note properties cannot override provenance or computed link fields.
    editable = {key: metadata[key] for key in FIELDS if key in metadata}
    if 'labels' in metadata:
        editable['tags'] = metadata['labels']
    result = {**manifest, **editable, 'summary': parts['General summary'],
              'reading_notes': parts.get('Reading notes', ''),
              'relevance_notes': parts.get('Project relevance', ''), 'note_body': body,
              'obsidian': {'vault': config['path'], 'note_path': manifest['note_path'],
                           'absolute_path': str(note), 'uri': open_uri(note)}}
    pdf = metadata.get('pdf')
    if pdf:
        attachment = contained(vault, pdf, must_exist=False)
        if not pdf.startswith('Attachments/') or attachment.suffix.lower() != '.pdf':
            raise ValueError('PDF property must refer to Attachments/*.pdf inside the vault')
        result['pdf'] = {'path': pdf, 'available': attachment.is_file()}
    return result


def make_note(paper, contexts):
    metadata = {'id': paper['id']}
    for key in sorted(FIELDS):
        if key in paper:
            metadata['labels' if key == 'tags' else key] = paper[key]
    metadata.setdefault('reading_status', 'metadata_only')
    # JSON-valued YAML is accepted by Obsidian; its editor may save block-list YAML.
    header = '\n'.join(key + ': ' + json.dumps(value, ensure_ascii=False) for key, value in metadata.items())
    links = []
    for context in contexts:
        title = context['project_title'] + (' / ' + context['checkpoint_title'] if context['checkpoint_title'] else '')
        links.append(f'- {title}: canonical project `{context["project_id"]}`' +
                     (f', checkpoint `{context["checkpoint_id"]}`.' if context['checkpoint_id'] else '.'))
    return (f'---\n{header}\n---\n\n# {paper["title"]}\n\n'
            f'## General summary\n\n{paper["summary"]}\n\n'
            '## Reading notes\n\nNo reading notes recorded yet. Opening or attaching a PDF does not mark this reference as read.\n\n'
            '## Project relevance\n\nAdd your interpretation here after reading. Keep it separate from the general summary. '
            'Existing source-backed relationships remain in Hikari’s project and paper-link records.\n\n'
            '## Research records\n\n' + ('\n'.join(links) or 'No linked research records yet.') + '\n\n'
            '[Open research dashboard](http://127.0.0.1:8767/#research) · '
            '[Open literature dashboard](http://127.0.0.1:8767/#papers)\n\n'
            'The identifiers above are a migration-time navigation aid. Current relationships and provenance '
            'are shown in the dashboard; edits here do not rewrite historical checkpoints.\n\n'
            '## PDF and annotations\n\nNo PDF attachment is registered for this note. '
            'Keep page references and annotation excerpts here; leave the original PDF unchanged.\n')


def migrate(root=ROOT, folder='Hikari Research'):
    from library import load_library
    config_path = root / 'library/vault.json'
    if config_path.exists():
        config, vault = vault_config(root)
        if config['path'] != folder:
            raise ValueError('another vault is already configured; do not overwrite it')
        papers = load_library(root)['papers']
        if any(p.get('storage_version') != 2 for p in papers):
            raise ValueError('mixed migration state; review preserved originals before proceeding')
        return {'status': 'unchanged', 'notes': len(papers), 'vault': str(vault)}
    target = contained(root, folder, must_exist=False)
    if target.exists():
        raise ValueError('vault destination already exists; refusing to merge or overwrite')
    data = load_library(root)
    originals = {p: p.read_bytes() for p in sorted((root / 'library/papers').glob('*.json'))}
    recovery = root / 'library/migrations/obsidian-v1-original-papers.json'
    if recovery.exists():
        raise ValueError('migration recovery file already exists; inspect previous attempt')
    notes = {p['id']: make_note(p, p['backlinks']) for p in data['papers']}
    # Everything is prepared before writes; originals are retained before any replacement.
    target.mkdir()
    (target / 'Papers').mkdir(); (target / 'Attachments').mkdir()
    for paper_id, content in notes.items():
        (target / 'Papers' / (paper_id + '.md')).write_text(content, encoding='utf-8')
    recovery.parent.mkdir(exist_ok=True)
    recovery.write_text(json.dumps({'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
        'originals': {p.name: {'sha256': hashlib.sha256(raw).hexdigest(), 'content': raw.decode('utf-8')} for p, raw in originals.items()}}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    config_path.write_text(json.dumps({'schema_version': 1, 'path': folder,
        'paper_storage_version': 2, 'notes_authoritative': True}, indent=2) + '\n', encoding='utf-8')
    for path, original in originals.items():
        paper = json.loads(original)
        manifest = {k: v for k, v in paper.items() if k not in FIELDS and k != 'summary'}
        manifest.update(storage_version=2, note_path='Papers/' + paper['id'] + '.md')
        if path.read_bytes() != original:
            raise ValueError('paper changed concurrently; originals preserved, reconcile before continuing')
        temporary = path.with_suffix('.migration.tmp')
        with temporary.open('x', encoding='utf-8') as output:
            output.write(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        os.replace(temporary, path)
    load_library(root)
    return {'status': 'migrated', 'notes': len(notes), 'vault': str(target)}


def attach_existing_pdf(root, paper_id):
    """Explicit local copy from an already indexed source; never download/overwrite."""
    from library import load_papers, identity
    identity(paper_id)
    paper = load_papers(root)[paper_id]
    config, vault = vault_config(root)
    source = Path(paper.get('local_path', ''))
    if not source.is_file() or source.suffix.lower() != '.pdf':
        raise ValueError('indexed local source is not an existing PDF')
    source_bytes = source.read_bytes()
    if not source_bytes.startswith(b'%PDF-'):
        raise ValueError('source does not have a PDF header')
    relative = 'Attachments/' + paper_id + '.pdf'
    destination = contained(vault, relative, must_exist=False)
    note = contained(vault, paper['note_path'])
    original = note.read_bytes()
    metadata, body, _ = read_note(note)
    ledger_path = root / 'library/vault-attachments.json'
    ledger = json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else []
    if destination.exists():
        if metadata.get('pdf') == relative and destination.read_bytes() == source_bytes and any(x['paper_id'] == paper_id for x in ledger):
            return {'status': 'unchanged', 'paper_id': paper_id}
        raise ValueError('attachment already exists; preserve it and reconcile manually')
    if metadata.get('pdf'):
        raise ValueError('note already points to a PDF; preserve the existing attachment')
    with destination.open('xb') as output:
        output.write(source_bytes)
    # Insert a single property and append an embed; preserve every prior body byte.
    raw = original.decode('utf-8')
    newline = '\r\n' if '\r\n' in raw else '\n'
    updated = raw.replace('---' + newline, '---' + newline + 'pdf: ' + json.dumps(relative) + newline, 1)
    updated += '\n\n### Local PDF copy\n\n![[ ' + relative + ' ]]\n'
    updated = updated.replace('![[ ' + relative + ' ]]', '![[' + relative + ']]')
    updated = updated.replace('No PDF attachment is registered for this note.', 'The registered local PDF copy is embedded below.')
    if note.read_bytes() != original:
        raise ValueError('note changed concurrently; copy retained, note not overwritten')
    note.write_text(updated, encoding='utf-8', newline='')
    ledger.append({'paper_id': paper_id, 'source_path': str(source), 'attachment': relative,
                   'sha256': hashlib.sha256(source_bytes).hexdigest(), 'bytes': len(source_bytes),
                   'copied_at': datetime.now(timezone.utc).isoformat(),
                   'note': 'Verified existing file/header and copied bytes; paper content not read.'})
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'status': 'attached', 'paper_id': paper_id, 'bytes': len(source_bytes)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['migrate', 'attach-pdf'])
    parser.add_argument('--paper')
    args = parser.parse_args()
    try:
        result = migrate() if args.command == 'migrate' else attach_existing_pdf(ROOT, args.paper)
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'Vault error: {error}\n')
