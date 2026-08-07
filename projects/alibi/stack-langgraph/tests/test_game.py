"""The scripted game on LangGraph: same story as Strands, different grain."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from alibi_engine.case import COLORS
from alibi_engine.events import ListSink

from alibi_langgraph import config, prompts
from alibi_langgraph.demo import SCRIPTS, SEED
from alibi_langgraph.harness import AlibiHarness
from alibi_langgraph.scripted import ScriptedChatModel

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[4] / "shared" / "schemas" / "alibi-event.schema.json")
    .read_text(encoding="utf-8")
)


@pytest.fixture(scope="module")
def played():
    sink = ListSink()
    models = {c: ScriptedChatModel(script=list(SCRIPTS[c]), seen=[]) for c in COLORS}
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
        assert model.cursor == len(SCRIPTS[color]), f"{color} left script unused"


def test_metering_counts_every_call(played):
    harness, _, sink, _ = played
    calls = [e for e in sink.events if e["type"] == "llm_call"]
    expected = sum(len(s) for s in SCRIPTS.values())
    assert len(calls) == expected == harness.meter.calls
    assert all(e["payload"]["tokens"]["input"] > 0 for e in calls)
    purposes = {e["payload"]["purpose"] for e in calls}
    assert purposes == {"suggest", "show", "accuse", "conclude", "reflect"}


def test_the_archivist_tool_ran_in_the_graph(played):
    _, _, sink, _ = played
    searches = [e for e in sink.events if e["type"] == "archive_searched"]
    assert [e["payload"]["query"] for e in searches] == [
        "photographer cloakroom service hatch",
        "security guard Asha Nair",
    ]
    assert searches[0]["payload"]["results"] == ["doc-016", "doc-018", "doc-013"]
    assert searches[1]["payload"]["results"] == ["doc-002", "doc-009"]


def test_notebook_lives_in_the_framework_store(played):
    harness, _, sink, _ = played
    writes = [e for e in sink.events if e["type"] == "memory_write"]
    assert len(writes) == 4
    items = harness.store.search(("notebook", "red"), limit=100)
    assert len(items) == 3  # red wrote two notes on turn 1, one on turn 5


def test_conversation_lives_in_the_checkpointer(played):
    harness, _, _, _ = played
    state = harness.agents["red"].get_state({"configurable": {"thread_id": "red"}})
    assert len(state.values.get("messages", [])) > 0


def test_prompts_never_leak_another_hand(played):
    harness, models, _, _ = played
    hands = {c: ", ".join(harness.game.case.hands[c]) for c in COLORS}
    for reader, model in models.items():
        seen = "\n".join(model.seen)
        for owner, hand_text in hands.items():
            if owner == reader:
                continue
            assert hand_text not in seen, f"{reader} saw {owner}'s hand"


def test_provenance_names_this_framework(played):
    _, _, sink, _ = played
    started = sink.events[0]["payload"]
    assert started["stack"] == "langgraph"
    assert started["framework"]["name"] == "langgraph"
    assert started["prompt_set"]["hash"].startswith("sha256:")


def test_engine_skeleton_matches_the_strands_fixture(played):
    """Same seed, same scripted decisions — the engine events must agree with
    the committed Strands fixture event for event (agent events differ)."""
    _, _, sink, _ = played
    strands = (Path(__file__).resolve().parents[2]
               / "games" / "scripted-strands-seed7.jsonl")
    engine_types = {
        "game_started", "case_dealt", "archive_generated", "turn_started",
        "archive_searched", "suggestion_made", "refutation_made",
        "accusation_made", "detective_eliminated", "belief_declared",
        "invalid_action", "turn_ended", "game_ended",
    }

    def skeleton(events):
        out = []
        for e in events:
            if e["type"] not in engine_types or e["type"] == "game_started":
                continue
            out.append((e["turn"], e["type"], json.dumps(e["payload"], sort_keys=True)))
        return out

    mine = skeleton(sink.events)
    theirs = skeleton([json.loads(line) for line in
                       strands.read_text(encoding="utf-8").splitlines() if line])
    assert mine == theirs
