"""The harness end to end, against scripted models. No keys, no cost."""

import json
from pathlib import Path

import pytest
from relay_engine.events import ListSink

from relay_langgraph import demo
from relay_langgraph.harness import parse_decision

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


def test_the_conversation_lives_in_the_checkpointer_not_the_harness(race):
    """LangGraph's grain: state belongs to the runtime. The harness holds no
    message list at all — it names a thread."""
    harness, _, _ = race
    assert not hasattr(harness, "messages")
    state = harness.agents["red"].get_state({"configurable": {"thread_id": "red"}})
    assert len(state.values["messages"]) > 2


def test_the_notebook_lives_in_the_framework_store(race):
    harness, _, _ = race
    notes = harness.store.search(("notebook", "red"), limit=1000)
    assert notes
    assert all(n.value["kind"] == "self" for n in notes)


def test_anchor_calls_are_metered_on_the_lane_that_paid(race):
    _, sink, _ = race
    anchor_calls = [c for c in events_of(sink, "llm_call") if c.get("actor") == "anchor"]
    assert len(anchor_calls) == 8          # the whole pool
    for call in anchor_calls:
        assert call["model"] == "scripted-anchor"
        assert call["purpose"] == "escalate"
        assert call["player"] in ("red", "yellow", "blue")


def test_every_escalation_has_exactly_one_anchor_call(race):
    _, sink, _ = race
    escalated = [a for a in events_of(sink, "stage_attempted") if a["escalated"]]
    anchor_calls = [c for c in events_of(sink, "llm_call") if c.get("actor") == "anchor"]
    assert len(escalated) == len(anchor_calls)


def test_the_budget_gate_stops_the_last_call(race):
    """Not a bug — the finding, pinned.

    This stack carries an unbounded checkpointer thread where the Strands stack
    pins a 12-message window, so the same race costs it about 1.6x as many
    tokens. On the same per-game ceiling it runs out, and the middleware jumps
    past the model rather than overspending. The race is unaffected; the last
    reflection simply never happens.
    """
    harness, sink, _ = race
    assert harness.meter.spent > harness.meter.max_tokens
    reflects = [c for c in events_of(sink, "llm_call") if c["purpose"] == "reflect"]
    assert len(reflects) == demo.MAX_TURNS - 1


def test_a_note_that_lies_is_published_and_a_forged_one_is_blocked(race):
    _, sink, _ = race
    notes = [a["note"] for a in events_of(sink, "stage_attempted") if a["note"]]
    assert any("monster" in n for n in notes)
    assert not any("quota is unlimited" in n for n in notes)
    assert events_of(sink, "guardrail_triggered")[0]["rule"] == "forged_state"


def test_parse_reads_the_three_lines():
    assert parse_decision("DECISION: answer\nANSWER: 42") == ("answer", "42", None)
    assert parse_decision("DECISION: escalate\nANSWER:\nNOTE: hi") == \
        ("escalate", None, "hi")


def test_an_unparseable_reply_raises_rather_than_being_repaired():
    with pytest.raises(ValueError):
        parse_decision("I think the answer might be 42?")
