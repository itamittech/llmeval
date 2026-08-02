# LUDO — Agent Harness Contract

**The specification all three stacks implement.** Strands, LangGraph, and Spring AI each build an *agent harness*: the layer between the deterministic engine and a model API. This document says what that layer must do.

It exists because of a problem [ADR-0007](../../decisions/adr-0007-ui-alongside-first-stack.md) names but cannot solve on its own: **the first stack written becomes the de facto standard.** Whatever shape Strands gives memory, negotiation, and event timing is what LangGraph and Spring AI will copy — including the parts that are Strands-shaped rather than neutral. Writing the contract down *as* the first stack is built means stacks two and three implement a specification and any contortion they need becomes a [capability-matrix](../../architecture/stack-comparison.md) finding rather than an invisible tax.

Requirement levels are RFC 2119: **MUST**, **MUST NOT**, **SHOULD**, **MAY**.

## Related

- [agent-design.md](agent-design.md) — the *design* this specifies; read it first for the reasoning
- [engine-design.md](engine-design.md) — the `Decider` protocol a harness implements
- [shared/prompts](../../../shared/prompts/README.md) · [shared/schemas](../../../shared/schemas/README.md) — the two contracts this binds together

---

## 1. Who owns what

| Layer | Owns | Never touches |
|---|---|---|
| **Engine** | Rules, legality, dice, turn order, engine events | Models, prompts, memory |
| **`shared/`** | Prompt text, model config, event schema | Anything executable |
| **Harness** *(this spec)* | Model calls, memory, compaction, budgets, agent events | Rule decisions, prompt text |

The dividing line is sharp on purpose: **a harness never decides whether a move is legal.** It picks from a list the engine already validated. Everything the harness does is therefore safe to get wrong in interesting ways — an agent can lie, misremember, or run out of budget without ever corrupting the game.

## 2. The turn loop

Every stack MUST execute exactly this sequence, once per turn:

```
observe → negotiate → [roll → decide → resolve]+ → reflect
                       └── engine repeats on a 6 or a capture ──┘
```

**Observe.** The harness MUST build the model context from: the `StateView`, the recent event window, and that agent's own memory. It MUST NOT include another agent's memory, reasoning, or private messages.

**Negotiate.** Only the agent whose turn it is MAY open a conversation, sending at most `budgets.max_messages_per_turn` messages of at most `budgets.max_message_chars` each. An agent that received a direct message this turn MAY reply exactly once. No agent may broadcast on another agent's turn.

**Roll / decide / resolve.** The engine rolls, offers legal moves, applies the chosen one. This block repeats within a turn on a six or a capture — **negotiation and reflection MUST NOT repeat with it.** An agent that talks once per extra roll gets a free multiplier on both influence and cost.

**Reflect.** The harness MUST offer the agent one memory-write opportunity per turn, after the turn resolves.

### 2.1 The hooks the engine provides

Writing this spec surfaced that the engine could not support it. `Game.play(deciders)` ran the whole match, `_play_turn` was private, and there was no hook before the first roll or after the turn ended — so a harness could not place negotiation and reflection where this section requires without reimplementing turn order, extra rolls, and three-sixes cancellation itself. That would have duplicated rule logic across three stacks and defeated [ADR-0002](../../decisions/adr-0002-engine-per-language.md).

**Built in the Python engine.** The `Decider` protocol now has two optional siblings the engine calls at the named points:

| Method | Called | Optional |
|---|---|---|
| `negotiate(ctx)` | Once per turn, before the first roll | Yes — absent on `RandomBot` |
| `choose(ctx)` | Once per roll | **Required** |
| `reflect(ctx)` | Once per turn, after it resolves | Yes |

Optional because the engine must keep working with bot deciders that have no model behind them — which is also what keeps the engine testable at speed and keeps [`turn_order.py`](../../../projects/ludo/engine-python/examples/turn_order.py) runnable. In Python these are `runtime_checkable` Protocols, so the engine's check is method presence; in Java, default interface methods.

`negotiate` receives a `TurnStart`, `reflect` a `TurnEnd` carrying the turn's end reason and every engine event it emitted — so a harness can render `{{turn_summary}}` without reconstructing the turn from the sink.

**A harness MUST NOT let an exception escape either hook.** The engine deliberately does not catch them: it absorbs a failure only where one has a defined in-game meaning, and a forfeit is a real outcome while a provider error mid-negotiation is not. Handling it belongs to the code that made the call, and a harness that lets one propagate takes the whole run down.

**The Java engine must match this before `stack-springai`.**

## 3. Event obligations

The transcript is the only output ([ADR-0003](../../decisions/adr-0003-shared-event-stream.md)). A harness MUST emit these, in this order relative to the engine's own events:

