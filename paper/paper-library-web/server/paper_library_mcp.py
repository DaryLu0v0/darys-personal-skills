#!/usr/bin/env python3
"""MCP adapter for the local paper-library engine.

The server intentionally keeps the vault private and exposes a bounded tool
surface. It can run over stdio for Codex or behind OpenAI Secure MCP Tunnel for
ChatGPT on the web.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import threading
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations


_WRITE_LOCK = threading.RLock()
_CORE: Any | None = None


def _engine_path() -> Path:
    explicit = os.environ.get("PAPER_LIBRARY_ENGINE", "").strip()
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    plugin_path = Path(__file__).resolve()
    candidates.append(plugin_path.parents[2] / "paper-library" / "scripts" / "paper_library.py")
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    searched = ", ".join(str(path) for path in candidates)
    raise RuntimeError(f"Paper-library engine not found. Checked: {searched}")


def _core() -> Any:
    global _CORE
    if _CORE is not None:
        return _CORE
    engine = _engine_path()
    spec = importlib.util.spec_from_file_location("paper_library_web_core", engine)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load paper-library engine: {engine}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _CORE = module
    return module


def _config_path(core: Any) -> Path:
    explicit = os.environ.get("PAPER_LIBRARY_CONFIG", "").strip()
    if explicit:
        return core.resolve_config_path(explicit)
    detected = core.resolve_config_path(None)
    if detected.exists():
        return detected
    # Preserve the user's established project/vault split without requiring a
    # machine-specific path in the plugin manifest.
    for candidate in (
        Path("E:/paper/.paper-library.json"),
        Path("E:/paper/.paper-obsidian.json"),
        Path.home() / ".paper-library.json",
    ):
        if candidate.exists():
            return candidate
    raise RuntimeError(
        "Paper-library config not found. Set PAPER_LIBRARY_CONFIG to .paper-library.json "
        "or .paper-obsidian.json."
    )


def _library() -> tuple[Any, dict[str, Any], Path, Path]:
    core = _core()
    config_path = _config_path(core)
    config = core.load_config(config_path)
    vault = core.resolve_vault(config)
    return core, config, vault, config_path


def _entry_payload(core: Any, entry: Any, vault: Path, *, include_note: bool = False) -> dict[str, Any]:
    payload = core.note_result(entry, vault)
    payload.pop("score", None)
    if include_note:
        payload["note_markdown"] = entry.body
        payload["metadata"] = entry.metadata
    return payload


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
WRITE_SAFE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)

mcp = FastMCP(
    "paper-library",
    instructions=(
        "Search before saving to avoid duplicates. Read tools inspect one configured private "
        "paper vault. Write tools may create or update paper notes and rebuild the index, but "
        "never delete files. Confirm the target paper before updates."
    ),
    stateless_http=True,
)


@mcp.tool(
    title="Paper library status",
    description="Check the configured private paper vault, record count, integrity, and label counts.",
    annotations=READ_ONLY,
    structured_output=True,
)
def library_status() -> dict[str, Any]:
    core, config, vault, config_path = _library()
    entries = core.load_notes(vault, config)
    id_counts: dict[str, int] = {}
    labels = {key: {} for key in ("status", "fields", "topics", "methods", "tags")}
    incomplete = []
    for entry in entries:
        paper_id = str(entry.metadata.get("paper_id", ""))
        if paper_id:
            id_counts[paper_id] = id_counts.get(paper_id, 0) + 1
        missing = [key for key in ("paper_id", "title", "status") if not entry.metadata.get(key)]
        if missing:
            incomplete.append({"note_path": str(entry.path), "missing": missing})
        for key in labels:
            value = entry.metadata.get(key, [] if key != "status" else "")
            values = value if isinstance(value, list) else ([value] if value else [])
            for item in values:
                bucket = labels[key]
                bucket[str(item)] = bucket.get(str(item), 0) + 1
    duplicates = sorted(paper_id for paper_id, count in id_counts.items() if count > 1)
    return {
        "healthy": not duplicates and not incomplete,
        "config_path": str(config_path.resolve()),
        "vault_path": str(vault),
        "papers": len(entries),
        "duplicate_ids": duplicates,
        "incomplete_records": incomplete,
        "labels": labels,
    }


@mcp.tool(
    title="Search papers",
    description="Search saved paper titles, authors, labels, and reading notes with optional metadata filters.",
    annotations=READ_ONLY,
    structured_output=True,
)
def search_papers(
    query: str = "",
    field: str = "",
    topic: str = "",
    method: str = "",
    tag: str = "",
    status: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    core, config, vault, _ = _library()
    if status and status not in core.STATUSES:
        raise ValueError(f"status must be one of: {', '.join(core.STATUSES)}")
    args = argparse.Namespace(
        query=query,
        field=field or None,
        topic=topic or None,
        method=method or None,
        tag=tag or None,
        status=status or None,
        limit=limit,
    )
    selected = core.selected_entries(args, vault, config)
    return {
        "query": query,
        "count": len(selected),
        "results": [core.note_result(entry, vault, score) for entry, score in selected],
    }


@mcp.tool(
    title="Get paper",
    description="Retrieve one saved paper by stable ID, DOI, filename, or unique title text, including its reading note.",
    annotations=READ_ONLY,
    structured_output=True,
)
def get_paper(identifier: str) -> dict[str, Any]:
    core, config, vault, _ = _library()
    entry = core.match_identifier(core.load_notes(vault, config), identifier)
    return _entry_payload(core, entry, vault, include_note=True)


@mcp.tool(
    title="Add paper",
    description=(
        "Create a deduplicated paper record from authoritative metadata and optional Markdown reading notes. "
        "Search first; an existing match is returned without overwrite unless update_existing is true."
    ),
    annotations=WRITE_SAFE,
    structured_output=True,
)
def add_paper(
    title: str,
    authors: list[str] | None = None,
    year: str = "",
    venue: str = "",
    doi: str = "",
    source_url: str = "",
    status: str = "interested",
    priority: str = "normal",
    fields: list[str] | None = None,
    topics: list[str] | None = None,
    methods: list[str] | None = None,
    tags: list[str] | None = None,
    why_saved: str = "",
    reading_notes: str = "",
    update_existing: bool = False,
) -> dict[str, Any]:
    core, config, vault, config_path = _library()
    if not title.strip():
        raise ValueError("title is required")
    if status not in core.STATUSES:
        raise ValueError(f"status must be one of: {', '.join(core.STATUSES)}")
    if priority not in core.PRIORITIES:
        raise ValueError(f"priority must be one of: {', '.join(core.PRIORITIES)}")
    if reading_notes.startswith("---\n"):
        raise ValueError("reading_notes must not contain YAML frontmatter")
    args = argparse.Namespace(
        config=str(config_path),
        vault=None,
        source=source_url,
        title=title,
        author=authors or [],
        year=year,
        venue=venue,
        doi=doi,
        url=source_url,
        status=status,
        priority=priority,
        field=fields or [],
        topic=topics or [],
        method=methods or [],
        tag=tags or [],
        why_saved=why_saved,
        no_copy_pdf=True,
    )
    with _WRITE_LOCK:
        result = core.command_add(args)
        entry = core.match_identifier(core.load_notes(vault, config), str(result["paper_id"]))
        if result["action"] == "existing" and not update_existing:
            payload = _entry_payload(core, entry, vault)
            payload["action"] = "existing"
            payload["overwritten"] = False
            return payload
        metadata = dict(entry.metadata)
        metadata.update(
            {
                "title": title.strip(),
                "authors": [item.strip() for item in (authors or []) if item.strip()],
                "year": year.strip(),
                "venue": venue.strip(),
                "status": status,
                "priority": priority,
                "updated": core.today_iso(),
            }
        )
        if doi:
            metadata["doi"] = core.normalize_doi(doi)
        if source_url:
            metadata["url"] = core.canonical_url(source_url)
            metadata["source_type"] = "url"
            metadata["source_ref"] = metadata["url"]
        metadata["fields"] = core.merge_unique(metadata.get("fields", []), fields or [])
        metadata["topics"] = core.merge_unique(metadata.get("topics", []), topics or [])
        metadata["methods"] = core.merge_unique(metadata.get("methods", []), methods or [])
        metadata["tags"] = core.merge_unique(metadata.get("tags", []), tags or [])
        body = reading_notes.strip() if reading_notes.strip() else entry.body
        core.write_note(entry.path, metadata, body)
        payload = _entry_payload(core, core.NoteEntry(entry.path, metadata, body), vault)
        payload["action"] = result["action"] if result["action"] == "created" else "updated"
        payload["overwritten"] = result["action"] == "existing"
        return payload


@mcp.tool(
    title="Update paper",
    description="Update one confirmed paper's state, labels, reading note, or reading log without deleting files.",
    annotations=WRITE_SAFE,
    structured_output=True,
)
def update_paper(
    identifier: str,
    status: str = "",
    priority: str = "",
    fields: list[str] | None = None,
    topics: list[str] | None = None,
    methods: list[str] | None = None,
    tags: list[str] | None = None,
    reading_notes: str = "",
    reading_log: str = "",
    replace_labels: bool = False,
) -> dict[str, Any]:
    core, config, vault, _ = _library()
    if status and status not in core.STATUSES:
        raise ValueError(f"status must be one of: {', '.join(core.STATUSES)}")
    if priority and priority not in core.PRIORITIES:
        raise ValueError(f"priority must be one of: {', '.join(core.PRIORITIES)}")
    if reading_notes.startswith("---\n"):
        raise ValueError("reading_notes must not contain YAML frontmatter")
    with _WRITE_LOCK:
        entry = core.match_identifier(core.load_notes(vault, config), identifier)
        metadata = dict(entry.metadata)
        if status:
            metadata["status"] = status
        if priority:
            metadata["priority"] = priority
        for key, values in (
            ("fields", fields),
            ("topics", topics),
            ("methods", methods),
            ("tags", tags),
        ):
            if replace_labels:
                metadata[key] = core.normalize_labels(values or [])
            elif values:
                metadata[key] = core.merge_unique(metadata.get(key, []), values)
        body = reading_notes.strip() if reading_notes.strip() else entry.body
        if reading_log.strip():
            marker = "## Reading Log"
            line = f"- {core.today_iso()}: {reading_log.strip()}"
            if marker not in body:
                body = body.rstrip() + f"\n\n{marker}\n\n{line}\n"
            elif line not in body:
                body = body.rstrip() + f"\n\n{line}\n"
        metadata["updated"] = core.today_iso()
        core.write_note(entry.path, metadata, body)
        payload = _entry_payload(core, core.NoteEntry(entry.path, metadata, body), vault)
        payload["action"] = "updated"
        return payload


@mcp.tool(
    title="Export paper context",
    description="Return a bounded corpus of matching saved reading notes for field review or brainstorming.",
    annotations=READ_ONLY,
    structured_output=True,
)
def export_context(
    query: str = "",
    field: str = "",
    topic: str = "",
    method: str = "",
    tag: str = "",
    status: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    if limit < 1 or limit > 50:
        raise ValueError("limit must be between 1 and 50")
    core, config, vault, _ = _library()
    args = argparse.Namespace(
        query=query,
        field=field or None,
        topic=topic or None,
        method=method or None,
        tag=tag or None,
        status=status or None,
        limit=limit,
    )
    selected = core.selected_entries(args, vault, config)
    return {
        "scope": {
            "query": query,
            "field": field,
            "topic": topic,
            "method": method,
            "tag": tag,
            "status": status,
            "limit": limit,
        },
        "count": len(selected),
        "coverage_warning": "This is a selected personal library, not an exhaustive field review.",
        "papers": [
            {**core.note_result(entry, vault, score), "note_markdown": entry.body}
            for entry, score in selected
        ],
    }


@mcp.tool(
    title="Rebuild paper index",
    description="Refresh the static Obsidian paper-library index after confirmed paper writes.",
    annotations=WRITE_SAFE,
    structured_output=True,
)
def rebuild_index() -> dict[str, Any]:
    core, _, _, config_path = _library()
    args = argparse.Namespace(config=str(config_path), vault=None)
    with _WRITE_LOCK:
        result = core.command_index(args)
    return {**result, "action": "rebuilt"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the private paper library over MCP.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default=os.environ.get("PAPER_LIBRARY_MCP_TRANSPORT", "stdio"),
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
