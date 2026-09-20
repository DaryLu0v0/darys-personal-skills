from tex_reviewer.annotations import annotate_revision, remove_review_comments
from tex_reviewer.models import EditNote, ReviewScore


def score(ai: float, correctness: float) -> ReviewScore:
    return ReviewScore(ai, 0.8, 0.8, 0.8, correctness, 0.8, 0.8)


def test_annotation_preserves_original_and_comments_replacement() -> None:
    original = "\\begin{document}\nThis are the result.\n\\end{document}\n"
    candidate = "\\begin{document}\nThis is the result.\n\\end{document}\n"
    annotated = annotate_revision(
        original,
        candidate,
        baseline=score(0.7, 0.7),
        final=score(0.4, 0.9),
        summaries=("Corrected agreement for precise scientific prose.",),
        notes=(
            EditNote(
                original="This are the result.",
                replacement="This is the result.",
                category="grammar",
                explanation="The singular subject requires a singular verb.",
            ),
        ),
    )
    assert remove_review_comments(annotated) == original
    assert "% TEX-REVIEW > This is the result." in annotated
    assert "The singular subject requires a singular verb." in annotated
    assert "not Grammarly explanations" in annotated


def test_annotation_reports_no_accepted_change() -> None:
    original = "\\begin{document}\nText.\n\\end{document}\n"
    annotated = annotate_revision(
        original,
        original,
        baseline=score(0.1, 0.95),
        final=score(0.1, 0.95),
    )
    assert remove_review_comments(annotated) == original
    assert "No candidate revision was accepted" in annotated
