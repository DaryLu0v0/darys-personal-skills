from pathlib import Path

from tex_reviewer.models import ReviewScore, Revision
from tex_reviewer.annotations import remove_review_comments
from tex_reviewer.workflow import ReviewConfig, review_document


SOURCE = r"""\documentclass{article}
\begin{document}
This are an example paragraph with enough words to stand in for a complete manuscript during a deterministic unit test of the iterative review workflow.
\end{document}
"""


def score(ai: float, correctness: float) -> ReviewScore:
    return ReviewScore(ai, 0.8, 0.8, 0.8, correctness, 0.8, 0.8)


class FakeScorer:
    def __init__(self, scores: list[ReviewScore]) -> None:
        self.scores = iter(scores)

    def assess(self, text: str, filename: str = "manuscript.txt") -> ReviewScore:
        return next(self.scores)


class FakeEditor:
    def __init__(self, revisions: list[str]) -> None:
        self.revisions = iter(revisions)

    def revise(self, latex: str, score: ReviewScore, *, attempt: int, feedback: str = "") -> Revision:
        return Revision(next(self.revisions), f"attempt {attempt}")


def test_keeps_only_improving_candidate(tmp_path: Path) -> None:
    improved = SOURCE.replace("This are", "This is")
    regressed = improved.replace("example paragraph", "illustrative paragraph")
    result = review_document(
        SOURCE,
        scorer=FakeScorer([score(0.7, 0.7), score(0.4, 0.9), score(0.5, 0.95)]),
        editor=FakeEditor([improved, regressed]),
        run_dir=tmp_path / "run",
        config=ReviewConfig(max_attempts=2, patience=1, target_ai=0.1, target_issue_level=0.01),
    )
    assert result.latex == improved
    assert remove_review_comments(result.annotated_latex) == SOURCE
    assert "This is" in result.annotated_latex
    assert result.accepted_revisions == 1
    assert result.stop_reason == "stopped after consecutive rejected revisions"
    assert (result.run_dir / "history.json").exists()
