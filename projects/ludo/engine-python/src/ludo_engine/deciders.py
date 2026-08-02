"""Move choosers.

The engine knows nothing about LLMs. It asks a `Decider` to pick from the moves
it has already validated as legal — which is what lets agents plug in without
the engine ever importing a model SDK, and what makes cheating structurally
impossible (ADR-0004).

Three call sites, only the middle one required:

    negotiate(TurnStart)   once per turn, before the first roll   optional
    choose(TurnContext)    once per ROLL                          required
    reflect(TurnEnd)       once per turn, after it resolves       optional

The per-turn / per-roll distinction is load-bearing. A six or a capture earns
another roll, so `choose` may run several times in one turn; if negotiation ran
with it, an agent on a hot streak would get a free multiplier on both influence
and cost. See the harness contract, docs/projects/ludo/harness-contract.md.

Optional so that bot deciders with no model behind them stay valid — which is
what keeps the engine fast to test and `examples/turn_order.py` runnable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .board import Color
from .dice import Dice
from .moves import Move
from .state import GameState, PlayerStats


class StateView:
    """A read-only window onto :class:`GameState`, handed to deciders.

    An agent may inspect the board; it may not change it. Collections are
    returned as tuples, so `view.tokens("red")[0] = 56` fails rather than
    silently corrupting the game.

    **Honest about the limit.** This stops mistakes, not determined attackers —
    Python has no hard in-process boundary, and code that reaches for the
    private ``_state`` can still get through. The point is that cheating now
    requires obviously-wrong code a reviewer will spot, instead of a plausible
    typo. The guarantee that actually matters is that the *LLM* can only ever
    return a move choice, which the engine validates regardless (ADR-0004).
    """

    __slots__ = ("_state",)

    def __init__(self, state: GameState) -> None:
        object.__setattr__(self, "_state", state)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("StateView is read-only")

    def tokens(self, color: Color) -> tuple[int, ...]:
        """One colour's four token positions."""
        return tuple(self._state.tokens[color])

    def board(self) -> dict[Color, tuple[int, ...]]:
        """Every colour's positions — the full public board."""
        return {c: tuple(p) for c, p in self._state.tokens.items()}

    def tokens_home(self, color: Color) -> int:
        return self._state.tokens_home(color)

    def progress(self, color: Color) -> int:
        return self._state.progress(color)

    def has_finished(self, color: Color) -> bool:
        return self._state.has_finished(color)

    def finished(self) -> tuple[Color, ...]:
        """Colours that are already home, in finishing order."""
        return tuple(self._state.finished)

    def stats(self, color: Color) -> PlayerStats:
        """A copy — mutating it changes nothing."""
        s = self._state.stats[color]
        return PlayerStats(s.captures_made, s.captures_suffered, s.turns_forfeited)

    def __repr__(self) -> str:
        return f"StateView({self.board()})"


@dataclass(frozen=True)
class TurnStart:
    """Handed to `negotiate`, once per turn, before the first roll."""

    state: StateView
    color: Color
    turn: int


@dataclass(frozen=True)
class TurnContext:
    """Everything a decider is allowed to see when choosing a move."""

    state: StateView
    color: Color
    die: int
    legal_moves: list[Move]
    turn: int
    #: 1 on the first ask, 2 after an illegal move was rejected.
    attempt: int = 1


@dataclass(frozen=True)
class TurnEnd:
    """Handed to `reflect`, once per turn, after it resolves."""

    state: StateView
    color: Color
    turn: int
    #: Same value as the `turn_ended` event: moved, no_legal_move,
    #: illegal_move, or three_sixes.
    reason: str
    #: Every engine event emitted during this turn, `turn_started` through
    #: `turn_ended`. Agent-layer events are not here — an agent already knows
    #: what it said.
    events: tuple[dict, ...]


class Decider(Protocol):
    """The whole required agent interface: pick from moves already validated."""

    def choose(self, ctx: TurnContext) -> Move: ...


@runtime_checkable
class Negotiator(Protocol):
    """Optional. The engine calls this once per turn, before rolling."""

    def negotiate(self, start: TurnStart) -> None: ...


@runtime_checkable
class Reflector(Protocol):
    """Optional. The engine calls this once per turn, after it resolves."""

    def reflect(self, end: TurnEnd) -> None: ...


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
