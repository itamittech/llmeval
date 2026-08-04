# Stack Capability Matrix

The running scoreboard. This file is the repo's headline output — the thing a reader comes for.

> From the brief: *"If any framework suppose Spring AI doesnt have the corresponding harness functionality that should be also highlighted."*

Gaps are results. When a framework can't do something, we record it here, build the workaround, note what it cost, and surface it in the UI.

## How to read it

| Rating | Meaning |
|---|---|
| **Native** | First-class feature. Idiomatic, documented, a few lines. |
| **Adapter** | Achievable via a supported extension point, but we wrote glue. |
| **Manual** | No framework support; we implemented it ourselves from scratch. |
| **Absent** | Not reasonably achievable within the framework's model. |
| **—** | Not yet evaluated. |

Every rating must link to the code that justifies it. **An unsourced rating is an opinion, and opinions don't go in this table.**

One more rule, from [ADR-0008](../decisions/adr-0008-framework-native-harness.md): stacks must use native primitives wherever the framework has them, so **Manual is legitimate only where the framework offers nothing**. A Manual rating sitting beside an existing framework feature means we broke our own rule, not that the framework lacks it.

## Matrix

> Populated as LUDO is built in each stack. Strands ratings began with its turn loop; a link means the code exists and its tests pass against the scripted model.

### Core agent mechanics

| Capability | Strands | LangGraph | Spring AI | Notes |
|---|---|---|---|---|
| Tool / function calling | **Native** — [hooks.py](../../projects/ludo/stack-strands/src/ludo_strands/hooks.py) | — | — | Strands: the swarm's own handoff tool, captured via `AfterToolCallEvent` |
| Structured output | — | — | — | |
| Multi-agent orchestration | **Native** — [harness.py](../../projects/ludo/stack-strands/src/ludo_strands/harness.py) | — | — | `Swarm` runs the table; protocol redesigned to fit it ([ADR-0009](../decisions/adr-0009-swarm-negotiation.md)) — see finding |
| Agent-to-agent messaging | **Native** — [hooks.py](../../projects/ludo/stack-strands/src/ludo_strands/hooks.py) | — | — | Handoff message = directed message; handoff context = table note |
| Streaming responses | — | — | — | |
| Turn/step control & interruption | — | — | — | |

### Harness engineering

| Capability | Strands | LangGraph | Spring AI | Notes |
|---|---|---|---|---|
| Short-term / conversation memory | — | — | — | |
| Long-term agent memory | **Native** — [players.py](../../projects/ludo/stack-strands/src/ludo_strands/players.py) | — | — | Cross-turn recall of opponents, on `AgentState` |
| Context compaction / summarisation | **Native** — [players.py](../../projects/ludo/stack-strands/src/ludo_strands/players.py) + [harness.py](../../projects/ludo/stack-strands/src/ludo_strands/harness.py) | — | — | Explicit goal of the project; see finding — the default path bypasses the hooks |
| Prompt templating & versioning | — | — | — | |
| Prompt caching | — | — | — | Provider- and framework-dependent |
| State persistence / resume | — | — | — | |
| Human-in-the-loop interrupt | — | — | — | |

### Operations

| Capability | Strands | LangGraph | Spring AI | Notes |
|---|---|---|---|---|
| Token accounting | **Native** — [hooks.py](../../projects/ludo/stack-strands/src/ludo_strands/hooks.py) | — | — | Lifecycle hooks + per-call usage — see finding below for the trap |
| Cost attribution | — | — | — | |
| OpenTelemetry tracing | — | — | — | |
| Retry / backoff / fallback model | — | — | — | |
| Guardrails integration | — | — | — | Bedrock Guardrails vs. framework-native |
| Rate limiting / concurrency control | — | — | — | |

### Model access

| Capability | Strands | LangGraph | Spring AI | Notes |
|---|---|---|---|---|
| Bedrock invocation | — | — | — | |
| Direct provider API | — | — | — | |
| Agent needs a compile-time dep on the engine | no | no | **yes** | Python `Protocol` is structural; Java `interface` needs `implements`. See the finding below |
| Provider swap without code change | — | — | — | Driven by `shared/models.yaml` |
| Bedrock-native guardrails | — | — | — | |
| Per-provider inference config | — | — | — | See the finding below — settings are **not** uniform across families |

### Finding: Strands accepts a wrong config keyword, warns, and ignores it

First real observation from building a stack, and a cautionary one for the other two.

`BedrockModel` and `AnthropicModel` take their configuration as **keyword arguments**. Passing `model_config={...}` — a plausible reading, since `update_config` takes exactly that name — is accepted, emits a `UserWarning`, and is then **discarded**. Every pinned setting reverts to a default.

That failure is invisible in the worst way: the model still answers, the game still plays, the transcript still validates, and the claim that all three stacks run identical inference settings is quietly false. It was caught only because the settings were asserted rather than assumed — `test_strands_client.py` now constructs each seat's model and reads `get_config()` back.

