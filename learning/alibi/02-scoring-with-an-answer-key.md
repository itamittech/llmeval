# Scoring With an Answer Key

LUDO's eval needed an LLM judge, seven rubric dimensions, anonymisation, multi-run spread — a small machine for extracting a defensible opinion. ALIBI's eval is [~200 lines of arithmetic](../../projects/alibi/eval/src/alibi_eval/scoring.py) with no model call anywhere.

The difference is one fact: ALIBI's engine *knows who did it*. `game_ended.solution` is an answer key, and an answer key changes what evaluation even is.

> **An answer key turns judging into arithmetic.**

## Calibration, the score that needs the key

Every turn each detective declares a best-guess triple with a confidence per dimension. Because the truth is sealed in the transcript, the eval can score not just *were you right* but *did you know how right you were* — calibration, via the **Brier score**:

```
brier = (confidence − outcome)²      outcome: 1 if the declared element was the answer, else 0
```

averaged over every declared dimension. Lower is better.

**Before you scroll:** detective A declares the right suspect at confidence 0.9. Detective B declares the *same right suspect* at 0.5. Detective C declares the wrong one at 0.9. Rank their Brier scores.

| declaration | outcome | brier |
|---|---|---|
| right at 0.9 | 1 | (0.9−1)² = **0.01** |
| right at 0.5 | 1 | (0.5−1)² = 0.25 |
| wrong at 0.5 | 0 | (0.5−0)² = 0.25 |
| wrong at 0.9 | 0 | (0.9−0)² = **0.81** |

A hedged coin-flip costs 0.25 whichever way it lands — hedging buys safety, not points. Being *sure and wrong* costs 0.81, thirty times the cost of being sure and right. Now connect that to the game: what does a red herring do? It manufactures confidence in a wrong elimination. **The corpus's lies and the eval's ruler are aimed at the same spot** — that is not a coincidence, it is the design.

Red's fixture turn 1 makes it concrete: fed two herrings, red declares a triple wrong in all three dimensions at confidences 0.25 / 0.3 / 0.2 — modest, appropriately unsure — mean Brier **0.0642**. Had red *believed* the archive at 0.9, the same wrong triple would have scored ≈ 0.81. The scorer cannot see who was fooled; the confidence numbers confess it anyway.

## Exposure is not belief

The result also counts `red_herrings_read` — how many lying documents a detective's searches returned. Red's is **3**: all of them. Is red therefore fooled?

The number alone cannot say — exposure is what *reached* you, belief is what you *did*. The verdict is in the trajectory: turn 1's belief is herring-shaped (wrong everywhere the lies pointed); turn 5's accusation is correct. Read together: fed three lies, swallowed two for four turns, cross-checked, recovered. One detective, one game, and the whole story is in five numbers — which is what "measurable against ground truth" was always for.

**Named and killed:** `red_herrings_read` is NOT a penalty. Reading lies is unavoidable — they are *written to be retrieved* ([doc 00](00-retrieval-before-embeddings.md)). The pair (exposure, calibration) is the insight; either alone misleads.

## The scorer that checks itself

The eval folds over events, recomputing solved/eliminated, counters, and final-belief correctness — all facts the engine *already wrote* into `game_ended.standings`. Then it compares, and publishes the verdict as `checks.standings_match`.

Why score things the referee already scored? Because a scorer that *can* disagree with the referee and *doesn't* is verified, and one that disagrees silently is worse than none. On mismatch the result is still emitted — flagged, never hidden: a scorer that suppresses its own disagreement has decided its bugs outrank the data. Same discipline as LUDO's fold self-verification, inherited on purpose.

## What still needs a judge — named, not forgotten

Interrogation craft, bluff quality, whether the table notes actually misled anyone — no answer key covers those, and a judged dimension can land later on LUDO's judge machinery unchanged. V1 omits it *because* the deterministic scores already order the outcomes that matter; the [eval README](../../projects/alibi/eval/README.md) records the scope decision.

## Run it

```bash
uv run --directory projects/alibi/eval python -m alibi_eval score projects/alibi/games/scripted-strands-seed7.jsonl
```

```bash
uv run --directory projects/alibi/eval python -m alibi_eval compare projects/alibi/games/scripted-strands-seed7.jsonl projects/alibi/games/scripted-langgraph-seed7.jsonl projects/alibi/games/scripted-springai-seed7.jsonl
```

`compare` proves the three engine spines identical *before* printing what differs — so every difference it shows is, by construction, the framework. The 22/22/20 in its output is [doc 01](01-the-archivist-agent-as-tool.md)'s finding as a table row.

## Check yourself

1. Why does a 0.5-confidence declaration score 0.25 whether right or wrong, and what does that imply about hedging? ([answer](#calibration-the-score-that-needs-the-key))
2. Red read all three herrings yet scored Brier 0.06. Reconcile. ([answer](#exposure-is-not-belief))
3. What does the eval do when its fold disagrees with `game_ended.standings`, and why that instead of the alternatives? ([answer](#the-scorer-that-checks-itself))

Next: [one corpus, two languages](03-one-corpus-two-languages.md) — why any of these numbers can be trusted across engines at all.
