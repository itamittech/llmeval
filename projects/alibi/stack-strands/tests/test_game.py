"""The scripted game, end to end: outcome, events, schema, privacy, metering."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from alibi_engine.case import COLORS
from alibi_engine.events import ListSink

from alibi_strands import config, prompts
from alibi_strands.demo import SCRIPTS, SEED
from alibi_strands.harness import AlibiHarness
from alibi_strands.scripted import ScriptedModel

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[4] / "shared" / "schemas" / "alibi-event.schema.json")
    .read_text(encoding="utf-8")
)


@pytest.fixture(scope="module")
def played():
    sink = ListSink()
    models = {c: ScriptedModel(list(SCRIPTS[c])) for c in COLORS}
    harness = AlibiHarness(config.load("dev"), prompts.load(), models, sink, seed=SEED)
    outcome = harness.play()
    return harness, models, sink, outcome


def test_red_solves_on_turn_five(played):
    _, _, _, outcome = played
    assert outcome.reason == "solved"
    assert outcome.turns_played == 5
    assert outcome.winner == "red"


def test_every_event_is_schema_valid(played):
    _, _, sink, _ = played
    validator = Draft202012Validator(SCHEMA)
    problems = [f"{e['seq']}: {err.message}"
                for e in sink.events for err in validator.iter_errors(e)]
    assert problems == []
    assert [e["seq"] for e in sink.events] == list(range(len(sink.events)))


def test_scripts_fully_consumed(played):
    _, models, _, _ = played
    for color, model in models.items():
        assert model.calls == len(SCRIPTS[color]), f"{color} left script unused"


def test_metering_counts_every_call(played):
    harness, _, sink, _ = played
    calls = [e for e in sink.events if e["type"] == "llm_call"]
    expected = sum(len(s) for s in SCRIPTS.values())
    assert len(calls) == expected == harness.hooks.calls
    assert all(e["payload"]["tokens"]["input"] > 0 for e in calls)
    assert harness.hooks.spent > 0
    purposes = {e["payload"]["purpose"] for e in calls}
    assert purposes == {"suggest", "show", "accuse", "conclude", "reflect"}


def test_the_archivist_was_a_real_tool_call(played):
    _, _, sink, _ = played
    searches = [e for e in sink.events if e["type"] == "archive_searched"]
    assert [e["payload"]["query"] for e in searches] == [
        "photographer cloakroom service hatch",
        "security guard Asha Nair",
    ]
    # Turn 1's search feeds red BOTH red herrings; turn 5's surfaces the counter.
    assert searches[0]["payload"]["results"] == ["doc-016", "doc-018", "doc-013"]
    assert searches[1]["payload"]["results"] == ["doc-002", "doc-009"]


def test_refutation_was_the_detectives_choice(played):
    _, _, sink, _ = played
    refutation = next(e for e in sink.events if e["type"] == "refutation_made")
    assert refutation["payload"]["refuter"] == "green"
    assert refutation["payload"]["element"] == "magician"
    assert refutation["payload"]["chosen_by"] == "detective"


def test_notebook_writes_reached_the_transcript(played):
    _, _, sink, _ = played
    writes = [e for e in sink.events if e["type"] == "memory_write"]
    assert len(writes) == 4  # red 2 + red 1 + yellow 1; empty arrays write nothing
    kinds = {e["payload"]["kind"] for e in writes}
    assert kinds <= {"deduction", "suspicion", "plan", "observation"}


def test_reasoning_is_private_but_recorded(played):
    _, _, sink, _ = played
    reasonings = [e for e in sink.events if e["type"] == "agent_reasoning"]
    assert any("Bluff my own terrace" in e["payload"]["text"] for e in reasonings)


def test_in_fiction_note_passed_the_guardrails(played):
    _, _, sink, _ = played
    assert not any(e["type"] == "guardrail_triggered" for e in sink.events)
    suggestion = next(e for e in sink.events if e["type"] == "suggestion_made")
    assert suggestion["payload"]["note"] == "The service hatch keeps coming up in the logs."


def test_prompts_never_leak_another_hand(played):
    harness, models, _, _ = played
    hands = {c: ", ".join(harness.game.case.hands[c]) for c in COLORS}
    for reader, model in models.items():
        seen = "\n".join(model.seen)
        for owner, hand_text in hands.items():
            if owner == reader:
                continue
            assert hand_text not in seen, f"{reader} saw {owner}'s hand"


def test_provenance_is_recorded(played):
    _, _, sink, _ = played
    started = sink.events[0]["payload"]
    assert started["stack"] == "strands"
    assert started["profile"] == "dev"
    assert started["prompt_set"]["hash"].startswith("sha256:")
    assert started["framework"]["name"] == "strands"
    assert started["archivist"] == {"agent": "baseline-retriever",
                                    "retrieval_profile": "baseline"}