**The two providers also disagree within the same framework.** `BedrockConfig` has `temperature` and `top_p` as first-class keys; `AnthropicConfig` has neither and takes a `params` passthrough instead. So even inside one stack, "pin the inference settings" is per-provider plumbing rather than one call — the same asymmetry already recorded below for `models.yaml`, now confirmed at the SDK layer.

**What to check in LangGraph and Spring AI:** whether a mistyped or misplaced config key fails loudly, warns, or is silently dropped. A framework that fails loudly deserves credit for it in this matrix.

### Finding: Strands `Swarm` cannot carry LUDO's negotiation protocol

Recorded before the turn loop exists, from reading the pinned `strands-agents 1.50.2` source while mapping harness responsibilities to primitives for [ADR-0008](../decisions/adr-0008-framework-native-harness.md). Line numbers refer to `strands/multiagent/swarm.py` at that version.

First, a distinction that matters: **agent-swarm *architecture* — four peers, own goals, no coordinator — is not what's ruled out.** LUDO implements it either way, and Strands supports it through more than one pattern. What's ruled out is the `Swarm` *class* as the transport for [the negotiation protocol of answered question 6](../open-questions.md): active-agent-driven, reply-exactly-once, private pairwise channels.

`Swarm` is built for a different job — stateless specialist workers over a shared blackboard, collaborating on one task until whoever holds the floor declares it done. Three mechanics, each fine for that job, each colliding with this protocol:

1. **Every activation resets the agent to swarm-construction state.** `SwarmNode.__post_init__` snapshots the agent's messages *and* its `AgentState` (78–81); `reset_executor_state` restores both (115–116); the execution loop calls it before **every** node activation (886). Memory lives in `AgentState` per ADR-0008 — so red messages blue, blue replies, and red re-activates having *forgotten its own mid-negotiation memory writes*. The primitive assumes private state is disposable and the blackboard is the memory; this game is about private beliefs.
2. **The floor belongs to whoever spoke last.** Every node input ends with *"If you don't hand off to another agent, the swarm will consider the task complete"* (699–701). The protocol needs the active agent to keep the floor and a recipient to reply exactly once — in `Swarm`, return-to-sender is a hope encoded in a prompt, and a recipient that answers without handing back silently ends the whole phase with the active agent's remaining messages unsent.
3. **Cross-activation carriers are broadcast or ephemeral.** The handoff `context` dict is stored in `SharedContext` (621–624) and rendered to every later activation (678–685); node history — *who* talked to *whom* — is shown to everyone (676). Only the handoff `message` string is pairwise, and it is cleared after being shown once (879). No durable private channel; and no broadcast primitive at all, so "public" messages would be delivered by the harness out-of-band anyway.

An earlier version of this finding claimed everything an agent contributes goes through `SharedContext` — overstated: the handoff message is genuinely pairwise. The correction came from being challenged on it, and the fuller reading above is what the challenge produced.

`Graph` doesn't fit either, for a simpler reason: it wires a *deterministic* topology in advance, while who talks to whom each turn is the active agent's runtime choice.

The finding's original conclusion — written before ADR-0009 reversed the direction of fit, and kept as the record — was to use **agents-as-tools** instead: also a Strands-documented multi-agent pattern, so a choice between two native patterns, not native vs. hand-rolled. The active agent would get a tool addressing a chosen opponent; a public message would land in every agent's context, a private one would reach exactly one. The turn phases themselves need no orchestrator either way — the engine's `negotiate`/`choose`/`reflect` hooks already sequence them.

Worth stating the counterfactual: a negotiation redesigned as all-public with autonomous floor-passing would fit `Swarm` natively. The mismatch is with *this* protocol — chosen because private channels are what make deception observable — not with multi-agent orchestration per se.

**What to check in LangGraph and Spring AI:** whether their multi-agent stories can express per-pair visibility natively — LangGraph's graph state is shared by default too. A framework that can do it natively earns the credit here.

**Postscript, same day — the direction of fit was reversed.** [ADR-0009](../decisions/adr-0009-swarm-negotiation.md): rather than transporting the original protocol over a different pattern, the maintainer chose to redesign the protocol to `Swarm`'s semantics — directed messages as handoffs, table notes as shared-context posts, `max_floor_passes` as the handoff cap, per-agent briefings delivered through the construction-time snapshot that the reset semantics restore. The analysis above stands as the record of *why* the original protocol couldn't ride on `Swarm` unchanged, and it became the input to the redesign. What to check in LangGraph shifts accordingly: `langgraph-swarm` implements the same handoff pattern, so the two Python stacks now compare the *same orchestration architecture* — and whether Spring AI has any counterpart at all is the open headline row.

### Finding: in Strands hooks, per-call token usage rides the message, not the totals

Found building the turn loop, caught by a test, invisible in a live run.

The obvious way to meter tokens from `AfterModelCallEvent` is to read `agent.event_loop_metrics.accumulated_usage` and diff against the previous total. It is wrong: the event loop fires the hook **before** it updates the accumulated metrics, so the diff reads zeros on the first call and stays one call behind forever. The correct source is the assistant message itself — the loop attaches `message["metadata"]["usage"]` *before* firing the hook, precisely so hooks can read per-call numbers ([hooks.py](../../projects/ludo/stack-strands/src/ludo_strands/hooks.py)).

