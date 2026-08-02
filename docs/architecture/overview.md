# Architecture Overview

> Unfamiliar term? The [glossary](../glossary.md) defines everything this repo uses as shorthand — *parity*, *stack*, *event stream*, *harness*, *conformance vector*, and the rest.

## The core problem

We build every project three times — Strands, LangChain/LangGraph, Spring AI — and compare the results. That comparison is worthless unless the three implementations differ **only** in the agent framework.

Left alone, they won't. Three teams (or three sessions) writing a Ludo engine will produce three subtly different games, and every downstream difference becomes uninterpretable. So the architecture's main job is **controlling the variables**.

## The parity model

Split every project into layers, and decide deliberately which layer is allowed to vary.

| Layer | Varies per stack? | Why |
|---|---|---|
| **Game engine** — rules, board state, dice, legal moves, win detection | **No** | Deterministic, no LLM involved. Any variation here is pure noise. |
| **Tool contract** — what the agent can call on the engine | **No** | This is the parity contract. Same tools, same names, same schemas. |
| **Agent layer** — LLM calls, memory, context management, prompts | **Yes** ← | **This is the thing under study.** |
| **Orchestration** — turn loop, swarm coordination, negotiation | **Yes** ← | Also under study; frameworks differ most here. |
| **Event stream** — what the system emits as it runs | **No** | Shared schema. Enables one UI + one eval harness for all three. |
| **Evaluation** — scoring, LLM-as-judge | **No** | Judging three stacks with three judges proves nothing. |
| **UI** | **No** | One implementation, consumes the shared event stream. |

Two rows carry the whole design:

### Keystone 1 — the shared tool contract

Agents never touch game state directly. They act through a fixed set of tools:

```
get_board_state()      → full public game state
get_legal_moves()      → the moves available for the current roll
roll_dice()            → engine-controlled RNG, seeded and logged
make_move(token, to)   → validated; illegal moves are rejected, not corrected
send_message(to, text) → table talk / alliance negotiation
get_memory(topic)      → this agent's recall about opponents
```

Every stack binds the *same* contract to its own tool-calling mechanism. The engine validates everything. **An agent cannot cheat by producing bad output** — it can only lose a turn. This is what makes lenient guardrails safe (see [LUDO agent design](../projects/ludo/agent-design.md)).

### Keystone 2 — the shared event stream

Every implementation emits the same append-only event stream: dice rolls, moves, captures, messages sent, agent reasoning, token counts, latencies, costs, guardrail triggers, memory writes, context compactions.

This single decision buys a lot:

- **One UI** works against all three stacks, and against recorded games with no backend running.
- **One eval harness** scores all three identically.
- **A game becomes a file.** Reproducible, diffable, shareable, replayable — you can review a match without re-spending tokens.
- **Comparison is mechanical**, not vibes: diff the streams.

The schema lives in `shared/schemas/` and is versioned. Adding an event type is cheap; changing one is a breaking change that all three stacks must follow together.

## System shape

```
                    ┌─────────────────────────────────┐
                    │      Shared, stack-neutral      │
                    │  rules spec · tool contract ·   │
                    │  event schema · prompts · eval  │
                    └───────────────┬─────────────────┘
                                    │  (all three conform)
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│    Strands    │          │   LangGraph   │          │   Spring AI   │
│    (Python)   │          │    (Python)   │          │     (Java)    │
│  agent layer  │          │  agent layer  │          │  agent layer  │
│ orchestration │          │ orchestration │          │ orchestration │
└───────┬───────┘          └───────┬───────┘          └───────┬───────┘
        │                          │                          │
        └──── Python engine ───────┘                   Java engine
                    │                                         │
                    └──────── conformance vectors ────────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │  event stream (.jsonl) │
                         └──────────┬──────────┘
                              ┌─────┴─────┐
                              ▼           ▼
                            UI      eval harness
```

Note there are **two** engines, not three — see below.

## Why two engines, not three

The Ludo engine is ordinary deterministic code. Writing it three times triples the surface area for rule drift while teaching nothing about LLMs.

