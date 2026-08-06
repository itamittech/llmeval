"""Session persistence: agent state surviving the process — with no save call.

Two harnesses over one directory stand in for two processes, mirroring the
other stacks' session tests. The difference IS the finding: Strands needed an
explicit final ``persist()`` (sync runs on the framework's schedule), Spring
AI needed the harness to save beliefs itself (the framework has no place for
them) — here both halves already live in framework stores whose write moments
cover the game loop, so there is nothing left outside the framework to save,
and this stack has no persist method at all. The first test pins that claim
literally.
"""

from __future__ import annotations

import pytest
from ludo_engine.board import COLORS
from ludo_engine.deciders import StateView, TurnContext, TurnEnd
from ludo_engine.events import ListSink
from ludo_engine.moves import Move
from ludo_engine.state import GameState

from ludo_langgraph import config, prompts
from ludo_langgraph.harness import LudoHarness
from ludo_langgraph.memory import render_memory
from ludo_langgraph.scripted import ScriptedChatModel

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


def build(profile, prompt_set, session_dir, script=()):
    models = {c: ScriptedChatModel(script=list(script) if c == "red" else [])
              for c in COLORS}
    return LudoHarness(profile, prompt_set, models, ListSink(),
                       session_dir=session_dir)


def play_one_red_turn(harness):
    view = StateView(GameState())
    harness.deciders["red"].choose(TurnContext(view, "red", 6, [Move(0, -1, 0)], 1))
    harness.deciders["red"].reflect(TurnEnd(view, "red", 1, "moved", ()))


def test_everything_survives_the_process_with_no_save_call(profile, prompt_set, tmp_path):
    first = build(profile, prompt_set, tmp_path, SCRIPT)
    play_one_red_turn(first)
    # Deliberately: no persist(), no flush, no sync. The claim is that none
    # exists to call — pinned literally, so adding one breaks this test and
    # forces the README and matrix to be rewritten with it.
    assert not hasattr(first, "persist")

    # "Process two": a fresh harness over the same directory. Construction is
    # the restore — threads from the checkpointer, beliefs from the store.
    second = build(profile, prompt_set, tmp_path)

    assert len(second.conversation("red")) == 4            # decide u/a + reflect u/a
    assert "promised not to capture me" in render_memory(second.store, "red")
    assert (tmp_path / "session.db").exists()              # one file, both stores


def test_a_restored_thread_continues_not_restarts(profile, prompt_set, tmp_path):
    first = build(profile, prompt_set, tmp_path, SCRIPT)
    play_one_red_turn(first)

    second = build(profile, prompt_set, tmp_path,
                   ['{"token": 0, "to": 0, "reasoning": "still here"}'])
    view = StateView(GameState())
    move = second.deciders["red"].choose(TurnContext(view, "red", 6, [Move(0, -1, 0)], 1))

    assert move == Move(0, -1, 0)
    # 4 restored messages + the new exchange: the conversation continued.
    assert len(second.conversation("red")) == 6
