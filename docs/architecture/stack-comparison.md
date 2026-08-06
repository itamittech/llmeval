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
| Tool / function calling | **Native** — [hooks.py](../../projects/ludo/stack-strands/src/ludo_strands/hooks.py) | **Native** — [table.py](../../projects/ludo/stack-langgraph/src/ludo_langgraph/table.py) `pass_floor` via `ToolNode` | **Native** — [Harness.java](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Harness.java) `passFloorTool` | Strands: the swarm's handoff tool. LangGraph: `@tool` + the framework's tool-executor node. Spring AI: `pass_floor` as a `FunctionToolCallback`, executed by `ToolCallingManager` — but see the metering finding |
| Structured output | — | — | — | |
| Multi-agent orchestration | **Native** — [harness.py](../../projects/ludo/stack-strands/src/ludo_strands/harness.py) | **Native** — [table.py](../../projects/ludo/stack-langgraph/src/ludo_langgraph/table.py) draws ADR-0009 as a `StateGraph` | **Manual** — [Harness.java](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Harness.java) `runTable` | Strands: prebuilt `Swarm` runs the table. LangGraph: the protocol IS the graph — but its own swarm *package* was rejected, see finding. Spring AI: no orchestrator exists — see finding |
| Agent-to-agent messaging | **Native** — [hooks.py](../../projects/ludo/stack-strands/src/ludo_strands/hooks.py) | **Adapter** — [table.py](../../projects/ludo/stack-langgraph/src/ludo_langgraph/table.py) `_deliver` | **Manual** — same loop | Strands: handoff = directed message, 1:1. LangGraph: transport is graph state via `Command`, delivery is glue in the tool body. Spring AI: the harness delivers. One row, all three ratings |
| Streaming responses | — | — | — | |
| Turn/step control & interruption | — | — | — | |

### Harness engineering

| Capability | Strands | LangGraph | Spring AI | Notes |
|---|---|---|---|---|
| Short-term / conversation memory | — | **Native** — [harness.py](../../projects/ludo/stack-langgraph/src/ludo_langgraph/harness.py) checkpointer thread per agent | **Native** — [Harness.java](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Harness.java) `askInConversation` | LangGraph: the conversation is checkpointer state under `thread_id=color`; code holds none of it. Spring AI: `ChatMemory` + `MessageChatMemoryAdvisor`, one conversation per agent |
| Long-term agent memory | **Native** — [players.py](../../projects/ludo/stack-strands/src/ludo_strands/players.py) | **Native** — [memory.py](../../projects/ludo/stack-langgraph/src/ludo_langgraph/memory.py) on the framework `Store` | **Manual** — [Memory.java](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Memory.java) | Strands: `AgentState`, repurposed. LangGraph: the only *dedicated* belief-store primitive of the three — namespaced, cross-thread. (Footgun: `Store.search` defaults to `limit=10` — an unwary read silently caps memory at ten beliefs.) Spring AI: no key-value store exists |
| Context compaction / summarisation | **Native** — [players.py](../../projects/ludo/stack-strands/src/ludo_strands/players.py) + [harness.py](../../projects/ludo/stack-strands/src/ludo_strands/harness.py) | **Native** — [players.py](../../projects/ludo/stack-langgraph/src/ludo_langgraph/players.py) `SummarizationMiddleware` | **Manual** — [Harness.java](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Harness.java) `maybeCompact` | Strands ships a summarising manager (with the hook-bypass trap); LangGraph ships summarisation middleware that answers both pre-registered questions cleanly — see finding; Spring AI only truncates, so the summariser is harness code |
| Prompt templating & versioning | — | — | — | |
| Prompt caching | — | — | — | Provider- and framework-dependent |
| State persistence / resume | **Native** — [harness.py](../../projects/ludo/stack-strands/src/ludo_strands/harness.py) + [test_session.py](../../projects/ludo/stack-strands/tests/test_session.py) | **Native ×2** — [session.py](../../projects/ludo/stack-langgraph/src/ludo_langgraph/session.py) + [test_session.py](../../projects/ludo/stack-langgraph/tests/test_session.py) | **Split** — [Session.java](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Session.java) + [SessionTest.java](../../projects/ludo/stack-springai/src/test/java/com/llmeval/ludo/springai/SessionTest.java) | All opt-in. Strands: `FileSessionManager`, everything in one store, on the framework's sync schedule (see finding). LangGraph: sqlite checkpointer + sqlite Store — no save call exists at all, see finding. Spring AI: conversations **Native** (`JdbcChatMemoryRepository` over embedded H2, write-through), beliefs **Manual** (`beliefs.json`) — see finding |
| Human-in-the-loop interrupt | — | — | — | |

