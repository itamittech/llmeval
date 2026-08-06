"""Assembling, validating, and summarising one game's eval result.

The machine-readable result is validated against
``shared/schemas/eval-result.schema.json`` before it leaves this module —
an eval that emits results its own schema rejects would be the measuring
instrument nobody calibrated. The human summary is a terminal rendering of
the same dict; the UI's eval view, when it exists, reads the JSON.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from jsonschema import Draft202012Validator

from .judge import JudgeOutcome, repo_root
from .scoring import score
from .transcript import COLORS, GameFold


def build_result(path: str | Path, events: list[dict], game: GameFold,
                 judge: JudgeOutcome | None = None) -> dict:
    players = score(game, events)
    tokens_in = sum(p["efficiency"]["tokens_in"] for p in players.values())
    tokens_out = sum(p["efficiency"]["tokens_out"] for p in players.values())
    costs = [p["efficiency"]["cost_usd"] for p in players.values()
             if p["efficiency"]["cost_usd"] is not None]
    result = {
        "eval_version": 1,
        "game": {
            "file": Path(path).name,
            "stack": game.stack,
            "seed": game.seed,
            "turns_played": game.turns_played,
            "reason": game.reason if game.reason in ("completed", "turn_cap")
                      else "unknown",
        },
        "players": players,
        "judge": None if judge is None else {
            "model": judge.judge_model,
            "prompt_hash": judge.prompt_hash,
            "runs": judge.runs,
            "failed_runs": judge.failed_runs,
            "discarded_unsourced": judge.discarded_unsourced,
            "agreement_with_outcome": judge.agreement_with_outcome,
            "scores": judge.scores,
        },
        "totals": {
            "events": len(events),
            "llm_calls": sum(p["efficiency"]["llm_calls"] for p in players.values()),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": sum(costs) if costs else None,
        },
    }
    validate(result)
    return result


def validate(result: dict) -> None:
    schema = json.loads(
        (repo_root() / "shared" / "schemas" / "eval-result.schema.json")
        .read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(result)


def summary(result: dict) -> str:
    """The terminal rendering: standings first, then what they cost."""
    game = result["game"]
    lines = [f"{game['file']} — stack {game['stack']}, seed {game['seed']}, "
             f"{game['turns_played']} turns, {game['reason']}", ""]
    by_rank = sorted(COLORS, key=lambda c: result["players"][c]["rank"])
    for color in by_rank:
        p = result["players"][color]
        pos, play, eff = p["position"], p["play"], p["efficiency"]
        lines.append(
            f"  {p['rank']}. {color:<7} home {pos['tokens_home']}  "
            f"progress {pos['progress']:>3}  score {pos['score']:>4}  | "
            f"captures {play['captures_made']}/{play['captures_suffered']}  "
            f"forfeits {play['turns_forfeited']}  | "
            f"calls {eff['llm_calls']:>2}  tokens {eff['tokens_in'] + eff['tokens_out']:>6}")
    totals = result["totals"]
    lines.append("")
    lines.append(f"  game: {totals['events']} events, {totals['llm_calls']} llm calls, "
                 f"{totals['tokens_in'] + totals['tokens_out']} tokens"
                 + (f", ${totals['cost_usd']:.4f}" if totals["cost_usd"] else ""))
    judge = result["judge"]
    if judge:
        lines.append(f"  judge: {judge['model']} ×{judge['runs']} runs "
                     f"({judge['failed_runs']} failed, "
                     f"{judge['discarded_unsourced']} unsourced scores discarded)"
                     + (f", agreement with outcome {judge['agreement_with_outcome']}"
                        if judge["agreement_with_outcome"] is not None else ""))
        for color in by_rank:
            cells = judge["scores"][color]
            means = [f"{key.split('_')[0]} {cell['mean']}"
                     for key, cell in cells.items() if cell["mean"] is not None]
            if means:
                lines.append(f"    {color:<7} " + "  ".join(means))
    return "\n".join(lines)


def compare(results: list[dict]) -> str:
    """The framework question: the same matchup, three runtimes, side by side.

    Everything here is stack overhead, not play quality — the players are the
    same scripts; only the harness differs (evaluation.md, "which stack ran
    the game best").
    """
    lines = ["stack       events  calls  tokens_in  tokens_out  messages  "
             "compactions  forfeits"]
    for r in sorted(results, key=lambda r: r["game"]["stack"] or ""):
        players = r["players"].values()
        lines.append(
            f"{(r['game']['stack'] or '?'):<11} "
            f"{r['totals']['events']:>6}  "
            f"{r['totals']['llm_calls']:>5}  "
            f"{r['totals']['tokens_in']:>9}  "
            f"{r['totals']['tokens_out']:>10}  "
            f"{sum(p['negotiation']['messages_sent'] + p['negotiation']['table_notes'] for p in players):>8}  "
            f"{sum(p['negotiation']['compactions'] for p in players):>11}  "
            f"{sum(p['play']['turns_forfeited'] for p in players):>8}")
    return "\n".join(lines)
