from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Protocol

from .annotations import annotate_revision
from .latex import LatexValidationError, latex_to_plain_text, validate_revision
from .models import EditNote, ReviewScore, Revision, score_is_acceptable


class Scorer(Protocol):
    def assess(self, text: str, filename: str = "manuscript.txt") -> ReviewScore: ...


class Editor(Protocol):
    def revise(
        self,
        latex: str,
        score: ReviewScore,
        *,
        attempt: int,
        feedback: str = "",
    ) -> Revision: ...


@dataclass(frozen=True)
class ReviewConfig:
    max_attempts: int = 5
    patience: int = 2
    target_issue_level: float = 0.05
    tolerance: float = 0.0
    preference: str = "scientific"


@dataclass(frozen=True)
class ReviewResult:
    latex: str
    annotated_latex: str
    baseline_score: ReviewScore
    score: ReviewScore
    stop_reason: str
    accepted_revisions: int
    attempts: int
    run_dir: Path


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def review_document(
    source: str,
    *,
    scorer: Scorer,
    editor: Editor,
    run_dir: Path,
    config: ReviewConfig,
) -> ReviewResult:
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "original.tex").write_text(source, encoding="utf-8")

    current = source
    score = scorer.assess(latex_to_plain_text(current))
    baseline_score = score
    history: list[dict[str, object]] = [
        {"attempt": 0, "status": "baseline", "score": score.to_dict()}
    ]
    accepted = 0
    accepted_summaries: list[str] = []
    accepted_notes: list[EditNote] = []
    failures = 0
    feedback = ""
    stop_reason = "maximum attempts reached"
    attempts_run = 0

    if score.issue_level <= config.target_issue_level:
        stop_reason = "correctness target satisfied by original"
    else:
        for attempt in range(1, config.max_attempts + 1):
            attempts_run = attempt
            revision = editor.revise(
                current, score, attempt=attempt, feedback=feedback
            )
            candidate_path = run_dir / f"attempt-{attempt:02d}-candidate.tex"
            candidate_path.write_text(revision.latex, encoding="utf-8")
            entry: dict[str, object] = {
                "attempt": attempt,
                "summary": revision.summary,
            }
            try:
                validate_revision(current, revision.latex)
            except LatexValidationError as exc:
                failures += 1
                feedback = f"Rejected by LaTeX safety validation: {exc}"
                entry.update({"status": "rejected-structure", "reason": str(exc)})
                history.append(entry)
            else:
                candidate_score = scorer.assess(latex_to_plain_text(revision.latex))
                entry["score"] = candidate_score.to_dict()
                if score_is_acceptable(
                    score, candidate_score, tolerance=config.tolerance
                ):
                    current = revision.latex
                    score = candidate_score
                    accepted += 1
                    accepted_summaries.append(revision.summary)
                    accepted_notes.extend(revision.notes)
                    failures = 0
                    feedback = "The previous revision was accepted; continue with smaller edits."
                    entry["status"] = "accepted"
                    (run_dir / f"accepted-{accepted:02d}.tex").write_text(
                        current, encoding="utf-8"
                    )
                else:
                    failures += 1
                    feedback = (
                        "Rejected because Grammarly correctness did not improve. "
                        f"Issue level {score.issue_level:.4f}->{candidate_score.issue_level:.4f}. "
                        "AI likelihood is reported for context only and is not an acceptance objective."
                    )
                    entry.update({"status": "rejected-score", "reason": feedback})
                history.append(entry)

            _write_json(run_dir / "history.json", history)
            if score.issue_level <= config.target_issue_level:
                stop_reason = "correctness target satisfied"
                break
            if failures >= config.patience:
                stop_reason = "stopped after consecutive rejected revisions"
                break

    annotated = annotate_revision(
        source,
        current,
        baseline=baseline_score,
        final=score,
        summaries=accepted_summaries,
        notes=accepted_notes,
        preference=config.preference,
    )
    (run_dir / "final-candidate.tex").write_text(current, encoding="utf-8")
    (run_dir / "review-comments.tex").write_text(annotated, encoding="utf-8")
    _write_json(run_dir / "history.json", history)
    _write_json(
        run_dir / "result.json",
        {
            "score": score.to_dict(),
            "stop_reason": stop_reason,
            "accepted_revisions": accepted,
            "attempts": attempts_run,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return ReviewResult(
        latex=current,
        annotated_latex=annotated,
        baseline_score=baseline_score,
        score=score,
        stop_reason=stop_reason,
        accepted_revisions=accepted,
        attempts=attempts_run,
        run_dir=run_dir,
    )
