from tex_reviewer.reviewers import DEFAULT_REVIEWERS, REVIEWER_ROLES, get_reviewer_roles


def test_default_panel_contains_four_distinct_roles() -> None:
    assert DEFAULT_REVIEWERS == ("ai-rate", "grammar", "concept", "iclr-overview")
    assert set(DEFAULT_REVIEWERS) == set(REVIEWER_ROLES)


def test_role_selection_preserves_requested_order() -> None:
    roles = get_reviewer_roles(("concept", "grammar"))
    assert [role.reviewer_id for role in roles] == ["concept", "grammar"]

