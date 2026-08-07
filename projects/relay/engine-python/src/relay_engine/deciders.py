"""Runners.

The engine knows nothing about LLMs. Once per turn it asks a `Runner` for an
`Attempt` and adjudicates what comes back — which is what lets agents plug in
without the engine importing a model SDK.

RELAY's whole game is one decision, so there is one call site:

    attempt(TurnContext) -> Attempt        answer, or pass
    reflect(TurnEnd)                       optional

**Escalation is not something a runner reports — it is something the engine
performs.** `ctx.desk.ask()` consults the anchor: the engine charges the shared
quota, calls whatever anchor the game was configured with, and hands back the
answer. A runner therefore cannot secretly use the anchor (it never holds one)
and cannot claim to have when it did not (the engine kept the receipt). Lying
in a public note stays entirely legal — the ADR-0004 line, in this game's
shape.

Privacy is by construction, as everywhere in this repo: a `RunnerView` is built
per runner and simply does not contain any stage's tier or answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable

from .track import PublicStage, Stage, normalise

COLORS = ("red", "green", "yellow", "blue")
Color = str


@dataclass(frozen=True)
class Attempt:
    """One turn's move. `answer=None` is a pass."""

    answer: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class LaneSnapshot:
    """What everyone can see of one lane. No reasoning, no memory, no answers."""

    color: Color
    position: int
    ticks: int
    escalations: int
    finished: bool


@dataclass(frozen=True)
class NoteRecord:
    turn: int
    player: Color
    text: str


@dataclass(frozen=True)
class AttemptRecord:
    """A runner's own result history — the raw material for self-knowledge.
    Which family it keeps missing is the one thing worth remembering in this
    game, and it is derivable from here without any privileged information."""

    turn: int
    stage: str
    family: str
    escalated: bool
    correct: bool


class RunnerView:
    """A read-only, single-lane window onto the race.

    What is absent is the point: no stage carries a tier or an answer, because
    judging difficulty unaided is the move the game is made of.
    """

    __slots__ = ("_color", "_stage", "_position", "_ticks", "_track_length",
                 "_quota_left", "_lanes", "_notes", "_history")

    def __init__(self, color: Color, stage: PublicStage, position: int, ticks: int,
                 track_length: int, quota_left: int,
                 lanes: tuple[LaneSnapshot, ...], notes: tuple[NoteRecord, ...],
                 history: tuple[AttemptRecord, ...]) -> None:
        object.__setattr__(self, "_color", color)
        object.__setattr__(self, "_stage", stage)
        object.__setattr__(self, "_position", position)
        object.__setattr__(self, "_ticks", ticks)
        object.__setattr__(self, "_track_length", track_length)
        object.__setattr__(self, "_quota_left", quota_left)
        object.__setattr__(self, "_lanes", lanes)
        object.__setattr__(self, "_notes", notes)
        object.__setattr__(self, "_history", history)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("RunnerView is read-only")

    @property
    def color(self) -> Color:
        return self._color

    @property
    def stage(self) -> PublicStage:
        """The stage this runner is facing — prompt only."""
        return self._stage

    @property
    def position(self) -> int:
        return self._position

    @property
    def ticks(self) -> int:
        return self._ticks

    @property
    def track_length(self) -> int:
        return self._track_length

    @property
    def quota_left(self) -> int:
        """The shared pool. Public by design: spending it is a move against
        everyone, so everyone gets to watch it drain."""
        return self._quota_left

    def lanes(self) -> tuple[LaneSnapshot, ...]:
        return self._lanes

    def notes(self) -> tuple[NoteRecord, ...]:
        """Public table talk, in order. Any of it may be a lie."""
        return self._notes

    def own_history(self) -> tuple[AttemptRecord, ...]:
        return self._history


class EscalationDesk:
    """The anchor, behind a meter.

    Ask and you are charged one unit of the shared quota whether or not you use
    what comes back — the call was made. Ask with an empty pool and you get
    `None` plus an `invalid_action` in the transcript.
    """

    def __init__(self, stage: Stage, quota_left: Callable[[], int],
                 spend: Callable[[], None], anchor: Callable[[PublicStage], str] | None,
                 on_refused: Callable[[], None]) -> None:
        self._stage = stage
        self._quota_left = quota_left
        self._spend = spend
        self._anchor = anchor
        self._on_refused = on_refused
        self.used = False

    @property
    def quota_left(self) -> int:
        return self._quota_left()

    def ask(self) -> str | None:
        if self._quota_left() <= 0:
            self._on_refused()
            return None
        self._spend()
        self.used = True
        if self._anchor is None:
            # Engine-only games model a perfect anchor. Stated rather than
            # assumed: a live anchor is a real model and can be wrong, and the
            # bench numbers are optimistic by exactly that much.
            return self._stage.answer
        return self._anchor(self._stage.public())


@dataclass(frozen=True)
class TurnContext:
    view: RunnerView
    color: Color
    turn: int
    desk: EscalationDesk
    #: 1 on the first ask, 2 after an invalid action was rejected.
    attempt: int = 1