### Operations

| Capability | Strands | LangGraph | Spring AI | Notes |
|---|---|---|---|---|
| Token accounting | **Native** — [hooks.py](../../projects/ludo/stack-strands/src/ludo_strands/hooks.py) | **Native** — [meter.py](../../projects/ludo/stack-langgraph/src/ludo_langgraph/meter.py) callback handler | **Native** — [Harness.java](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Harness.java) `ask` | Strands: lifecycle hooks (see finding for the trap). LangGraph: one callback propagated to every call underneath an invoke — the summariser's included. Spring AI: `ChatResponse` usage metadata, read synchronously — no trap to fall into |
| Cost attribution | — | — | — | |
| OpenTelemetry tracing | — | — | — | |
| Retry / backoff / fallback model | — | — | — | |
| Guardrails integration | **Native** — [guardrails.py](../../projects/ludo/stack-strands/src/ludo_strands/guardrails.py) via `BeforeToolCallEvent.cancel_tool` in [hooks.py](../../projects/ludo/stack-strands/src/ludo_strands/hooks.py) | **Manual** — [guardrails.py](../../projects/ludo/stack-langgraph/src/ludo_langgraph/guardrails.py) inside the `pass_floor` tool | **Manual** — [Guardrails.java](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Guardrails.java) inside the `pass_floor` tool | Same three rules in all three stacks, same leniency tests. Strands cancels at a framework hook; LangGraph and Spring AI have no cancellable tool boundary, so the gate is the tool's own body (a gate *node* was available in the graph — but placement is not a primitive). Bedrock Guardrails (abuse class) deferred to live games |
| Rate limiting / concurrency control | — | — | — | |

### Model access

| Capability | Strands | LangGraph | Spring AI | Notes |
|---|---|---|---|---|
| Bedrock invocation | — | — | — | |
| Direct provider API | — | — | — | |
| Agent needs a compile-time dep on the engine | no | no | **yes** | Python `Protocol` is structural; Java `interface` needs `implements`. See the finding below |
| Provider swap without code change | — | — | — | Driven by `shared/models.yaml` |
| Bedrock-native guardrails | — | — | — | |
| Per-provider inference config | **Native** — [strands_client.py](../../projects/ludo/stack-strands/src/ludo_strands/strands_client.py) | **Native** — [langgraph_client.py](../../projects/ludo/stack-langgraph/src/ludo_langgraph/langgraph_client.py) | **Native** — [LiveModels.java](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/LiveModels.java) | See the finding below — settings are **not** uniform across families, and neither are the knobs: Claude 5 `reasoning_effort` is a typed field in langchain-anthropic, a raw `params` passthrough in Strands, and absent from Spring AI's options surface |

### Finding: Strands accepts a wrong config keyword, warns, and ignores it

First real observation from building a stack, and a cautionary one for the other two.

`BedrockModel` and `AnthropicModel` take their configuration as **keyword arguments**. Passing `model_config={...}` — a plausible reading, since `update_config` takes exactly that name — is accepted, emits a `UserWarning`, and is then **discarded**. Every pinned setting reverts to a default.

That failure is invisible in the worst way: the model still answers, the game still plays, the transcript still validates, and the claim that all three stacks run identical inference settings is quietly false. It was caught only because the settings were asserted rather than assumed — `test_strands_client.py` now constructs each seat's model and reads `get_config()` back.

**The two providers also disagree within the same framework.** `BedrockConfig` has `temperature` and `top_p` as first-class keys; `AnthropicConfig` has neither and takes a `params` passthrough instead. So even inside one stack, "pin the inference settings" is per-provider plumbing rather than one call — the same asymmetry already recorded below for `models.yaml`, now confirmed at the SDK layer.

**What to check in LangGraph and Spring AI:** whether a mistyped or misplaced config key fails loudly, warns, or is silently dropped. A framework that fails loudly deserves credit for it in this matrix. *Both answered. langchain-anthropic: `ChatAnthropic(max_tokenz=123)` warns, shunts the typo into `model_kwargs` (bound for the API request), and the intended setting silently reverts to its default — `max_tokens` becomes 128000; the same reversion trap with a different tail. Spring AI: `AnthropicChatOptions` is a typed builder, so a misspelled setter does not compile — the one family where this whole class of bug is structural.*

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

