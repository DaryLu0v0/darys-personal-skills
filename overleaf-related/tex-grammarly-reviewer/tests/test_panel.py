from pathlib import Path

from tex_reviewer.models import ReviewComment, ReviewScore, RoleReview
from tex_reviewer.panel import anchor_comment, generate_panel
from tex_reviewer.reviewers import REVIEWER_ROLES


SOURCE = "\\begin{document}\nThe method is robust in every setting.\n\\end{document}\n"


def score() -> ReviewScore:
    return ReviewScore(0.6, 0.8, 0.7, 0.7, 0.8, 0.7, 0.7)


def comment(anchor: str) -> ReviewComment:
    role = REVIEWER_ROLES["concept"]
    return ReviewComment(
        reviewer_id=role.reviewer_id,
        reviewer_label=role.label,
        anchor_text=anchor,
        body="Please delimit the settings supported by the evidence.",
        category="claim-evidence",
        severity="major",
        suggestion="Name the evaluated settings or qualify the claim.",
        rationale="The universal claim is broader than the evidence visible here.",
        confidence=0.85,
        requires_author_check=True,
    )


class FakeReviewer:
    def review(self, latex, score, role, *, max_comments):
        valid = comment("The method is robust in every setting.")
        valid = ReviewComment(
            **{
                **valid.to_dict(),
                "reviewer_id": role.reviewer_id,
                "reviewer_label": role.label,
            }
        )
        invalid = ReviewComment(
            **{
                **valid.to_dict(),
                "anchor_text": "This text does not exist.",
            }
        )
        return RoleReview(role.reviewer_id, role.label, "One major claim needs qualification.", (valid, invalid))


def test_anchor_comment_records_exact_position() -> None:
    anchored = anchor_comment(SOURCE, comment("The method is robust in every setting."))
    assert SOURCE[anchored.start_offset : anchored.end_offset] == anchored.anchor_text
    assert anchored.start_line == 2
    assert anchored.start_column == 1


def test_anchor_comment_rejects_nonunique_text() -> None:
    repeated = "same\nsame\n"
    try:
        anchor_comment(repeated, comment("same"))
    except ValueError as exc:
        assert "not unique" in str(exc)
    else:
        raise AssertionError("nonunique anchor was accepted")


def test_generate_panel_writes_validated_manifest(tmp_path: Path) -> None:
    result = generate_panel(
        SOURCE,
        filename="paper.tex",
        score=score(),
        reviewer=FakeReviewer(),
        roles=(REVIEWER_ROLES["concept"],),
        output_dir=tmp_path / "panel",
        max_comments_per_reviewer=4,
    )
    assert result.accepted_comments == 1
    assert result.rejected_comments == 1
    assert result.manifest_path.exists()
    assert result.markdown_path.exists()
    assert result.manifest["publication"]["status"] == "not-published"
    saved = result.manifest["reviews"][0]["comments"][0]
    assert saved["comment_id"] == "CONCEPT-001"
    assert saved["filename"] == "paper.tex"
    assert "[Scientific concept reviewer]" in saved["overleaf_comment"]
    assert "inference, not a verified fact" in saved["overleaf_comment"]

