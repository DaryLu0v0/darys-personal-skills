from __future__ import annotations

from difflib import SequenceMatcher
from typing import Iterable

from .models import EditNote, ReviewScore


_PREFIX = "% TEX-REVIEW"


def _comment(label: str, value: str = "") -> list[str]:
    lines = value.splitlines() or [""]
    return [f"{_PREFIX} {label}{(': ' + line) if line else ''}\n" for line in lines]


def _matching_explanation(
    original: str,
    replacement: str,
    notes: Iterable[EditNote],
    fallback: str,
) -> tuple[str, str]:
    original_flat = " ".join(original.split())
    replacement_flat = " ".join(replacement.split())
    for note in reversed(tuple(notes)):
        note_original = " ".join(note.original.split())
        note_replacement = " ".join(note.replacement.split())
        original_match = note_original and (
            note_original in original_flat or original_flat in note_original
        )
        replacement_match = note_replacement and (
            note_replacement in replacement_flat or replacement_flat in note_replacement
        )
        if original_match or replacement_match:
            return note.category, note.explanation
    return "scientific-edit", fallback


def annotate_revision(
    original: str,
    candidate: str,
    *,
    baseline: ReviewScore,
    final: ReviewScore,
    summaries: Iterable[str] = (),
    notes: Iterable[EditNote] = (),
    preference: str = "scientific",
) -> str:
    """Return original LaTeX plus comment-only proposed edits."""
    summary_list = tuple(summaries)
    note_list = tuple(notes)
    output: list[str] = []
    output.extend(_comment("REPORT-BEGIN"))
    output.extend(_comment("preference", preference))
    output.extend(
        _comment(
            "measurement",
            f"Grammarly AI likelihood {baseline.ai_generated:.4f} -> {final.ai_generated:.4f}; "
            f"correctness deficit {baseline.issue_level:.4f} -> {final.issue_level:.4f}",
        )
    )
    output.extend(
        _comment(
            "provenance",
            "Grammarly supplied aggregate scores; explanations are scientific-editor rationale, "
            "not Grammarly explanations.",
        )
    )
    if summary_list:
        for index, summary in enumerate(summary_list, start=1):
            output.extend(_comment(f"accepted-rationale-{index:02d}", summary))
    else:
        output.extend(_comment("status", "No candidate revision was accepted."))
    output.extend(_comment("REPORT-END"))

    original_lines = original.splitlines(keepends=True)
    candidate_lines = candidate.splitlines(keepends=True)
    matcher = SequenceMatcher(a=original_lines, b=candidate_lines, autojunk=False)
    suggestion = 0
    fallback = summary_list[-1] if summary_list else "No accepted editor rationale is available."
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            output.extend(original_lines[i1:i2])
            continue

        suggestion += 1
        original_text = "".join(original_lines[i1:i2])
        replacement_text = "".join(candidate_lines[j1:j2])
        category, explanation = _matching_explanation(
            original_text, replacement_text, note_list, fallback
        )
        output.extend(_comment(f"SUGGESTION-{suggestion:03d}-BEGIN"))
        output.extend(_comment("category", category))
        output.extend(_comment("rationale", explanation))
        if replacement_text:
            output.extend(_comment("proposed-replacement"))
            for line in replacement_text.splitlines():
                output.append(f"{_PREFIX} > {line}\n")
        else:
            output.extend(_comment("proposed-replacement", "delete the following original text"))
        output.extend(_comment(f"SUGGESTION-{suggestion:03d}-END"))
        output.extend(original_lines[i1:i2])

    return "".join(output)


def remove_review_comments(annotated: str) -> str:
    """Remove this tool's comments; useful for verifying source preservation."""
    return "".join(
        line for line in annotated.splitlines(keepends=True) if not line.startswith(_PREFIX)
    )
