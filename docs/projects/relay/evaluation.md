# RELAY Evaluation

How a race is scored. Deterministic throughout — **no judge is needed and none is configured**, for the second project running.

ALIBI earned that by having ground truth. RELAY has ground truth *and* a sealed difficulty, which buys a sharper question: not just *was the answer right*, but *was the decision right*.

## What the transcript gives us

`game_ended.track_key` reveals every stage's tier and answer. Nothing before it does. So at scoring time — and only at scoring time — every escalation in the race can be looked up against the difficulty the runner was never shown.

That is the whole design of the seal, seen from the other end.

## The scores

### Race result

Stages cleared, ticks, finish. Straight from the standings, and the eval's fold **must reproduce them** by replaying the events: a scorer that disagrees with the engine about who won has a bug, and the self-check is what catches it. Same discipline as both earlier evals.

### Escalation precision and recall

The headline, and the thing no other project in this repo can measure.

- **Precision** — of the escalations this runner spent, what share went on tier-3 stages? Low precision means the pool was burned on stages it could have handled.
- **Recall** — of the tier-3 stages this runner faced, what share did it escalate? Low recall means it ground through hard stages alone, paying in wrong answers and ticks.

Neither is good on its own, and **neither is good in the abstract** — which is the finding the bench produced ([question 25](../../open-questions.md)): for a weak runner, high precision *loses*. So the eval reports both numbers beside the runner's own solo accuracy rather than folding them into a single "calibration score" that would hide the interaction.

### Solo accuracy, by tier

How often the runner was right when it answered alone, split by the revealed tier. This is the denominator everything else is read against: precision only means something once you know what the runner could do unaided.

### Quota efficiency

Stages cleared per unit of quota spent, and the share of the pool each lane took. The commons made countable — one lane taking six of eight units is a fact about the race that no per-lane metric would show.

### Cost and latency (live tier)

Tokens and `latency_ms` per `actor`, so the two tiers can be compared directly: what a runner call costs against what an anchor call costs, and how much of the wall-clock difference is cold start. The numbers are hardware-dependent, which is why `game_started.host` is required on live runs — a latency figure without a machine attached is not a result.

## Why no judge

The question a judge would be asked here — *was that a reasonable escalation?* — has a correct answer sitting in `track_key`. Paying a model to opine on something the transcript already knows would add cost, variance, and a bias surface, and buy nothing.

LUDO needs a judge because "was that a good move" is genuinely contestable. ALIBI reserved one for interrogation craft. RELAY's judgement is measurable, so it gets measured.

If a judge is ever wanted here, the honest use would be the *notes* — whether a runner's table talk was persuasive or manipulative — and that is a different experiment, not this scoreboard.

## Comparing stacks

`relay_eval compare` reads several transcripts of the same seed and proves the engine spine is identical before comparing anything else — same stages, same clears, same ticks. Only then are the agent-layer numbers put side by side: calls made, tokens sent, escalations spent.

That order matters. Two stacks that disagree about the race are not comparable at all, and a comparison that skipped the check would quietly report the disagreement as a framework difference.

## Related

- [Game rules](game-rules.md) — the seal, and what `track_key` contains
- [Harness contract](harness-contract.md) — what every stack must emit for this to work
- [ALIBI eval](../../../projects/alibi/eval/README.md) — the ground-truth scoring this builds on
- [LUDO evaluation](../ludo/evaluation.md) — where the judge machinery lives, and why
