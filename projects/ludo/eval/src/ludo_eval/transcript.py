"""Loading a transcript, and folding it back into a game.

The eval never asks an engine what happened — it replays the event stream,
the same discipline as the UI's projector. The one subtlety both share:
**three consecutive sixes cancel the whole turn**, engine-side, by restoring
a snapshot. The fold mirrors that with apply-on-commit: a turn's effects
accumulate in a buffer and land only when ``turn_ended`` says the turn stood.
No undo journal, no drift — a discarded buffer is exactly a restored snapshot.

Trust, but verify: :func:`fold` cross-checks its own final positions against
``game_ended.standings`` — the engine's authoritative account — and raises if
they disagree. A fold that quietly diverged from the engine would poison
every number downstream of it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

COLORS = ("red", "green", "yellow", "blue")
HOME = 56
CIRCUIT_LEN = 52


def load(path: str | Path) -> list[dict]:
    """Read a JSONL transcript, in seq order, with the order verified."""
    events = [json.loads(line)
              for line in Path(path).read_text(encoding="utf-8").splitlines() if line]
    for i, event in enumerate(events):
        if event.get("seq") != i:
            raise ValueError(f"{path}: seq {event.get('seq')} at line {i + 1} — "
                             f"transcript is not a contiguous sequence")
    return events


@dataclass
class PlayerFold:
    """One player's replayed game."""

    positions: list[int] = field(default_factory=lambda: [-1, -1, -1, -1])
    captures_made: int = 0
    captures_suffered: int = 0
    #: The engine's counter: illegal moves (and, live, timeouts). Three sixes
    #: cancel a turn but the engine does NOT count them here — verified
    #: against game_ended.standings, which is how this comment got written.
    turns_forfeited: int = 0
    three_sixes: int = 0
    home_entries: int = 0
    turns_taken: int = 0
    #: Committed turn-ends at which this player held a block — two or more of
    #: their own tokens on one circuit square (evaluation.md's play record).
    block_turns: int = 0

    @property
    def tokens_home(self) -> int:
        return sum(1 for p in self.positions if p == HOME)

    @property
    def tokens_in_base(self) -> int:
        return sum(1 for p in self.positions if p == -1)

    @property
    def progress(self) -> int:
        return sum(p + 1 for p in self.positions if p >= 0)


@dataclass
class GameFold:
    """The whole game, replayed from its stream."""

    players: dict[str, PlayerFold]
    stack: str
    seed: int | None
    seats: dict[str, dict]
    turns_played: int
    reason: str
    standings: list[dict]

    def standing_rank(self, color: str) -> int:
        for row in self.standings:
            if row["player"] == color:
                return row["rank"]
        raise KeyError(color)


def fold(events: list[dict]) -> GameFold:
    players = {c: PlayerFold() for c in COLORS}
    stack, seed, seats = "unknown", None, {}
    turns_played, reason, standings = 0, "unknown", []

    # The turn buffer: (kind, *args) applied only if the turn commits.
    pending: list[tuple] = []

    def commit() -> None:
        for entry in pending:
            kind = entry[0]
            if kind == "move":
                _, color, token, to = entry
                players[color].positions[token] = to
            elif kind == "capture":
                _, attacker, victim, victim_token = entry
                players[attacker].captures_made += 1
                players[victim].captures_suffered += 1
                players[victim].positions[victim_token] = -1
            elif kind == "home":
                _, color = entry
                players[color].home_entries += 1
        pending.clear()

    for event in events:
        type_, payload = event["type"], event["payload"]

        if type_ == "game_started":
            stack = payload.get("stack", "unknown")
            seed = payload.get("seed")
            # The engine serialises players as a list of {color, agent, seat?,
            # model?, access?}; key it by colour for everyone downstream.
            seats = {p["color"]: p for p in payload.get("players") or []}
        elif type_ == "move_made":
            pending.append(("move", payload["player"], payload["token"], payload["to"]))
        elif type_ == "token_captured":
            pending.append(("capture", payload["captor"],
                            payload["victim"], payload["victim_token"]))
        elif type_ == "token_home":
            pending.append(("home", payload["player"]))
        elif type_ == "turn_ended":
            color = payload["player"]
            if payload["reason"] == "three_sixes":
                pending.clear()          # the engine restored its snapshot; we drop ours
                players[color].three_sixes += 1
            else:
                commit()
                if payload["reason"] in ("illegal_move", "timeout"):
                    players[color].turns_forfeited += 1
            players[color].turns_taken += 1
            fold_ = players[color]
            circuit = [p % CIRCUIT_LEN for p in _absolute(color, fold_.positions)]
            if len(circuit) != len(set(circuit)):
                fold_.block_turns += 1
        elif type_ == "game_ended":
            turns_played = payload["turns_played"]
            reason = payload["reason"]
            standings = payload["standings"]

    result = GameFold(players, stack, seed, seats, turns_played, reason, standings)
    _verify(result)
    return result


def _absolute(color: str, positions: list[int]) -> list[int]:
    """Circuit positions only (0–50 relative), as absolute squares."""
    offset = COLORS.index(color) * 13
    return [(p + offset) for p in positions if 0 <= p <= 50]


def _verify(game: GameFold) -> None:
    """The fold must agree with the engine's own final account."""
    for row in game.standings:
        fold_ = game.players[row["player"]]
        for claim, ours in (("tokens_home", fold_.tokens_home),
                            ("progress", fold_.progress),
                            ("captures_made", fold_.captures_made),
                            ("captures_suffered", fold_.captures_suffered),
                            ("turns_forfeited", fold_.turns_forfeited)):
            if claim in row and row[claim] != ours:
                raise ValueError(
                    f"fold disagrees with game_ended for {row['player']}: "
                    f"{claim} replayed as {ours}, engine says {row[claim]} — "
                    f"the transcript and this fold cannot both be right")
