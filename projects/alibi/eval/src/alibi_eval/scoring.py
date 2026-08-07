"""Deterministic scoring for ALIBI transcripts.

The luxury LUDO's eval never had: **ground truth**. `game_ended.solution` is
the sealed answer, so accusation accuracy and belief calibration are computed,
not judged. Everything here folds over the event stream (ADR-0003 — the
transcript is the only input) and then self-verifies against the engine's own
standings: a scorer that can disagree with the referee and not notice is a
scorer nobody should trust.

Claims stay claims: nothing in a suggestion note, an archive document, or a
notebook write is treated as true. What IS measured about the archive is
*exposure* — which searches returned red-herring documents — because who was
fed a lie, and who then believed it (visible in the belief trajectory), is the
game's own story told in numbers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DIMENSIONS = ("who", "how", "where")


def read_transcript(path: Path) -> list[dict]:
    events = [json.loads(line) for line in
              path.read_text(encoding="utf-8").splitlines() if line]
    if not events:
        raise ValueError(f"{path}: empty transcript")
    if [e["seq"] for e in events] != list(range(len(events))):
        raise ValueError(f"{path}: seq numbers are not contiguous from 0")
    return events


def score(path: Path) -> dict[str, Any]:
    events = read_transcript(path)
    started = _one(events, "game_started")["payload"]
    ended = _one(events, "game_ended")["payload"]
    solution = ended["solution"]
    herrings = set(ended.get("red_herrings", []))
    colors = [p["color"] for p in started["players"]]
    seats = {p["color"]: p.get("seat") for p in started["players"]}

    per: dict[str, dict[str, Any]] = {
        c: {
            "suggestions_made": 0, "refutations_given": 0, "searches_made": 0,
            "herring_docs": set(), "invalid_actions": 0, "memory_writes": 0,
            "tokens_in": 0, "tokens_out": 0, "calls": 0,
            "beliefs": [], "accusation": None, "solved": False, "eliminated": False,
        }
        for c in colors
    }

    for event in events:
        kind, p, turn = event["type"], event["payload"], event["turn"]
        if kind == "suggestion_made":
            per[p["player"]]["suggestions_made"] += 1
        elif kind == "refutation_made" and p["refuter"] is not None:
            per[p["refuter"]]["refutations_given"] += 1
        elif kind == "archive_searched":
            d = per[p["player"]]
            d["searches_made"] += 1
            d["herring_docs"].update(set(p["results"]) & herrings)
        elif kind == "belief_declared":
            per[p["player"]]["beliefs"].append(p)
        elif kind == "accusation_made":
            d = per[p["player"]]
            d["accusation"] = {"turn": turn, "correct": p["correct"]}
            if p["correct"]:
                d["solved"] = True
        elif kind == "detective_eliminated":
            per[p["player"]]["eliminated"] = True
        elif kind == "invalid_action":
            per[p["player"]]["invalid_actions"] += 1
        elif kind == "memory_write":
            per[p["player"]]["memory_writes"] += 1
        elif kind == "llm_call":
            d = per[p["player"]]
            d["tokens_in"] += p["tokens"].get("input", 0)
            d["tokens_out"] += p["tokens"].get("output", 0)
            d["calls"] += 1

    rank_by_color = {s["player"]: s for s in ended["standings"]}
    detectives = []
    for color in colors:
        d = per[color]
        detectives.append({
            "player": color,
            "seat": seats.get(color),
            "rank": rank_by_color[color]["rank"],
            "solved": d["solved"],
            "eliminated": d["eliminated"],
            "accusation": d["accusation"],
            "beliefs": _belief_scores(d["beliefs"], solution),
            "suggestions_made": d["suggestions_made"],
            "refutations_given": d["refutations_given"],
            "searches_made": d["searches_made"],
            "red_herrings_read": len(d["herring_docs"]),
            "invalid_actions": d["invalid_actions"],
            "memory_writes": d["memory_writes"],
            "tokens": {"input": d["tokens_in"], "output": d["tokens_out"],
                       "calls": d["calls"]},
        })

    result = {
        "game": {
            "file": path.name,
            "seed": started["seed"],
            "stack": started.get("stack", "none"),
            **({"profile": started["profile"]} if "profile" in started else {}),
            **({"prompt_set": started["prompt_set"]} if "prompt_set" in started else {}),
            "reason": ended["reason"],
            "turns_played": ended["turns_played"],
            "solution": solution,
            "red_herrings": sorted(herrings),
        },
        "detectives": detectives,
        "checks": {"standings_match": _verify(per, ended["standings"], solution)},
    }
    return result


def _belief_scores(beliefs: list[dict], solution: dict) -> dict[str, Any]:
    """Brier over every declared dimension: (confidence - outcome)^2, where the
    outcome is 1 when the declared element was the sealed one. 0 = clairvoyant,
    1 = confidently wrong. Rounded, so results diff cleanly."""
    if not beliefs:
        return {"declared": 0, "final_dimensions_correct": 0, "mean_brier": None}
    total, n = 0.0, 0
    for belief in beliefs:
        for dim in DIMENSIONS:
            outcome = 1.0 if belief[dim] == solution[dim] else 0.0
            total += (float(belief["confidence"][dim]) - outcome) ** 2
            n += 1
    final = beliefs[-1]
    return {
        "declared": len(beliefs),
        "final_dimensions_correct": sum(final[d] == solution[d] for d in DIMENSIONS),
        "mean_brier": round(total / n, 4),
    }


def _verify(per: dict, standings: list[dict], solution: dict) -> bool:
    """The fold must agree with the referee. Any mismatch is a broken scorer or
    a broken transcript — flagged, never hidden."""
    for row in standings:
        d = per[row["player"]]
        beliefs = d["beliefs"]
        final_correct = (sum(beliefs[-1][dim] == solution[dim] for dim in DIMENSIONS)
                         if beliefs else 0)
        if (d["solved"] != row["solved"]
                or d["eliminated"] != row["eliminated"]
                or final_correct != row["belief_dimensions_correct"]
                or d["suggestions_made"] != row["suggestions_made"]
                or d["refutations_given"] != row["refutations_given"]
                or d["searches_made"] != row["searches_made"]):
            return False
    return True


def engine_skeleton(events: list[dict]) -> list[tuple]:
    """The engine-event spine, for cross-stack conformance: same seed and same
    scripted decisions must produce identical spines in every stack."""
    engine_types = {
        "case_dealt", "archive_generated", "turn_started", "archive_searched",
        "suggestion_made", "refutation_made", "accusation_made",
        "detective_eliminated", "belief_declared", "invalid_action",
        "turn_ended", "game_ended",
    }
    return [
        (e["turn"], e["type"], json.dumps(e["payload"], sort_keys=True))
        for e in events if e["type"] in engine_types
    ]


def _one(events: list[dict], type_: str) -> dict:
    found = [e for e in events if e["type"] == type_]
    if len(found) != 1:
        raise ValueError(f"expected exactly one {type_}, found {len(found)}")
    return found[0]
