"""Board geometry and coordinate mapping.

Positions are **colour-relative**: every colour measures from its own start
square, so movement logic is identical for all four players. Absolute circuit
squares are derived only where colours must interact — capture and blocking.

    -1        base (off the board)
     0        start square
     0..50    main circuit, 51 squares
    51..55    home column
    56        home triangle

A token therefore takes 56 steps from its start square to home, occupying 57
distinct positions. It traverses 51 of the circuit's 52 squares, turning into
its home column one square short of a full loop.
"""

from typing import Final

Color = str

COLORS: Final[tuple[Color, ...]] = ("red", "green", "yellow", "blue")

CIRCUIT_SIZE: Final = 52
TOKENS_PER_PLAYER: Final = 4

BASE: Final = -1
START: Final = 0
LAST_CIRCUIT: Final = 50
HOME_ENTRY: Final = 51
HOME: Final = 56

#: Where each colour joins the circuit. Evenly spaced, 13 apart.
START_SQUARE: Final[dict[Color, int]] = {"red": 0, "green": 13, "yellow": 26, "blue": 39}

#: The four start squares plus a star square 8 ahead of each. No capture here.
SAFE_SQUARES: Final[frozenset[int]] = frozenset({0, 8, 13, 21, 26, 34, 39, 47})


def to_square(color: Color, position: int) -> int | None:
    """Absolute circuit square for a colour-relative position.

    Returns None when the token is not on the shared circuit — in its base,
    its home column, or home — because those are private to one colour and
    cannot interact with anyone else.
    """
    if position < START or position > LAST_CIRCUIT:
        return None
    return (START_SQUARE[color] + position) % CIRCUIT_SIZE


def is_safe(square: int | None) -> bool:
    return square is not None and square in SAFE_SQUARES


def token_progress(position: int) -> int:
    """Steps travelled, counting the start square as 1 and home as 57.

    Base is 0, so leaving the base always registers as progress.
    """
    return 0 if position == BASE else position + 1
