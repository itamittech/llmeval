"""Deterministic scoring for one RELAY race.

No judge, and none is configured. ALIBI earned that by having ground truth;
RELAY has ground truth *and* a sealed difficulty, which buys a sharper
question: not just was the answer right, but **was the decision right**.

Everything here reads a committed transcript and nothing else — no engine, no
framework, no keys (ADR-0003). The one input that makes it possible arrives in
the last event: ``game_ended.track_key`` reveals every stage's tier, so at
scoring time — and only at scoring time — each escalation can be looked up
against the difficulty the runner was never shown.

The fold **self-verifies**: replaying the events must reproduce the engine's
own standings. A scorer that disagrees with the engine about who won has a bug,
and saying so out loud is cheaper than trusting it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


@dataclass
class LaneScore:
    player: str
    stages_cleared: int = 0
    ticks: int = 0
    finished: bool = False
    #: Attempts this lane made on its own, and how many were right.
    solo_attempts: int = 0
    solo_correct: int = 0
    #: Solo accuracy split by the tier the runner could not see.
    solo_by_tier: dict[int, list[int]] = field(default_factory=dict)
    escalations: int = 0
    escalations_on_hard: int = 0
    hard_stages_faced: int = 0
    hard_stages_escalated: int = 0
    #: Solo results per stage family, and which families each escalation went on.
    solo_by_family: dict[str, list[int]] = field(default_factory=dict)
    escalated_families: list[str] = field(default_factory=list)
    passes: int = 0
    notes: int = 0
    tokens: int = 0
    calls: int = 0
    anchor_calls: int = 0

    @property
    def solo_accuracy(self) -> float | None:
        if not self.solo_attempts:
            return None
        return round(self.solo_correct / self.solo_attempts, 4)

    @property
    def escalation_precision(self) -> float | None:
        """Of the units this lane spent, what share went on genuinely hard
        stages? Low means the pool was burned on work it could have done."""
        if not self.escalations:
            return None
        return round(self.escalations_on_hard / self.escalations, 4)

    @property
    def escalation_recall(self) -> float | None:
        """Of the hard stages this lane faced, what share did it escalate? Low
        means it ground through them alone, paying in wrong answers and ticks."""
        if not self.hard_stages_faced:
            return None
        return round(self.hard_stages_escalated / self.hard_stages_faced, 4)

    @property
    def escalation_fit(self) -> float | None:
        """Of the units this lane spent, what share went on a family it is
        actually bad at?

        Precision asks whether an escalation went on an *objectively* hard
        stage. This asks whether it went on one that was hard **for this
        runner** — and the two come apart, which is the point of reporting
        both. A tier-1 ordering puzzle is trivial by the ladder and impossible
        for a runner that cannot do ordering at all, and spending a unit on it
        is the right move however low it scores on precision.
        """
        if not self.escalated_families:
            return None
        weak = {family for family, results in self.solo_by_family.items()
                if sum(results) / len(results) < 0.5}
        # A family it never attempted alone is one it has no evidence about,
        # and counts as weak: escalating the unknown is not a mistake.
        hit = sum(1 for family in self.escalated_families
                  if family in weak or family not in self.solo_by_family)
        return round(hit / len(self.escalated_families), 4)

    @property
    def quota_efficiency(self) -> float | None:
        """Stages cleared per unit of the commons spent."""
        if not self.escalations:
            return None
        return round(self.stages_cleared / self.escalations, 4)

    def payload(self) -> dict[str, Any]:
        return {
            "player": self.player,
            "stages_cleared": self.stages_cleared,
            "ticks": self.ticks,
            "finished": self.finished,
            "solo_attempts": self.solo_attempts,
            "solo_accuracy": self.solo_accuracy,
            "solo_accuracy_by_tier": {
                str(tier): round(sum(results) / len(results), 4)
                for tier, results in sorted(self.solo_by_tier.items())
            },
            "solo_accuracy_by_family": {
                family: round(sum(results) / len(results), 4)
                for family, results in sorted(self.solo_by_family.items())
            },
            "escalations": self.escalations,
            "escalation_precision": self.escalation_precision,
            "escalation_recall": self.escalation_recall,
            "escalation_fit": self.escalation_fit,
            "quota_efficiency": self.quota_efficiency,
            "passes": self.passes,
            "notes": self.notes,
            "tokens": self.tokens,
            "calls": self.calls,
            "anchor_calls": self.anchor_calls,
        }


#: Which tiers count as "genuinely hard" for precision and recall. Tier 3 is
#: the top of the ladder, and the bench showed it is where the anchor earns its
#: keep for a competent runner. Named rather than inlined because it is a
#: judgement call and should be arguable.
HARD_TIER = 3


def load(path: str | Path) -> list[dict[str, Any]]:
    return [json.loads(line)
            for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def score(events: list[dict[str, Any]]) -> dict[str, Any]:
    started = _one(events, "game_started")
    ended = _one(events, "game_ended")
    key = {entry["id"]: entry for entry in ended["track_key"]}

    lanes: dict[str, LaneScore] = {}
    for player in (p["color"] for p in started["players"]):
        lanes[player] = LaneScore(player=player)

    quota_spent = 0
    guardrails = 0

    families = {stage["id"]: stage["family"]
                for stage in _one(events, "track_generated")["stages"]}

    for event in events:
        kind, payload = event["type"], event["payload"]
        if kind == "stage_attempted":
            lane = lanes[payload["player"]]
            tier = key[payload["stage"]]["tier"]
            family = families[payload["stage"]]
            hard = tier >= HARD_TIER

            if hard:
                lane.hard_stages_faced += 1
            if payload["escalated"]:
                lane.escalations += 1
                lane.escalated_families.append(family)
                quota_spent += 1
                if hard:
                    lane.escalations_on_hard += 1
                    lane.hard_stages_escalated += 1
            elif payload["answer"] is None:
                lane.passes += 1
            else:
                lane.solo_attempts += 1
                lane.solo_correct += bool(payload["correct"])
                correct = int(bool(payload["correct"]))
                lane.solo_by_tier.setdefault(tier, []).append(correct)
                lane.solo_by_family.setdefault(family, []).append(correct)
            if payload.get("note"):
                lane.notes += 1

        elif kind == "llm_call":
            lane = lanes[payload["player"]]
            lane.calls += 1
            lane.tokens += sum(payload["tokens"].get(k, 0)
                               for k in ("input", "output", "cache_read", "cache_write"))
            if payload.get("actor") == "anchor":
                lane.anchor_calls += 1

        elif kind == "guardrail_triggered":
            guardrails += 1

    for standing in ended["standings"]:
        lane = lanes[standing["player"]]
        lane.stages_cleared = standing["stages_cleared"]
        lane.ticks = standing["ticks"]
        lane.finished = standing["finished"]

    return {
        "schema": "relay-eval/1",
        "version": SCHEMA_VERSION,
        "seed": started["seed"],
        "stack": started.get("stack", "none"),
        "profile": started.get("profile"),
        "framework": started.get("framework"),
        "prompt_set": started.get("prompt_set"),
        "reason": ended["reason"],
        "turns_played": ended["turns_played"],
        "track": {
            "stages": started["track"]["stages"],
            "tiers": started["track"]["tiers"],
            "hard_tier": HARD_TIER,
        },
        "commons": {
            "quota": started.get("escalation_quota"),
            "spent": quota_spent,
            "exhausted": quota_spent >= (started.get("escalation_quota") or 0),
            "share": {
                player: round(lane.escalations / quota_spent, 4) if quota_spent else 0.0
                for player, lane in lanes.items()
            },
        },
        "guardrails_triggered": guardrails,
        "lanes": [lanes[s["player"]].payload() for s in ended["standings"]],
        "self_check": self_check(events, lanes, ended),
    }


def self_check(events: list[dict[str, Any]], lanes: dict[str, LaneScore],
               ended: dict[str, Any]) -> dict[str, Any]:
    """Replay the attempts and rebuild the standings the engine claimed.

    Not decoration. Every number above is derived from the same events, so a
    scorer that had drifted would report a confident, wrong answer. This is the
    cheapest possible check that it has not.
    """
    replay: dict[str, dict[str, int]] = {
        player: {"cleared": 0, "ticks": 0} for player in lanes
    }
    ticks = _one(events, "game_started").get("ticks") or {}

    for event in events:
        if event["type"] != "stage_attempted":
            continue
        p = event["payload"]
        lane = replay[p["player"]]
        lane["ticks"] += p["ticks_charged"]
        if p["correct"]:
            lane["cleared"] += 1

        # And check the engine's own arithmetic while we are here.
        expected = (ticks.get("escalate") if p["escalated"]
                    else ticks.get("pass") if p["answer"] is None
                    else ticks.get("answer"))
        if expected is not None and not p["correct"] and p["answer"] is not None:
            expected += ticks.get("wrong", 0)
        if expected is not None and expected != p["ticks_charged"]:
            return {"ok": False,
                    "detail": f"{p['stage']}: charged {p['ticks_charged']}, "
                              f"the price list says {expected}"}

    for standing in ended["standings"]:
        lane = replay[standing["player"]]
        if lane["cleared"] != standing["stages_cleared"]:
            return {"ok": False,
                    "detail": f"{standing['player']}: replayed "
                              f"{lane['cleared']} clears, standings say "
                              f"{standing['stages_cleared']}"}
        if lane["ticks"] != standing["ticks"]:
            return {"ok": False,
                    "detail": f"{standing['player']}: replayed {lane['ticks']} "
                              f"ticks, standings say {standing['ticks']}"}
    return {"ok": True, "detail": "replay reproduces the engine's standings"}


def _one(events: list[dict[str, Any]], type_: str) -> dict[str, Any]:
    for event in events:
        if event["type"] == type_:
            return event["payload"]
    raise ValueError(f"transcript has no {type_}")
