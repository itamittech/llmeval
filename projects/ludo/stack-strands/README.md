# LUDO — Strands Stack

The first of three agent harnesses. Implements [harness-contract.md](../../../docs/projects/ludo/harness-contract.md) on the [Strands Agents SDK](https://strandsagents.com/).

> **🚧 In progress.** The turn loop runs end to end against scripted models — swarm negotiation, memory, budgets, events, all on Strands primitives. Context compaction and content guardrails are not built, and no live game can run until the Nova and DeepSeek model ids are pinned. See [Status](#status).

See it play, free and offline — the committed [UI fixture](../games/scripted-strands-seed7.jsonl) is this command's byte-identical output:

```bash
uv run --directory projects/ludo/stack-strands python -m ludo_strands.demo out.jsonl
```

> **Finding the code hard to follow?** [learning/strands](../../../learning/strands/) teaches it from the framework up — the agent loop, one turn traced end to end, and the swarm table — and [class-design.md §9](../../../docs/projects/ludo/class-design.md#9-the-harness-layer-the-same-turn-on-strands) has the object graph and call diagrams.

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

**The framework is the implementation, not a dependency to contain.** Per [ADR-0008](../../../docs/decisions/adr-0008-framework-native-harness.md), harness responsibilities are met with Strands' own primitives: `AgentState` for memory, hooks for token metering, budget enforcement and event emission, `SummarizingConversationManager` for context compaction — **each agent is its own summariser**, so the summary call is metered and budget-gated like any other — and **negotiation runs on the `Swarm` orchestrator itself**. The one primitive not yet wired is next in line: a session manager for cross-game persistence. That took a real decision: `Swarm`'s semantics could not carry the original negotiation protocol, so [ADR-0009](../../../docs/decisions/adr-0009-swarm-negotiation.md) redesigned the protocol to fit the orchestrator — directed messages as handoffs, table notes as shared-context posts, the floor-pass cap as `max_handoffs`, per-agent briefings seeded through the construction-time snapshot. The [capability matrix](../../../docs/architecture/stack-comparison.md) keeps the full analysis.

The first cut of this stack was built the other way — framework-independent `memory.py`, `budget.py`, and a `ModelClient` seam, with Strands confined to one adapter file. Those files are **gone**, replaced by the primitives above; [ADR-0008](../../../docs/decisions/adr-0008-framework-native-harness.md) records why the rework was chosen. What survived them: the note shape and the never-reconciled rule (memory records what an agent *believes*, including what it was lied to about — that is contract, not implementation), and the budget *numbers*, which stay in [`shared/models.yaml`](../../../shared/models.yaml).

**The scripted model goes through Strands' own extension point.** The harness contract asks all three stacks to produce the same event sequence from the same seed and script, which requires an injectable fake model — implemented in [`scripted.py`](src/ludo_strands/scripted.py) as a real Strands `Model`, so the whole loop (swarm, hooks, metrics) runs exactly as it would live. A framework that cannot accept one is itself a finding.

| Module | Job |
|---|---|
| [`harness.py`](src/ludo_strands/harness.py) | The turn loop: the engine's `negotiate`/`choose`/`reflect` hooks, answered with Strands |
| [`players.py`](src/ludo_strands/players.py) | The four agents; memory on `AgentState` |
| [`hooks.py`](src/ludo_strands/hooks.py) | Lifecycle hooks: `llm_call` metering, the budget ceiling, floor-pass capture, the guardrail gate |
| [`guardrails.py`](src/ludo_strands/guardrails.py) | Three deterministic out-of-fiction rules; in-game cunning passes, and a test asserts it |
| [`scripted.py`](src/ludo_strands/scripted.py) | The scripted `Model` (contract §8) |
| [`demo.py`](src/ludo_strands/demo.py) | One scripted game → the committed fixture |
| [`prompts.py`](src/ludo_strands/prompts.py) · [`config.py`](src/ludo_strands/config.py) · [`strands_client.py`](src/ludo_strands/strands_client.py) | Shared-layer loading: prompt set, `models.yaml`, provider model construction |

**Prompts are loaded, never authored.** [`prompts.py`](src/ludo_strands/prompts.py) reads `shared/prompts/ludo`, refuses any template containing control flow, and requires declared variables to match used ones exactly — in both directions. A missing `{{board}}` would otherwise reach a model as literal braces and produce plausible nonsense.

**Seats rotate.** [`config.py`](src/ludo_strands/config.py) assigns colours to seats per game ([ADR-0006](../../../docs/decisions/adr-0006-seat-rotation.md)), so no model permanently occupies one colour.

## Status

| Piece | State |
|---|---|
| Prompt loading, validation, provenance hash | ✅ |
| `models.yaml` profiles, seats, budgets, seat rotation | ✅ |
| Memory on `AgentState` | ✅ [`players.py`](src/ludo_strands/players.py) |
| Token accounting + per-game ceiling, in lifecycle hooks | ✅ [`hooks.py`](src/ludo_strands/hooks.py) |
| Scripted model through Strands' `Model` interface | ✅ [`scripted.py`](src/ludo_strands/scripted.py) |
| Strands model construction, settings pinned and read back | ✅ [`strands_client.py`](src/ludo_strands/strands_client.py) |
| Turn loop: negotiate → decide (with retry) → reflect | ✅ [`harness.py`](src/ludo_strands/harness.py) |
| Negotiation on the `Swarm` orchestrator ([ADR-0009](../../../docs/decisions/adr-0009-swarm-negotiation.md)) | ✅ |
| Agent event emission, one sequence with engine events | ✅ schema-validated [fixture](../games/scripted-strands-seed7.jsonl) |
| Context compaction (`SummarizingConversationManager`, agent-as-own-summariser) | ✅ [`harness.py`](src/ludo_strands/harness.py) `_maybe_compact` |
| Content guardrails — lenient by design, at the message boundary | ✅ [`guardrails.py`](src/ludo_strands/guardrails.py) + the `BeforeToolCallEvent` gate in [`hooks.py`](src/ludo_strands/hooks.py) |
| Session persistence across games | ⬜ |
| Live game | ⬜ blocked on Nova + DeepSeek model ids |

**No live game has been run.** Two of the four seats (Amazon Nova, DeepSeek) still have `TBD` model ids in [`shared/models.yaml`](../../../shared/models.yaml), so a real match cannot be played yet. Everything above is exercised by the scripted model instead — free, offline, and byte-for-byte deterministic, which is what lets the fixture be committed at all.
