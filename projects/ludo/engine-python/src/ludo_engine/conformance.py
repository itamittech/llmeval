"""Cross-engine conformance vectors.

ADR-0002 keeps one engine per language rather than one per stack. The Python and
Java engines are held to the same rules by these vectors: given a seed and the
deterministic `first-legal` decider, both must produce an identical event stream.

Because the decider is deterministic, a vector need only record the seed — the
entire game follows from it. The digest covers every event, so any divergence in
rules, ordering, or dice shows up as a mismatch.
"""

from __future__ import annotations

import hashlib
from typing import Any

from .deciders import FirstLegal
from .events import ListSink, canonical
from .game import Game, GameConfig

DEFAULT_SEEDS = tuple(range(1, 21))
DEFAULT_MAX_TURNS = 400


def for_digest(event: dict[str, Any]) -> dict[str, Any]:
    """Drop the one field that is *required* to differ between engines.

    `game_started.payload.engine` records which engine produced the transcript —
    `{"language": "python"}` here, `{"language": "java"}` there. Including it made the
    vectors unsatisfiable by any engine but the one that generated them, which is the
    opposite of what they are for. Found the first time the Java engine was run against
    them; nothing else in the payload is excluded, because everything else is either
    rules-driven or already an explicit field on the vector.
    """
    if event["type"] != "game_started":
        return event
    payload = {k: v for k, v in event["payload"].items() if k != "engine"}
    return {**event, "payload": payload}


def digest(events: list[dict[str, Any]]) -> str:
    """SHA-256 over the canonical form of every event, minus engine identity."""
    h = hashlib.sha256()
    for event in events:
        h.update(canonical(for_digest(event)).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def run_vector(seed: int, max_turns: int = DEFAULT_MAX_TURNS) -> dict[str, Any]:
    """Play one fully deterministic game and summarise it."""
    from .board import COLORS

    sink = ListSink()
    game = Game(GameConfig(seed=seed, max_turns=max_turns), sink)
    outcome = game.play({c: FirstLegal() for c in COLORS})

    return {
        "seed": seed,
        "max_turns": max_turns,
        "decider": FirstLegal.name,
        "reason": outcome.reason,
        "turns_played": outcome.turns_played,
        "events": len(sink.events),
        "standings": [
            {"player": s["player"], "rank": s["rank"],
             "tokens_home": s["tokens_home"], "progress": s["progress"]}
            for s in outcome.standings
        ],
        "digest": digest(sink.events),
    }


def generate(seeds: tuple[int, ...] = DEFAULT_SEEDS,
             max_turns: int = DEFAULT_MAX_TURNS) -> dict[str, Any]:
    from .game import ENGINE_VERSION

    return {
        "schema": "ludo-conformance/1",
        "engine_version": ENGINE_VERSION,
        "note": "Regenerate only when the rules change deliberately. "
                "An unexpected diff here is a bug, not a refresh.",
        "vectors": [run_vector(s, max_turns) for s in seeds],
    }


def check(expected: dict[str, Any]) -> list[str]:
    """Replay every vector and return human-readable mismatches."""
    failures: list[str] = []
    for want in expected["vectors"]:
        got = run_vector(want["seed"], want["max_turns"])
        for field in ("digest", "reason", "turns_played", "events", "standings"):
            if got[field] != want[field]:
                failures.append(
                    f"seed {want['seed']}: {field} expected {want[field]!r}, got {got[field]!r}"
                )
    return failures
