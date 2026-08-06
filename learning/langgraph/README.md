# Learning the LangGraph Harness

The [engine walkthrough](../python/01-walkthrough-game.md) ends where the engine hands a turn to a `Decider` and waits. This folder explains the third answer to that call — the [LangGraph stack](../../projects/ludo/stack-langgraph/), where the answer is not an object you call or a loop that calls you, but **a graph you draw and hand to a runtime**. It is the strangest of the three grains coming from Java or classic Python, and the most worth internalising: half the current agent ecosystem thinks this way.

Everything here is checked against **langgraph 1.2.10 / langchain 1.3.14 / langchain-core 1.5.3**, the exact versions pinned in the stack's lockfile. Where a claim depends on framework internals, it came from reading that version's installed source.

## What LangGraph is, in one paragraph

LangGraph runs *your* control flow over *its* state. You declare a state schema (a typed dict with per-field merge rules), nodes (functions from state to state-updates), and edges (including conditional ones); `compile()` turns the drawing into a runnable. Then the framework owns everything at runtime: it routes, it merges updates, it **checkpoints state after every step** under a caller-chosen `thread_id` — so "a conversation" is not an object anywhere, it is what the checkpointer replays when you invoke the same thread again. Agents, tools, memory, persistence are all libraries over that one idea.

## Read in this order

| Doc | Question it answers |
|---|---|
| [00 — the graph is the program](00-the-graph-is-the-program.md) | What `StateGraph` + `invoke` actually do, why the harness holds no conversation, and what the scripted model had to implement that the shipped fakes don't |
| [01 — one turn on a thread](01-one-turn-on-a-thread.md) | How decide/retry/reflect ride `create_agent` + `thread_id`, how middleware gates the budget and compacts the context, and why the summariser here *cannot* dodge metering |
| [02 — the drawn table](02-the-drawn-table.md) | ADR-0009 as nodes and edges: the privacy wipe, the pass as a `Command`, why the family's own swarm package was rejected on evidence — and the shortest persistence story in the repo |

The reference diagrams — object graph, the turn trace, the drawn table graph, the three-grains table — are [class-design §11](../../docs/projects/ludo/class-design.md#11-the-harness-layer-third-take-the-same-turn-on-langgraph).

## The LangGraph / LangChain classes this stack touches

| Class | What it is | Who calls whom | Where in this stack |
|---|---|---|---|
| `StateGraph` | The core primitive: schema + nodes + edges → compiled runnable | We draw; the framework runs | the table — [`table.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/table.py) |
| `Command` | A state-update (and optionally a route) returned from inside the graph | Our tool returns one; framework applies it | `pass_floor` |
| `ToolNode` / `tools_condition` | The framework's tool executor as a *visible graph node*, and the standard edge that routes to it | Framework executes **our** tool | `table.py` |
| `create_agent` | The prebuilt agent: model + tools + middleware + checkpointer, compiled | We build four, invoke per thread | [`players.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/players.py) |
| `AgentMiddleware` | The extension seam inside the agent loop (`before_model`, `jump_to`) | Framework calls **us** | `BudgetGate` |
| `SummarizationMiddleware` | Shipped compaction: trigger, keep, token counter, summary prompt — all constructor args | Framework fires it inside invocations | subclassed as `Compactor` |
| checkpointer (`InMemorySaver` / `SqliteSaver`) | Saves graph state per step, keyed by `thread_id`; invoking a thread resumes it | Framework calls it around every step | conversations — [`harness.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/harness.py), [`session.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/session.py) |
| `Store` (`InMemoryStore` / `SqliteStore`) | Namespaced cross-thread key-value memory — the only dedicated belief store among the three frameworks | We call `put`/`search` (mind `limit=10`!) | beliefs — [`memory.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/memory.py) |
| `BaseChatModel` | The provider seam: implement `_generate`, and `bind_tools` if you mean it | Framework calls it | [`scripted.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/scripted.py); live options in [`langgraph_client.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/langgraph_client.py) |
| `BaseCallbackHandler` | The observation seam: propagated to every call under an invoke | Framework calls **us**, however deep | metering — [`meter.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/meter.py) |
| `RemoveMessage(REMOVE_ALL_MESSAGES)` | The sanctioned way to rewrite a messages channel | We return it from nodes/middleware | the table's privacy wipe; the summariser's rewrite |

## Running things

Same rule as the other framework folders: **the stack's tests are the examples**, in the stack's own venv (never shared with Strands — [environment strategy](../../docs/architecture/environment-strategy.md)):

```bash
uv run --directory projects/ludo/stack-langgraph pytest -q
```

One test by keyword — the drawn table, say:

```bash
uv run --directory projects/ludo/stack-langgraph pytest -k table -q
```

And a full scripted game, free and offline, byte-identical to the committed [fixture](../../projects/ludo/games/scripted-langgraph-seed7.jsonl):

```bash
uv run --directory projects/ludo/stack-langgraph python -m ludo_langgraph.demo out.jsonl
```

## Check yourself

1. `harness.py` has no field holding red's conversation, yet the retry sees red's rejected answer. Reconcile. → [00](00-the-graph-is-the-program.md), [01](01-one-turn-on-a-thread.md)
2. The shipped fake chat model was rejected for the scripted seam on two grounds. Name both. → [00](00-the-graph-is-the-program.md)
3. Strands' summariser bypassed its own hooks. Why can't this stack's summariser dodge the meter, *by construction*? → [01](01-one-turn-on-a-thread.md)
4. `langgraph-swarm` has handoff tools that map beautifully onto floor passes. What single line of its source disqualified the whole package? → [02](02-the-drawn-table.md)
5. This stack has no `persist()` method, and a test asserts that. What two framework facts make the method unnecessary? → [02](02-the-drawn-table.md)

## Related

- [Stack README](../../projects/ludo/stack-langgraph/README.md) — design decisions and status
- [Harness contract](../../docs/projects/ludo/harness-contract.md) — the behaviour every stack must produce
- [ADR-0008](../../docs/decisions/adr-0008-framework-native-harness.md) / [ADR-0009](../../docs/decisions/adr-0009-swarm-negotiation.md) — why native primitives, and why the table protocol is shaped as it is
- [Capability matrix](../../docs/architecture/stack-comparison.md) — what building this taught us about LangGraph
