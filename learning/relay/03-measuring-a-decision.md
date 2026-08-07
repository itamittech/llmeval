# 03 — Measuring a decision

## The problem, before the solution

Scoring an answer is easy: there is a right one, and you compare.

Scoring a *decision* is not. "Should this runner have escalated?" has no entry in the transcript, and asking a model to opine would cost money, add variance, and produce an opinion where a fact is available.

RELAY has the fact, because [the seal](02-the-seal.md) opens at the end.

## Before you scroll

A runner escalates every stage it cannot personally do. None of them happens to be top-tier. **What is its escalation precision?**

## Two rulers

Once `game_ended.track_key` reveals every tier, two numbers fall out per lane:

- **Precision** — of the units this lane spent, what share went on genuinely hard (tier-3) stages? Low means the pool was burned on work it could have done.
- **Recall** — of the hard stages this lane faced, what share did it escalate? Low means it ground through them alone, paying in wrong answers and ticks.

Standard information-retrieval shapes, pointed at a decision rather than a result. Run it:

```bash
uv run --directory projects/relay/eval python -m relay_eval score ../games/scripted-strands-seed7.jsonl
```

```
lane      cleared  ticks  esc  solo acc  precision   recall   fit   share
red             6     18    2      100%         0%       0%  100%     25%
blue            5     19    1       80%         0%       0%  100%     12%
yellow          5     28    5         —        20%     100%  100%     62%
green           2     28    0       33%          —       0%     —      0%
```

**Red wins the race with an escalation precision of zero.**

## Why the ruler was wrong

Red escalates exactly what it cannot do: ordering puzzles, which it has no way to solve. None of those happened to be tier-3. So by the ladder, every unit red spent was "wasted" — and red finished furthest ahead, on the fewest ticks, in the whole field.

The ladder does not know what red is bad at. **A tier-1 ordering puzzle is trivial by the ladder and impossible for a runner that cannot order at all.**

So the eval grew a third number:

- **Fit** — of the units this lane spent, what share went on a family it is *measurably* bad at, judged from its own solo accuracy in this race.

Red scores 100%. So do blue and yellow. Green, which never escalates, scores nothing at all — `None`, not zero, because a lane that spent nothing was not inaccurate.

**The handle: hard is relative to the runner.** Precision measures alignment with objective difficulty; fit measures alignment with your own competence. They come apart, and the second one is what wins races.

That is the same finding [the bench](00-knowing-what-you-dont-know.md) produced from the other end — where perfect insight *lost* for weak runners — arriving now from the scoring side.

## Why both are still reported

The tempting move is to drop precision and keep fit. Resist it.

Fit is computed from the lane's own record *in this race*, so it is circular in a way precision is not: a runner that never attempts a family alone is credited with escalating "the unknown", which is generous. Precision is anchored to something outside the lane.

Neither is a score. Together they are a description, and the gap between them is the interesting part. Folding them into one number would hide exactly the thing worth seeing — which is why [ALIBI's eval](../alibi/02-scoring-with-an-answer-key.md) reports exposure beside belief rather than netting them off, and why this one reports three columns and not one.

## The scorer checks itself

Every number above is derived from the same events, so a scorer that had drifted would report a confident wrong answer with no symptom.

So the fold replays the race — every `stage_attempted`, rebuilding positions and clocks — and compares its own totals against `game_ended.standings`. It also re-derives each tick charge from the price list in `game_started`:

```
self-check: ok — replay reproduces the engine's standings
```

Two tests tamper with a fixture to prove it bites: bump a standing, and the check reports the mismatch; nudge one `ticks_charged`, and it reports that the price list disagrees.

**The handle: a scorer that cannot disagree with the referee cannot be trusted to agree with it.**

## And `compare` proves the race first

```bash
uv run --directory projects/relay/eval python -m relay_eval compare ../games/*.jsonl
```

```
engine spine identical across 3 transcripts (75 engine events each)

                             strands     langgraph      springai
llm_call events                   56            55            55
tokens sent                   75,626       123,067       123,067
```

The first line is the load-bearing one. Two stacks that disagree about the race are not comparable at all, and a comparison that skipped the check would report the disagreement as a framework difference. `compare` refuses outright rather than printing a plausible table.

## Check yourself

1. Green's precision is `None`, not `0.0`. Why does the distinction matter?
2. Fit uses the lane's solo accuracy from the same race it is scoring. Name the bias that introduces.
3. Why can this eval retire the judge when LUDO's cannot?
4. The self-check recomputes tick charges from `game_started.ticks`. What class of bug does that catch that replaying standings alone would not?

## Where to go next

- [the matrix's third act](../../docs/architecture/stack-comparison.md#relay-the-third-act) — the framework findings these races produced
- [learning/alibi/02](../alibi/02-scoring-with-an-answer-key.md) — the same discipline on a different answer key
- [ADR-0011](../../docs/decisions/adr-0011-project-three-relay.md) — why the project exists, and the bench result nobody predicted
