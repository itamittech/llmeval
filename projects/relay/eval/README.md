# RELAY eval

Deterministic scoring for one race. **No judge, and none is configured** — for the second project running.

ALIBI earned that by having ground truth. RELAY has ground truth *and* a sealed difficulty, which buys a sharper question: not just *was the answer right*, but **was the decision right**.

## Run it

```bash
uv run --directory projects/relay/eval pytest
```

```bash
uv run --directory projects/relay/eval python -m relay_eval score ../games/scripted-strands-seed7.jsonl
```

```bash
uv run --directory projects/relay/eval python -m relay_eval compare ../games/scripted-strands-seed7.jsonl ../games/scripted-langgraph-seed7.jsonl ../games/scripted-springai-seed7.jsonl
```

Transcripts only — no engine, no framework, no keys ([ADR-0003](../../../docs/decisions/adr-0003-shared-event-stream.md)).

## What it measures

**Escalation precision** — of the units a lane spent, what share went on genuinely hard stages. Low means the pool was burned on work the runner could have done.

**Escalation recall** — of the hard stages a lane faced, what share it escalated. Low means it ground through them alone, paying in wrong answers and ticks.

Both are only computable because `game_ended.track_key` reveals every tier, and only *after* the race — which is the seal's entire payoff, seen from the other end.

**Solo accuracy, by tier** — how often a lane was right when it answered alone, split by the difficulty it could not see. This is the denominator the other two are read against: precision only means something once you know what the runner could do unaided. The bench found the interaction runs backwards for weak runners, so the eval reports the numbers side by side rather than folding them into one score that would hide it.

**Quota efficiency and share** — stages cleared per unit spent, and what fraction of the commons each lane took. One lane taking five of eight is a fact about the race no per-lane metric would show.

## The self-check

The fold replays the events and rebuilds the standings, then compares them to the engine's own. It also re-derives every tick charge from the price list in `game_started`.

Not decoration: every number above comes from the same events, so a scorer that had drifted would report a confident wrong answer. This is the cheapest possible check that it has not, and it is the same discipline both earlier evals use.

## `compare` proves the race first

Before comparing anything, `compare` asserts that every transcript's **engine spine** is identical — same stages, same clears, same ticks. Only then does it put the agent-layer numbers side by side.

That order matters. Two stacks that disagree about the race are not comparable at all, and a comparison that skipped the check would quietly report the disagreement as a framework difference.

## Why there is no judge

The question a judge would be asked — *was that a reasonable escalation?* — has a correct answer sitting in `track_key`. Paying a model to opine on something the transcript already knows would add cost, variance, and a bias surface, and buy nothing.

If a judge is ever wanted here, the honest use would be the **notes** — whether a runner's table talk was persuasive or manipulative. That is a different experiment, not this scoreboard.

## Related

- [Evaluation design](../../../docs/projects/relay/evaluation.md)
- [Game rules](../../../docs/projects/relay/game-rules.md#does-the-escalation-decision-actually-matter) — the bench result these scores are read against
- [ALIBI eval](../../alibi/eval/README.md) — the ground-truth scoring this builds on
