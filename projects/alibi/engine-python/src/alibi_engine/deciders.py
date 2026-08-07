"""Detectives.

The engine knows nothing about LLMs. It asks a `Detective` for each phase of a
turn and validates everything that comes back — which is what lets agents plug
in without the engine importing a model SDK, and what keeps cheating
structurally impossible (ADR-0004): a lying detective is still only lying.

Call sites, in turn order:

    suggest(TurnContext)  -> Suggestion | None    the interrogation move
    show(ShowContext)     -> element id           compelled when you can refute
    accuse(TurnContext)   -> Triple | None        after seeing the refutation
    conclude(TurnContext) -> Belief               required — the eval's input
    reflect(TurnEnd)                              optional

`suggest` and `accuse` receive an archive handle and may search during
deliberation — that is the seam the LLM stacks wire to the archivist tool, and
the engine meters it. Privacy is enforced by construction: a `DetectiveView`
is built per detective and simply does not contain other hands, other shown
exhibits, or anyone's reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .archive import Archive, Document
from .case import ALL_ELEMENTS, COLORS, DIMENSIONS, ELEMENTS, Color, Dimension

#: Confidence values a bot may declare: 1/n for n remaining candidates,
#: quantised to a literal table. Never computed — division would put
#: floating-point formatting on the conformance path, and the two languages
#: must emit identical bytes.
CONFIDENCE: dict[int, float] = {
    1: 1.0, 2: 0.5, 3: 0.3333, 4: 0.25, 5: 0.2, 6: 0.1667, 7: 0.1429, 8: 0.125,
}


@dataclass(frozen=True)
class Suggestion:
    who: str
    how: str
    where: str
    note: str | None = None

    def named(self) -> tuple[str, str, str]:
        return (self.who, self.how, self.where)


@dataclass(frozen=True)
class Triple:
    who: str
    how: str
    where: str


@dataclass(frozen=True)
class Belief:
    who: str
    how: str
    where: str
    confidence: dict[Dimension, float] = field(default_factory=dict)


@dataclass(frozen=True)
class SuggestionRecord:
    """What everyone at the table saw of one suggestion. The shown exhibit is
    deliberately absent — only the suggester learned it."""

    turn: int
    player: Color
    who: str
    how: str
    where: str
    note: str | None
    refuter: Color | None


class DetectiveView:
    """A read-only, single-detective window onto the game.

    Unlike LUDO's StateView this is not one shared view — what red may see and
    what blue may see are different objects, built from different slices of
    the state. The honest limit is the same as LUDO's: this stops mistakes,
    not determined attackers; the guarantee that matters is that a detective
    can only ever return element ids, which the engine validates regardless.
    """

    __slots__ = ("_color", "_hand", "_shown", "_eliminated", "_log")

    def __init__(self, color: Color, hand: tuple[str, ...],
                 shown: dict[str, Color], eliminated: tuple[Color, ...],
                 log: tuple[SuggestionRecord, ...]) -> None:
        object.__setattr__(self, "_color", color)
        object.__setattr__(self, "_hand", hand)
        object.__setattr__(self, "_shown", dict(shown))
        object.__setattr__(self, "_eliminated", eliminated)
        object.__setattr__(self, "_log", log)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("DetectiveView is read-only")

    @property
    def color(self) -> Color:
        return self._color

    def my_hand(self) -> tuple[str, ...]:
        return self._hand

    def shown_to_me(self) -> dict[str, Color]:
        """Exhibits opponents have shown me, element -> who showed it."""
        return dict(self._shown)

    def known_not_solution(self) -> tuple[str, ...]:
        """Own hand plus everything shown — the certain eliminations."""
        seen = set(self._hand) | set(self._shown)
        return tuple(e for e in ALL_ELEMENTS if e in seen)

    def eliminated(self) -> tuple[Color, ...]:
        return self._eliminated

    def suggestions(self) -> tuple[SuggestionRecord, ...]:
        """The public record: every suggestion, who refuted, never what."""
        return self._log


class SearchBudget:
    """The archive handle a detective deliberates through. Counts queries,
    emits events, refuses politely when the turn's quota is spent."""

    def __init__(self, archive: Archive, quota: int, on_search) -> None:
        self._archive = archive
        self._quota = quota
        self._on_search = on_search

    @property
    def quota_left(self) -> int:
        return self._quota

    def search(self, query: str) -> list[Document]:
        if self._quota <= 0:
            self._on_search(query, None)  # emits invalid_action, not results
            return []
        self._quota -= 1
        results = self._archive.search(query)
        self._on_search(query, results)
        return results


@dataclass(frozen=True)
class TurnContext:
    view: DetectiveView
    color: Color
    turn: int
    archive: SearchBudget
    #: 1 on the first ask, 2 after an invalid action was rejected.
    attempt: int = 1
    #: On `accuse` only: what this turn's suggestion just taught, if anything.
    refutation: tuple[Color, str] | None = None
    no_refutation: Suggestion | None = None


