"""Session persistence: agent state surviving the process — and the sync trap.

Two harnesses over one directory stand in for two processes. The second test
is the important one: it pins the framework behaviour that makes the explicit
final sync *required*, not tidy — sync fires after invocations, and this
harness writes memory after invocations return.
"""

from __future__ import annotations

import pytest
from ludo_engine.board import COLORS
from ludo_engine.deciders import StateView, TurnContext, TurnEnd
from ludo_engine.events import ListSink
from ludo_engine.moves import Move
from ludo_engine.state import GameState

from ludo_strands import config, prompts
from ludo_strands.harness import LudoHarness
from ludo_strands.players import render_memory
from ludo_strands.scripted import ScriptedModel

SCRIPT = [
    '{"token": 0, "to": 0, "reasoning": "out of base"}',
    '{"notes": [{"kind": "commitment", "about": "blue", "text": "promised not to capture me"}]}',
]


@pytest.fixture(scope="module")
def prompt_set():
    return prompts.load()


@pytest.fixture(scope="module")
def profile():
    return config.load("dev")


def build(profile, prompt_set, session_dir):
    models = {c: ScriptedModel(list(SCRIPT) if c == "red" else []) for c in COLORS}
    return LudoHarness(profile, prompt_set, models, ListSink(), session_dir=session_dir)


def play_one_red_turn(harness):
    view = StateView(GameState())
    harness.deciders["red"].choose(TurnContext(view, "red", 6, [Move(0, -1, 0)], 1))
    harness.deciders["red"].reflect(TurnEnd(view, "red", 1, "moved", ()))


def test_state_and_conversation_survive_the_process(profile, prompt_set, tmp_path):
    first = build(profile, prompt_set, tmp_path)
    play_one_red_turn(first)
    first.persist()                      # what play() does in its finally

    # "Process two": a fresh harness over the same directory. Constructing
    # the agents IS the restore — no explicit load call exists or is needed.
    second = build(profile, prompt_set, tmp_path)
    red = second.players["red"]

    notes = red.state.get("notes")
    assert [n["text"] for n in notes] == ["promised not to capture me"]
    assert "promised" in render_memory(red)
    assert len(red.messages) == 4        # decide + reply, reflect + reply — restored


def test_without_the_final_sync_the_last_writes_are_lost(profile, prompt_set, tmp_path):
    # The trap this stack's persist() exists for. The framework syncs after
    # each INVOCATION — but reflect's notes are written by the harness after
    # the invocation returns. Skip the final sync and the note written in
    # process one simply never reaches disk: restored state is empty.
    first = build(profile, prompt_set, tmp_path)
    play_one_red_turn(first)
    # no first.persist()

    second = build(profile, prompt_set, tmp_path)
    assert second.players["red"].state.get("notes") == []      # silently gone
    assert len(second.players["red"].messages) == 4            # messages DID persist
