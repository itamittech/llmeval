"""The harness end to end, against scripted models. No keys, no cost."""

import json
from pathlib import Path

import pytest
from relay_engine.events import ListSink

from relay_strands import demo
from relay_strands.harness import parse_decision

SCHEMA = Path(__file__).resolve().parents[4] / "shared" / "schemas" / "relay-event.schema.json"


@pytest.fixture(scope="module")
def race():
    sink = ListSink()
    harness = demo.build(sink)
    outcome = harness.play()
    return harness, sink, outcome


def events_of(sink, type_):
    return [e["payload"] for e in sink.events if e["type"] == type_]


def test_the_race_runs_to_the_cap(race):
    _, _, outcome = race
    assert outcome.turns_played == demo.MAX_TURNS
    assert outcome.reason == "turn_cap"


def test_every_event_validates_against_the_shared_schema(race):
    jsonschema = pytest.importorskip("jsonschema")
    validator = jsonschema.Draft202012Validator(
        json.loads(SCHEMA.read_text(encoding="utf-8")))
    _, sink, _ = race
    for event in sink.events:
        errors = list(validator.iter_errors(event))
        assert not errors, f"{event['type']}: {errors[0].message}"


def test_the_shared_pool_is_drained_by_the_lanes_that_spend_it(race):
    harness, sink, outcome = race
    assert harness.game.quota == 0
    spent = {row["player"]: row["escalations"] for row in outcome.standings}
    # Yellow escalates everything it can; green refuses on principle.
    assert spent["yellow"] > spent["red"] > spent["green"] == 0


def test_the_disciplined_runner_wins_and_the_hoarder_comes_last(race):
    """The fixture's whole argument, asserted rather than admired.

    Red buys help exactly when it needs it and finishes furthest. Yellow buys
    help it did not need, and pays in ticks for every slow anchor call. Green
    refuses the pool and is wrong four times, which is dearer than either.
    """
    _, _, outcome = race
    order = [row["player"] for row in outcome.standings]
    assert order[0] == "red"
    assert order[-1] == "green"

    by_lane = {row["player"]: row for row in outcome.standings}
    assert by_lane["red"]["ticks"] < by_lane["yellow"]["ticks"]
    assert by_lane["green"]["wrong"] > by_lane["red"]["wrong"] == 0


def test_anchor_calls_are_metered_on_the_lane_that_paid(race):
    _, sink, _ = race
    anchor_calls = [c for c in events_of(sink, "llm_call") if c.get("actor") == "anchor"]
    assert anchor_calls
    for call in anchor_calls:
        assert call["player"] in ("red", "yellow", "blue")   # green never escalates
        assert call["model"] == "scripted-anchor"
        assert call["purpose"] == "escalate"


def test_every_escalation_has_exactly_one_anchor_call(race):
    """The engine performs escalation, so the receipt and the invoice must agree."""
    _, sink, _ = race
    escalated = [a for a in events_of(sink, "stage_attempted") if a["escalated"]]
    anchor_calls = [c for c in events_of(sink, "llm_call") if c.get("actor") == "anchor"]
    assert len(escalated) == len(anchor_calls)


def test_one_model_call_per_turn_plus_one_reflect(race):
    """No tool means no hidden loop: a turn is one attempt call and one reflect
    call, plus an anchor call when the runner escalated. Nothing else."""
    harness, sink, _ = race
    runner_calls = [c for c in events_of(sink, "llm_call") if c.get("actor") != "anchor"]
    anchor_calls = [c for c in events_of(sink, "llm_call") if c.get("actor") == "anchor"]
    assert len(runner_calls) == demo.MAX_TURNS * 2
    assert harness.hooks.calls == len(runner_calls) + len(anchor_calls)


def test_a_note_that_lies_about_the_puzzle_is_published(race):
    _, sink, _ = race
    notes = [a["note"] for a in events_of(sink, "stage_attempted") if a["note"]]
    assert any("monster" in note for note in notes), "the in-fiction lie was suppressed"


def test_a_note_that_forges_engine_authority_is_blocked(race):
    _, sink, _ = race
    blocked = events_of(sink, "guardrail_triggered")
    assert blocked and blocked[0]["rule"] == "forged_state"
    notes = [a["note"] for a in events_of(sink, "stage_attempted") if a["note"]]
    assert not any("quota is unlimited" in note for note in notes)


def test_runners_write_notes_about_themselves(race):
    _, sink, _ = race
    writes = events_of(sink, "memory_write")
    assert writes
    assert all(w["kind"] == "self" for w in writes)


# -- parsing ---------------------------------------------------------------


def test_parse_reads_the_three_lines():
    assert parse_decision("DECISION: answer\nANSWER: 42") == ("answer", "42", None)
    assert parse_decision("DECISION: escalate\nANSWER:\nNOTE: hi") == \
        ("escalate", None, "hi")
    assert parse_decision("DECISION: pass\nANSWER:") == ("pass", None, None)


def test_an_unparseable_reply_raises_rather_than_being_repaired():
    """The engine's retry machinery is the arbiter, not harness guesswork."""
    with pytest.raises(ValueError):
        parse_decision("I think the answer might be 42?")
