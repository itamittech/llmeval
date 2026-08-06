"""The turn loop.

Drives a game to completion or to the turn cap, emitting the shared event
stream as it goes. Knows nothing about agents beyond the `Decider` protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .board import COLORS, HOME, Color, to_square
from .deciders import (
    Decider, Negotiator, Reflector, StateView, TurnContext, TurnEnd, TurnStart,
)
from .dice import Dice
from .events import EventSink
from .moves import Move, apply_move, legal_moves
from .state import GameState, standings

ENGINE_VERSION = "0.1.0"

#: Consecutive sixes that forfeit the turn and revert everything done in it.
SIX_LIMIT = 3

#: Chances an agent gets to produce a legal move before forfeiting the turn.
MOVE_ATTEMPTS = 2


@dataclass
class GameConfig:
    seed: int = 1
    max_turns: int = 200
    ruleset: str = "baseline"
    stack: str = "none"
    #: Per-colour metadata for the game_started event (agent name, model, access).
    players: dict[Color, dict] = field(default_factory=dict)
    #: Provenance the harness supplies and the schema defines — profile name,
    #: {"version", "hash"} of the prompt set, {"name", "version"} of the
    #: framework. None on engine-only runs, and then OMITTED from the event,
    #: which is what keeps the conformance vectors byte-stable.
    profile: str | None = None
    prompt_set: dict | None = None
    framework: dict | None = None


@dataclass
class Outcome:
    reason: str
    turns_played: int
    standings: list[dict]

    @property
    def winner(self) -> Color:
        return self.standings[0]["player"]


class Game:
    def __init__(self, config: GameConfig, sink: EventSink) -> None:
        self.config = config
        self.sink = sink
        self.state = GameState()
        self.dice = Dice(config.seed)
        self.turn = 0
        self._rotation = -1
        #: Engine events emitted during the current turn, handed to `reflect`.
        self._turn_events: list[dict] = []

    # -- public ----------------------------------------------------------

    def play(self, deciders: dict[Color, Decider]) -> Outcome:
        self._emit_start(deciders)

        # Stop at three finishers: the fourth player's place is already decided.
        while self.turn < self.config.max_turns and len(self.state.finished) < 3:
            color = self._next_player()
            self.turn += 1
            self._play_turn(color, deciders[color])

        reason = "completed" if len(self.state.finished) >= 3 else "turn_cap"
        result = standings(self.state)
        self._emit("game_ended", {
            "reason": reason,
            "turns_played": self.turn,
            "standings": result,
        })
        return Outcome(reason, self.turn, result)

    # -- turn ------------------------------------------------------------

    def _play_turn(self, color: Color, decider: Decider) -> None:
        """One turn, with the two optional agent hooks around the roll loop.

        Neither hook is wrapped in try/except, unlike `choose`. The engine
        absorbs a failure only when it has a defined in-game meaning — a bad
        `choose` forfeits the turn, which is a real outcome. A model provider
        erroring mid-negotiation has no such meaning, so it belongs to the
        harness that made the call. Swallowing it here would produce a
        transcript that lies about what happened.
        """
        self._turn_events = []
        self._emit("turn_started", {"player": color})

        # One view for the whole turn: agents inspect, they do not mutate.
        view = StateView(self.state)

        if isinstance(decider, Negotiator):
            decider.negotiate(TurnStart(view, color, self.turn))

        reason = self._roll_loop(color, decider, view)
        self._emit("turn_ended", {"player": color, "reason": reason})

        if isinstance(decider, Reflector):
            decider.reflect(
                TurnEnd(view, color, self.turn, reason, tuple(self._turn_events))
            )

    def _roll_loop(self, color: Color, decider: Decider, view: StateView) -> str:
        """Roll, decide, resolve — repeating on a six or a capture.

        Returns the reason the turn ended, which the caller emits.
        """
        before = self.state.snapshot()
        sixes = 0
        roll_index = 0

        while True:
            die = self.dice.roll()
            self._emit("dice_rolled", {"player": color, "value": die, "roll_index": roll_index})
            roll_index += 1

            sixes = sixes + 1 if die == 6 else 0
            if sixes == SIX_LIMIT:
                # Cancel the whole turn, including movement and captures.
                self.state.restore(before)
                return "three_sixes"

            moves = legal_moves(self.state, color, die)
            if not moves:
                return "no_legal_move"

            move = self._decide(color, decider, die, moves, view)
            if move is None:
                self.state.stats[color].turns_forfeited += 1
                return "illegal_move"

            captured = self._apply(color, move)

            if self.state.has_finished(color):
                self.state.finished.append(color)
                self._emit("player_finished", {
                    "player": color, "rank": len(self.state.finished),
                })
                return "moved"

            if die == 6 or captured:
                self._emit("extra_roll_granted", {
                    "player": color, "reason": "six" if die == 6 else "capture",
                })
                continue

            return "moved"

    def _apply(self, color: Color, move: Move) -> bool:
        captures = apply_move(self.state, color, move)
        self._emit("move_made", {
            "player": color,
            "token": move.token,
            "from": move.frm,
            "to": move.to,
            "from_square": to_square(color, move.frm),
            "to_square": to_square(color, move.to),
        })
        for cap in captures:
            self._emit("token_captured", {
                "captor": color,
                "captor_token": move.token,
                "victim": cap.victim,
                "victim_token": cap.victim_token,
                "square": cap.square,
            })
        if move.to == HOME:
            self._emit("token_home", {"player": color, "token": move.token})
        return bool(captures)

    def _decide(
        self, color: Color, decider: Decider, die: int, moves: list[Move],
        view: StateView,
    ) -> Move | None:
        """Ask for a move, rejecting illegal ones rather than correcting them."""
        allowed = set(moves)

        for attempt in range(1, MOVE_ATTEMPTS + 1):
            ctx = TurnContext(view, color, die, list(moves), self.turn, attempt)
            try:
                move = decider.choose(ctx)
            except Exception as exc:  # a broken agent forfeits; it does not crash the game
                self._emit("illegal_move_rejected", {
                    "player": color, "token": None, "requested_to": None,
                    "reason": f"decider error: {type(exc).__name__}", "attempt": attempt,
                })
                continue

            if move in allowed:
                return move

            self._emit("illegal_move_rejected", {
                "player": color,
                "token": getattr(move, "token", None),
                "requested_to": getattr(move, "to", None),
                "reason": "not a legal move for this roll",
                "attempt": attempt,
            })

        return None

    def _next_player(self) -> Color:
        while True:
            self._rotation = (self._rotation + 1) % len(COLORS)
            color = COLORS[self._rotation]
            if not self.state.has_finished(color):
                return color

    # -- emission --------------------------------------------------------

    def _emit(self, type_: str, payload: dict) -> None:
        # Also buffered for the turn, so `reflect` gets what happened without
        # the harness having to reconstruct it from the sink.
        self._turn_events.append({"type": type_, "payload": payload})
        self.sink.emit(type_, payload, turn=self.turn)

    def _emit_start(self, deciders: dict[Color, Decider]) -> None:
        players = []
        for color in COLORS:
            meta = dict(self.config.players.get(color, {}))
            meta.setdefault("agent", getattr(deciders.get(color), "name", "unknown"))
            players.append({"color": color, **meta})

        payload = {
            "seed": self.config.seed,
            "max_turns": self.config.max_turns,
            "ruleset": self.config.ruleset,
            "stack": self.config.stack,
            "engine": {"language": "python", "version": ENGINE_VERSION},
            "players": players,
        }
        for key in ("profile", "prompt_set", "framework"):
            value = getattr(self.config, key)
            if value is not None:
                payload[key] = value
        self._emit("game_started", payload)
