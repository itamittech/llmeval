"""Rule tests, including every edge case resolved in docs/projects/ludo/game-rules.md."""

import pytest

from ludo_engine.board import BASE, HOME, to_square
from ludo_engine.moves import Move, apply_move, legal_moves
from ludo_engine.state import GameState

# Green's relative position 44 lands on absolute square 5, which red reaches at
# its own relative 5. Absolute 5 is not safe, so it is where captures happen.
GREEN_ON_ABS_5 = 44
GREEN_ON_ABS_8 = 47  # absolute 8 is a star square, so this one is safe


def state(**tokens: list[int]) -> GameState:
    s = GameState()
    for color, positions in tokens.items():
        s.tokens[color] = list(positions)
    return s


def test_only_a_six_releases_a_token_from_base():
    s = state()
    for die in range(1, 6):
        assert legal_moves(s, "red", die) == []
    moves = legal_moves(s, "red", 6)
    assert moves == [Move(t, BASE, 0) for t in range(4)]


def test_home_requires_an_exact_roll():
    s = state(red=[55, HOME, HOME, HOME])
    assert legal_moves(s, "red", 1) == [Move(0, 55, HOME)]
    for die in range(2, 7):
        assert legal_moves(s, "red", die) == [], f"die {die} should overshoot"


def test_tokens_already_home_never_move():
    s = state(red=[HOME] * 4)
    assert all(legal_moves(s, "red", d) == [] for d in range(1, 7))


def test_landing_on_a_lone_opponent_captures_it():
    s = state(red=[3, BASE, BASE, BASE], green=[GREEN_ON_ABS_5, BASE, BASE, BASE])
    assert to_square("red", 5) == to_square("green", GREEN_ON_ABS_5) == 5

    captures = apply_move(s, "red", Move(0, 3, 5))

    assert len(captures) == 1
    assert captures[0].victim == "green" and captures[0].square == 5
    assert s.tokens["green"][0] == BASE
    assert s.stats["red"].captures_made == 1
    assert s.stats["green"].captures_suffered == 1


def test_no_capture_on_a_safe_square():
    s = state(red=[6, BASE, BASE, BASE], green=[GREEN_ON_ABS_8, BASE, BASE, BASE])
    assert to_square("red", 8) == 8

    captures = apply_move(s, "red", Move(0, 6, 8))

    assert captures == []
    assert s.tokens["green"][0] == GREEN_ON_ABS_8, "both tokens share the safe square"


def test_entering_from_base_does_not_capture_an_occupied_start_square():
    """Start squares are safe — the edge case the rules doc resolves explicitly."""
    green_on_red_start = (0 - 13) % 52  # green's relative position for absolute 0
    s = state(green=[green_on_red_start, BASE, BASE, BASE])

    captures = apply_move(s, "red", Move(0, BASE, 0))

    assert captures == []
    assert s.tokens["green"][0] == green_on_red_start


def test_an_opponent_block_cannot_be_landed_on():
    s = state(red=[3, BASE, BASE, BASE], green=[GREEN_ON_ABS_5, GREEN_ON_ABS_5, BASE, BASE])
    assert Move(0, 3, 5) not in legal_moves(s, "red", 2)


def test_an_opponent_block_cannot_be_passed():
    s = state(red=[3, BASE, BASE, BASE], green=[GREEN_ON_ABS_5, GREEN_ON_ABS_5, BASE, BASE])
    assert legal_moves(s, "red", 4) == [], "red must not pass through absolute square 5"


def test_a_single_opponent_does_not_block_passage():
    s = state(red=[3, BASE, BASE, BASE], green=[GREEN_ON_ABS_5, BASE, BASE, BASE])
    assert Move(0, 3, 7) in legal_moves(s, "red", 4)


def test_you_may_always_pass_and_join_your_own_stack():
    s = state(red=[3, 5, 5, BASE])
    moves = legal_moves(s, "red", 2)
    assert Move(0, 3, 5) in moves, "own stack is landable"
    assert Move(0, 3, 7) in legal_moves(s, "red", 4), "own stack is passable"


def test_a_block_on_a_safe_square_still_blocks():
    s = state(red=[6, BASE, BASE, BASE], green=[GREEN_ON_ABS_8, GREEN_ON_ABS_8, BASE, BASE])
    assert legal_moves(s, "red", 2) == []


def test_the_home_column_is_private_and_unreachable_by_others():
    s = state(red=[52, BASE, BASE, BASE], green=[BASE] * 4)
    assert to_square("red", 52) is None
    assert Move(0, 52, 54) in legal_moves(s, "red", 2)


@pytest.mark.parametrize("die", range(1, 7))
def test_generated_moves_are_ordered_by_token_index(die):
    """FirstLegal and the conformance vectors depend on this ordering."""
    s = state(red=[0, 10, 20, 30])
    tokens = [m.token for m in legal_moves(s, "red", die)]
    assert tokens == sorted(tokens)