**What to check in LangGraph and Spring AI:** whether their multi-agent stories can express per-pair visibility natively — LangGraph's graph state is shared by default too. A framework that can do it natively earns the credit here. *Answered for both: Spring AI has no multi-agent story at all (its finding below), and LangGraph splits exactly along the prediction — the swarm* package *cannot express it (shared channel by architecture), the graph* primitive *can (own state schema): see [the langgraph-swarm finding](#finding-langgraph-swarm-cannot-carry-ludos-negotiation-protocol--the-primitive-underneath-can).*

**Postscript, same day — the direction of fit was reversed.** [ADR-0009](../decisions/adr-0009-swarm-negotiation.md): rather than transporting the original protocol over a different pattern, the maintainer chose to redesign the protocol to `Swarm`'s semantics — directed messages as handoffs, table notes as shared-context posts, `max_floor_passes` as the handoff cap, per-agent briefings delivered through the construction-time snapshot that the reset semantics restore. The analysis above stands as the record of *why* the original protocol couldn't ride on `Swarm` unchanged, and it became the input to the redesign. What to check in LangGraph shifts accordingly: `langgraph-swarm` implements the same handoff pattern, so the two Python stacks now compare the *same orchestration architecture* — and whether Spring AI has any counterpart at all is the open headline row.

### Finding: in Strands hooks, per-call token usage rides the message, not the totals

Found building the turn loop, caught by a test, invisible in a live run.

The obvious way to meter tokens from `AfterModelCallEvent` is to read `agent.event_loop_metrics.accumulated_usage` and diff against the previous total. It is wrong: the event loop fires the hook **before** it updates the accumulated metrics, so the diff reads zeros on the first call and stays one call behind forever. The correct source is the assistant message itself — the loop attaches `message["metadata"]["usage"]` *before* firing the hook, precisely so hooks can read per-call numbers ([hooks.py](../../projects/ludo/stack-strands/src/ludo_strands/hooks.py)).

It surfaced only because the scripted loop asserted a nonzero `llm_call`; against a live provider every transcript would have carried plausible-looking, uniformly stale token counts. **What to check in LangGraph and Spring AI:** where per-call versus accumulated usage lives, and whether their callback ordering has the same trap. *Both answered, both clean: Spring AI attaches usage to the `ChatResponse` itself; LangGraph attaches it to each `AIMessage` (`usage_metadata`), so `on_llm_end` reads the call's own numbers — per-call by construction, nothing accumulated, no diffing, no ordering to get wrong.*

### Finding: Strands' summariser bypasses Strands' own hook system

Found wiring compaction, by reading `summarizing_conversation_manager.py` in the pinned `1.50.2` source.

`SummarizingConversationManager`'s default path generates the summary by calling `model.stream()` **directly** — deliberately skipping the agent pipeline (the code comments cite re-entrancy: summarising *during* an invocation would deadlock on the agent's lock). The consequence for anyone metering with lifecycle hooks: the summarisation is an **invisible model call** — no `BeforeModelCallEvent`, no `AfterModelCallEvent`, so no `llm_call` event, no budget gate, and a token meter that silently undercounts exactly when contexts are largest.

Two other properties matter for a game harness: the built-in *proactive* trigger keys off the **model's** `context_window_limit` (~200k), which a game budget should never approach — so a per-game budget means calling `reduce_context` yourself; and the summarisation prompt in the default path is framework-authored text, the same parity boundary as the swarm's handoff-tool description.

The fix used here: register each agent as its **own** `summarization_agent`. That path runs a full agent invocation — hooks fire, `llm_call` lands with `purpose: "compact"`, the per-game ceiling applies, and the contract's own-model-own-settings rule is satisfied by construction. Safe because the harness compacts *between* calls, where no invocation lock is held.

**What to check in LangGraph and Spring AI:** whether their summarisation/compaction machinery routes through the same instrumentation as ordinary model calls, or around it — and whether their compaction triggers can be driven by an application budget rather than the provider's context limit. *Both answered: Spring AI has no summarisation machinery to route anywhere (its finding below); LangGraph answers yes on both counts — see [its finding](#finding-langgraphs-summariser-answers-the-questions-strands-raised--native-on-both-counts).*

