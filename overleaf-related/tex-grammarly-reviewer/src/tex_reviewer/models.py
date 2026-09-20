from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ReviewScore:
    ai_generated: float
    ai_confidence: float
    general: float
    engagement: float
    correctness: float
    delivery: float
    clarity: float

    @property
    def issue_level(self) -> float:
        """A score-derived proxy because Grammarly's API does not return issue cards."""
        return 1.0 - self.correctness

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["issue_level"] = self.issue_level
        return result


@dataclass(frozen=True)
class EditNote:
    original: str
    replacement: str
    category: str
    explanation: str


@dataclass(frozen=True)
class Revision:
    latex: str
    summary: str
    notes: tuple[EditNote, ...] = ()


@dataclass(frozen=True)
class ReviewComment:
    reviewer_id: str
    reviewer_label: str
    anchor_text: str
    body: str
    category: str
    severity: str
    suggestion: str
    rationale: str
    confidence: float
    requires_author_check: bool
    start_offset: int = -1
    end_offset: int = -1
    start_line: int = -1
    start_column: int = -1
    end_line: int = -1
    end_column: int = -1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RoleReview:
    reviewer_id: str
    reviewer_label: str
    summary: str
    comments: tuple[ReviewComment, ...]


def score_is_acceptable(
    previous: ReviewScore,
    candidate: ReviewScore,
    *,
    tolerance: float = 0.0,
    minimum_improvement: float = 1e-6,
) -> bool:
    """Require Pareto improvement in AI rate and correctness deficit."""
    ai_ok = candidate.ai_generated <= previous.ai_generated + tolerance
    issue_ok = candidate.issue_level <= previous.issue_level + tolerance
    improved = (
        candidate.ai_generated < previous.ai_generated - minimum_improvement
        or candidate.issue_level < previous.issue_level - minimum_improvement
    )
    return ai_ok and issue_ok and improved
