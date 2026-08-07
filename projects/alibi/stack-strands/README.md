# alibi-strands

ALIBI's first harness: four detective agents on the Strands Agents SDK, the
archivist as a **real framework tool** (the agent-as-tool architecture is the
deliverable), notebooks on `AgentState`, metering and the budget ceiling in
lifecycle hooks. Binds to the [harness contract](../../../docs/projects/alibi/harness-contract.md).

No swarm, deliberately: answered [question 22](../../../docs/open-questions.md#-22-does-alibi-keep-ludos-negotiation-channels)
removed negotiation, so each detective is a single-agent loop with tools — the
architectural contrast with [LUDO's Strands stack](../../ludo/stack-strands/) is the point.

## Module map

| Module | What it owns |
|---|---|
| `prompts.py` | The shared prompt set, loaded verbatim; the archivist pair's fixed contract |
| `config.py` | Seats from `models.yaml` profiles; ALIBI budgets and archivist from its `alibi` section |
| `scripted.py` | The scripted model through Strands' own `Model` seam — a consultation costs two entries, visibly |
| `players.py` | Detective agents, the notebook on `AgentState`, the `consult_archivist` tool |
| `hooks.py` | `llm_call` per invocation (usage rides the message — LUDO's trap, honoured), the per-game ceiling |
| `guardrails.py` | Lenient: bluffs pass; injection, engine-authority claims, and forged citations do not |
| `harness.py` | The engine-facing adapter: render → ask → parse → hand the engine exactly what the model said |
| `demo.py` | The committed fixture's script — red is fooled by both red herrings, cross-checks the witness, solves |

## Run it

```bash
uv run --directory projects/alibi/stack-strands pytest
```

A full scripted game, offline and free — regenerates the committed fixture byte-identically:

```bash
uv run --directory projects/alibi/stack-strands python -m alibi_strands.demo out.jsonl
```
