"""Two harnesses, one race.

The comparison this repo exists for is only meaningful if the stacks agree
about what happened. So before any framework difference is reported, this test
reads the **Strands fixture** — written by a different framework, in a
different virtual environment — and asserts that the engine's own events are
identical to this stack's.

What may differ: `llm_call`, `memory_write`, `guardrail_triggered` — the agent
layer, which is the comparison. What may not: a single stage, tick, or clear.
"""

import json
from pathlib import Path

import pytest
from relay_engine.events import ListSink

from relay_langgraph import demo

GAMES = Path(__file__).resolve().parents[2] / "games"
STRANDS = GAMES / "scripted-strands-seed7.jsonl"

#: Everything the engine emits. Agent-layer events are the stacks' own.
ENGINE_EVENTS = {
    "game_started", "track_generated", "turn_started", "stage_attempted",
    "runner_finished", "invalid_action", "turn_ended", "game_ended",
}


def spine(events: list[dict]) -> list[dict]:
    """Engine events only, with the one field that must differ removed."""
    out = []
    for event in events:
        if event["type"] not in ENGINE_EVENTS:
            continue
        payload = dict(event["payload"])
        if event["type"] == "game_started":
            # Framework name, model labels and prompt provenance are the
            # stack's business; the race is not.
            for key in ("stack", "framework", "players", "anchor", "engine"):
                payload.pop(key, None)
        out.append({"turn": event["turn"], "type": event["type"], "payload": payload})
    return out


@pytest.fixture(scope="module")
def ours():
    sink = ListSink()
    demo.build(sink).play()
    return sink.events


@pytest.fixture(scope="module")
def theirs():
    if not STRANDS.exists():
        pytest.skip("the Strands fixture is not committed yet")
    return [json.loads(line) for line in STRANDS.read_text(encoding="utf-8").splitlines()
            if line]


def test_the_engine_spine_is_identical(ours, theirs):
    assert spine(ours) == spine(theirs)


def test_the_standings_agree(ours, theirs):
    def standings(events):
        return next(e["payload"]["standings"] for e in events if e["type"] == "game_ended")

    assert standings(ours) == standings(theirs)


def test_the_prompt_set_hash_agrees(ours, theirs):
    """Two independent loaders, two virtual environments, one digest. The
    property both earlier games earned, inherited here for free."""
    def prompt_set(events):
        return next(e["payload"]["prompt_set"] for e in events if e["type"] == "game_started")

    assert prompt_set(ours) == prompt_set(theirs)


def test_the_agent_layer_is_allowed_to_differ(ours, theirs):
    """And does — this stack costs more and loses its last call to the ceiling.
    Asserting the difference exists stops the equality tests above from being
    accidentally satisfied by two identical harnesses."""
    def calls(events):
        return len([e for e in events if e["type"] == "llm_call"])

    assert calls(ours) < calls(theirs)
