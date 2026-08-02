"""Deciders get a read-only window onto the board (open question 15).

ADR-0004 claims cheating is structurally impossible. That is true of the LLM,
which only ever returns a move choice. These tests cover the other half: the
decider *code* wrapping it shouldn't be able to reach through and edit the
board by accident either.
"""

import pytest

from ludo_engine.board import BASE, COLORS, HOME
from ludo_engine.deciders import StateView
from ludo_engine.events import ListSink
from ludo_engine.game import Game, GameConfig
from ludo_engine.state import GameState


@pytest.fixture
def view():
    state = GameState()
    state.tokens["red"] = [0, 5, BASE, HOME]
    state.stats["red"].captures_made = 2
    state.finished.append("green")
    return StateView(state), state


def test_it_reads_the_real_board(view):
    v, _ = view
    assert v.tokens("red") == (0, 5, BASE, HOME)
    assert v.tokens_home("red") == 1
    assert v.has_finished("green") is False  # only one token home in this fixture
    assert v.finished() == ("green",)
    assert v.stats("red").captures_made == 2


def test_positions_come_back_immutable(view):
    v, _ = view
    assert isinstance(v.tokens("red"), tuple)
    with pytest.raises(TypeError):
        v.tokens("red")[0] = 56


def test_the_full_board_is_immutable_too(view):
    v, _ = view
    board = v.board()
    assert set(board) == set(COLORS)
    with pytest.raises(TypeError):
        board["red"][0] = 56


def test_mutating_the_returned_board_dict_cannot_reach_the_real_state(view):
    v, state = view
    board = v.board()
    board["red"] = (56, 56, 56, 56)          # rebinding the copy is allowed
    assert state.tokens["red"] == [0, 5, BASE, HOME], "real board must be untouched"


def test_stats_are_a_copy(view):
    v, state = view
    s = v.stats("red")
    s.captures_made = 999
    assert state.stats["red"].captures_made == 2


def test_attributes_cannot_be_set(view):
    v, _ = view
    with pytest.raises(AttributeError):
        v.tokens = {}


def test_the_engine_hands_deciders_a_view_not_the_state():
    seen = {}

    class Peeker:
        name = "peeker"

        def choose(self, ctx):
            seen["type"] = type(ctx.state).__name__
            seen["has_mutable_tokens"] = hasattr(ctx.state, "restore")
            return ctx.legal_moves[0]

    game = Game(GameConfig(seed=4, max_turns=3), ListSink())
    # Put a token on the board so ANY roll produces a legal move — otherwise a
    # short game can end without the decider ever being asked.
    game.state.tokens["red"] = [0, BASE, BASE, BASE]
    game.play({**{c: Peeker() for c in COLORS}})

    assert seen["type"] == "StateView"
    assert seen["has_mutable_tokens"] is False, "restore() must not be reachable"


def test_a_decider_trying_to_cheat_changes_nothing():
    """The realistic accident: an agent writes to what it was handed."""

    class Cheater:
        name = "cheater"

        def choose(self, ctx):
            try:
                ctx.state.tokens("red")[0] = HOME      # tuple -> TypeError
            except TypeError:
                pass
            try:
                ctx.state.board()["red"] = (HOME,) * 4  # copy -> no effect
            except Exception:
                pass
            return ctx.legal_moves[0]

    game = Game(GameConfig(seed=9, max_turns=6), ListSink())
    game.state.tokens["red"] = [0, BASE, BASE, BASE]
    game.play({**{c: Cheater() for c in COLORS}})

    assert game.state.tokens_home("red") < 4, "red must not have cheated its way home"
