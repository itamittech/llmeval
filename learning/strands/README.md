# Learning the Strands Harness

The [engine walkthrough](../python/01-walkthrough-game.md) ends where the engine hands a turn to a `Decider` and waits. This folder explains what happens on the other side of that call — the [Strands stack](../../projects/ludo/stack-strands/), where four framework `Agent`s negotiate, choose moves, and remember.

Everything here is checked against **`strands-agents 1.50.2`**, the exact version pinned in the stack's lockfile. Where a claim depends on framework internals, it came from reading that version's source, not its docs.

## What Strands is, in one paragraph

Strands is an agent framework built around one loop: give an `Agent` a model, a system prompt, and some tools, then call it with a prompt. The framework asks the model; if the model answers with text, you get the text back; if it answers with a *tool call*, the framework runs the tool, appends the result, and asks the model again — repeating until the model stops with a plain answer. Everything else the framework offers — state, hooks, multi-agent orchestration, conversation management — hangs off that loop. [Doc 00](00-the-agent-loop.md) walks it in detail, because every line of the harness assumes it.

## Read in this order

| Doc | Question it answers |
|---|---|
| [00 — the agent loop](00-the-agent-loop.md) | What actually happens when you call `agent("...")`? And how do you fake a model through the framework's own interface? |
| [01 — one turn through the harness](01-one-turn-through-the-harness.md) | How the engine's `negotiate` / `choose` / `reflect` hooks are answered — rendering, parsing, retries, budgets, events |
| [02 — the swarm table](02-the-swarm-table.md) | How negotiation runs on `Swarm` — handoffs, the snapshot-reset trick that delivers briefings, and what the orchestrator would not allow |

The diagrams live in [class-design.md §9](../../docs/projects/ludo/class-design.md#9-the-harness-layer-the-same-turn-on-strands) — the harness object graph and one turn traced across engine → harness → framework.

## The Strands classes this stack touches

The lookup table. "We call" means harness code invokes it; "framework calls" means Strands invokes *our* code there.

| Strands class | What it is | Who calls whom | Where in this stack |
|---|---|---|---|
| `Agent` | The loop: model + system prompt + tools + state + hooks | We call — `agent(prompt)` in choose/reflect; `Swarm` calls it during negotiation | built in [`players.py`](../../projects/ludo/stack-strands/src/ludo_strands/players.py), called in [`harness.py`](../../projects/ludo/stack-strands/src/ludo_strands/harness.py) |
| `Model` (ABC) | The provider seam: `stream()` yields the response as events | Framework calls it inside the loop | implemented by [`scripted.py`](../../projects/ludo/stack-strands/src/ludo_strands/scripted.py); provider models built in [`strands_client.py`](../../projects/ludo/stack-strands/src/ludo_strands/strands_client.py) |
| `BedrockModel`, `AnthropicModel` | The two provider bindings — different config surfaces, same seam | We construct, framework calls | [`strands_client.py`](../../projects/ludo/stack-strands/src/ludo_strands/strands_client.py) |
| `AgentState` | Per-agent key-value store, JSON-validated, deep-copied on read | We call — `state.get` / `state.set` | memory lives here — [`players.py`](../../projects/ludo/stack-strands/src/ludo_strands/players.py) |
| `HookProvider` / `HookRegistry` | The lifecycle-event system: subscribe callbacks to named points in the loop | Framework calls our callbacks | [`hooks.py`](../../projects/ludo/stack-strands/src/ludo_strands/hooks.py) |
| `BeforeModelCallEvent` | Fires before each model invocation; settable `cancel` | Framework → us | the budget ceiling |
| `AfterModelCallEvent` | Fires after each invocation, success or failure | Framework → us | one `llm_call` event per firing |
| `AfterToolCallEvent` | Fires after each tool execution, carrying the tool's input | Framework → us | a floor pass becomes `message_sent` |
| `Swarm` | Multi-agent orchestrator: agents hand off to each other until one stops | We construct one per negotiation phase; it drives the agents | [`harness.py`](../../projects/ludo/stack-strands/src/ludo_strands/harness.py) `_run_table` |
| `handoff_to_agent` | The tool `Swarm` injects into every member — its only steering wheel | The *model* calls it | captured in [`hooks.py`](../../projects/ludo/stack-strands/src/ludo_strands/hooks.py) |
| `AgentResult` | What `agent(...)` returns: message, stop reason, metrics | We read — `str(result)` is the reply text | [`harness.py`](../../projects/ludo/stack-strands/src/ludo_strands/harness.py) |
| `SummarizingConversationManager` | The framework's context compaction: summarises the oldest messages, keeps the rest | We call `reduce_context` when the *game's* budget is exceeded | wired in [`players.py`](../../projects/ludo/stack-strands/src/ludo_strands/players.py) (each agent is its own summariser), driven from [`harness.py`](../../projects/ludo/stack-strands/src/ludo_strands/harness.py) `_maybe_compact` |
| `FileSessionManager` | Persists agent state across processes | — | **not wired yet** — session persistence work item |

The unwired row is deliberate: listing only what exists keeps this table from teaching code that was never written.

## Running things

No `examples/` folder here, unlike [learning/python](../python/) and [learning/java](../java/) — a Strands example cannot be dependency-free, and that rule exists so learning material never needs a build. Instead, **the stack's tests are the examples**: each one is a small, runnable, asserted demonstration, and they run in the stack's own environment:

```bash
uv run --directory projects/ludo/stack-strands pytest -q
```

One test by keyword — the swarm negotiation, say:

```bash
uv run --directory projects/ludo/stack-strands pytest -k table -q
```

And a full scripted game, free and offline, producing the same bytes as the committed [fixture](../../projects/ludo/games/scripted-strands-seed7.jsonl):

```bash
uv run --directory projects/ludo/stack-strands python -m ludo_strands.demo out.jsonl
```

## Check yourself

After the three docs, these should come without looking. Each answer is a link; a surprise marks the doc to reread.

1. One negotiation phase, three floor holdings, two handoffs. How many `llm_call` events — and why isn't it three? → [00](00-the-agent-loop.md)
2. Your metering hook needs this call's token count. Why is diffing the agent's accumulated totals wrong, and what is right? → [00](00-the-agent-loop.md)
3. The model names an illegal move and the harness knows it. What does `choose` return, and who emits the rejection? → [01](01-one-turn-through-the-harness.md)
4. Red is activated twice in one conversation. What does it remember of its first activation, and where did that design decision push memory writes? → [02](02-the-swarm-table.md)
5. A directed message's *content* is private. Name two things about it that are public anyway. → [02](02-the-swarm-table.md)

## Related

- [Stack README](../../projects/ludo/stack-strands/README.md) — module map and status
- [Harness contract](../../docs/projects/ludo/harness-contract.md) — the behaviour every stack must produce; this folder explains *one* way of producing it
- [ADR-0008](../../docs/decisions/adr-0008-framework-native-harness.md) — why the harness is built from framework parts
- [ADR-0009](../../docs/decisions/adr-0009-swarm-negotiation.md) — why the negotiation protocol fits the orchestrator, not the other way round
- [Capability matrix](../../docs/architecture/stack-comparison.md) — what building this taught us about Strands
