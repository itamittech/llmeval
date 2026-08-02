"""Move choosers.

The engine knows nothing about LLMs. It asks a `Decider` to pick from the moves
it has already validated as legal — which is what lets agents plug in without
the engine ever importing a model SDK, and what makes cheating structurally
impossible (ADR-0004).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .board import Color
from .dice import Dice
from .moves import Move
from .state import GameState


@dataclass(frozen=True)
class TurnContext:
    """Everything a decider is allowed to see when choosing a move."""

    state: GameState
    color: Color
    die: int
    legal_moves: list[Move]
    turn: int
    #: 1 on the first ask, 2 after an illegal move was rejected.
    attempt: int = 1


class Decider(Protocol):
    def choose(self, ctx: TurnContext) -> Move: ...


class FirstLegal:
    """Always takes the first legal move.

    Fully deterministic given a seed, which is what conformance vectors rely on:
    seed alone reproduces the entire game, so vectors need not record decisions.
    """

    name = "first-legal"

    def choose(self, ctx: TurnContext) -> Move:
        return ctx.legal_moves[0]


class RandomBot:
    """Uniformly random legal move.

    Seeded from the same portable RNG as the dice so bot games replay exactly.
    Used to calibrate the turn cap without spending a single token.
    """

    name = "random-bot"

    def __init__(self, seed: int) -> None:
        self._rng = Dice(seed)

    def choose(self, ctx: TurnContext) -> Move:
        # roll() returns 1..6; reduce to an index without another primitive.
        pick = 0
        for _ in range(4):
            pick = pick * 6 + (self._rng.roll() - 1)
        return ctx.legal_moves[pick % len(ctx.legal_moves)]
