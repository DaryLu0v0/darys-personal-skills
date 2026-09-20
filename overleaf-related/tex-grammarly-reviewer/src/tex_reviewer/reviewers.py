from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewerRole:
    reviewer_id: str
    label: str
    short_label: str
    instructions: str


REVIEWER_ROLES: dict[str, ReviewerRole] = {
    "humanize": ReviewerRole(
        reviewer_id="humanize",
        label="Humanization reviewer",
        short_label="Humanize",
        instructions=(
            "Read the available Grammarly writing measurements and any validated passage-level Grammarly "
            "observations, then identify prose that sounds formulaic, generic, over-smoothed, repetitive, "
            "or detached from the paper's concrete method and evidence. Recommend clearer, more specific, "
            "natural scientific expression that preserves the author's voice and technical meaning. "
            "Produce comments only: do not rewrite the source. Treat the Grammarly AI likelihood as context, "
            "not an objective or proof of authorship. Never optimize for detector evasion, inject arbitrary "
            "variation, or replace valid technical terminology merely to change a score. Clearly distinguish "
            "Grammarly observations from reviewer inference."
        ),
    ),
    "grammar": ReviewerRole(
        reviewer_id="grammar",
        label="Grammar and clarity reviewer",
        short_label="Grammar",
        instructions=(
            "Focus on grammar, punctuation, sentence structure, antecedents, terminology consistency, "
            "and local clarity in scientific English. Propose the smallest correction that preserves "
            "meaning, mathematics, citations, units, and the author's voice. Do not demand active voice "
            "when passive voice is scientifically appropriate."
        ),
    ),
    "concept": ReviewerRole(
        reviewer_id="concept",
        label="Scientific concept reviewer",
        short_label="Concept",
        instructions=(
            "Focus on internal scientific coherence: definitions, assumptions, units, causal claims, "
            "claim-to-evidence alignment, methodological completeness, controls, uncertainty, and "
            "reproducibility. Do not invent missing facts or rely on unstated external knowledge. Phrase "
            "uncertain findings as questions for the author and mark them as requiring author checking."
        ),
    ),
    "iclr-overview": ReviewerRole(
        reviewer_id="iclr-overview",
        label="ICLR overview reviewer",
        short_label="ICLR",
        instructions=(
            "Provide a constructive ICLR-style pre-review aligned with the ICLR 2027 reviewer guide. "
            "Assess the specific problem, motivation and placement in the literature, whether claims are "
            "supported with scientifically rigorous evidence, significance and new knowledge, clarity, "
            "technical correctness, experimental rigor, and reproducibility. Distinguish decision-critical "
            "weaknesses from optional improvements. Do not treat lack of state-of-the-art performance alone "
            "as grounds for rejection. This is an AI-assisted author pre-review, not an official review or "
            "submission-ready recommendation."
        ),
    ),
}


DEFAULT_REVIEWERS = tuple(REVIEWER_ROLES)


def get_reviewer_roles(ids: tuple[str, ...]) -> tuple[ReviewerRole, ...]:
    unknown = sorted(set(ids) - REVIEWER_ROLES.keys())
    if unknown:
        raise ValueError(f"unknown reviewer role(s): {', '.join(unknown)}")
    return tuple(REVIEWER_ROLES[reviewer_id] for reviewer_id in ids)
