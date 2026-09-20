import importlib.util
from pathlib import Path

from tex_reviewer.models import ReviewComment, ReviewScore, RoleReview
from tex_reviewer.panel import generate_panel
from tex_reviewer.reviewers import REVIEWER_ROLES


VALIDATOR = (
    Path(__file__).parents[1]
    / "skills"
    / "scientific-tex-reviewer"
    / "scripts"
    / "validate_manifest.py"
)


def _load_validator():
    spec = importlib.util.spec_from_file_location("skill_manifest_validator", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeReviewer:
    def review(self, latex, score, role, *, max_comments, grammarly_observations=()):
        return RoleReview(
            reviewer_id=role.reviewer_id,
            reviewer_label=role.label,
            summary="A bounded test review.",
            comments=(
                ReviewComment(
                    reviewer_id=role.reviewer_id,
                    reviewer_label=role.label,
                    anchor_text="This claim needs evidence.",
                    body="Identify the evidence supporting this claim.",
                    category="claim-evidence",
                    severity="major",
                    suggestion="Add a result reference or qualify the claim.",
                    rationale="The sentence is unqualified.",
                    confidence=0.8,
                    requires_author_check=True,
                ),
            ),
        )


def test_skill_validator_accepts_generated_manifest_and_rejects_drift(tmp_path: Path) -> None:
    source = "\\begin{document}\nThis claim needs evidence.\n\\end{document}\n"
    score = ReviewScore(0.3, 0.8, 0.8, 0.8, 0.9, 0.8, 0.8)
    panel = generate_panel(
        source,
        filename="paper.tex",
        score=score,
        reviewer=FakeReviewer(),
        roles=(REVIEWER_ROLES["concept"],),
        output_dir=tmp_path / "panel",
    )
    validator = _load_validator()
    valid = validator.validate(panel.manifest, source, "paper.tex")
    assert valid["valid"] is True
    assert valid["comments"] == 1

    drifted = validator.validate(panel.manifest, source.replace("evidence", "support"), "paper.tex")
    assert drifted["valid"] is False
    assert any("SHA-256" in error for error in drifted["errors"])
