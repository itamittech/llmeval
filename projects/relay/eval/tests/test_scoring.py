"""Scoring, against the committed fixtures and against hand-built transcripts."""

import json
from pathlib import Path

import pytest

from relay_eval import cli, scoring

GAMES = Path(__file__).resolve().parents[2] / "games"
FIXTURES = sorted(GAMES.glob("*.jsonl"))


def test_there_are_fixtures_to_score():
    assert FIXTURES, "no committed races — the stacks' demos write them"


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_every_committed_race_scores_and_self_verifies(path):
    """The fold must reproduce the engine's own standings. A scorer that
    disagreed with the engine about who won would report a confident, wrong
    answer — this is the cheapest possible check that it has not."""
    result = scoring.score(scoring.load(path))
    assert result["self_check"]["ok"], result["self_check"]["detail"]


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_results_validate_against_the_shared_shape(path):
    result = scoring.score(scoring.load(path))
    assert result["schema"] == "relay-eval/1"
    assert len(result["lanes"]) == 4
    for lane in result["lanes"]:
        assert set(lane) >= {"player", "stages_cleared", "ticks", "escalation_precision",
                             "escalation_recall", "escalation_fit"}


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_the_commons_adds_up(path):
    result = scoring.score(scoring.load(path))
    spent = sum(lane["escalations"] for lane in result["lanes"])
    assert spent == result["commons"]["spent"]
    assert spent <= result["commons"]["quota"]


def test_all_three_stacks_share_one_engine_spine():
    """The claim every cross-stack number rests on."""
    spines = {path.stem: cli._spine(scoring.load(path)) for path in FIXTURES}
    assert len(set(map(tuple, spines.values()))) == 1, (
        f"stacks disagree about the race: {sorted(spines)}")


def test_precision_and_fit_come_apart():
    """The finding, asserted rather than admired.

    Red escalates nothing that is objectively tier-3, so its precision is zero.
    Every unit it spends goes on a family it genuinely cannot do, so its fit is
    perfect — and it wins the race. Difficulty by the ladder and difficulty for
    *this runner* are different rulers, which is why the eval reports both.
    """
    result = scoring.score(scoring.load(GAMES / "scripted-strands-seed7.jsonl"))
    red = next(lane for lane in result["lanes"] if lane["player"] == "red")
    assert red["stages_cleared"] == max(l["stages_cleared"] for l in result["lanes"])
    assert red["escalation_precision"] == 0.0
    assert red["escalation_fit"] == 1.0


def test_a_lane_that_never_escalates_has_no_precision_to_report():
    """None, not zero. A lane that spent nothing was not inaccurate."""
    result = scoring.score(scoring.load(GAMES / "scripted-strands-seed7.jsonl"))
    green = next(lane for lane in result["lanes"] if lane["player"] == "green")
    assert green["escalations"] == 0
    assert green["escalation_precision"] is None
    assert green["escalation_fit"] is None


# -- the self-check catches things ----------------------------------------


def _tampered(path, mutate):
    events = scoring.load(path)
    mutate(events)
    return events


def test_the_self_check_catches_a_forged_standing():
    def bump(events):
        for event in events:
            if event["type"] == "game_ended":
                event["payload"]["standings"][0]["stages_cleared"] += 1

    result = scoring.score(_tampered(GAMES / "scripted-strands-seed7.jsonl", bump))
    assert not result["self_check"]["ok"]
    assert "clears" in result["self_check"]["detail"]


def test_the_self_check_catches_a_mischarged_tick():
    def fiddle(events):
        for event in events:
            if event["type"] == "stage_attempted":
                event["payload"]["ticks_charged"] += 1
                return

    result = scoring.score(_tampered(GAMES / "scripted-strands-seed7.jsonl", fiddle))
    assert not result["self_check"]["ok"]
    assert "price list" in result["self_check"]["detail"]


# -- the CLI ---------------------------------------------------------------


def test_compare_refuses_transcripts_that_are_not_the_same_race(tmp_path, capsys):
    """Two stacks that disagree about the race are not comparable at all."""
    original = (GAMES / "scripted-strands-seed7.jsonl").read_text(encoding="utf-8")
    events = [json.loads(line) for line in original.splitlines() if line]
    for event in events:
        if event["type"] == "stage_attempted":
            event["payload"]["correct"] = not event["payload"]["correct"]
            break

    forged = tmp_path / "forged.jsonl"
    forged.write_text("\n".join(json.dumps(e, separators=(",", ":")) for e in events) + "\n",
                      encoding="utf-8")

    code = cli.main(["compare", str(GAMES / "scripted-strands-seed7.jsonl"), str(forged)])
    assert code == 1
    assert "ENGINE SPINES DIFFER" in capsys.readouterr().err


def test_score_writes_a_result_file(tmp_path):
    target = tmp_path / "race.jsonl"
    target.write_text((GAMES / "scripted-strands-seed7.jsonl").read_text(encoding="utf-8"),
                      encoding="utf-8")
    assert cli.main(["score", str(target), "--write"]) == 0
    written = json.loads((tmp_path / "race.jsonl.eval.json").read_text(encoding="utf-8"))
    assert written["self_check"]["ok"]