@dataclass(frozen=True)
class TurnEnd:
    view: RunnerView
    color: Color
    turn: int
    reason: str
    events: tuple[dict, ...]


class Runner(Protocol):
    """The required agent interface. Every return is validated by the engine."""

    def attempt(self, ctx: TurnContext) -> Attempt: ...


@runtime_checkable
class Reflector(Protocol):
    """Optional. Called once per own turn, after it resolves."""

    def reflect(self, end: TurnEnd) -> None: ...


# -- bots ------------------------------------------------------------------


class LadderRunner:
    """The deterministic decider the conformance vectors run on.

    Its competence is a program's competence, which is the honest shape for a
    bot: it is flawless at mechanical work and helpless at inference. It solves
    `chain` stages and `cipher` stages whose shift is stated, by reading the
    prompt and doing the arithmetic. Everything else — `order`, and the tier-3
    ciphers that withhold the shift — it escalates, and once the shared quota
    is gone it simply passes.

    That makes it a real player of this game rather than a puppet: it spends
    the commons on exactly the stages it cannot do, and the runners behind it
    in the rotation live with what is left. With the pool empty it guesses
    rather than passing, which is both the more human failure and the one that
    puts wrong answers into the conformance vectors.
    """

    name = "ladder-runner"

    def attempt(self, ctx: TurnContext) -> Attempt:
        stage = ctx.view.stage
        solved = _solve(stage)
        if solved is not None:
            return Attempt(answer=solved)
        escalated = ctx.desk.ask()
        if escalated is not None:
            return Attempt(answer=escalated)
        return Attempt(answer=_guess(stage))


class ProfileRunner:
    """A measuring device, not a player — it is handed the track at
    construction and therefore knows every answer.

    It exists to answer open question 25: for which combinations of *skill*
    (how often it solves a tier) and *insight* (how often it correctly senses
    how hard a stage is) does the escalation decision actually matter? Skill
    without insight burns the quota on stages it would have got; insight
    without quota is worth nothing. Sweeping the pair is the bench.
    """

    name = "profile-runner"

    def __init__(self, seed: int, track: tuple[Stage, ...],
                 skill: dict[int, int], insight: int, escalate_at: int = 3) -> None:
        from .rng import Rng
        self._rng = Rng(seed)
        self._track = track
        self._skill = skill          # tier -> percent chance of solving it alone
        self._insight = insight      # percent chance of sensing the true tier
        self._escalate_at = escalate_at

    def attempt(self, ctx: TurnContext) -> Attempt:
        stage = self._track[ctx.view.position]
        perceived = (stage.tier if self._rng.below(100) < self._insight
                     else self._rng.below(3) + 1)

        if perceived >= self._escalate_at:
            answer = ctx.desk.ask()
            if answer is not None:
                return Attempt(answer=answer)
            # Quota gone; fall through and have a go anyway.

        if self._rng.below(100) < self._skill[stage.tier]:
            return Attempt(answer=stage.answer)
        return Attempt(answer="unknown")


def _solve(stage: PublicStage) -> str | None:
    """Read the prompt and do the mechanical part, or admit it cannot.

    Deliberately a parser over the public prompt rather than a peek at the
    answer: the bot has to earn its correct answers from what a runner is
    actually shown, or the vectors would prove nothing about the view.
    """
    if stage.family == "chain":
        return _solve_chain(stage.prompt)
    if stage.family == "cipher":
        return _solve_cipher(stage.prompt)
    return None


def _solve_chain(prompt: str) -> str:
    value = 0
    for sentence in prompt.split(". "):
        words = sentence.strip().rstrip(".?").split()
        if not words:
            continue
        head = words[0]
        if head == "Start":
            value = int(words[2])
        elif head == "Add":
            value += int(words[1])
        elif head == "Subtract":
            value -= int(words[1])
        elif head == "Double":
            value *= 2
        elif head == "Triple":
            value *= 3
    return str(value)


def _solve_cipher(prompt: str) -> str | None:
    words = prompt.replace(",", " ").split()
    if "unknown" in words:
        return None  # tier 3: the shift has to be inferred, which is not arithmetic
    shift = int(words[words.index("forward") + 1])
    token = next(w for w in words if w.isupper() and len(w) > 1)
    encoded = "".join(ch for ch in token if ch.isalpha())  # the sentence's full stop rides along
    return "".join(
        chr(ord("a") + (ord(ch.lower()) - ord("a") - shift) % 26) for ch in encoded
    )


def _guess(stage: PublicStage) -> str:
    """What a program says when it has nothing. For an ordering puzzle it names
    the first runner mentioned — which is occasionally right, and that lucky
    clear is worth having in the vectors. For a cipher it hands back the
    ciphertext, which never is."""
    from .track import ORDER_NAMES

    words = stage.prompt.replace(",", " ").replace(".", " ").split()
    if stage.family == "order":
        return next((w for w in words if w in ORDER_NAMES), "ada")
    token = next((w for w in words if w.isupper() and len(w) > 1), "")
    return "".join(ch for ch in token if ch.isalpha()).lower() or "0"


def check(answer: str | None, stage: Stage) -> bool:
    return answer is not None and normalise(answer) == normalise(stage.answer)
