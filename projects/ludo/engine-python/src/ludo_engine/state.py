"""Mutable game state, plus the snapshot support the three-sixes rule needs."""

from __future__ import annotations

from dataclasses import dataclass, field

from .board import BASE, COLORS, HOME, TOKENS_PER_PLAYER, Color, token_progress


@dataclass
class PlayerStats:
    captures_made: int = 0
    captures_suffered: int = 0
    turns_forfeited: int = 0


@dataclass
class GameState:
    """Board position and running counters.

    Turn number and whose turn it is live in :class:`~ludo_engine.game.Game`,
    not here — they survive a three-sixes cancellation, whereas everything in
    this class is reverted by it.
    """

    tokens: dict[Color, list[int]] = field(
        default_factory=lambda: {c: [BASE] * TOKENS_PER_PLAYER for c in COLORS}
    )
    stats: dict[Color, PlayerStats] = field(
        default_factory=lambda: {c: PlayerStats() for c in COLORS}
    )
    #: Colours that have got all four tokens home, in finishing order.
    finished: list[Color] = field(default_factory=list)

    # -- queries ---------------------------------------------------------

    def tokens_home(self, color: Color) -> int:
        return sum(1 for p in self.tokens[color] if p == HOME)

    def progress(self, color: Color) -> int:
        """Total steps travelled by all four tokens. Maximum 4 x 57 = 228."""
        return sum(token_progress(p) for p in self.tokens[color])

    def has_finished(self, color: Color) -> bool:
        return self.tokens_home(color) == TOKENS_PER_PLAYER

    # -- snapshot --------------------------------------------------------

    def snapshot(self) -> Snapshot:
        """Capture everything three consecutive sixes must undo."""
        return Snapshot(
            tokens={c: list(p) for c, p in self.tokens.items()},
            stats={c: PlayerStats(s.captures_made, s.captures_suffered, s.turns_forfeited)
                   for c, s in self.stats.items()},
            finished=list(self.finished),
        )

    def restore(self, snap: Snapshot) -> None:
        self.tokens = {c: list(p) for c, p in snap.tokens.items()}
        self.stats = {c: PlayerStats(s.captures_made, s.captures_suffered, s.turns_forfeited)
                      for c, s in snap.stats.items()}
        self.finished = list(snap.finished)


@dataclass(frozen=True)
class Snapshot:
    tokens: dict[Color, list[int]]
    stats: dict[Color, PlayerStats]
    finished: list[Color]


def standings(state: GameState) -> list[dict]:
    """Final or mid-game ranking.

    Players who finished are ranked by finishing order. Everyone else is ranked
    by tokens home, then total progress — which is what makes a turn-capped game
    scoreable rather than void.
    """
    ranked: list[Color] = list(state.finished)
    rest = [c for c in COLORS if c not in state.finished]
    rest.sort(key=lambda c: (state.tokens_home(c), state.progress(c)), reverse=True)
    ranked.extend(rest)

    return [
        {
            "player": c,
            "rank": i + 1,
            "tokens_home": state.tokens_home(c),
            "progress": state.progress(c),
            "finished": c in state.finished,
            "captures_made": state.stats[c].captures_made,
            "captures_suffered": state.stats[c].captures_suffered,
            "turns_forfeited": state.stats[c].turns_forfeited,
        }
        for i, c in enumerate(ranked)
    ]