@dataclass(frozen=True)
class ShowContext:
    view: DetectiveView
    color: Color
    turn: int
    suggester: Color
    suggestion: Suggestion
    #: The named elements this detective holds — what it may legally show.
    options: tuple[str, ...]


@dataclass(frozen=True)
class TurnEnd:
    view: DetectiveView
    color: Color
    turn: int
    reason: str
    events: tuple[dict, ...]


class Detective(Protocol):
    """The required agent interface. Every return is validated by the engine."""

    def suggest(self, ctx: TurnContext) -> Suggestion | None: ...
    def show(self, ctx: ShowContext) -> str: ...
    def accuse(self, ctx: TurnContext) -> Triple | None: ...
    def conclude(self, ctx: TurnContext) -> Belief: ...


@runtime_checkable
class Reflector(Protocol):
    """Optional. Called once per own turn, after it resolves."""

    def reflect(self, end: TurnEnd) -> None: ...


class EliminationBot:
    """Strict-logic deduction, no reading, no bluffing, no luck.

    The deterministic decider conformance vectors run on (LUDO's `first-legal`
    analogue): it eliminates exactly what it holds and what it is shown,
    suggests the first open candidate per dimension in canonical order, and
    accuses only at certainty — either one candidate left per dimension, or
    its own suggestion drew no refutation while it held none of the named.

    It issues one fixed archive query per turn (its current top suspect) and
    ignores the results — bots cannot read testimony, but the query exercises
    `archive_searched` determinism so the vectors cover retrieval too.
    """

    name = "elimination-bot"

    def __init__(self) -> None:
        self._certain: Triple | None = None

    def _candidates(self, view: DetectiveView, dim: Dimension) -> list[str]:
        known = set(view.known_not_solution())
        return [e for e in ELEMENTS[dim] if e not in known]

    def suggest(self, ctx: TurnContext) -> Suggestion | None:
        picks = {d: self._candidates(ctx.view, d) for d in DIMENSIONS}
        ctx.archive.search(picks["who"][0] if picks["who"] else "sapphire")
        if self._certain or all(len(c) == 1 for c in picks.values()):
            return None  # nothing left to learn; accuse this turn
        return Suggestion(picks["who"][0], picks["how"][0], picks["where"][0])

    def show(self, ctx: ShowContext) -> str:
        return ctx.options[0]

    def accuse(self, ctx: TurnContext) -> Triple | None:
        if ctx.no_refutation is not None:
            s = ctx.no_refutation
            held = set(ctx.view.my_hand())
            if not held & set(s.named()):
                self._certain = Triple(s.who, s.how, s.where)
        picks = {d: self._candidates(ctx.view, d) for d in DIMENSIONS}
        if self._certain is None and all(len(c) == 1 for c in picks.values()):
            self._certain = Triple(picks["who"][0], picks["how"][0], picks["where"][0])
        return self._certain

    def conclude(self, ctx: TurnContext) -> Belief:
        picks = {d: self._candidates(ctx.view, d) for d in DIMENSIONS}
        return Belief(
            who=picks["who"][0], how=picks["how"][0], where=picks["where"][0],
            confidence={d: CONFIDENCE[len(picks[d])] for d in DIMENSIONS},
        )


class RandomSleuth:
    """Suggests blind, never accuses. The pace floor for the bench: a table of
    these never solves, so every game runs to the cap — which is exactly what
    sizing the cap needs to see. Seeded with the portable RNG so replays match."""

    name = "random-sleuth"

    def __init__(self, seed: int) -> None:
        from .rng import Rng
        self._rng = Rng(seed)

    def suggest(self, ctx: TurnContext) -> Suggestion | None:
        return Suggestion(
            ELEMENTS["who"][self._rng.below(len(ELEMENTS["who"]))],
            ELEMENTS["how"][self._rng.below(len(ELEMENTS["how"]))],
            ELEMENTS["where"][self._rng.below(len(ELEMENTS["where"]))],
        )

    def show(self, ctx: ShowContext) -> str:
        return ctx.options[self._rng.below(len(ctx.options))]

    def accuse(self, ctx: TurnContext) -> Triple | None:
        return None

    def conclude(self, ctx: TurnContext) -> Belief:
        picks = {d: self._candidates(ctx.view, d) for d in DIMENSIONS}
        return Belief(
            who=picks["who"][0], how=picks["how"][0], where=picks["where"][0],
            confidence={d: CONFIDENCE[len(picks[d])] for d in DIMENSIONS},
        )

    def _candidates(self, view: DetectiveView, dim: Dimension) -> list[str]:
        known = set(view.known_not_solution())
        open_ = [e for e in ELEMENTS[dim] if e not in known]
        return open_ or list(ELEMENTS[dim])
