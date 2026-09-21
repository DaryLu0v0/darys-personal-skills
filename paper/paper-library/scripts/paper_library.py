#!/usr/bin/env python3
"""Maintain an Obsidian-compatible personal paper library.

The helper deliberately uses only the Python standard library. It stores
structured Markdown notes, performs conservative duplicate detection, and
exports bounded corpora for later model-assisted synthesis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit, urlunsplit


CONFIG_NAMES = (".paper-library.json", ".paper-obsidian.json")
STATUSES = ("interested", "to-read", "reading", "read", "archived")
PRIORITIES = ("low", "normal", "high")
SCHEMA_VERSION = 1


class LibraryError(RuntimeError):
    """A concise, user-facing library error."""


@dataclass(frozen=True)
class NoteEntry:
    path: Path
    metadata: dict[str, Any]
    body: str


def today_iso() -> str:
    return date.today().isoformat()


def default_config() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "vault_path": "",
        "notes_folder": "Literature/Papers",
        "attachments_folder": "Literature/PDFs",
        "reviews_folder": "Literature/Reviews",
        "index_note": "Literature/Paper Library.md",
        "copy_pdfs": True,
        "default_status": "interested",
        "default_priority": "normal",
        "default_tags": ["paper"],
    }


def resolve_config_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env_path = os.environ.get("PAPER_LIBRARY_CONFIG", "").strip()
    if env_path:
        return Path(env_path).expanduser()
    current = Path.cwd().resolve()
    for directory in (current, *current.parents):
        for name in CONFIG_NAMES:
            candidate = directory / name
            if candidate.exists():
                return candidate
    return Path(CONFIG_NAMES[0])


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise LibraryError(
            f"Config not found: {path}. Run `paper_library.py init --vault <path>` first."
        )
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LibraryError(f"Cannot read config {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise LibraryError(f"Config must be a JSON object: {path}")
    config = default_config()
    config.update(loaded)
    return config


def resolve_vault(config: dict[str, Any], override: str | None = None) -> Path:
    raw = (override or str(config.get("vault_path", ""))).strip()
    if not raw:
        raise LibraryError("No vault path is configured.")
    vault = Path(raw).expanduser().resolve()
    if not vault.is_dir():
        raise LibraryError(f"Vault directory does not exist: {vault}")
    return vault


def normalize_doi(value: str) -> str:
    doi = value.strip().lower()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    return doi.strip().rstrip(".")


def doi_from_url(value: str) -> str:
    if not value:
        return ""
    parts = urlsplit(value)
    if parts.netloc.lower() not in {"doi.org", "dx.doi.org"}:
        return ""
    return normalize_doi(unquote(parts.path.lstrip("/")))


def canonical_url(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise LibraryError(f"Invalid paper URL: {value}")
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def normalize_label(value: str) -> str:
    label = value.strip().lower().lstrip("#")
    label = re.sub(r"[^a-z0-9]+", "-", label).strip("-")
    return label


def normalize_labels(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        label = normalize_label(value)
        if label and label not in seen:
            seen.add(label)
            result.append(label)
    return result


def merge_unique(*groups: Iterable[str]) -> list[str]:
    return normalize_labels(value for group in groups for value in group)


def slugify(value: str, max_length: int = 72) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "paper"
    return slug[:max_length].rstrip("-") or "paper"


def extract_arxiv_id(url: str) -> str:
    if not url:
        return ""
    match = re.search(r"arxiv\.org/(?:abs|pdf)/([^/?#]+)", url, flags=re.IGNORECASE)
    if not match:
        return ""
    return re.sub(r"v\d+$", "", match.group(1), flags=re.IGNORECASE).lower()


def stable_paper_id(*, doi: str, url: str, title: str, year: str) -> str:
    if doi:
        return f"doi:{normalize_doi(doi)}"
    arxiv_id = extract_arxiv_id(url)
    if arxiv_id:
        return f"arxiv:{arxiv_id}"
    if url:
        digest = hashlib.sha256(canonical_url(url).encode("utf-8")).hexdigest()[:16]
        return f"url:{digest}"
    basis = f"{normalize_text(title)}|{year.strip()}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"title:{digest}"


def yaml_scalar(value: Any) -> str:
    if value is None or value == "":
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def parse_scalar(value: str) -> Any:
    raw = value.strip()
    if raw == "[]":
        return []
    if raw == "true":
        return True
    if raw == "false":
        return False
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if raw.startswith('"'):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return raw


METADATA_ORDER = (
    "type",
    "schema_version",
    "paper_id",
    "title",
    "authors",
    "year",
    "venue",
    "doi",
    "url",
    "status",
    "priority",
    "fields",
    "topics",
    "methods",
    "tags",
    "source_type",
    "source_ref",
    "pdf",
    "added",
    "updated",
)
LIST_KEYS = {"authors", "fields", "topics", "methods", "tags"}


def render_frontmatter(metadata: dict[str, Any]) -> str:
    lines = ["---"]
    keys = list(METADATA_ORDER) + sorted(set(metadata) - set(METADATA_ORDER))
    for key in keys:
        if key not in metadata:
            continue
        value = metadata[key]
        if key in LIST_KEYS:
            values = list(value or [])
            if values:
                lines.append(f"{key}:")
                lines.extend(f"  - {yaml_scalar(item)}" for item in values)
            else:
                lines.append(f"{key}: []")
        else:
            lines.append(f"{key}: {yaml_scalar(value)}")
    lines.extend(["---", ""])
    return "\n".join(lines)


def split_note(text: str) -> tuple[dict[str, Any], str]:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized
    end = normalized.find("\n---\n", 4)
    if end < 0:
        return {}, normalized
    data: dict[str, Any] = {}
    current_key = ""
    for line in normalized[4:end].splitlines():
        if line.startswith("  - ") and current_key:
            data.setdefault(current_key, []).append(parse_scalar(line[4:]))
            continue
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        current_key = key.strip()
        data[current_key] = [] if not raw.strip() else parse_scalar(raw)
    return data, normalized[end + len("\n---\n") :].lstrip("\n")


def default_body(title: str, source_note: str = "") -> str:
    source_line = source_note.strip() or "Source registered; reading notes not yet completed."
    return "\n".join(
        [
            f"# {title}",
            "",
            "## Why I Saved This",
            "",
            source_line,
            "",
            "## One-line Takeaway",
            "",
            "- ",
            "",
            "## Summary",
            "",
            "",
            "## Key Contributions",
            "",
            "- ",
            "",
            "## Claims and Evidence",
            "",
            "| Claim | Evidence | Source location | Confidence |",
            "| --- | --- | --- | --- |",
            "|  |  |  |  |",
            "",
            "## Methods",
            "",
            "",
            "## Results",
            "",
            "",
            "## Limitations",
            "",
            "- ",
            "",
            "## Questions",
            "",
            "- ",
            "",
            "## Connections",
            "",
            "- ",
            "",
            "## Ideas and Hypotheses",
            "",
            "- ",
            "",
            "## Reading Log",
            "",
            f"- {today_iso()}: Added to the paper library.",
            "",
        ]
    )


def load_notes(vault: Path, config: dict[str, Any]) -> list[NoteEntry]:
    notes_dir = vault / str(config["notes_folder"])
    entries: list[NoteEntry] = []
    if not notes_dir.exists():
        return entries
    for path in sorted(notes_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        metadata, body = split_note(text)
        if metadata.get("type") == "paper":
            entries.append(NoteEntry(path=path, metadata=metadata, body=body))
    return entries


def note_result(entry: NoteEntry, vault: Path, score: int = 0) -> dict[str, Any]:
    metadata = entry.metadata
    return {
        "paper_id": metadata.get("paper_id", ""),
        "title": metadata.get("title", entry.path.stem),
        "authors": metadata.get("authors", []),
        "year": metadata.get("year", ""),
        "venue": metadata.get("venue", ""),
        "doi": metadata.get("doi", ""),
        "url": metadata.get("url", ""),
        "status": metadata.get("status", ""),
        "priority": metadata.get("priority", ""),
        "fields": metadata.get("fields", []),
        "topics": metadata.get("topics", []),
        "methods": metadata.get("methods", []),
        "tags": metadata.get("tags", []),
        "note_path": str(entry.path),
        "note_relative": entry.path.relative_to(vault).as_posix(),
        "score": score,
    }


def find_duplicate(entries: list[NoteEntry], metadata: dict[str, Any]) -> NoteEntry | None:
    wanted_id = str(metadata.get("paper_id", ""))
    wanted_doi = normalize_doi(str(metadata.get("doi", "")))
    wanted_url = str(metadata.get("url", ""))
    wanted_title = normalize_text(str(metadata.get("title", "")))
    wanted_year = str(metadata.get("year", ""))
    for entry in entries:
        item = entry.metadata
        if wanted_id and str(item.get("paper_id", "")) == wanted_id:
            return entry
        if wanted_doi and normalize_doi(str(item.get("doi", ""))) == wanted_doi:
            return entry
        item_url = str(item.get("url", ""))
        if wanted_url and item_url:
            try:
                if canonical_url(item_url) == wanted_url:
                    return entry
            except LibraryError:
                pass
        if (
            wanted_title
            and normalize_text(str(item.get("title", ""))) == wanted_title
            and str(item.get("year", "")) == wanted_year
        ):
            return entry
    return None


def infer_title(source: str) -> str:
    if not source:
        return "Untitled paper"
    if re.match(r"^https?://", source, flags=re.IGNORECASE):
        path = unquote(urlsplit(source).path)
        stem = Path(path).stem
    else:
        stem = Path(source).stem
    return re.sub(r"[_-]+", " ", stem).strip() or "Untitled paper"


def classify_source(source: str) -> tuple[str, str, str]:
    if not source:
        return "manual", "", ""
    if re.match(r"^https?://", source, flags=re.IGNORECASE):
        url = canonical_url(source)
        return "url", url, url
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise LibraryError(f"Source file does not exist: {path}")
    if path.suffix.lower() != ".pdf":
        raise LibraryError(f"Only local PDF sources are supported: {path}")
    return "pdf", str(path), ""


def write_note(path: Path, metadata: dict[str, Any], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_frontmatter(metadata) + body.rstrip() + "\n", encoding="utf-8")


def command_init(args: argparse.Namespace) -> dict[str, Any]:
    config_path = resolve_config_path(args.config)
    if config_path.exists() and not args.force:
        raise LibraryError(f"Config already exists: {config_path}. Use --force to replace it.")
    vault = Path(args.vault).expanduser().resolve()
    if not vault.is_dir():
        raise LibraryError(f"Vault directory does not exist: {vault}")
    config = default_config()
    config["vault_path"] = str(vault)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for key in ("notes_folder", "attachments_folder", "reviews_folder"):
        (vault / str(config[key])).mkdir(parents=True, exist_ok=True)
    return {"config_path": str(config_path.resolve()), "vault_path": str(vault)}


def library_context(args: argparse.Namespace) -> tuple[Path, dict[str, Any], Path]:
    config_path = resolve_config_path(args.config)
    config = load_config(config_path)
    vault = resolve_vault(config, getattr(args, "vault", None))
    return config_path, config, vault


def command_add(args: argparse.Namespace) -> dict[str, Any]:
    _, config, vault = library_context(args)
    source_type, source_ref, source_url = classify_source(args.source or "")
    url = canonical_url(args.url) if args.url else source_url
    doi = normalize_doi(args.doi or "") or doi_from_url(url)
    title = (args.title or infer_title(args.source or "")).strip()
    status = args.status or str(config.get("default_status", "interested"))
    priority = args.priority or str(config.get("default_priority", "normal"))
    if status not in STATUSES:
        raise LibraryError(f"Unknown status: {status}")
    if priority not in PRIORITIES:
        raise LibraryError(f"Unknown priority: {priority}")
    metadata: dict[str, Any] = {
        "type": "paper",
        "schema_version": SCHEMA_VERSION,
        "paper_id": stable_paper_id(doi=doi, url=url, title=title, year=args.year or ""),
        "title": title,
        "authors": [item.strip() for item in (args.author or []) if item.strip()],
        "year": (args.year or "").strip(),
        "venue": (args.venue or "").strip(),
        "doi": doi,
        "url": url,
        "status": status,
        "priority": priority,
        "fields": normalize_labels(args.field or []),
        "topics": normalize_labels(args.topic or []),
        "methods": normalize_labels(args.method or []),
        "tags": merge_unique(config.get("default_tags", []), args.tag or []),
        "source_type": source_type,
        "source_ref": source_ref,
        "pdf": "",
        "added": today_iso(),
        "updated": today_iso(),
    }
    existing = find_duplicate(load_notes(vault, config), metadata)
    if existing:
        result = note_result(existing, vault)
        result["action"] = "existing"
        return result

    if source_type == "pdf":
        pdf_path = Path(source_ref)
        if bool(config.get("copy_pdfs", True)) and not args.no_copy_pdf:
            target_dir = vault / str(config["attachments_folder"])
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / pdf_path.name
            if target.resolve() != pdf_path.resolve():
                shutil.copy2(pdf_path, target)
            metadata["pdf"] = f"[[{target.relative_to(vault).as_posix()}]]"
        else:
            metadata["pdf"] = str(pdf_path)

    suffix = hashlib.sha256(str(metadata["paper_id"]).encode("utf-8")).hexdigest()[:10]
    year_prefix = f"{metadata['year']}-" if metadata["year"] else ""
    filename = f"{year_prefix}{slugify(title)}--{suffix}.md"
    path = vault / str(config["notes_folder"]) / filename
    write_note(path, metadata, default_body(title, args.why_saved or ""))
    result = note_result(NoteEntry(path, metadata, default_body(title)), vault)
    result["action"] = "created"
    return result


def match_identifier(entries: list[NoteEntry], identifier: str) -> NoteEntry:
    needle = identifier.strip().lower()
    exact: list[NoteEntry] = []
    partial: list[NoteEntry] = []
    normalized_needle_doi = normalize_doi(needle)
    for entry in entries:
        metadata = entry.metadata
        candidates = {
            str(metadata.get("paper_id", "")).lower(),
            normalize_doi(str(metadata.get("doi", ""))),
            entry.path.name.lower(),
            entry.path.stem.lower(),
        }
        if needle in candidates or (normalized_needle_doi and normalized_needle_doi in candidates):
            exact.append(entry)
        elif needle in str(metadata.get("title", "")).lower():
            partial.append(entry)
    matches = exact or partial
    if not matches:
        raise LibraryError(f"No paper matches: {identifier}")
    if len(matches) > 1:
        titles = "; ".join(str(item.metadata.get("title", item.path.stem)) for item in matches[:5])
        raise LibraryError(f"Identifier is ambiguous: {identifier}. Matches: {titles}")
    return matches[0]


def command_update(args: argparse.Namespace) -> dict[str, Any]:
    _, config, vault = library_context(args)
    entries = load_notes(vault, config)
    entry = match_identifier(entries, args.identifier)
    metadata = dict(entry.metadata)
    body = entry.body
    scalar_updates = {
        "status": args.status,
        "priority": args.priority,
        "venue": args.venue,
        "url": canonical_url(args.url) if args.url else None,
        "doi": normalize_doi(args.doi) if args.doi else None,
    }
    for key, value in scalar_updates.items():
        if value is not None:
            metadata[key] = value
    if args.doi or args.url:
        metadata["paper_id"] = stable_paper_id(
            doi=str(metadata.get("doi", "")),
            url=str(metadata.get("url", "")),
            title=str(metadata.get("title", "")),
            year=str(metadata.get("year", "")),
        )
        duplicate = find_duplicate([item for item in entries if item.path != entry.path], metadata)
        if duplicate:
            raise LibraryError(f"Updated identity would duplicate: {duplicate.path}")
    if args.replace_labels:
        metadata["fields"] = normalize_labels(args.field or [])
        metadata["topics"] = normalize_labels(args.topic or [])
        metadata["methods"] = normalize_labels(args.method or [])
        metadata["tags"] = normalize_labels(args.tag or [])
    else:
        for key, values in (
            ("fields", args.field),
            ("topics", args.topic),
            ("methods", args.method),
            ("tags", args.tag),
        ):
            metadata[key] = merge_unique(metadata.get(key, []), values or [])
    if args.reading_notes:
        notes_path = Path(args.reading_notes).expanduser().resolve()
        if not notes_path.is_file():
            raise LibraryError(f"Reading notes file does not exist: {notes_path}")
        body = notes_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        if body.startswith("---\n"):
            raise LibraryError("Reading notes must not contain YAML frontmatter.")
    if args.reading_log:
        marker = "## Reading Log"
        line = f"- {today_iso()}: {args.reading_log.strip()}"
        if marker in body:
            body = body.rstrip() + "\n" if not body.rstrip().endswith(line) else body
            position = body.find(marker) + len(marker)
            next_heading = body.find("\n## ", position)
            if next_heading < 0:
                body = body.rstrip() + "\n\n" + line + "\n"
            else:
                body = body[:next_heading].rstrip() + "\n\n" + line + "\n" + body[next_heading:]
        else:
            body = body.rstrip() + f"\n\n{marker}\n\n{line}\n"
    metadata["updated"] = today_iso()
    write_note(entry.path, metadata, body)
    result = note_result(NoteEntry(entry.path, metadata, body), vault)
    result["action"] = "updated"
    return result


def entry_matches(entry: NoteEntry, args: argparse.Namespace) -> tuple[bool, int]:
    metadata = entry.metadata
    filters = (
        ("fields", getattr(args, "field", None)),
        ("topics", getattr(args, "topic", None)),
        ("methods", getattr(args, "method", None)),
        ("tags", getattr(args, "tag", None)),
    )
    for key, wanted in filters:
        if wanted and normalize_label(wanted) not in normalize_labels(metadata.get(key, [])):
            return False, 0
    status = getattr(args, "status", None)
    if status and metadata.get("status") != status:
        return False, 0
    query = normalize_text(getattr(args, "query", "") or "")
    if not query:
        return True, 1
    tokens = query.split()
    title = normalize_text(str(metadata.get("title", "")))
    authors = normalize_text(" ".join(str(x) for x in metadata.get("authors", [])))
    labels = normalize_text(
        " ".join(
            str(x)
            for key in ("fields", "topics", "methods", "tags")
            for x in metadata.get(key, [])
        )
    )
    body = normalize_text(entry.body)
    haystack = " ".join((title, authors, labels, body))
    if not all(token in haystack for token in tokens):
        return False, 0
    score = 0
    if query in title:
        score += 100
    score += sum(20 for token in tokens if token in title)
    score += sum(10 for token in tokens if token in authors)
    score += sum(8 for token in tokens if token in labels)
    score += sum(1 for token in tokens if token in body)
    return True, score


def selected_entries(args: argparse.Namespace, vault: Path, config: dict[str, Any]) -> list[tuple[NoteEntry, int]]:
    selected: list[tuple[NoteEntry, int]] = []
    for entry in load_notes(vault, config):
        matched, score = entry_matches(entry, args)
        if matched:
            selected.append((entry, score))
    selected.sort(key=lambda item: (-item[1], str(item[0].metadata.get("title", "")).lower()))
    return selected[: args.limit]


def command_find(args: argparse.Namespace) -> dict[str, Any]:
    _, config, vault = library_context(args)
    selected = selected_entries(args, vault, config)
    return {
        "query": args.query or "",
        "count": len(selected),
        "results": [note_result(entry, vault, score) for entry, score in selected],
    }


def command_context(args: argparse.Namespace) -> dict[str, Any]:
    _, config, vault = library_context(args)
    selected = selected_entries(args, vault, config)
    bundle = {
        "generated": today_iso(),
        "scope": {
            "query": args.query or "",
            "field": args.field or "",
            "topic": args.topic or "",
            "method": args.method or "",
            "tag": args.tag or "",
            "status": args.status or "",
            "limit": args.limit,
        },
        "count": len(selected),
        "coverage_warning": "This bundle represents the selected personal library, not an exhaustive field review.",
        "papers": [
            {**note_result(entry, vault, score), "note_markdown": entry.body}
            for entry, score in selected
        ],
    }
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {"output": str(output), "count": len(selected), "scope": bundle["scope"]}
    return bundle


def command_labels(args: argparse.Namespace) -> dict[str, Any]:
    _, config, vault = library_context(args)
    entries = load_notes(vault, config)
    result: dict[str, Any] = {"papers": len(entries)}
    for key in ("status", "fields", "topics", "methods", "tags"):
        counter: Counter[str] = Counter()
        for entry in entries:
            value = entry.metadata.get(key, [] if key != "status" else "")
            if isinstance(value, list):
                counter.update(str(item) for item in value)
            elif value:
                counter[str(value)] += 1
        result[key] = dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))
    return result


def command_index(args: argparse.Namespace) -> dict[str, Any]:
    _, config, vault = library_context(args)
    entries = load_notes(vault, config)
    index_path = vault / str(config["index_note"])
    lines = [
        "---",
        "type: paper-library-index",
        f"updated: {json.dumps(today_iso())}",
        "---",
        "",
        "# Paper Library",
        "",
        f"{len(entries)} papers. Updated {today_iso()}.",
        "",
    ]
    for status in STATUSES:
        group = [entry for entry in entries if entry.metadata.get("status") == status]
        if not group:
            continue
        lines.extend([f"## {status.replace('-', ' ').title()}", ""])
        for entry in sorted(group, key=lambda item: str(item.metadata.get("title", "")).lower()):
            rel = entry.path.relative_to(vault).as_posix().removesuffix(".md")
            title = entry.metadata.get("title", entry.path.stem)
            year = entry.metadata.get("year", "")
            suffix = f" ({year})" if year else ""
            labels = list(entry.metadata.get("fields", [])) + list(entry.metadata.get("topics", []))
            label_text = f" — {', '.join(labels)}" if labels else ""
            lines.append(f"- [[{rel}|{title}]]{suffix}{label_text}")
        lines.append("")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {"index_path": str(index_path), "papers": len(entries)}


def upgraded_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(metadata)
    title = str(upgraded.get("title", "")).strip()
    year = str(upgraded.get("year", "")).strip()
    doi = normalize_doi(str(upgraded.get("doi", "")))
    url = str(upgraded.get("url", "")).strip()
    if url:
        try:
            url = canonical_url(url)
        except LibraryError:
            pass
    doi = doi or doi_from_url(url)
    source_ref = str(upgraded.get("source_ref") or upgraded.get("source_pdf") or url)
    if url:
        source_type = "url"
    elif source_ref.lower().endswith(".pdf") or upgraded.get("pdf"):
        source_type = "pdf"
    else:
        source_type = "manual"
    status = str(upgraded.get("status", "interested"))
    if status not in STATUSES:
        status = "interested"
    priority = str(upgraded.get("priority", "normal"))
    if priority not in PRIORITIES:
        priority = "normal"
    upgraded.update(
        {
            "type": "paper",
            "schema_version": SCHEMA_VERSION,
            "paper_id": stable_paper_id(doi=doi, url=url, title=title, year=year),
            "title": title or "Untitled paper",
            "authors": list(upgraded.get("authors", []) or []),
            "year": year,
            "venue": str(upgraded.get("venue", "")),
            "doi": doi,
            "url": url,
            "status": status,
            "priority": priority,
            "fields": normalize_labels(upgraded.get("fields", []) or []),
            "topics": normalize_labels(upgraded.get("topics", []) or []),
            "methods": normalize_labels(upgraded.get("methods", []) or []),
            "tags": normalize_labels(upgraded.get("tags", []) or []),
            "source_type": source_type,
            "source_ref": source_ref,
            "pdf": str(upgraded.get("pdf", "")),
            "added": str(upgraded.get("added") or upgraded.get("created") or today_iso()),
            "updated": today_iso(),
        }
    )
    return upgraded


def command_migrate(args: argparse.Namespace) -> dict[str, Any]:
    _, config, vault = library_context(args)
    entries = load_notes(vault, config)
    candidates = [(entry, upgraded_metadata(entry.metadata)) for entry in entries]
    id_counts = Counter(str(metadata.get("paper_id", "")) for _, metadata in candidates)
    conflicts = sorted(paper_id for paper_id, count in id_counts.items() if paper_id and count > 1)
    changed: list[str] = []
    skipped: list[str] = []
    for entry, metadata in candidates:
        if metadata == entry.metadata:
            continue
        if str(metadata.get("paper_id", "")) in conflicts:
            skipped.append(str(entry.path))
            continue
        changed.append(str(entry.path))
        if args.apply:
            write_note(entry.path, metadata, entry.body)
    return {
        "mode": "applied" if args.apply else "preview",
        "papers": len(entries),
        "changed": len(changed),
        "changed_notes": changed,
        "conflicting_ids": conflicts,
        "skipped_notes": skipped,
    }


def command_doctor(args: argparse.Namespace) -> dict[str, Any]:
    config_path, config, vault = library_context(args)
    entries = load_notes(vault, config)
    id_counts = Counter(str(entry.metadata.get("paper_id", "")) for entry in entries)
    duplicate_ids = sorted(key for key, count in id_counts.items() if key and count > 1)
    incomplete = []
    for entry in entries:
        missing = [key for key in ("paper_id", "title", "status") if not entry.metadata.get(key)]
        if entry.metadata.get("status") and entry.metadata.get("status") not in STATUSES:
            missing.append("valid-status")
        if entry.metadata.get("priority") and entry.metadata.get("priority") not in PRIORITIES:
            missing.append("valid-priority")
        if missing:
            incomplete.append({"note_path": str(entry.path), "missing": missing})
    return {
        "healthy": not duplicate_ids and not incomplete,
        "config_path": str(config_path.resolve()),
        "vault_path": str(vault),
        "papers": len(entries),
        "duplicate_ids": duplicate_ids,
        "incomplete_records": incomplete,
        "notes_folder": str(vault / str(config["notes_folder"])),
        "attachments_folder": str(vault / str(config["attachments_folder"])),
    }


def add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--vault", help="Override the configured vault path.")


def add_filter_options(parser: argparse.ArgumentParser) -> None:
    add_common_options(parser)
    parser.add_argument("query", nargs="?", default="", help="All search terms must match.")
    parser.add_argument("--field")
    parser.add_argument("--topic")
    parser.add_argument("--method")
    parser.add_argument("--tag")
    parser.add_argument("--status", choices=STATUSES)
    parser.add_argument("--limit", type=int, default=50)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maintain a personal academic-paper library.")
    parser.add_argument("--config", help="Config path; otherwise auto-detected.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a machine-local library config.")
    init_parser.add_argument("--vault", required=True)
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=command_init)

    add_parser = subparsers.add_parser("add", help="Add a local PDF, URL, or manual record.")
    add_common_options(add_parser)
    add_parser.add_argument("source", nargs="?", default="")
    add_parser.add_argument("--title")
    add_parser.add_argument("--author", action="append")
    add_parser.add_argument("--year", default="")
    add_parser.add_argument("--venue", default="")
    add_parser.add_argument("--doi", default="")
    add_parser.add_argument("--url", default="")
    add_parser.add_argument("--status", choices=STATUSES)
    add_parser.add_argument("--priority", choices=PRIORITIES)
    add_parser.add_argument("--field", action="append")
    add_parser.add_argument("--topic", action="append")
    add_parser.add_argument("--method", action="append")
    add_parser.add_argument("--tag", action="append")
    add_parser.add_argument("--why-saved", default="")
    add_parser.add_argument("--no-copy-pdf", action="store_true")
    add_parser.set_defaults(func=command_add)

    update_parser = subparsers.add_parser("update", help="Update one existing paper note.")
    add_common_options(update_parser)
    update_parser.add_argument("identifier", help="Paper ID, DOI, filename, or unique title text.")
    update_parser.add_argument("--status", choices=STATUSES)
    update_parser.add_argument("--priority", choices=PRIORITIES)
    update_parser.add_argument("--venue")
    update_parser.add_argument("--doi")
    update_parser.add_argument("--url")
    update_parser.add_argument("--field", action="append")
    update_parser.add_argument("--topic", action="append")
    update_parser.add_argument("--method", action="append")
    update_parser.add_argument("--tag", action="append")
    update_parser.add_argument("--replace-labels", action="store_true")
    update_parser.add_argument("--reading-notes", help="Markdown body without frontmatter.")
    update_parser.add_argument("--reading-log")
    update_parser.set_defaults(func=command_update)

    find_parser = subparsers.add_parser("find", help="Search titles, labels, authors, and notes.")
    add_filter_options(find_parser)
    find_parser.set_defaults(func=command_find)

    context_parser = subparsers.add_parser("context", help="Export a bounded corpus for synthesis.")
    add_filter_options(context_parser)
    context_parser.add_argument("--output")
    context_parser.set_defaults(func=command_context)

    labels_parser = subparsers.add_parser("labels", help="Count the labels used in the library.")
    add_common_options(labels_parser)
    labels_parser.set_defaults(func=command_labels)

    index_parser = subparsers.add_parser("index", help="Rebuild the static Obsidian index.")
    add_common_options(index_parser)
    index_parser.set_defaults(func=command_index)

    migrate_parser = subparsers.add_parser("migrate", help="Preview or apply legacy-note metadata upgrades.")
    add_common_options(migrate_parser)
    migrate_parser.add_argument("--apply", action="store_true", help="Write upgrades; preview is the default.")
    migrate_parser.set_defaults(func=command_migrate)

    doctor_parser = subparsers.add_parser("doctor", help="Check configuration and record integrity.")
    add_common_options(doctor_parser)
    doctor_parser.set_defaults(func=command_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if hasattr(args, "limit") and args.limit < 1:
        print("paper-library: --limit must be positive", file=sys.stderr)
        return 2
    try:
        result = args.func(args)
    except (LibraryError, OSError, UnicodeError) as exc:
        print(f"paper-library: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
