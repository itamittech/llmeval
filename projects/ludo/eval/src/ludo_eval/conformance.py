"""Harness-contract §8, mechanised: the cross-stack event-sequence comparison.

The contract's claim: with a fixed seed and the same script, all three stacks
must produce the same event sequence — after normalising away what cannot
match (wall-clock, latency, cost, and the one field that is *supposed* to
differ). This module does the normalising and the comparing, in two layers,
because the two layers mean different things:

- **Engine events** are deterministic: same seed + same *decisions* must give
  an identical sequence. A divergence here means either the harnesses fed the
  engine different decisions (script-alignment, visible and explainable) or —
  the case this tool exists to catch — an engine or harness quietly drifted.
  The report names the first diverging event so the two cases can be told
  apart in seconds.
- **Agent events** are allowed to differ in *rhythm* (each framework's call
  pattern is framework territory — one stack's floor pass is one metered
  invocation, another's is two) but not in *story*: the same messages, the
  same memory writes, the same guardrail outcomes. The report profiles both.

No pass/fail exit today, deliberately: the three committed fixtures are known
to differ (documented rhythm divergence, plus per-stack script alignment),
and a gate that always fails is a gate people disable. When same-decision
fixtures exist, the engine-layer comparison becomes a CI assertion.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

ENGINE_EVENTS = {
    "game_started", "turn_started", "dice_rolled", "move_made", "token_captured",
    "token_home", "extra_roll_granted", "illegal_move_rejected", "turn_ended",
    "player_finished", "game_ended",
}

#: What §8 says cannot match, and therefore is stripped before comparison.
#: `stack` and `framework` name the harness; `engine` names the language
#: (ADR-0002 — the Java stack runs the Java engine, and the conformance
#: vectors are what prove the two engines interchangeable).
_VOLATILE_LLM = ("latency_ms", "cost_usd")
_VOLATILE_START = ("stack", "framework", "engine")


def normalise(events: list[dict]) -> list[dict]:
    """A copy of the stream with the incomparable fields removed."""
    out = []
    for event in events:
        payload = dict(event["payload"])
        payload.pop("ts", None)
        if event["type"] == "llm_call":
            for key in _VOLATILE_LLM:
                payload.pop(key, None)
        if event["type"] == "game_started":
            for key in _VOLATILE_START:
                payload.pop(key, None)
            # players[].agent names the stack by construction
            # ("strands:scripted") — supposed to differ, like stack itself.
            # Found by this tool's own first run; the contract's table gained
            # the row the same day.
            payload["players"] = [
                {k: v for k, v in p.items() if k != "agent"}
                for p in payload.get("players") or []
            ]
        out.append({"seq": event["seq"], "turn": event["turn"],
                    "type": event["type"], "payload": payload})
    return out


@dataclass
class Comparison:
    stacks: list[str]
    engine_identical: bool
    first_divergence: dict | None
    agent_profile: dict[str, dict[str, Counter]] = field(default_factory=dict)
    story: dict[str, dict] = field(default_factory=dict)


def compare(named_streams: list[tuple[str, list[dict]]]) -> Comparison:
    normalised = [(name, normalise(events)) for name, events in named_streams]

    engine_seqs = {
        name: [e for e in events if e["type"] in ENGINE_EVENTS]
        for name, events in normalised
    }
    identical, divergence = _first_divergence(engine_seqs)

    profile = {
        name: _per_turn_agent_counts(events) for name, events in normalised
    }
    story = {name: _story(events) for name, events in normalised}

    return Comparison(
        stacks=[name for name, _ in normalised],
        engine_identical=identical,
        first_divergence=divergence,
        agent_profile=profile,
        story=story,
    )


def _first_divergence(engine_seqs: dict[str, list[dict]]):
    names = list(engine_seqs)
    baseline_name = names[0]
    baseline = engine_seqs[baseline_name]
    for other_name in names[1:]:
        other = engine_seqs[other_name]
        for i, (a, b) in enumerate(zip(baseline, other)):
            stripped_a = {"type": a["type"], "payload": a["payload"]}
            stripped_b = {"type": b["type"], "payload": b["payload"]}
            if stripped_a != stripped_b:
                return False, {
                    "index": i,
                    baseline_name: stripped_a,
                    other_name: stripped_b,
                }
        if len(baseline) != len(other):
            return False, {
                "index": min(len(baseline), len(other)),
                baseline_name: f"{len(baseline)} engine events",
                other_name: f"{len(other)} engine events",
            }
    return True, None


def _per_turn_agent_counts(events: list[dict]) -> dict[int, Counter]:
    out: dict[int, Counter] = {}
    for event in events:
        if event["type"] in ENGINE_EVENTS:
            continue
        out.setdefault(event["turn"], Counter())[event["type"]] += 1
    return out


def _story(events: list[dict]) -> dict:
    """The framework-independent facts: what was said, remembered, blocked."""
    messages, notes = [], []
    counts = Counter()
    for event in events:
        type_, payload = event["type"], event["payload"]
        if type_ in ENGINE_EVENTS:
            continue
        counts[type_] += 1
        if type_ == "message_sent":
            messages.append((payload["player"], payload["to"], payload["text"]))
        elif type_ == "memory_write":
            notes.append((payload["player"], payload["kind"], payload["text"]))
    return {"counts": dict(counts), "messages": messages, "memory": notes}


def render(comparison: Comparison) -> str:
    lines = ["§8 cross-stack comparison — " + " vs ".join(comparison.stacks), ""]

    if comparison.engine_identical:
        lines.append("engine events: IDENTICAL after normalisation — same seed, "
                     "same decisions, same sequence")
    else:
        d = comparison.first_divergence or {}
        lines.append(f"engine events: diverge at engine-event #{d.get('index')}:")
        for key, value in d.items():
            if key != "index":
                lines.append(f"  {key}: {value}")
        lines.append("  (same seed, so a divergence here means the harnesses fed the "
                     "engine different decisions — or something drifted)")

    lines.append("")
    lines.append("the story, per stack (must agree):")
    baseline = None
    for name in comparison.stacks:
        story = comparison.story[name]
        lines.append(f"  {name}: {story['counts']} — "
                     f"{len(story['messages'])} messages, {len(story['memory'])} notes")
        if baseline is None:
            baseline = (story["messages"], story["memory"])
    stories_agree = all(
        (comparison.story[n]["messages"], comparison.story[n]["memory"]) == baseline
        for n in comparison.stacks)
    lines.append(f"  delivered messages and memory writes "
                 f"{'AGREE across stacks' if stories_agree else 'DIFFER — inspect above'}")

    lines.append("")
    lines.append("agent-event rhythm, per turn (framework territory — differences "
                 "are findings, not failures):")
    turns = sorted({t for p in comparison.agent_profile.values() for t in p})
    for turn in turns:
        lines.append(f"  turn {turn}:")
        for name in comparison.stacks:
            counts = comparison.agent_profile[name].get(turn, Counter())
            rendered = ", ".join(f"{k}×{v}" for k, v in sorted(counts.items())) or "—"
            lines.append(f"    {name:<10} {rendered}")
    return "\n".join(lines)
