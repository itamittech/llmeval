from ludo_engine.board import (
    BASE, CIRCUIT_SIZE, HOME, LAST_CIRCUIT, SAFE_SQUARES, START_SQUARE,
    is_safe, to_square, token_progress,
)


def test_start_squares_are_evenly_spaced():
    offsets = sorted(START_SQUARE.values())
    assert offsets == [0, 13, 26, 39]
    gaps = {b - a for a, b in zip(offsets, offsets[1:])}
    assert gaps == {13}, "each colour must join the circuit 13 squares after the last"


def test_relative_positions_map_onto_the_shared_circuit():
    assert to_square("red", 0) == 0
    assert to_square("green", 0) == 13
    assert to_square("red", 50) == 50
    # Green wraps past the end of the circuit.
    assert to_square("green", 50) == (13 + 50) % CIRCUIT_SIZE == 11


def test_private_positions_have_no_circuit_square():
    for position in (BASE, LAST_CIRCUIT + 1, HOME):
        assert to_square("red", position) is None, position


def test_a_token_visits_51_of_the_52_circuit_squares():
    """It turns into its home column one square short of a full loop."""
    visited = {to_square("blue", p) for p in range(0, LAST_CIRCUIT + 1)}
    assert len(visited) == 51
    missing = set(range(CIRCUIT_SIZE)) - visited
    assert missing == {(START_SQUARE["blue"] - 1) % CIRCUIT_SIZE}


def test_safe_squares_are_the_starts_plus_a_star_eight_ahead():
    stars = {(s + 8) % CIRCUIT_SIZE for s in START_SQUARE.values()}
    assert SAFE_SQUARES == set(START_SQUARE.values()) | stars
    assert len(SAFE_SQUARES) == 8
    assert is_safe(0) and not is_safe(5) and not is_safe(None)


def test_progress_counts_the_start_square_as_one_and_home_as_57():
    assert token_progress(BASE) == 0
    assert token_progress(0) == 1
    assert token_progress(HOME) == 57