It surfaced only because the scripted loop asserted a nonzero `llm_call`; against a live provider every transcript would have carried plausible-looking, uniformly stale token counts. **What to check in LangGraph and Spring AI:** where per-call versus accumulated usage lives, and whether their callback ordering has the same trap.

### Finding: Strands' summariser bypasses Strands' own hook system

Found wiring compaction, by reading `summarizing_conversation_manager.py` in the pinned `1.50.2` source.

`SummarizingConversationManager`'s default path generates the summary by calling `model.stream()` **directly** — deliberately skipping the agent pipeline (the code comments cite re-entrancy: summarising *during* an invocation would deadlock on the agent's lock). The consequence for anyone metering with lifecycle hooks: the summarisation is an **invisible model call** — no `BeforeModelCallEvent`, no `AfterModelCallEvent`, so no `llm_call` event, no budget gate, and a token meter that silently undercounts exactly when contexts are largest.

Two other properties matter for a game harness: the built-in *proactive* trigger keys off the **model's** `context_window_limit` (~200k), which a game budget should never approach — so a per-game budget means calling `reduce_context` yourself; and the summarisation prompt in the default path is framework-authored text, the same parity boundary as the swarm's handoff-tool description.

The fix used here: register each agent as its **own** `summarization_agent`. That path runs a full agent invocation — hooks fire, `llm_call` lands with `purpose: "compact"`, the per-game ceiling applies, and the contract's own-model-own-settings rule is satisfied by construction. Safe because the harness compacts *between* calls, where no invocation lock is held.

**What to check in LangGraph and Spring AI:** whether their summarisation/compaction machinery routes through the same instrumentation as ordinary model calls, or around it — and whether their compaction triggers can be driven by an application budget rather than the provider's context limit.

### Finding: the Java agent must depend on the engine; the Python agents need not

Recorded from the engine port, before any stack exists.

In Python, `Decider` is a `Protocol`. An agent satisfies it by having a `choose` method of the right shape — no import, no inheritance, no compile-time relationship between the engine package and the agent package at all. That is what lets the Strands and LangGraph stacks keep [genuinely separate dependency trees](environment-strategy.md) while sharing one engine.

Java's `interface` needs an explicit `implements`, so every Spring AI agent must have `ludo-engine` on its compile classpath. Nothing breaks — but the isolation the Python stacks get for free has to be arranged deliberately on the JVM, and a future change to `Decider` is a recompile for the Java stack and a no-op for the Python ones.

A second, smaller one from the same port: **Java test seams must be designed in advance.** Python's engine tests reach three-sixes cancellation by assigning `game.dice` on a live object; Java has no equivalent, so `Game` carries a package-private constructor taking an `IntSupplier`. Expect the same asymmetry wherever the Spring AI stack needs to substitute a model client — which is exactly what the harness contract's [scripted-model conformance](../projects/ludo/harness-contract.md) will require.

### Finding: inference settings are not uniformly pinnable

Recorded before any stack exists, because it changes what "identical configuration" can mean.

The plan was to pin `temperature`, `top_p`, and `max_output_tokens` in [`shared/models.yaml`](../../shared/models.yaml) so that no framework's defaults could leak into the comparison. **That is not achievable across these four families.** The Claude 5 models reject `temperature`, `top_p`, and `top_k` with a 400 and control reasoning depth with an `effort` level instead; Amazon Nova and DeepSeek take the sampling parameters and have no equivalent effort knob.

So `models.yaml` pins settings **per provider** — the honest shape — rather than asserting a single number that two of the four seats would reject.

**What this costs, precisely:** nothing in the [ADR-0005](../decisions/adr-0005-model-access-control.md) control. Seats 1 and 3 are the same model with the same settings, so Bedrock-vs-direct stays clean. What's lost is the weaker claim that *all four seats* were configured identically — which was never a controlled comparison to begin with, since the models differ in every other respect too. The value of writing it down is that the limitation is now visible rather than assumed.

A related consequence: on Claude 5, thinking is on by default and its tokens count against `max_output_tokens`, so a budget sized for the answer alone truncates mid-response. `max_output_tokens` is set with that headroom included.

## Quantitative comparison

Filled from recorded games. Same seeds, same models, same rules — so these numbers mean something.

| Metric | Strands | LangGraph | Spring AI |
|---|---|---|---|
| Lines of code (agent + orchestration layer) | — | — | — |
| Direct dependencies | — | — | — |
| Cold start to first move | — | — | — |
| Median agent turn latency | — | — | — |
| Tokens per game (same seed) | — | — | — |
| Cache hit rate | — | — | — |
| Cost per game | — | — | — |

Engine and UI code are excluded from the LOC count — they're shared, so counting them would flatter everyone equally and tell you nothing.

## Narrative findings

> Populated during implementation. This is where the actual insight lives — the table above is just the index.

Each entry: what we tried, what happened, what it cost, and what we'd tell someone choosing a framework.

## Related

- [Architecture overview](overview.md) — why parity makes these numbers comparable
- [Vision](../vision.md) — why negative results get equal billing
