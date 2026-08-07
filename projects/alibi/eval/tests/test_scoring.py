"""Scoring the three committed fixtures — the eval's whole diet in v1."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from alibi_eval import scoring

GAMES = Path(__file__).resolve().parents[2] / "games"
SCHEMA = json.loads(
    (Path(__file__).resolve().parents[4] / "shared" / "schemas"
     / "alibi-eval-result.schema.json").read_text(encoding="utf-8"))

FIXTURES = [
    "scripted-strands-seed7.jsonl",
    "scripted-langgraph-seed7.jsonl",
    "scripted-springai-seed7.jsonl",
]


@pytest.mark.parametrize("name", FIXTURES)
def test_fixture_scores_and_validates(name):
    result = scoring.score(GAMES / name)
    assert [e.message for e in Draft202012Validator(SCHEMA).iter_errors(result)] == []
    assert result["checks"]["standings_match"] is True
    assert result["game"]["reason"] == "solved"
    assert result["game"]["solution"] == {
        "who": "photographer", "how": "service-hatch", "where": "cloakroom"}


@pytest.mark.parametrize("name", FIXTURES)
def test_red_won_with_a_readable_story(name):
    result = scoring.score(GAMES / name)
    red = next(d for d in result["detectives"] if d["player"] == "red")
    assert red["rank"] == 1 and red["solved"]
    assert red["accusation"] == {"turn": 5, "correct": True}
    # Exposure: turn 1's search fed red two herrings, and turn 5's cross-check
    # surfaced the third (doc-002) right beside the counter that broke it.
    assert red["red_herrings_read"] == 3
    # Turn 1's belief was wrong in every dimension with modest confidence,
    # so calibration lands well away from both 0 and 1.
    assert red["beliefs"]["declared"] == 1
    assert red["beliefs"]["final_dimensions_correct"] == 0
    assert 0.0 < red["beliefs"]["mean_brier"] < 0.3


def test_brier_arithmetic():
    beliefs = [{"who": "a", "how": "b", "where": "c",
                "confidence": {"who": 1.0, "how": 0.5, "where": 0.0}}]
    solution = {"who": "a", "how": "x", "where": "c"}
    scores = scoring._belief_scores(beliefs, solution)
    # (1-1)^2 + (0.5-0)^2 + (0-1)^2 over 3 = 1.25/3
    assert scores["mean_brier"] == round(1.25 / 3, 4)
    assert scores["final_dimensions_correct"] == 2


def test_cross_stack_spines_agree():
    spines = [scoring.engine_skeleton(scoring.read_transcript(GAMES / n))
              for n in FIXTURES]
    assert spines[0] == spines[1] == spines[2]
    assert len(spines[0]) > 20


def test_framework_grain_differs_where_recorded():
    calls = {}
    for name in FIXTURES:
        result = scoring.score(GAMES / name)
        calls[result["game"]["stack"]] = sum(
            d["tokens"]["calls"] for d in result["detectives"])
    # The Python stacks meter the consult round as two calls; Spring AI's
    # internal tool execution aggregates it — the matrix finding, in numbers.
    assert calls["strands"] == calls["langgraph"] == 22
    assert calls["springai"] == 20


def test_engine_only_transcript_scores_too(tmp_path):
    """A bot game has no agent events at all; the scorer must not care."""
    import subprocess
    import sys
    out = tmp_path / "bots.jsonl"
    subprocess.run(
        [sys.executable, "-m", "alibi_engine.cli", "play", "--seed", "3",
         "--out", str(out)],
        cwd=Path(__file__).resolve().parents[2] / "engine-python" / "src",
        check=True,
    )
    result = scoring.score(out)
    assert result["checks"]["standings_match"] is True
    assert all(d["tokens"]["calls"] == 0 for d in result["detectives"])