### Finding: session sync runs on the framework's schedule, not yours

Found wiring `FileSessionManager`, from the session-manager source and pinned by a test.

Strands syncs an agent to its session store at two moments: when a message is appended, and when an invocation ends. Both are the *framework's* moments. A harness that writes state at its own moments — this one writes reflect notes and compaction folds **after** the invocation returns — finds those writes silently missing from the store: the last sync ran just before they happened, and no later one comes. The final turn's memory of every game would simply never reach disk. Hence `LudoHarness.persist()`, an explicit `sync_agent` per player in `play()`'s `finally` — required, not tidy. [`test_session.py`](../../projects/ludo/stack-strands/tests/test_session.py) pins the trap by demonstrating the loss.

The mirror asymmetry on messages: persistence hangs off the *append* chokepoint, so the swarm's activation messages (appended by real invocations) **are** captured, while this harness's curation — briefing seeds and the post-table restore, both plain assignments — is invisible to the store. The persisted conversation is therefore the *appended* history, table fragments included, not the curated conversation the agent actually carries. Harmless for state-only restore; a real semantic wrinkle for conversation restore, and one input to [open question 18](../open-questions.md) on cross-game memory.

**What to check in LangGraph and Spring AI:** when their checkpointers/persistence actually write (per step? per graph run? explicit?), and whether state mutated outside the framework's own moments survives a restart without a manual flush. *Both answered below: Spring AI's repository writes through on every exchange, so the trap inverts — and LangGraph's write moments cover everything the harness holds, so no flush exists to forget.*

### Finding: Spring AI's missing harness primitives — and its simplest seam

The prediction this repo made before any stack existed — *"suppose Spring AI doesn't have the corresponding harness functionality"* — landed exactly where expected, and somewhere it wasn't.

**Missing, and hand-built as legitimate Manuals (ADR-0008):**
- **No multi-agent orchestrator.** Strands has `Swarm`; LangGraph has `langgraph-swarm`; Spring AI has nothing that passes a conversation between agents. The floor-passing table of [ADR-0009](../decisions/adr-0009-swarm-negotiation.md) is orchestrated by harness code — [`Harness.runTable`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Harness.java) delivers directed messages, fans table notes into inboxes, and enforces the pass cap itself. The observable protocol is identical across stacks; the machinery producing it is the comparison.
- **No agent belief store.** `ChatMemory` is conversation history — messages in, messages out — not a key-value state an agent owns. Strands' `AgentState` has no counterpart, so [`Memory.java`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Memory.java) is a plain class rendering the `{{memory}}` variable byte-identically to the Python stacks.

**And the counterweight, because honest findings cut both ways:** Spring AI's `ChatModel` seam produced **the simplest scripted model of the three stacks** — one synchronous `call(Prompt) → ChatResponse` with usage attached to the response object itself. No stream-event choreography (Strands needed five event shapes per reply), no hook-ordering trap (usage is *on the response*, read after the call returns — the accumulated-metrics pitfall recorded above for Strands cannot exist here). Faking a provider took forty lines. For a framework aimed at enterprise Java, the flattest possible model seam is exactly the right instinct, and it deserves the credit here.

### Finding: Spring AI's internal tool execution hides model invocations from the caller

Found making `pass_floor` a real framework tool, and it matters for anyone doing cost accounting.

Spring AI executes tools *inside* the `ChatModel` — the provider binding loops (model → tool → model) and hands the caller **one** `ChatResponse` for what was **two or more** model invocations. Client-level metering therefore cannot see the individual calls: this stack's scripted model aggregates usage across its internal chain so nothing goes unmetered, but per-invocation granularity is gone, and one `llm_call` event covers a whole tool round-trip. Contrast Strands, whose lifecycle hooks fired around *every* invocation, tool rounds included — the two frameworks disagree about what "one call" even is.

The escape hatch exists and is the plan for live play: `ToolCallingChatOptions.setInternalToolExecutionEnabled(false)` returns the tool call to the caller, who runs the loop — per-invocation metering restored, at the price of owning the loop. **What to check in LangGraph:** where its tool execution sits relative to its callbacks, and what a "call" means to its token accounting. *Answered, and it is the exact opposite grain: tool execution is a graph node (`ToolNode`), so the model↔tool loop is drawn as visible steps and every model invocation is its own call through the callback system. Nothing is hidden — in this stack's table, a delivered pass is one metered invocation and a blocked one is two, both in the transcript.*

