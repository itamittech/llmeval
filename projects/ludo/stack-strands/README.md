# LUDO — Strands Stack

The first of three agent harnesses. Implements [harness-contract.md](../../../docs/projects/ludo/harness-contract.md) on the [Strands Agents SDK](https://strandsagents.com/).

> **🚧 In progress.** The framework-independent core is built and tested; the Strands binding and the full turn loop are not finished. See [Status](#status) for exactly what runs today.

## Why this exists twice more

This stack, the LangGraph stack, and the Spring AI stack (neither built yet) all implement the *same specification* — not a copy of each other. The contract was written before this stack so that Strands could not quietly become the standard the other two inherit. Anything Strands makes easy or hard is a [capability-matrix](../../../docs/architecture/stack-comparison.md) finding, not an implementation detail.

## Environment

Its own virtual environment, its own lockfile. **Never shared with the LangGraph stack** — that is a hard rule in [environment-strategy.md](../../../docs/architecture/environment-strategy.md), and it is why `ludo-engine` is a path dependency rather than a `uv` workspace member. A workspace would give both stacks one resolved dependency set, which would make "same framework, different dependency trees" untestable.

```bash
uv sync --directory projects/ludo/stack-strands
```

```bash
uv run --directory projects/ludo/stack-strands pytest
```

Python is pinned to **3.12** exactly, matching the LangGraph stack, so the interpreter cannot become a variable in the comparison.

## Design

**The model is behind a seam.** Everything above [`model.py`](src/ludo_strands/model.py) talks to a `ModelClient` with one method. Two implementations: one that calls a provider, and `ScriptedModel`, which replays a committed list of replies and never touches the network.

That is not a testing convenience added late. The harness contract asks all three stacks to produce the *same event sequence* from the same seed and the same script — which is only possible if each can accept an injected client. A framework that cannot is itself a finding, so the seam is designed in rather than retrofitted.

**Prompts are loaded, never authored.** [`prompts.py`](src/ludo_strands/prompts.py) reads `shared/prompts/ludo`, refuses any template containing control flow, and requires declared variables to match used ones exactly — in both directions. A missing `{{board}}` would otherwise reach a model as literal braces and produce plausible nonsense.

**Memory is explicit.** [`memory.py`](src/ludo_strands/memory.py) is a real subsystem rather than whatever the framework does implicitly, because an implicit implementation cannot be compared across three frameworks. It is also deliberately **not** reconciled against the board: it records what an agent believes, including things it was lied to about.

**Seats rotate.** [`config.py`](src/ludo_strands/config.py) assigns colours to seats per game ([ADR-0006](../../../docs/decisions/adr-0006-seat-rotation.md)), so no model permanently occupies one colour.

## Status

| Piece | State |
|---|---|
| Prompt loading, validation, provenance hash | ✅ |
| `models.yaml` profiles, seats, budgets, seat rotation | ✅ |
| Memory subsystem | ✅ |
| Token accounting and per-game ceiling | ✅ |
| `ModelClient` seam + `ScriptedModel` | ✅ |
| Strands binding | ⬜ |
| Turn loop: negotiate → decide → reflect | ⬜ |
| Agent event emission | ⬜ |
| Context compaction | ⬜ |
| Content guardrails | ⬜ |

**No live game has been run.** Two of the four seats (Amazon Nova, DeepSeek) still have `TBD` model ids in [`shared/models.yaml`](../../../shared/models.yaml), so a real match cannot be played yet. Everything above is exercised by the scripted client instead, which is free and deterministic.
