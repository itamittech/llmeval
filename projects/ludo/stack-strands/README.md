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

**The framework is the implementation, not a dependency to contain.** Per [ADR-0008](../../../docs/decisions/adr-0008-framework-native-harness.md), harness responsibilities are met with Strands' own primitives: `AgentState` plus a session manager for memory, `SummarizingConversationManager` for compaction, hooks for token metering, budget enforcement and event emission, and negotiation via the agents-as-tools pattern — also Strands-native. The `Swarm` orchestrator was evaluated and [ruled out for this protocol](../../../docs/architecture/stack-comparison.md): it resets each agent's state on every activation, gives the floor to whoever spoke last, and its durable carriers are broadcast — a shared-blackboard design, where this game needs private beliefs and an active agent who keeps the floor.

The first cut of this stack was built the other way — framework-independent `memory.py`, `budget.py`, and a `ModelClient` seam, with Strands confined to one adapter file. Those files still exist and still pass their tests, but they implement a retired design and are being replaced; the ADR records why. What survives them: the `Note` shape and the never-reconciled rule (memory records what an agent *believes*, including what it was lied to about — that is contract, not implementation), and the budget *numbers*, which stay in [`shared/models.yaml`](../../../shared/models.yaml).

**The scripted model goes through Strands' own extension point.** The harness contract asks all three stacks to produce the same event sequence from the same seed and script, which requires an injectable fake model — implemented here as a custom Strands `Model`, not as a parallel client interface beside the framework. A framework that cannot accept one is itself a finding.

**Prompts are loaded, never authored.** [`prompts.py`](src/ludo_strands/prompts.py) reads `shared/prompts/ludo`, refuses any template containing control flow, and requires declared variables to match used ones exactly — in both directions. A missing `{{board}}` would otherwise reach a model as literal braces and produce plausible nonsense.

**Seats rotate.** [`config.py`](src/ludo_strands/config.py) assigns colours to seats per game ([ADR-0006](../../../docs/decisions/adr-0006-seat-rotation.md)), so no model permanently occupies one colour.

## Status

| Piece | State |
|---|---|
| Prompt loading, validation, provenance hash | ✅ |
| `models.yaml` profiles, seats, budgets, seat rotation | ✅ |
| Memory subsystem | ♻️ built; being replaced by `AgentState` + session persistence ([ADR-0008](../../../docs/decisions/adr-0008-framework-native-harness.md)) |
| Token accounting and per-game ceiling | ♻️ built; metering and enforcement moving into Strands hooks |
| `ModelClient` seam + `ScriptedModel` | ♻️ built; being redone as a Strands `Model` implementation |
| Strands model construction, settings pinned and read back | ✅ [`strands_client.py`](src/ludo_strands/strands_client.py) |
| Turn loop: negotiate → decide → reflect | ⬜ on Strands primitives |
| Negotiation via agents-as-tools | ⬜ |
| Agent event emission (hooks) | ⬜ |
| Context compaction (`SummarizingConversationManager`) | ⬜ |
| Content guardrails | ⬜ |

**No live game has been run.** Two of the four seats (Amazon Nova, DeepSeek) still have `TBD` model ids in [`shared/models.yaml`](../../../shared/models.yaml), so a real match cannot be played yet. Everything above is exercised by the scripted client instead, which is free and deterministic.
