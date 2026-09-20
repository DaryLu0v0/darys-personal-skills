import json

from tex_reviewer.cli import _read_grammarly_observations


def test_reads_uniquely_anchored_grammarly_observations(tmp_path) -> None:
    path = tmp_path / "grammarly-observations.json"
    path.write_text(
        json.dumps(
            {
                "document_title": "Introduction test",
                "observed_at": "2026-09-20T20:00:00Z",
                "observations": [
                    {
                        "anchor_text": "This sentence is unusually generic.",
                        "category": "ai-pattern",
                        "explanation": "The wording follows a predictable pattern.",
                        "pattern_class": "moderate",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    observations = _read_grammarly_observations(
        path, "Before. This sentence is unusually generic. After."
    )
    assert len(observations) == 1
    assert observations[0].provenance == "grammarly-ui-observation"
    assert observations[0].pattern_class == "moderate"
    assert observations[0].document_title == "Introduction test"
    assert observations[0].observed_at == "2026-09-20T20:00:00Z"


def test_rejects_ambiguous_grammarly_observation_anchor(tmp_path) -> None:
    path = tmp_path / "grammarly-observations.json"
    path.write_text(
        json.dumps(
            [
                {
                    "anchor_text": "Repeated sentence.",
                    "category": "clarity",
                    "explanation": "This wording is unclear.",
                }
            ]
        ),
        encoding="utf-8",
    )
    try:
        _read_grammarly_observations(
            path, "Repeated sentence. Repeated sentence."
        )
    except ValueError as exc:
        assert "exactly once" in str(exc)
    else:
        raise AssertionError("ambiguous Grammarly anchor was accepted")
