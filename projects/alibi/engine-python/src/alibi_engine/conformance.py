"""Cross-engine conformance vectors — ALIBI.

Same discipline as LUDO's (ADR-0002): given a seed and the deterministic
`elimination-bot` decider, the Python and Java engines must produce an
identical event stream. The digest covers every event — and because the
archive rides in the transcript (`archive_generated`), **corpus bytes are
inside the digest**: a Java template that renders one comma differently
fails every vector. That is the point.
"""

from __future__ import annotations

import hashlib
from typing import Any

from .case import COLORS
from .deciders import EliminationBot
from .events import ListSink, canonical
from .game import Game, GameConfig

DEFAULT_SEEDS = tuple(range(1, 21))
#: Above the benched p99 of 45, so every vector ends "solved" and the digest
#: exercises the full accusation path.
DEFAULT_MAX_TURNS = 60


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
    outcome = game.play({c: EliminationBot() for c in COLORS})

    return {
        "seed": seed,
        "max_turns": max_turns,
        "decider": EliminationBot.name,
        "reason": outcome.reason,
        "turns_played": outcome.turns_played,
        "events": len(sink.events),
        "solution": outcome.solution,
        "standings": [
            {"player": s["player"], "rank": s["rank"], "solved": s["solved"],
             "belief_dimensions_correct": s["belief_dimensions_correct"]}
            for s in outcome.standings
        ],
        "digest": digest(sink.events),
    }


def generate(seeds: tuple[int, ...] = DEFAULT_SEEDS,
             max_turns: int = DEFAULT_MAX_TURNS) -> dict[str, Any]:
    from .game import ENGINE_VERSION

    return {
        "schema": "alibi-conformance/1",
        "engine_version": ENGINE_VERSION,
        "note": "Regenerate only when the rules or the corpus change deliberately. "
                "An unexpected diff here is a bug, not a refresh.",
        "vectors": [run_vector(s, max_turns) for s in seeds],
    }


def check(expected: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for want in expected["vectors"]:
        got = run_vector(want["seed"], want["max_turns"])
        for field in ("digest", "reason", "turns_played", "events", "solution", "standings"):
            if got[field] != want[field]:
                failures.append(
                    f"seed {want['seed']}: {field} expected {want[field]!r}, got {got[field]!r}"
                )
    return failures
