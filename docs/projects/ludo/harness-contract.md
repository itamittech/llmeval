# LUDO — Agent Harness Contract

**The specification all three stacks implement.** Strands, LangGraph, and Spring AI each build an *agent harness*: the layer between the deterministic engine and a model API. This document says what that layer must do.

It exists because of a problem [ADR-0007](../../decisions/adr-0007-ui-alongside-first-stack.md) names but cannot solve on its own: **the first stack written becomes the de facto standard.** Whatever shape Strands gives memory, negotiation, and event timing is what LangGraph and Spring AI will copy — including the parts that are Strands-shaped rather than neutral. Writing the contract down *as* the first stack is built means stacks two and three implement a specification and any contortion they need becomes a [capability-matrix](../../architecture/stack-comparison.md) finding rather than an invisible tax.

Requirement levels are RFC 2119: **MUST**, **MUST NOT**, **SHOULD**, **MAY**.

**This contract specifies observable behaviour — what a reader holding only the transcript could check — never internal structure.** Which classes exist, where memory lives, how compaction works inside: those are each framework's business, per [ADR-0008](../../decisions/adr-0008-framework-native-harness.md), and differences there between stacks are findings, not violations. An earlier reading of this document treated the harness as a component design to reproduce three times; that reading is retired.

## Related

- [ADR-0008](../../decisions/adr-0008-framework-native-harness.md) — why this contract binds behaviour and never mechanism
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

### 1.1 Behaviour, not mechanism

Everything in the harness row is a *responsibility*, not a component. A stack MUST meet each one with its framework's native primitives wherever the framework has them ([ADR-0008](../../decisions/adr-0008-framework-native-harness.md)); hand-rolling is reserved for what the framework cannot do, and every hand-rolled piece MUST be recorded in the [capability matrix](../../architecture/stack-comparison.md). Two stacks that satisfy this contract with entirely different machinery are the point of the exercise, not a problem with it.

## 2. The turn loop

Every stack MUST execute exactly this sequence, once per turn:

```
observe → negotiate → [roll → decide → resolve]+ → reflect
                       └── engine repeats on a 6 or a capture ──┘
```

**Observe.** The harness MUST build the model context from: the `StateView`, the recent event window, and that agent's own memory. It MUST NOT include another agent's memory, reasoning, or directed messages the agent was not the addressee of.

**Negotiate** *(redesigned by [ADR-0009](../../decisions/adr-0009-swarm-negotiation.md) to fit the swarm orchestrator)*. The phase is a floor-passing conversation. The active agent opens holding the floor. A floor-holder MAY send **one message of at most `budgets.max_message_chars` to one named player**, optionally carrying a **table note** visible to every player for the rest of the phase — doing so passes the floor to the addressee. A floor-holder that sends nothing ends the phase. The phase also ends after `budgets.max_floor_passes` passes.

Visibility rules, which every stack MUST reproduce: the directed message content reaches only its addressee; who-spoke-to-whom and table notes are visible to all players in the phase. Before the conversation starts, the harness MUST seed each agent's context with its own private briefing (`turn/briefing.md`: its memory, and messages addressed to it since its last turn). Whether an agent retains the conversation *within* the phase is framework behaviour ([ADR-0008](../../decisions/adr-0008-framework-native-harness.md)); the transcript is the durable record.

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

| Model does | Event carries | Why they differ |
|---|---|---|
| Passes the floor to a player with a message | `message_sent`, `to: "<colour>"` | the pass is a framework action (a handoff in Strands); the event is its neutral record |
| Leaves a table note while passing | `message_sent`, `to: null` | `null` marks the public channel unambiguously in the schema |
| `{"token", "to", "reasoning"}` | `reasoning` → `agent_reasoning.text`; the move goes to the engine | reasoning is an observation, not an instruction |
| `{"notes": [...]}` | one `memory_write` per note | one event per fact keeps the UI and eval able to count them |

A harness MUST classify each note into a `kind` (`opponent_model`, `commitment`, `strategy`, `observation`). Where the model does not supply one, the harness MUST default to `observation` rather than guessing — an invented `commitment` would be a fabricated fact about the game.

## 4. Memory

Memory MUST be private per agent, MUST persist across turns, and MUST survive compaction.

**Memory MUST NOT be corrected.** It records what an agent *believes*, including things it was successfully deceived about. A harness that "helpfully" reconciles memory against the board destroys the phenomenon under study.