### Finding: Spring AI persists the conversation into a database — and nothing else

Found answering the Strands session finding's own question — *when does persistence actually write, and does state mutated outside the framework's moments survive?* — and the answers came back inverted.

Spring AI's persistence primitive is a repository **behind** the memory, not a store **beside** the agent: `ChatMemory` delegates every read and write to a `ChatMemoryRepository`, so swapping the in-memory default for [`JdbcChatMemoryRepository`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Session.java) makes the database the conversation's *actual backing store*. There is no sync moment to forget, because there is no sync: every exchange the advisor saves is written through as it happens, and [`SessionTest.java`](../../projects/ludo/stack-springai/src/test/java/com/llmeval/ludo/springai/SessionTest.java) shows a conversation surviving a "process" that never called save. The Strands trap — writes after the last sync silently lost — cannot exist here.

Three prices for that inversion, all read from the module itself:

- **Every shipped backend is a database.** Eight SQL dialects in the JDBC module (this stack runs H2 in file mode — embedded, serverless, pure Java), Cassandra and Neo4j elsewhere — but no file store. Strands' inspectable JSON session directory has no counterpart: reading a persisted conversation means SQL. And without Boot, the table doesn't create itself — `Session.open` runs the module's own `schema-h2.sql` by hand, the one line of glue the starter would have hidden.
- **Only text survives.** The schema is `(conversation_id, content, type, timestamp)` — a message's text and role, nothing else. Metadata and tool-call structure are not columns, so they do not exist after a restart. Plain exchanges (this game's decide/reflect conversations) round-trip perfectly; anything richer would come back flattened.
- **Beliefs never enter the framework at all.** There is no `AgentState` for `Memory` to live in, so nothing the framework offers can persist it: `beliefs.json` is written by `Harness.persist()` in `play()`'s finally and read back at construction. The asymmetry is pinned by a test — skip the save and the conversations survive while every note silently vanishes.

One framework persists everything, on its own schedule; the other persists half of everything, continuously. Neither gives you resume for free — you either flush at the end or save your own half. **What to check in LangGraph:** its checkpointer writes per graph step — whose moments are those, and does any of this harness's state live outside them? *Answered [below](#finding-langgraph-persistence--swap-the-stores-and-there-is-nothing-left-to-save): nothing does, and the third answer is the shortest.*

### Finding: langgraph-swarm cannot carry LUDO's negotiation protocol — the primitive underneath can

The mirror image of the Strands `Swarm` finding, discovered the same way: by reading the installed source before writing a line against it.

