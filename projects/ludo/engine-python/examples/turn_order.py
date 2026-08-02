"""Does moving first win Ludo games?

    uv run --directory projects/ludo/engine-python python examples/turn_order.py

Red moves first, then green, yellow, blue. The intuition that this is an
advantage is strong enough that ADR-0006 was originally written asserting it.
It isn't true, and this is the script that said so.

Both runs put IDENTICAL deciders in all four seats, so turn order is the only
thing that differs between them. Any win-rate skew is the seat, not the player.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from custom_agent import GreedyBot
from ludo_engine import COLORS, Game, GameConfig, ListSink, RandomBot

GAMES = 2000
CRITICAL_5PCT = 7.81          # chi-square, 3 degrees of freedom


def run(label: str, make_deciders) -> None:
    wins: Counter[str] = Counter()
    for seed in range(GAMES):
        game = Game(GameConfig(seed=seed, max_turns=800), ListSink())
        wins[game.play(make_deciders(seed)).winner] += 1

    expected = GAMES / 4
    chi = sum((wins[c] - expected) ** 2 / expected for c in COLORS)

    print(f"\n{label} — {GAMES} games")
    for i, color in enumerate(COLORS, start=1):
        pct = 100 * wins[color] / GAMES
        print(f"  {i}. {color:<7}{wins[color]:>5}{pct:7.2f}%  " + "#" * round(pct))
    print(f"  chi-square {chi:5.2f} on 3 df (5% critical value {CRITICAL_5PCT})"
          f"  ->  {'seat matters' if chi > CRITICAL_5PCT else 'no detectable effect'}")


def main() -> None:
    # Bot seeds vary with the game so no colour gets a permanently lucky bot.
    run("Four random bots",
        lambda seed: {c: RandomBot(seed=seed * 10 + i) for i, c in enumerate(COLORS)})

    # Skill could plausibly amplify a first-mover edge that noise hides.
    run("Four identical heuristic bots",
        lambda seed: {c: GreedyBot() for c in COLORS})

    print("\nNeither is significant. See ADR-0006 for why the seat mapping still rotates.")


if __name__ == "__main__":
    main()
