# alibi-eval

Deterministic evaluation for ALIBI transcripts — **no judge in v1, on purpose**.
LUDO needed an LLM judge because "who played best" from a board position is not
computable. ALIBI's engine seals an answer, so the interesting scores *are*
computable: accusation accuracy, rounds-to-solve, and **belief calibration**
(Brier against the revealed solution), plus red-herring exposure — who was fed
a lie, and whether their beliefs show they swallowed it. A judged dimension
(interrogation craft, bluff quality) can arrive later on LUDO's judge
machinery; nothing here blocks it.

Consumes event streams only (ADR-0003): free, offline, no keys.

## What a result holds

Per detective: rank, solved/eliminated, the accusation if any, `beliefs`
(declarations, final dimensions correct, mean Brier), table activity counts,
`red_herrings_read`, invalid actions, notebook writes, token totals. Per game:
outcome, solution, the revealed red herrings. And `checks.standings_match` —
the fold recomputes what the engine's own standings say and must agree, or the
result is flagged rather than trusted.

Results validate against
[`alibi-eval-result.schema.json`](../../../shared/schemas/alibi-eval-result.schema.json)
before being written. Committed results live beside their games in
[`../games/`](../games/).

## Run it

```bash
uv run --directory projects/alibi/eval pytest
```

```bash
uv run --directory projects/alibi/eval python -m alibi_eval score projects/alibi/games/scripted-strands-seed7.jsonl
```

```bash
uv run --directory projects/alibi/eval python -m alibi_eval compare projects/alibi/games/scripted-strands-seed7.jsonl projects/alibi/games/scripted-langgraph-seed7.jsonl projects/alibi/games/scripted-springai-seed7.jsonl
```

`compare` first proves the engine spines identical — same seed, same scripted
decisions, same story in all three — and only then prints what differs, which
is by construction the framework: call counts (Spring AI's internal tool
execution aggregates the consult round), token estimates (window against
growing thread), nothing else.