`langgraph-swarm` 0.1.0 is the framework family's own swarm package — the obvious counterpart to the primitive the Strands stack runs on. It is also ~200 lines over `StateGraph`, and its state model settles the question by itself: `SwarmState` extends `MessagesState`, **one shared `messages` channel for every agent**, and its handoff tool's `Command` re-publishes the full history on every transfer. Whoever holds the floor reads everything everyone has said — every directed message, every other player's words. That is the exact thing the harness contract's MUST NOT forbids (§7: never expose one agent's received directed messages to another), and no configuration escapes it: the sharing is the package's architecture, built for cooperating specialists serving one user's conversation, not adversaries with private channels.

Where the Strands finding led to ADR-0009 *redesigning the protocol to fit the orchestrator*, that door is closed now — two shipped stacks share the protocol, so the protocol wins. The fix was to drop **one layer down**: [`table.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/table.py) draws the floor-passing table as a custom `StateGraph` — private per-holding context seeded by a `brief` node (the same `RemoveMessage(REMOVE_ALL_MESSAGES)` wipe the framework's own summariser uses), the pass as a real tool run by `ToolNode`, floor routing as conditional edges, the framework's `recursion_limit` as the runaway bound. Same machinery the swarm package itself is made of; different state shape. Orchestration still rates **Native** — in LangGraph the graph *is* the framework — but the package that looked like a free lunch does not ship in this venv.

**What this stack would tell a chooser:** "the framework has a swarm package" and "the swarm package fits your protocol" are different claims, and the second one is decided by a state schema, not a feature list. Prebuilts encode assumptions; primitives don't.

### Finding: LangGraph's summariser answers the questions Strands' raised — Native on both counts

When Strands' summarising manager turned out to bypass its own hook system, the matrix pre-registered two questions for the other stacks. LangGraph's `SummarizationMiddleware` (shipped in langchain 1.x) answers both the right way:

- **Does summarisation route through the same instrumentation as ordinary calls?** Yes. The middleware invokes its summary model as a normal model call, so the callback meter sees it like any other — [the test](../../projects/ludo/stack-langgraph/tests/test_harness.py) pins one `llm_call` with `purpose: "compact"`, no special path, no bypass to fix. (Strands needed the agent-as-its-own-summariser workaround for the same property.)
- **Can the trigger be an application budget rather than the provider's window?** Yes, by constructor: `trigger=("tokens", max_context_tokens)` with a caller-supplied `token_counter` — the game's budget and the parity counter drop straight in.

The harness's [`Compactor`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/players.py) subclass adds *observation*, not behaviour: ~30 lines to capture the summary for `context_compacted`, fold it into durable memory (contract §5), and stamp the summary call's purpose. Two mechanics worth knowing before relying on it: `keep=("messages", N)` is a **target**, not a promise — a safe-boundary rule chooses the actual cutoff, and at this pinned version it will happily summarise a single opening message; and the summary re-enters the thread as a `HumanMessage` tagged `lc_source: "summarization"`, which is the clean way to detect that a compaction happened.

### Finding: LangGraph persistence — swap the stores, and there is nothing left to save

The three stacks give three different answers to "what survives the process?", and this is the shortest one. Strands persisted everything through one manager **on the framework's sync schedule** — miss the final explicit sync and the last writes are gone. Spring AI persisted the conversation continuously through its repository — **but beliefs never touch the framework**, so the harness saves them itself. LangGraph's harness already keeps *both* halves in framework stores — the conversation in the checkpointer (written per super-step, during the run), beliefs in the `Store` (written at `put`, immediately). Persistence is [`session.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/session.py): swap both in-memory implementations for their sqlite twins (`SqliteSaver` + `SqliteStore`, one extra package) over one session file — and that is the whole feature. **No save call exists in this stack**, and [the test](../../projects/ludo/stack-langgraph/tests/test_session.py) pins the claim literally: `assert not hasattr(harness, "persist")`.

One line of real glue, recorded because it cost an hour: the two components disagree about transactions when sharing one `sqlite3.Connection` — the checkpointer rides implicit transactions, the store issues its own `BEGIN`, and the combination is an `OperationalError` until the connection is opened in autocommit mode. The kind of integration seam a "both ship in one package" bullet never mentions.

### Finding: the Java agent must depend on the engine; the Python agents need not

Recorded from the engine port, before any stack exists.

In Python, `Decider` is a `Protocol`. An agent satisfies it by having a `choose` method of the right shape — no import, no inheritance, no compile-time relationship between the engine package and the agent package at all. That is what lets the Strands and LangGraph stacks keep [genuinely separate dependency trees](environment-strategy.md) while sharing one engine.

Java's `interface` needs an explicit `implements`, so every Spring AI agent must have `ludo-engine` on its compile classpath. Nothing breaks — but the isolation the Python stacks get for free has to be arranged deliberately on the JVM, and a future change to `Decider` is a recompile for the Java stack and a no-op for the Python ones.

Predicted from the port; now real: [`Harness.SpringDecider`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Harness.java) writes `implements Decider`, and the stack's pom depends on the engine by coordinates — built into the local repository first, exactly the arranged-deliberately step Python never needs.

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
| Tokens per game (same seed, scripted*) | **12,902** | **33,944** | **36,812** |
| Cache hit rate | — | — | — |
| Cost per game | — | — | — |

Engine and UI code are excluded from the LOC count — they're shared, so counting them would flatter everyone equally and tell you nothing.

\* Scripted tier, measured by [`ludo_eval compare`](../../projects/ludo/eval/README.md) over the three committed fixtures — the same seed and the same four-turn story in all three. These are chars//4 estimates of what each harness **actually sent**, so they measure prompt-volume overhead, not provider billing. The 2.6–2.9× spread is real architecture, not noise: Strands' swarm resets each activation to a short briefing, while LangGraph and Spring AI carry growing per-agent conversations into every call. Live numbers replace these when live games exist.

## Narrative findings

> Populated during implementation. This is where the actual insight lives — the table above is just the index.

Each entry: what we tried, what happened, what it cost, and what we'd tell someone choosing a framework.

## Related

- [Architecture overview](overview.md) — why parity makes these numbers comparable
- [Vision](../vision.md) — why negative results get equal billing
