# 00 — Knowing what you don't know

## The problem, before the solution

You have a small model on your laptop. It is free, it is fast, and it is wrong maybe a third of the time. You also have an account with a frontier model that is slower and costs money.

The obvious system routes every request to the small one and escalates when it fails. But "fails" is doing enormous work in that sentence. The small model does not return an error when it is wrong — it returns an answer, confidently, in the same format as a right one. There is nothing to catch.

So the routing decision has to be made **before** the answer, by the model that is about to be wrong, about itself.

That is the whole of RELAY.

## Before you scroll

Four runners, equal skill, racing each other. One always senses correctly when a stage is beyond it; one guesses at random. **How much more often does the first one win?**

Write it down.

## The game, in one paragraph

Ten stages, one track, four lanes. On your turn you face your current stage and either answer it, hand it to **the anchor** — one shared frontier model — or pass. Answering costs 2 ticks, escalating costs 5, being wrong costs 4 more. The anchor is drawn from a pool of 8 escalations that **all four runners share**, and the level is public.

And you are never told how hard a stage is. Tiers exist, they are shuffled across the track, and nobody sees them until the race ends.

[The rules](../../docs/projects/relay/game-rules.md) are normative; that paragraph is the part that matters here.

## The misconception, named and killed

> **"The runner should escalate the hard stages."**

That is what everyone writes first, and it is measurably wrong.

The bench ran four runners of equal skill and unequal *insight* — how often each correctly senses that a stage is beyond it — with the insight-to-lane assignment rotating per seed so turn order was not what got measured. 300 races per row, share of races won, against a 25% baseline:

| Runner skill | insight 0% | 33% | 66% | 100% |
|---|---|---|---|---|
| weak | **27%** | 27% | 26% | 21% |
| middle | 17% | 24% | 29% | **30%** |
| strong | 17% | 22% | **32%** | 29% |

Reproduce it yourself — it costs nothing and takes a minute:

```bash
uv run --directory projects/relay/engine-python python -m relay_engine.cli sweep --games 300
```

Two things to read off it.

**The mechanic works.** A middling runner that knows its own limits wins nearly twice as often as one that doesn't. If that column had been flat, RELAY would have been a game with no decision in it, and [ADR-0011](../../docs/decisions/adr-0011-project-three-relay.md) said out loud in advance that the honest response would be to reject the project rather than patch it.

**The weak row runs backwards.** Perfect insight wins *less* often than none at all.

## Why the weak row inverts

Sit with it, because it is not a bug and it is not noise.

A weak runner fails everywhere — the easy stages included. With perfect insight it spends its share of the pool precisely on the two hardest stages, and then fails four of the easy ones unaided. With *no* insight it escalates roughly at random, and a random escalation lands on a tier-1 stage it would also have failed, where the anchor rescues it anyway.

Precision is only valuable if the stages you skip are ones you can actually do.

**The handle: the right escalation threshold is a function of your own competence, not of the stage's difficulty.** A model that is right 95% of the time should escalate rarely and precisely. A model that is right 40% of the time should escalate almost everything it can afford to, and worry about precision when it gets better.

Nobody predicted that, and a benchmark harness measuring "when does the small model need help?" would have reported the average and missed it completely.

## Where the decision lives in the code

The engine asks a runner exactly once per turn:

```python
def attempt(self, ctx: TurnContext) -> Attempt: ...
```

and hands it a `RunnerView` containing the stage prompt, the public race state, and — the part that matters — `own_history()`: every stage this runner has faced, which family it was, whether it escalated, and whether it was right.

That is the evidence a runner has about itself. There is nothing else, because there is nothing else honest to give it. The harness renders it into the prompt as a tally:

```
- on your own, unaided: chain 4/4, cipher 1/1, order 0/2
```

A runner that reads that and keeps answering `order` stages alone is a runner ignoring the only data it has.

## Check yourself

1. Why can't the harness just catch the small model's error and retry with the big one?
2. A runner has 100% solo accuracy so far and faces a stage of a family it has never seen. Escalate or not, and what does the answer depend on?
3. The bench rotates which lane gets which insight level, per seed. What would the numbers measure if it didn't?
4. Skill and insight are separate knobs in `ProfileRunner`. Name a real model where they would come apart in each direction.

## Next

[01 — fallback is not escalation](01-fallback-is-not-escalation.md): three frameworks, three fallback primitives, and why not one of them fits the decision you just read about.
