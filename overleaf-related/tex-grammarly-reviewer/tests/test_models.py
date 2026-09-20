from tex_reviewer.models import ReviewScore, score_is_acceptable


def make_score(ai: float, correctness: float) -> ReviewScore:
    return ReviewScore(ai, 0.5, 0.8, 0.8, correctness, 0.8, 0.8)


def test_accepts_pareto_improvement() -> None:
    assert score_is_acceptable(make_score(0.6, 0.8), make_score(0.5, 0.9))


def test_rejects_tradeoff() -> None:
    assert not score_is_acceptable(make_score(0.6, 0.8), make_score(0.5, 0.7))


def test_rejects_no_change() -> None:
    score = make_score(0.6, 0.8)
    assert not score_is_acceptable(score, score)

