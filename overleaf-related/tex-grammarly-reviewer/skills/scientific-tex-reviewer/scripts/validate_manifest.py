#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


def _line_column(source: str, offset: int) -> tuple[int, int]:
    line = source.count("\n", 0, offset) + 1
    last_newline = source.rfind("\n", 0, offset)
    column = offset + 1 if last_newline == -1 else offset - last_newline
    return line, column


def validate(manifest: dict[str, Any], source: str, source_name: str) -> dict[str, Any]:
    errors: list[str] = []
    source_info = manifest.get("source")
    if not isinstance(source_info, dict):
        errors.append("manifest.source must be an object")
        source_info = {}

    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if source_info.get("sha256") != digest:
        errors.append("source SHA-256 does not match manifest")
    if source_info.get("characters") != len(source):
        errors.append("source character count does not match manifest")
    if source_info.get("filename") != source_name:
        errors.append(
            f"source filename mismatch: manifest={source_info.get('filename')!r}, actual={source_name!r}"
        )

    publication = manifest.get("publication")
    if not isinstance(publication, dict) or publication.get("status") != "not-published":
        errors.append("manifest publication status must be 'not-published'")

    reviews = manifest.get("reviews")
    if not isinstance(reviews, list):
        errors.append("manifest.reviews must be an array")
        reviews = []

    ids: set[str] = set()
    role_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    comment_count = 0
    for review_index, review in enumerate(reviews):
        if not isinstance(review, dict):
            errors.append(f"reviews[{review_index}] must be an object")
            continue
        reviewer_id = review.get("reviewer_id")
        if not isinstance(reviewer_id, str) or not reviewer_id:
            errors.append(f"reviews[{review_index}] has invalid reviewer_id")
            reviewer_id = "unknown"
        comments = review.get("comments")
        if not isinstance(comments, list):
            errors.append(f"reviews[{review_index}].comments must be an array")
            continue
        for comment_index, comment in enumerate(comments):
            path = f"reviews[{review_index}].comments[{comment_index}]"
            if not isinstance(comment, dict):
                errors.append(f"{path} must be an object")
                continue
            comment_id = comment.get("comment_id")
            if not isinstance(comment_id, str) or not comment_id:
                errors.append(f"{path} has invalid comment_id")
                continue
            if comment_id in ids:
                errors.append(f"duplicate comment_id: {comment_id}")
            ids.add(comment_id)
            anchor = comment.get("anchor_text")
            if not isinstance(anchor, str) or not anchor:
                errors.append(f"{comment_id}: anchor_text is empty or invalid")
                continue
            offsets: list[int] = []
            cursor = 0
            while True:
                position = source.find(anchor, cursor)
                if position == -1:
                    break
                offsets.append(position)
                cursor = position + 1
            if len(offsets) != 1:
                errors.append(f"{comment_id}: anchor occurs {len(offsets)} times; expected exactly 1")
                continue
            start = offsets[0]
            end = start + len(anchor)
            if comment.get("start_offset") != start or comment.get("end_offset") != end:
                errors.append(f"{comment_id}: stored offsets do not match exact anchor")
            start_line, start_column = _line_column(source, start)
            end_line, end_column = _line_column(source, end)
            expected_positions = {
                "start_line": start_line,
                "start_column": start_column,
                "end_line": end_line,
                "end_column": end_column,
            }
            for key, expected in expected_positions.items():
                if comment.get(key) != expected:
                    errors.append(f"{comment_id}: {key} does not match exact anchor")
            body = comment.get("overleaf_comment")
            if not isinstance(body, str) or not body.strip():
                errors.append(f"{comment_id}: overleaf_comment is empty or invalid")
            severity = comment.get("severity")
            if severity not in {"info", "minor", "major", "blocking"}:
                errors.append(f"{comment_id}: invalid severity {severity!r}")
            confidence = comment.get("confidence")
            if (
                isinstance(confidence, bool)
                or not isinstance(confidence, (int, float))
                or not 0 <= confidence <= 1
            ):
                errors.append(f"{comment_id}: confidence must be in [0, 1]")
            role_counts[reviewer_id] = role_counts.get(reviewer_id, 0) + 1
            severity_key = str(severity)
            severity_counts[severity_key] = severity_counts.get(severity_key, 0) + 1
            comment_count += 1

    return {
        "valid": not errors,
        "source_sha256": digest,
        "comments": comment_count,
        "by_reviewer": role_counts,
        "by_severity": severity_counts,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate an Overleaf comment manifest against an exact UTF-8 .tex source."
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("source", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        source = args.source.read_text(encoding="utf-8")
        result = validate(manifest, source, args.source.name)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
