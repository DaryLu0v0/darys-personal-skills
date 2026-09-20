from tex_reviewer.reviewers import DEFAULT_REVIEWERS, REVIEWER_ROLES, get_reviewer_roles


def test_default_panel_contains_five_distinct_roles() -> None:
    assert DEFAULT_REVIEWERS == (
        "humanize",
        "grammar",
        "concept",
        "citation",
        "overview",
    )
    assert set(DEFAULT_REVIEWERS) == set(REVIEWER_ROLES)


def test_humanize_role_is_comment_only_and_not_detector_driven() -> None:
    instructions = REVIEWER_ROLES["humanize"].instructions
    assert "Produce comments only" in instructions
    assert "not an objective or proof of authorship" in instructions


def test_role_selection_preserves_requested_order() -> None:
    roles = get_reviewer_roles(("concept", "grammar"))
    assert [role.reviewer_id for role in roles] == ["concept", "grammar"]


def test_citation_role_forbids_unverified_references() -> None:
    instructions = REVIEWER_ROLES["citation"].instructions
    assert "Never invent a paper" in instructions
    assert "independently verified source evidence" in instructions


def test_overview_role_is_venue_agnostic() -> None:
    instructions = REVIEWER_ROLES["overview"].instructions
    assert "venue-agnostic" in instructions
    assert "current venue profile" in instructions
