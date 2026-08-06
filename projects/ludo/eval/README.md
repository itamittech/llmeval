# LUDO — Evaluation Harness

[evaluation.md](../../../docs/projects/ludo/evaluation.md)'s two layers, implemented: **deterministic scoring** (built, free, runs on every committed game) and the **LLM judge** (machinery built and tested through scripted callers; the live call waits on the judge model id, like every live call in this repo).

> The eval consumes transcripts and nothing else — no engine import, no stack import, no model SDK. If it ever needs an arrow into the engine, something is bypassing the event stream (ADR-0003).

## Run it

Own venv, standalone:

```bash
uv sync --directory projects/ludo/eval
```

```bash
uv run --directory projects/ludo/eval pytest
```

Score any recorded game — free, instant:

```bash
uv run --directory projects/ludo/eval python -m ludo_eval score projects/ludo/games/scripted-strands-seed7.jsonl
```

The repo's real question — the same matchup across the three stacks:

```bash
uv run --directory projects/ludo/eval python -m ludo_eval compare projects/ludo/games/scripted-strands-seed7.jsonl projects/ludo/games/scripted-langgraph-seed7.jsonl projects/ludo/games/scripted-springai-seed7.jsonl
```

## Design

**The fold replays the game and then checks itself.** [`transcript.py`](src/ludo_eval/transcript.py) rebuilds positions, captures, and forfeits from the stream with *apply-on-commit* semantics — a turn's effects land only when `turn_ended` says the turn stood, which mirrors the engine's snapshot-restore on three sixes exactly. Then it verifies its replay against `game_ended.standings`, the engine's own account, and **raises on any disagreement** — a fold that quietly diverged would poison every number downstream. That check has already earned its keep twice: it caught a wrong guess about capture payload keys, and it taught us that the engine does *not* count three-sixes as a forfeited turn.

**Rank is the engine's; weights are provisional and say so.** [`scoring.py`](src/ludo_eval/scoring.py) computes position, play record, and efficiency — but a finished game has a winner, and nothing in this layer may reorder `game_ended.standings`. The position weights sit at the top of the file in capitals, provisional like every number in `models.yaml`. The verbosity metric (total reasoning length) is reported separately from every score, exactly as the judge-bias table demands.

**The judge's bias mitigations are machinery, not policy.** [`anonymize.py`](src/ludo_eval/anonymize.py) builds what the judge sees: colours relabelled `Player A`–`D` by a seeded shuffle **including colour words inside message text** ("ally against yellow?" leaks the mapping otherwise); `llm_call` events and `game_started`'s identifying half withheld (model ids, routes, stack); `game_ended` withheld (outcome-blind). [`judge.py`](src/ludo_eval/judge.py) runs the judge *k* times with a fresh shuffle per run, maps scores back to colours, reports mean **and spread**, discards any score with no cited turns (the capability-matrix rule, applied to the judge itself), and — on games that finished — reports Kendall's tau between the judge's ranking and the engine's standings. The rubric with its anchors lives in [`shared/prompts/ludo/judge/scoring.md`](../../../shared/prompts/ludo/judge/scoring.md), and its hash rides every judged result: scores made under different rubrics are not comparable.

**Every result is schema-checked before it leaves.** [`report.py`](src/ludo_eval/report.py) validates against [`shared/schemas/eval-result.schema.json`](../../../shared/schemas/eval-result.schema.json) — an eval that emits results its own schema rejects would be a measuring instrument nobody calibrated.

## Status

| Piece | State |
|---|---|
| Transcript fold, self-verified against `game_ended` | ✅ [`transcript.py`](src/ludo_eval/transcript.py) — all four committed games, incl. the finished 386-turn sample and a three-sixes reversal |
| Deterministic scoring: position, play record, efficiency, verbosity | ✅ [`scoring.py`](src/ludo_eval/scoring.py) |
| Anonymised judge view (relabel, strip, outcome-blind) | ✅ [`anonymize.py`](src/ludo_eval/anonymize.py) — leakage pinned by test |
| Judge rubric, 7 dimensions with anchors | ✅ [`scoring.md`](../../../shared/prompts/ludo/judge/scoring.md), hash recorded per result |
| Judge machinery: multi-run, citation-enforced, spread, agreement | ✅ [`judge.py`](src/ludo_eval/judge.py) — tested through scripted callers |
| Result schema + validation + CLI (`score`, `compare`) | ✅ [`eval-result.schema.json`](../../../shared/schemas/eval-result.schema.json) · [`cli.py`](src/ludo_eval/cli.py) |
| Live judge call (OpenAI) | ⬜ blocked on the judge model id — [`judge_client.py`](src/ludo_eval/judge_client.py) fails loudly until then |
| Judge validation runs (inter-judge, human spot-checks) | ⬜ need live games first |
| Eval view in the UI | ⬜ the UI renders transcripts today; the eval JSON is its future input |

32 tests, all offline. Nothing here costs anything until the judge id lands — and when it does, judging stays opt-in and priced, never a default.
