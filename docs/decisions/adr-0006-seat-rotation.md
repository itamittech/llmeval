# ADR-0006 — Rotate the seat-to-colour assignment between games

**Status:** Accepted
**Date:** 2026-08-02

## Context

[ADR-0005](adr-0005-model-access-control.md) fixes *which* models play and puts one on both access routes so Bedrock-vs-direct is measurable. It says nothing about *which colour* each model plays, and its illustrative config was keyed by colour — `red: {access: bedrock, model: X}`.

This ADR was originally drafted to fix what looked like an obvious second confound: red moves first, moving first is an advantage, so a fixed mapping would permanently hand that advantage to one model.

**We measured it, and it isn't true.**

[`examples/turn_order.py`](../../projects/ludo/engine-python/examples/turn_order.py) runs 2000 games with *identical* deciders in all four seats, so turn order is the only thing that varies:

| Seat | Random bots | Identical heuristic bots |
|---|---|---|
| 1. red *(moves first)* | 25.75% | 23.85% |
| 2. green | 26.25% | 25.30% |
| 3. yellow | 23.60% | 25.15% |
| 4. blue | 24.40% | 25.70% |
| | χ² = 3.56 | χ² = 1.54 |

Neither is close to the 5% critical value of 7.81 on 3 df. Skilled play doesn't amplify it either — if anything the heuristic run is flatter. Ludo is long enough, and a capture destroys enough progress, that a one-turn head start washes out completely.

So the premise was wrong. The question became whether the decision survives losing its main justification.

## Decision

**Seats are numbered, not coloured**, and the mapping rotates per game.

```yaml
seats:
  - seat: 1
    access: bedrock
    provider: anthropic
```

The mapping used is recorded in `game_started`: each entry in `players[]` carries both `color` and `seat`. Transcripts are self-describing, and **nothing downstream may assume red is the same model as in the previous transcript.**

Two reasons it stands despite the null result:

**1. Turn order is not the only thing attached to a colour.** Agents see colour names, address each other by colour, and negotiate about "blue" and "green" by name. Whether a model treats *red* differently from *blue* — more aggressively, more suspiciously — is a prompt-level effect that bot games cannot detect, because bots do not read prompts. It is untestable until real games run, by which point a fixed mapping has already baked it in.

**2. The measurement bounds turn order; it does not license fixing the mapping.** 2000 games say the turn-order effect is small. LLM games will run in *dozens*. At that sample size a confound would have to be enormous to show up, and rotation removes the entire class for free rather than requiring us to prove each member absent one at a time.

Four seats over four colours means a full rotation is four games. Any run supporting a claim about models should be a multiple of four.

## Consequences

**Good**
- Removes per-colour confounds — including ones we have not thought of and could not measure at our sample size — for essentially no cost.
- Same-seat comparison stays intact: seat identity is stable and recorded, so "how did seat 1 do" remains one query.
- Forces UI and eval to read `players[]` rather than hardcode colours, which they would otherwise be tempted to do.
- The measurement itself became a reusable artifact, and a documented case of the repo checking its own assumption.

**Bad**
- The primary justification is now precautionary rather than empirical. That is a weaker footing, and worth saying out loud.
- Transcripts get harder to skim. "Red is the Bedrock one" was a fact you could hold across games; now you look it up.
- Any UI colour-coding by model must read the per-game mapping. Getting it wrong yields a plausible chart that is simply false — the worst failure mode available to this project.
- A run that is not a multiple of four is *partially* rotated, leaving a residual bias small enough to overlook. Eval should refuse model conclusions from an incomplete rotation.
- ADR-0005's colour-keyed config sketch is now stale. That ADR's decision stands unchanged; only its illustrative YAML is superseded here.

## Alternatives

**Fixed assignment.** Simplest, and every game reads the same way. Now genuinely defensible on the turn-order evidence — but it does nothing about colour-name effects in prompts, and the cost of discovering one later is re-running everything.

**Randomise per game.** No schedule to maintain, no bookkeeping. Rejected: across dozens of games, randomisation can easily deal one model the first seat three times in four. Rotation guarantees in four games what randomisation only approaches over hundreds.

**Neutralise turn order in the rules** — randomise who starts within each game. Rejected, and now clearly unnecessary: there is nothing to neutralise, and it would change a game people recognise to simplify a measurement.

**Drop it, note a caveat in the writeup.** Rejected on the repo's own terms: a caveat does not make an unmeasurable claim measurable, and this one costs almost nothing to avoid.
