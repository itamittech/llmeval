"""Legal move generation and application.

This module is the rulebook. Everything it enforces is specified in
docs/projects/ludo/game-rules.md, including the edge cases resolved there.
"""

from __future__ import annotations

from dataclasses import dataclass

from .board import (
    BASE,
    COLORS,
    HOME,
    LAST_CIRCUIT,
    START,
    Color,
    is_safe,
    to_square,
)
from .state import GameState


@dataclass(frozen=True)
class Move:
    token: int
    frm: int
    to: int


@dataclass(frozen=True)
class Capture:
    victim: Color
    victim_token: int
    square: int


def legal_moves(state: GameState, color: Color, die: int) -> list[Move]:
    """Every move `color` may make with `die`, ordered by token index.

    The order is stable and part of the engine's contract: the deterministic
    `first_legal` decider used by conformance vectors depends on it.
    """
    moves: list[Move] = []
    for token, pos in enumerate(state.tokens[color]):
        if pos == HOME:
            continue

        if pos == BASE:
            # Only a 6 releases a token, and only onto its own start square.
            if die == 6 and _can_land(state, color, START):
                moves.append(Move(token, BASE, START))
            continue

        target = pos + die
        if target > HOME:
            continue  # home must be reached by exact count
        if not _path_clear(state, color, pos, target):
            continue
        if not _can_land(state, color, target):
            continue
        moves.append(Move(token, pos, target))

    return moves


def apply_move(state: GameState, color: Color, move: Move) -> list[Capture]:
    """Move a token and resolve any capture. Assumes `move` is legal."""
    state.tokens[color][move.token] = move.to

    square = to_square(color, move.to)
    if square is None or is_safe(square):
        return []

    captures: list[Capture] = []
    for other in COLORS:
        if other == color:
            continue
        for j, pos in enumerate(state.tokens[other]):
            if to_square(other, pos) == square:
                state.tokens[other][j] = BASE
                captures.append(Capture(other, j, square))
                state.stats[other].captures_suffered += 1
                state.stats[color].captures_made += 1

    return captures


# -- internals ------------------------------------------------------------


def _opponent_block(state: GameState, color: Color, square: int) -> bool:
    """Two or more tokens of one other colour: impassable and unlandable.

    Blocks apply on safe squares too, and never obstruct their own owner.
    """
    for other in COLORS:
        if other == color:
            continue
        if sum(1 for p in state.tokens[other] if to_square(other, p) == square) >= 2:
            return True
    return False


def _can_land(state: GameState, color: Color, position: int) -> bool:
    square = to_square(color, position)
    if square is None:
        return True  # home column and home are private to this colour
    return not _opponent_block(state, color, square)


def _path_clear(state: GameState, color: Color, frm: int, to: int) -> bool:
    """Check the squares strictly between `frm` and `to` for opponent blocks."""
    for position in range(frm + 1, to):
        if position > LAST_CIRCUIT:
            break  # home column: no opponent can be there
        square = to_square(color, position)
        if square is not None and _opponent_block(state, color, square):
            return False
    return True