| Event | When | Required payload |
|---|---|---|
| `llm_call` | After **every** model call | `player`, `model`, `access`, `tokens{input,output,cache_read,cache_write}` |
| `message_sent` | Per message, during negotiate | `player`, `to`, `text` |
| `agent_reasoning` | After decide | `player`, `text` |
| `memory_write` | Per note, during reflect | `player`, `kind`, `text` |
| `context_compacted` | When compaction runs | `player`, `tokens_before`, `tokens_after` |
| `guardrail_triggered` | When content policy fires | `player`, `rule`, `action` |

**`llm_call` is emitted per call, not per turn.** A turn with negotiation, a rejected move, a retry, and reflection produces four or more. Cost analysis, latency comparison, and the Bedrock-vs-direct measurement all read this event, and a harness that batches them destroys all three.

`access` MUST record how the call was actually routed. It is the field [ADR-0005](../../decisions/adr-0005-model-access-control.md) rests on.

### 3.1 Translations a harness MUST get right

The prompts and the schema deliberately differ where each is easier for its own consumer. These mappings are specified so three stacks don't each invent one:

| Model returns | Event carries | Why they differ |
|---|---|---|
| `"to": "all"` | `to: null` | `"all"` is easier for a model to emit reliably; `null` is unambiguous in a schema |
| `"to": "<colour>"` | `to: "<colour>"` | unchanged |
| `{"token", "to", "reasoning"}` | `reasoning` → `agent_reasoning.text`; the move goes to the engine | reasoning is an observation, not an instruction |
| `{"notes": [...]}` | one `memory_write` per note | one event per fact keeps the UI and eval able to count them |

A harness MUST classify each note into a `kind` (`opponent_model`, `commitment`, `strategy`, `observation`). Where the model does not supply one, the harness MUST default to `observation` rather than guessing — an invented `commitment` would be a fabricated fact about the game.

## 4. Memory

Memory MUST be private per agent, MUST persist across turns, and MUST survive compaction.

**Memory MUST NOT be corrected.** It records what an agent *believes*, including things it was successfully deceived about. A harness that "helpfully" reconciles memory against the board destroys the phenomenon under study.

Memory MUST be an explicit subsystem rather than whatever the framework does implicitly — it is one of the matrix rows most likely to separate the three frameworks, and an implicit implementation cannot be compared.

## 5. Compaction

When an agent's context exceeds its budget, the harness MUST summarise the oldest turns, fold durable facts into memory, drop the summarised turns from the window, and emit `context_compacted`.

It MUST NOT compact the system layer — that is the prompt-cacheable prefix, and touching it silently ends caching.

Compaction is a model call and MUST emit its own `llm_call` with `purpose: "compact"`.

## 6. Budgets and failure

| Situation | Required behaviour |
|---|---|
| Illegal move | Engine rejects; harness re-prompts **once** with `turn/retry.md`; a second failure forfeits the turn |
| Model timeout | Forfeit the turn |
| Provider error | Forfeit the turn |
| Per-game token ceiling reached | Stop the game; record the reason |

**A harness MUST NOT add retries beyond the one the engine allows.** Reliability is part of what is being measured — a stack that quietly retries three times looks better than one that doesn't, and the difference would be an artifact of harness code rather than a property of the framework.

Every forfeit MUST reach the transcript. A forfeit nobody can see is a measurement destroyed.

## 7. A harness MUST NOT

- Edit, reorder, or reformat anything in `shared/prompts/`
- Add sampling parameters beyond those in `shared/models.yaml`, or accept framework defaults for them
- Correct, validate, or second-guess a move the engine already accepted
- Expose one agent's memory, reasoning, or private messages to another
- Treat an agent's claim as fact anywhere in its own logic
- Emit an event type not in the schema, or omit a required field

## 8. Proving a stack conforms

The rules above are prose, and prose is not enforcement. The plan is to make harness parity **testable**, the way [conformance vectors](../../../shared/conformance/) already make engine parity testable:

**Scripted-model conformance.** Each stack wires its framework to a fake model client that replays a committed script of responses instead of calling a provider. With a fixed seed and the same script, all three stacks MUST produce the same event sequence.

Compared after normalising away what cannot match:

| Dropped before comparison | Because |
|---|---|
| `ts` | wall-clock |
| `llm_call.latency_ms`, `cost_usd` | no real call was made |
| `game_started.stack` | the one field that is *supposed* to differ |

What remains — event order, event types, payload contents, how many calls each turn took — is exactly the surface where a harness can silently diverge.

This does not exist yet and cannot until two stacks do. It is specified here so the first stack is built with a seam for injecting the fake client, rather than having one retrofitted later. **If a stack cannot accept an injected model client, that is a capability-matrix finding**, and a significant one.

## Status

Specification only — no stack implements it yet. Written before `stack-strands` deliberately; §2.1 names the engine change it requires.