*Where* memory lives is the framework's choice — its native state, session, or memory machinery, per [ADR-0008](../../decisions/adr-0008-framework-native-harness.md) — and it is one of the matrix rows most likely to separate the three frameworks. What MUST hold regardless of mechanism: notes reach the model only through `{{memory}}`, every write emits `memory_write`, and every note carries one of the schema's four kinds. Memory the framework holds but the transcript cannot see fails this contract — an invisible memory cannot be compared, judged, or replayed.

## 5. Compaction

When an agent's context exceeds its budget, the harness MUST summarise the oldest turns, fold durable facts into memory, drop the summarised turns from the window, and emit `context_compacted`. Whether that is a framework conversation manager or hand-written glue is [ADR-0008](../../decisions/adr-0008-framework-native-harness.md)'s business; the events are not optional either way.

It MUST NOT compact the system layer — that is the prompt-cacheable prefix, and touching it silently ends caching.

Compaction is a model call and MUST emit its own `llm_call` with `purpose: "compact"`. It MUST use the compacted agent's own model and settings — a cheaper summariser would make one stack's games cheaper for reasons invisible to the comparison — and it counts against the per-game ceiling and that agent's attribution like any other call.

## 6. Budgets and failure

| Situation | Required behaviour |
|---|---|
| Illegal move | Engine rejects; harness re-prompts **once** with `turn/retry.md`; a second failure forfeits the turn |
| Model timeout | Forfeit the turn |
| Provider error | Forfeit the turn |
| Per-game token ceiling reached | Stop the game; record the reason |

**A harness MUST NOT add retries beyond the one the engine allows.** Reliability is part of what is being measured — a stack that quietly retries three times looks better than one that doesn't, and the difference would be an artifact of harness code rather than a property of the framework.

That prohibition is about the application layer, and [ADR-0008](../../decisions/adr-0008-framework-native-harness.md) makes the line matter: transport retries inside the SDK — backoff on throttling or 5xx before any answer exists — are framework behaviour under test. Leave them at the framework's defaults and record what those defaults are in the matrix. The test is observable: anything that asks the model again a question it already answered is an application retry and forbidden; anything the SDK does to get one answer out is transport.

Every forfeit MUST reach the transcript. A forfeit nobody can see is a measurement destroyed.

## 7. A harness MUST NOT

- Edit, reorder, or reformat anything in `shared/prompts/`
- Add sampling parameters beyond those in `shared/models.yaml`, or accept framework defaults for them
- Correct, validate, or second-guess a move the engine already accepted
- Expose one agent's memory, reasoning, or received directed messages to another
- Treat an agent's claim as fact anywhere in its own logic
- Emit an event type not in the schema, or omit a required field

## 8. Proving a stack conforms

The rules above are prose, and prose is not enforcement. The plan is to make harness parity **testable**, the way [conformance vectors](../../../shared/conformance/) already make engine parity testable:

**Scripted-model conformance.** Each stack wires a scripted model that replays a committed script of responses instead of calling a provider — **through the framework's own model extension point**: a custom `Model` in Strands, a fake chat model in LangChain, a stubbed `ChatModel` in Spring AI. Never through a parallel client interface bolted on beside the framework, which would route the game around the very layer under test. With a fixed seed and the same script, all three stacks MUST produce the same event sequence.

Compared after normalising away what cannot match:

| Dropped before comparison | Because |
|---|---|
| `ts` | wall-clock |
| `llm_call.latency_ms`, `cost_usd` | no real call was made |
| `game_started.stack` | the one field that is *supposed* to differ |

What remains — event order, event types, payload contents, how many calls each turn took — is exactly the surface where a harness can silently diverge.

This does not exist yet and cannot until two stacks do. It is specified here so the first stack is built with a seam for injecting the fake client, rather than having one retrofitted later. **If a stack cannot accept an injected model client, that is a capability-matrix finding**, and a significant one.

## Status

Specification only — no stack implements it yet. Written before `stack-strands` deliberately; §2.1 names the engine change it required.

Re-scoped to observable behaviour by [ADR-0008](../../decisions/adr-0008-framework-native-harness.md) after the first cut of `stack-strands` showed what the earlier reading produced: a framework-independent harness that would have left the capability matrix comparing our own code with itself. The stack's built pieces are being reworked onto Strands-native primitives to match.