So: **one engine per language.** Strands and LangGraph share the Python engine — meaning the *only* difference between those two implementations is the agent framework itself. That's a genuinely controlled experiment. Spring AI gets a Java engine, kept honest by a shared set of **conformance vectors** (JSON files: given this seed and this move sequence, here is the exact resulting state) that both engines must reproduce.

Recorded as [ADR-0002](../decisions/adr-0002-engine-per-language.md).

## Model access is configuration, not code

[`shared/models.yaml`](../../shared/models.yaml) maps numbered seats to concrete providers. All three stacks read it:

```yaml
seats:
  - { seat: 1, access: bedrock, provider: anthropic, model: … }  # ─┐ same model,
  - { seat: 3, access: direct,  provider: anthropic, model: … }  # ─┘ two routes  ← the control
  - { seat: 2, access: bedrock, provider: amazon,   model: … }
  - { seat: 4, access: direct,  provider: deepseek, model: … }
```

Swapping a player from Bedrock to a direct API is a config edit, not a code change — which is what makes the **Bedrock vs. direct API** comparison (auth, latency, cost accounting, guardrail availability, observability hooks) cleanly measurable.

**Seats, not colours.** Which colour a seat plays rotates between games and is recorded per game in `game_started` ([ADR-0006](../decisions/adr-0006-seat-rotation.md)). Nothing may assume red is the same model it was last transcript.

One model deliberately occupies **both** access routes. Holding the model constant is what makes route differences attributable to the route rather than to the model — see [ADR-0005](../decisions/adr-0005-model-access-control.md).

**Two profiles**, `dev` and `headline`, differing in model tier and budget. A cheap shakedown run and a real result are then impossible to confuse, because the profile name is recorded in the transcript. All three stacks always run the same profile — the profile varies per *experiment*, never per stack.

Inference settings are pinned explicitly rather than left to the frameworks — an unpinned sampling parameter is a parity break that never announces itself. They are pinned **per provider**, because the families genuinely differ: the Claude 5 models reject `temperature`/`top_p` and use an `effort` level instead, while Nova and DeepSeek do the opposite. That asymmetry is a recorded [capability-matrix finding](stack-comparison.md#finding-inference-settings-are-not-uniformly-pinnable), not a hole in the control — seats 1 and 3 remain identically configured, which is what ADR-0005 actually rests on.

Families are settled and the Anthropic pair is pinned; **Nova, DeepSeek, and judge IDs are still [open](../open-questions.md)**.

## Cross-cutting concerns

**Observability.** Structured events are the substrate; OpenTelemetry spans wrap agent turns and LLM calls. Every stack emits the same span names and attributes so traces are comparable. Where a framework's native instrumentation doesn't reach, we adapt — and record the gap.

**Cost & tokens.** Every LLM call records input/output/cached tokens and computed cost. Per-agent and per-game budgets are enforceable, with a hard ceiling so a runaway negotiation can't drain an account.

**Caching.** The rules and system prompt are large and stable; the game state is small and changing. That's the ideal prompt-caching shape, and cache hit rates go into the event stream as a first-class metric.

**Guardrails.** Scoped to the *game boundary*, not to strategy. In-fiction deception is allowed and encouraged; out-of-fiction manipulation (prompt injection at other agents or the harness, attempts to forge state, abuse) is blocked. Detail in [agent design](../projects/ludo/agent-design.md).

**Harness engineering.** Agent memory and context compaction are explicit, visible subsystems — not incidental framework behaviour — because demonstrating them is a stated goal. Their events surface directly in the UI.

## Local first, cloud when it earns it

Everything runs locally against real model APIs before any of it is deployed. AWS services enter when a project actually needs them (Lambda + API Gateway for hosted play, AgentCore for managed agent runtime, SageMaker for the fine-tuning topics) rather than as an upfront requirement. See the [topic roadmap](../topics/roadmap.md).

## Related

- [Repository layout](repository-layout.md) — where this lands on disk
- [Environment strategy](environment-strategy.md) — keeping two Python stacks and a JVM from fighting
- [Stack capability matrix](stack-comparison.md) — the running record of framework gaps
