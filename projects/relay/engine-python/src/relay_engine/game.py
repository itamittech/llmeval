"""The turn loop — RELAY's referee.

Drives a race to a finisher, a stalled table, or the turn cap, emitting the
shared event stream as it goes. Knows nothing about agents beyond the `Runner`
protocol, and nothing about models at all: the anchor arrives as a plain
callable, the same way the engine has always taken deciders.

Three structural rules a reader should see enforced here rather than trusted:

- **The seal.** Tiers and answers exist in this module and appear in exactly
  one event, `game_ended`. `track_generated` carries prompts only. Nothing a
  runner can reach — its view, its context, its history — has ever held either.
- **The engine performs escalation.** Runners ask the desk; the desk charges
  the shared quota and calls the anchor. `escalated` in the transcript is
  therefore a receipt, not a claim.
- **Ticks are the clock.** Every action's cost is a constant charged here, so
  two runs of one seed produce identical clocks. Real latency is a measurement
  the harness attaches to `llm_call`, and it decides nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .deciders import (
    Attempt, AttemptRecord, Color, COLORS, EscalationDesk, LaneSnapshot,
    NoteRecord, Reflector, Runner, RunnerView, TurnContext, TurnEnd, check,
)
from .events import EventSink
from .rng import Rng
from .track import Stage, TRACK_STAGES, generate

ENGINE_VERSION = "0.1.0"

#: Chances a runner gets to produce a valid attempt before the engine passes
#: for it. Same number as both earlier games.
PHASE_ATTEMPTS = 2

#: The price list. Answering yourself is quick; the anchor is slower even when
#: it is right; being wrong costs on top of whichever you chose.
TICK_ANSWER = 2
TICK_ESCALATE = 5
TICK_WRONG = 4
TICK_PASS = 3

#: Sized by the sweep, not by taste. Above ~12 the pool stops binding at all
#: (quota 12 and quota 20 play identically); at 8 it binds, sharper runners win
#: more, and the weak-runner inversion the bench found is still visible.
ESCALATION_QUOTA = 8
MAX_STALLS = 3
MAX_NOTE_CHARS = 240


@dataclass
class GameConfig:
    seed: int = 1
    max_turns: int = 60
    stages: int = TRACK_STAGES
    escalation_quota: int = ESCALATION_QUOTA
    max_stalls: int = MAX_STALLS
    max_note_chars: int = MAX_NOTE_CHARS
    ruleset: str = "baseline"
    stack: str = "none"
    #: Per-colour metadata for game_started (agent name, model, access).
    players: dict[Color, dict] = field(default_factory=dict)
    #: What escalation consults. None means the perfect anchor of an
    #: engine-only run; a harness passes a closure over its real model, which
    #: receives the PUBLIC stage and never the answer.
    anchor: object = None
    #: Provenance the harness supplies (schema-defined); omitted when None,
    #: which is what keeps conformance vectors byte-stable.
    profile: str | None = None
    prompt_set: dict | None = None
    framework: dict | None = None
    host: dict | None = None
    anchor_meta: dict | None = None


@dataclass
class Outcome:
    reason: str
    turns_played: int
    standings: list[dict]

    @property
    def winner(self) -> Color | None:
        top = self.standings[0]
        return top["player"] if top["finished"] else None


@dataclass
class _LaneState:
    position: int = 0
    ticks: int = 0
    stalls: int = 0
    escalations: int = 0
    correct: int = 0
    wrong: int = 0
    passes: int = 0
    finished: bool = False
    history: list[AttemptRecord] = field(default_factory=list)


class Game:
    def __init__(self, config: GameConfig, sink: EventSink) -> None:
        self.config = config
        self.sink = sink
        self.track: tuple[Stage, ...] = generate(Rng(config.seed), config.stages)
        self.lanes = {c: _LaneState() for c in COLORS}
        self.notes: list[NoteRecord] = []
        self.quota = config.escalation_quota
        self.turn = 0
        self._rotation = -1
        self._finisher: Color | None = None
        self._turn_events: list[dict] = []

    # -- public ----------------------------------------------------------

    def play(self, runners: dict[Color, Runner]) -> Outcome:
        self._emit_start(runners)
        self._emit("track_generated", {
            "stages": [{"id": s.id, "family": s.family, "prompt": s.prompt}
                       for s in self.track],
        })

        while (self.turn < self.config.max_turns and self._finisher is None
               and not self._all_stalled()):
            color = self._next_lane()
            if color is None:
                break
            self.turn += 1
            self._play_turn(color, runners[color])

        if self._finisher is not None:
            reason = "finished"
        elif self._all_stalled():
            reason = "all_stalled"
        else:
            reason = "turn_cap"

        standings = self._standings()
        self._emit("game_ended", {
            "reason": reason,
            "turns_played": self.turn,
            "track_key": [{"id": s.id, "tier": s.tier, "answer": s.answer}
                          for s in self.track],
            "standings": standings,
        })
        return Outcome(reason, self.turn, standings)

    # -- turn ------------------------------------------------------------

    def _play_turn(self, color: Color, runner: Runner) -> None:
        self._turn_events = []
        lane = self.lanes[color]
        stage = self.track[lane.position]
        self._emit("turn_started", {"player": color, "stage": stage.id})

        attempt, desk = self._ask(color, runner, stage)
        note = self._vet_note(color, attempt.note)

        escalated = desk.used
        charged = TICK_ESCALATE if escalated else (
            TICK_PASS if attempt.answer is None else TICK_ANSWER)
        correct = check(attempt.answer, stage)
        if attempt.answer is None:
            lane.passes += 1
            lane.stalls += 1
            reason = "passed"
        elif correct:
            lane.correct += 1
            lane.position += 1
            lane.stalls = 0
            reason = "cleared"
        else:
            lane.wrong += 1
            lane.stalls += 1
            charged += TICK_WRONG
            reason = "missed"

        if escalated:
            lane.escalations += 1
        lane.ticks += charged
        lane.history.append(AttemptRecord(
            self.turn, stage.id, stage.family, escalated, correct))
        if note is not None:
            self.notes.append(NoteRecord(self.turn, color, note))

        self._emit("stage_attempted", {
            "player": color, "stage": stage.id, "answer": attempt.answer,
            "escalated": escalated, "correct": correct,
            "ticks_charged": charged, "ticks_total": lane.ticks,
            "quota_left": self.quota, "note": note,
        })

        if lane.position >= len(self.track):
            lane.finished = True
            self._finisher = color
            reason = "finished"
            self._emit("runner_finished", {"player": color, "ticks": lane.ticks})

        self._emit("turn_ended", {"player": color, "reason": reason})

        if isinstance(runner, Reflector):
            runner.reflect(TurnEnd(
                self._view(color, stage), color, self.turn, reason,
                tuple(self._turn_events),
            ))

    def _ask(self, color: Color, runner: Runner,
             stage: Stage) -> tuple[Attempt, EscalationDesk]:
        """Up to PHASE_ATTEMPTS goes at a valid attempt. The desk is built once
        per turn, so a runner that asks twice pays twice — as it should."""
        desk = self._desk(color, stage)
        for attempt_no in range(1, PHASE_ATTEMPTS + 1):
            ctx = TurnContext(self._view(color, stage), color, self.turn, desk, attempt_no)
            try:
                attempt = runner.attempt(ctx)
            except Exception as exc:  # a broken agent passes; it does not crash the race
                self._invalid(color, "attempt", f"runner error: {type(exc).__name__}", attempt_no)
                continue
            if attempt is None:
                self._invalid(color, "attempt", "no attempt returned", attempt_no)
                continue
            if attempt.answer is not None and not isinstance(attempt.answer, str):
                self._invalid(color, "attempt", "answer must be text", attempt_no)
                continue
            return attempt, desk
        return Attempt(), desk

    def _desk(self, color: Color, stage: Stage) -> EscalationDesk:
        def spend() -> None:
            self.quota -= 1

        def refused() -> None:
            self._invalid(color, "escalate", "shared quota exhausted", 1)

        return EscalationDesk(stage, lambda: self.quota, spend,
                              self.config.anchor, refused)

    def _vet_note(self, color: Color, note: str | None) -> str | None:
        """Notes may lie — that is in-fiction and legal. They may not be
        enormous: an unbounded channel is a cost problem, not a cunning one."""
        if note is None:
            return None
        if not isinstance(note, str):
            self._invalid(color, "note", "note must be text", 1)
            return None
        if len(note) > self.config.max_note_chars:
            self._invalid(color, "note", "note too long", 1)
            return None
        return note

    # -- plumbing --------------------------------------------------------

    def _view(self, color: Color, stage: Stage) -> RunnerView:
        lane = self.lanes[color]
        return RunnerView(
            color, stage.public(), lane.position, lane.ticks, len(self.track),
            self.quota,
            tuple(LaneSnapshot(c, self.lanes[c].position, self.lanes[c].ticks,
                               self.lanes[c].escalations, self.lanes[c].finished)
                  for c in COLORS),
            tuple(self.notes),
            tuple(lane.history),
        )

    def _next_lane(self) -> Color | None:
        for _ in range(len(COLORS)):
            self._rotation = (self._rotation + 1) % len(COLORS)
            color = COLORS[self._rotation]
            if not self.lanes[color].finished:
                return color
        return None

    def _stalled(self, color: Color) -> bool:
        lane = self.lanes[color]
        return lane.finished or lane.stalls > self.config.max_stalls

    def _all_stalled(self) -> bool:
        """Only a spent quota can strand the table: while there is quota left,
        any runner still has a way through its stage."""
        return self.quota <= 0 and all(self._stalled(c) for c in COLORS)

    def _invalid(self, color: Color, phase: str, reason: str, attempt: int) -> None:
        self._emit("invalid_action", {
            "player": color, "phase": phase, "reason": reason, "attempt": attempt,
        })

    def _standings(self) -> list[dict]:
        def key(color: Color):
            lane = self.lanes[color]
            # Further along wins; the clock settles equal progress; colour
            # order settles a dead heat.
            return (-lane.position, lane.ticks, COLORS.index(color))

        ranked = sorted(COLORS, key=key)
        return [
            {
                "player": c,
                "rank": i + 1,
                "stages_cleared": self.lanes[c].position,
                "ticks": self.lanes[c].ticks,
                "finished": self.lanes[c].finished,
                "escalations": self.lanes[c].escalations,
                "correct": self.lanes[c].correct,
                "wrong": self.lanes[c].wrong,
                "passes": self.lanes[c].passes,
            }
            for i, c in enumerate(ranked)
        ]

    # -- emission --------------------------------------------------------

    def _emit(self, type_: str, payload: dict) -> None:
        self._turn_events.append({"type": type_, "payload": payload})
        self.sink.emit(type_, payload, turn=self.turn)

    def _emit_start(self, runners: dict[Color, Runner]) -> None:
        players = []
        for color in COLORS:
            meta = dict(self.config.players.get(color, {}))
            meta.setdefault("agent", getattr(runners.get(color), "name", "unknown"))
            players.append({"color": color, **meta})

        tiers = {"1": 0, "2": 0, "3": 0}
        for stage in self.track:
            tiers[str(stage.tier)] += 1

        payload = {
            "seed": self.config.seed,
            "max_turns": self.config.max_turns,
            "escalation_quota": self.config.escalation_quota,
            "max_stalls": self.config.max_stalls,
            "max_note_chars": self.config.max_note_chars,
            "ruleset": self.config.ruleset,
            "stack": self.config.stack,
            "engine": {"language": "python", "version": ENGINE_VERSION},
            "track": {"stages": len(self.track), "tiers": tiers},
            "ticks": {"answer": TICK_ANSWER, "escalate": TICK_ESCALATE,
                      "wrong": TICK_WRONG, "pass": TICK_PASS},
            "players": players,
        }
        for key, name in (("profile", "profile"), ("prompt_set", "prompt_set"),
                          ("framework", "framework"), ("host", "host"),
                          ("anchor_meta", "anchor")):
            value = getattr(self.config, key)
            if value is not None:
                payload[name] = value
        self._emit("game_started", payload)
