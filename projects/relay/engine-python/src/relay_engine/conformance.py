"""Cross-engine conformance vectors — RELAY.

Same discipline as LUDO's and ALIBI's (ADR-0002): given a seed and the
deterministic `ladder-runner`, the Python and Java engines must produce an
identical event stream.

Two things ride inside the digest that are worth naming, because they are where
a port will actually break:

- **Stage prompts.** The whole track is in `track_generated`, so every
  generated sentence is hashed. A Java port that writes "Start with 7 ." or
  builds its constraint list in a different order fails every vector.
- **The bot's own arithmetic.** `ladder-runner` solves by parsing the prompt it
  was shown. If the two parsers disagree about anything — a trailing question
  mark, a negative number — the answers diverge and so do the standings.
"""

from __future__ import annotations

import hashlib
from typing import Any

from .deciders import COLORS, LadderRunner
from .events import ListSink, canonical
from .game import Game, GameConfig

DEFAULT_SEEDS = tuple(range(1, 21))
#: High enough that a seed which can finish, does — so the vectors cover the
#: finishing path as well as the stall.
DEFAULT_MAX_TURNS = 80


def for_digest(event: dict[str, Any]) -> dict[str, Any]:
    """Drop the one field that must differ between engines — same lesson the
    LUDO vectors learned the hard way."""
    if event["type"] != "game_started":
        return event
    payload = {k: v for k, v in event["payload"].items() if k != "engine"}
    return {**event, "payload": payload}


def digest(events: list[dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for event in events:
        h.update(canonical(for_digest(event)).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def run_vector(seed: int, max_turns: int = DEFAULT_MAX_TURNS) -> dict[str, Any]:
    sink = ListSink()
    game = Game(GameConfig(seed=seed, max_turns=max_turns), sink)
    outcome = game.play({c: LadderRunner() for c in COLORS})

    return {
        "seed": seed,
        "max_turns": max_turns,
        "decider": LadderRunner.name,
        "reason": outcome.reason,
        "turns_played": outcome.turns_played,
        "events": len(sink.events),
        "standings": [
            {"player": s["player"], "rank": s["rank"],
             "stages_cleared": s["stages_cleared"], "ticks": s["ticks"],
             "escalations": s["escalations"]}
            for s in outcome.standings
        ],
        "digest": digest(sink.events),
    }


def generate(seeds: tuple[int, ...] = DEFAULT_SEEDS,
             max_turns: int = DEFAULT_MAX_TURNS) -> dict[str, Any]:
    from .game import ENGINE_VERSION

    return {
        "schema": "relay-conformance/1",
        "engine_version": ENGINE_VERSION,
        "note": "Regenerate only when the rules or the stage generators change "
                "deliberately. An unexpected diff here is a bug, not a refresh.",
        "vectors": [run_vector(s, max_turns) for s in seeds],
    }


def check(expected: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for want in expected["vectors"]:
        got = run_vector(want["seed"], want["max_turns"])
        for field in ("digest", "reason", "turns_played", "events", "standings"):
            if got[field] != want[field]:
                failures.append(
                    f"seed {want['seed']}: {field} expected {want[field]!r}, got {got[field]!r}"
                )
    return failures
