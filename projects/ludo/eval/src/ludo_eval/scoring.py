"""Layer 1 — deterministic scoring. Free, instant, identical every replay.

Three families of signal per evaluation.md: **position** (the board when the
game ended), **play record** (what happened along the way), **efficiency**
(what it cost to get there). Plus the verbosity metric the judge-bias table
demands be reported *separately* rather than folded into any score.

Two honesty rules baked in rather than documented beside:

- **Rank is the engine's, never ours.** ``game_ended.standings`` already
  orders players (tokens home, then progress); a finished game has a winner
  and nothing in this layer — base penalties included — may reorder that.
  The position *score* is a reported scalar; the *rank* is copied.
- **Weights are provisional**, like every number in ``models.yaml``: chosen
  to make the components legible (a token home outweighs any progress; a
  token still in base drags), replaced by measured judgement once live games
  exist. They live here, at the top, in capitals, so nobody mistakes them
  for findings.
"""

from __future__ import annotations

from dataclasses import dataclass

from .transcript import COLORS, GameFold, PlayerFold

WEIGHT_TOKENS_HOME = 100     # dominant
WEIGHT_PROGRESS = 1          # secondary
PENALTY_IN_BASE = 10         # a token that never left costs, mildly


def position_score(fold: PlayerFold) -> int:
    return (WEIGHT_TOKENS_HOME * fold.tokens_home
            + WEIGHT_PROGRESS * fold.progress
            - PENALTY_IN_BASE * fold.tokens_in_base)


@dataclass(frozen=True)
class Usage:
    """Per-player accounting folded from ``llm_call`` and friends."""

    tokens_in: int = 0
    tokens_out: int = 0
    calls: int = 0
    cost_usd: float | None = None
    reasoning_chars: int = 0
    messages_sent: int = 0
    table_notes: int = 0
    memory_writes: int = 0
    compactions: int = 0
    guardrails_triggered: int = 0

    @property
    def tokens(self) -> int:
        return self.tokens_in + self.tokens_out


def usage_by_player(events: list[dict]) -> dict[str, Usage]:
    counts = {c: {"tokens_in": 0, "tokens_out": 0, "calls": 0, "cost": None,
                  "reasoning_chars": 0, "messages_sent": 0, "table_notes": 0,
                  "memory_writes": 0, "compactions": 0, "guardrails_triggered": 0}
              for c in COLORS}
    for event in events:
        payload = event["payload"]
        player = payload.get("player")
        if player not in counts:
            continue
        c = counts[player]
        type_ = event["type"]
        if type_ == "llm_call":
            tokens = payload.get("tokens") or {}
            c["tokens_in"] += tokens.get("input", 0) + tokens.get("cache_read", 0)
            c["tokens_out"] += tokens.get("output", 0)
            c["calls"] += 1
            if payload.get("cost_usd") is not None:
                c["cost"] = (c["cost"] or 0.0) + payload["cost_usd"]
        elif type_ == "agent_reasoning":
            c["reasoning_chars"] += len(payload.get("text") or "")
        elif type_ == "message_sent":
            if payload.get("to") is None:
                c["table_notes"] += 1
            else:
                c["messages_sent"] += 1
        elif type_ == "memory_write":
            c["memory_writes"] += 1
        elif type_ == "context_compacted":
            c["compactions"] += 1
        elif type_ == "guardrail_triggered":
            c["guardrails_triggered"] += 1
    return {color: Usage(tokens_in=v["tokens_in"], tokens_out=v["tokens_out"],
                         calls=v["calls"], cost_usd=v["cost"],
                         reasoning_chars=v["reasoning_chars"],
                         messages_sent=v["messages_sent"], table_notes=v["table_notes"],
                         memory_writes=v["memory_writes"], compactions=v["compactions"],
                         guardrails_triggered=v["guardrails_triggered"])
            for color, v in counts.items()}


def score(game: GameFold, events: list[dict]) -> dict[str, dict]:
    """The deterministic layer, per player, ready for the report."""
    usage = usage_by_player(events)
    out: dict[str, dict] = {}
    for color in COLORS:
        fold = game.players[color]
        u = usage[color]
        seat = (game.seats.get(color) or {}).get("seat")
        progress = fold.progress
        out[color] = {
            "seat": seat,
            "rank": game.standing_rank(color),          # the engine's, verbatim
            "position": {
                "tokens_home": fold.tokens_home,
                "progress": progress,
                "tokens_in_base": fold.tokens_in_base,
                "score": position_score(fold),
            },
            "play": {
                "captures_made": fold.captures_made,
                "captures_suffered": fold.captures_suffered,
                "turns_forfeited": fold.turns_forfeited,
                "three_sixes": fold.three_sixes,
                "home_entries": fold.home_entries,
                "block_turns": fold.block_turns,
            },
            "efficiency": {
                "llm_calls": u.calls,
                "tokens_in": u.tokens_in,
                "tokens_out": u.tokens_out,
                "progress_per_turn": round(progress / fold.turns_taken, 3)
                                     if fold.turns_taken else 0.0,
                "progress_per_1k_tokens": round(progress / (u.tokens / 1000), 3)
                                          if u.tokens else None,
                "cost_usd": u.cost_usd,
                # The verbosity metric, reported separately by design — the
                # judge rubric scores substance, this number carries length.
                "reasoning_chars": u.reasoning_chars,
            },
            "negotiation": {
                "messages_sent": u.messages_sent,
                "table_notes": u.table_notes,
                "memory_writes": u.memory_writes,
                "compactions": u.compactions,
                "guardrails_triggered": u.guardrails_triggered,
            },
        }
    return out
