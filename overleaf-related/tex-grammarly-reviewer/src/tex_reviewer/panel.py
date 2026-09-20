from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Protocol

from .models import (
    GrammarlyObservation,
    ReviewComment,
    ReviewScore,
    RoleReview,
    VenueProfile,
)
from .reviewers import ReviewerRole


class PanelReviewer(Protocol):
    def review(
        self,
        latex: str,
        score: ReviewScore,
        role: ReviewerRole,
        *,
        max_comments: int,
        grammarly_observations: tuple[GrammarlyObservation, ...] = (),
        venue_profile: VenueProfile = VenueProfile(),
    ) -> RoleReview: ...


@dataclass(frozen=True)
class PanelResult:
    manifest: dict[str, object]
    manifest_path: Path
    markdown_path: Path
    accepted_comments: int
    rejected_comments: int


def _line_column(source: str, offset: int) -> tuple[int, int]:
    line = source.count("\n", 0, offset) + 1
    last_newline = source.rfind("\n", 0, offset)
    column = offset + 1 if last_newline == -1 else offset - last_newline
    return line, column


def anchor_comment(source: str, comment: ReviewComment) -> ReviewComment:
    if not comment.anchor_text.strip():
        raise ValueError("empty anchor")
    occurrences: list[int] = []
    start = 0
    while True:
        index = source.find(comment.anchor_text, start)
        if index == -1:
            break
        occurrences.append(index)
        start = index + 1
    if not occurrences:
        raise ValueError("anchor is not an exact source substring")
    if len(occurrences) != 1:
        raise ValueError("anchor is not unique; reviewer must quote more context")
    start_offset = occurrences[0]
    end_offset = start_offset + len(comment.anchor_text)
    start_line, start_column = _line_column(source, start_offset)
    end_line, end_column = _line_column(source, end_offset)
    return replace(
        comment,
        start_offset=start_offset,
        end_offset=end_offset,
        start_line=start_line,
        start_column=start_column,
        end_line=end_line,
        end_column=end_column,
    )


def _comment_text(comment: ReviewComment) -> str:
    parts = [
        f"[{comment.reviewer_label}] [{comment.severity.upper()}] {comment.body}",
        f"Rationale: {comment.rationale}",
    ]
    if comment.suggestion:
        parts.append(f"Suggested action: {comment.suggestion}")
    if comment.requires_author_check:
        parts.append("Author check required: this point is an inference, not a verified fact.")
    parts.append(f"Confidence: {comment.confidence:.2f}")
    return "\n\n".join(parts)


def _markdown(manifest: dict[str, object]) -> str:
    lines = [
        "# Scientific review panel",
        "",
        "> AI-assisted pre-review. Verify every comment before publishing or acting on it.",
        "",
    ]
    for review in manifest["reviews"]:  # type: ignore[index]
        lines.extend(
            [
                f"## {review['reviewer_label']}",
                "",
                str(review["summary"]),
                "",
            ]
        )
        for comment in review["comments"]:
            lines.extend(
                [
                    f"### {comment['comment_id']} · {comment['severity']} · line {comment['start_line']}",
                    "",
                    f"> {comment['anchor_text']}",
                    "",
                    str(comment["overleaf_comment"]),
                    "",
                ]
            )
    if manifest["warnings"]:  # type: ignore[index]
        lines.extend(["## Validation warnings", ""])
        lines.extend(f"- {warning}" for warning in manifest["warnings"])  # type: ignore[index]
        lines.append("")
    return "\n".join(lines)


def generate_panel(
    source: str,
    *,
    filename: str,
    score: ReviewScore,
    reviewer: PanelReviewer,
    roles: tuple[ReviewerRole, ...],
    output_dir: Path,
    max_comments_per_reviewer: int = 12,
    grammarly_observations: tuple[GrammarlyObservation, ...] = (),
    venue_profile: VenueProfile = VenueProfile(),
) -> PanelResult:
    for index, observation in enumerate(grammarly_observations, start=1):
        occurrences = source.count(observation.anchor_text)
        if not observation.anchor_text.strip() or occurrences != 1:
            raise ValueError(
                f"Grammarly observation {index} anchor must be nonempty and occur exactly once; "
                f"found {occurrences}"
            )
    output_dir.mkdir(parents=True, exist_ok=False)
    reviews: list[dict[str, object]] = []
    warnings: list[str] = []
    accepted_count = 0
    rejected_count = 0
    seen: set[tuple[str, str, str]] = set()

    for role in roles:
        role_review = reviewer.review(
            source,
            score,
            role,
            max_comments=max_comments_per_reviewer,
            grammarly_observations=grammarly_observations,
            venue_profile=venue_profile,
        )
        comments: list[dict[str, object]] = []
        for raw_comment in role_review.comments[:max_comments_per_reviewer]:
            try:
                anchored = anchor_comment(source, raw_comment)
            except ValueError as exc:
                rejected_count += 1
                warnings.append(f"{role.reviewer_id}: rejected comment: {exc}")
                continue
            dedupe_key = (
                anchored.reviewer_id,
                anchored.anchor_text,
                anchored.body.strip().casefold(),
            )
            if dedupe_key in seen:
                rejected_count += 1
                warnings.append(f"{role.reviewer_id}: rejected duplicate comment")
                continue
            seen.add(dedupe_key)
            accepted_count += 1
            data = anchored.to_dict()
            data["comment_id"] = f"{role.short_label.upper()}-{len(comments) + 1:03d}"
            data["filename"] = filename
            data["overleaf_comment"] = _comment_text(anchored)
            comments.append(data)
        reviews.append(
            {
                "reviewer_id": role.reviewer_id,
                "reviewer_label": role.label,
                "summary": role_review.summary,
                "comments": comments,
            }
        )

    manifest: dict[str, object] = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "filename": filename,
            "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "characters": len(source),
        },
        "grammarly_measurement": score.to_dict(),
        "grammarly_observations": [
            observation.to_dict() for observation in grammarly_observations
        ],
        "venue_profile": venue_profile.to_dict(),
        "publication": {
            "target": "overleaf-native-comments",
            "status": "not-published",
            "requires_source_hash_match": True,
            "author_identity": "logged-in Overleaf account",
            "confirmation_required": True,
        },
        "reviews": reviews,
        "warnings": warnings,
    }
    manifest_path = output_dir / "overleaf-comments.json"
    markdown_path = output_dir / "review-panel.md"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(_markdown(manifest), encoding="utf-8")
    return PanelResult(
        manifest=manifest,
        manifest_path=manifest_path,
        markdown_path=markdown_path,
        accepted_comments=accepted_count,
        rejected_comments=rejected_count,
    )
