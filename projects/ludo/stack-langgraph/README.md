# LUDO — LangGraph Stack

The second Python harness: [harness-contract.md](../../../docs/projects/ludo/harness-contract.md) on [LangGraph](https://www.langchain.com/langgraph), over the [same engine the Strands stack uses](../engine-python/README.md) — which makes these two the cleanest pair in the repo: identical language, identical engine, identical prompts; **the framework is the only thing that moved**.

> **🚧 Feature-complete against scripted models.** Turn loop, the negotiation table drawn as a graph, conversation threads on the checkpointer, beliefs in the Store, compaction on the framework's summarisation middleware, guardrails, budgets, events, opt-in session persistence — the [fixture](../games/scripted-langgraph-seed7.jsonl) is committed and rendered by the UI **with zero UI changes** (ADR-0007's rule, proven against a fourth emitter). Only live provider calls remain, blocked on model IDs. See [Status](#status).

## Build and test

Own venv, own lockfile — never shared with the Strands stack ([environment strategy](../../../docs/architecture/environment-strategy.md)):

```bash
uv sync --directory projects/ludo/stack-langgraph
```

```bash
uv run --directory projects/ludo/stack-langgraph pytest
```

A full scripted game, offline and free — regenerates the committed fixture byte-identically:

```bash
uv run --directory projects/ludo/stack-langgraph python -m ludo_langgraph.demo out.jsonl
```

## Design

The reference diagrams for this layer — the object graph, one `choose` as calls, one table round as graph steps — are [class-design §11](../../../docs/projects/ludo/class-design.md#11-the-harness-layer-third-take-the-same-turn-on-langgraph). What follows states the decisions those diagrams draw.

**The table is a drawn graph, because that is what LangGraph *is*.** Strands handed negotiation to a prebuilt `Swarm`; Spring AI wrote a while loop; LangGraph's core primitive is the **StateGraph**, so [`table.py`](src/ludo_langgraph/table.py) draws ADR-0009's floor-passing protocol literally as nodes and edges — `brief` seats the next holder with a private context, `speak` makes one model call, the framework's own `ToolNode` executes `pass_floor`, and conditional edges route the floor until it lapses or the cap closes the table. Orchestration is **Native** here in the deepest sense available: the protocol is not code *around* the framework, it is a value *of* the framework's central type.

**`langgraph-swarm` was evaluated and rejected on evidence.** The obvious reach — the framework family's own swarm package, the counterpart of the primitive Strands used — turns out to be ~200 lines over `StateGraph` whose state is one shared `messages` channel: every activation reads the full history, every directed message, every other player's words. Built for cooperating specialists serving one conversation; LUDO's players are adversaries whose directed messages are private **by rule** (the contract's MUST NOT). The package does not ship in this venv; the [capability matrix](../../../docs/architecture/stack-comparison.md) records the verdict with the source it rests on. The mirror finding to Strands' — whose `Swarm` *could* carry the protocol after ADR-0009 redesigned it — and proof that "the framework has a swarm package" and "the swarm package fits" are different claims.

**Compaction is Native — and answers two questions the other stacks left open.** [`players.py`](src/ludo_langgraph/players.py) wires the framework's `SummarizationMiddleware` into each agent with the *game's* budget as its trigger and the parity token counter as its ruler; a small observing subclass (`Compactor`) captures the summary for `context_compacted` and folds it into durable memory. The two questions the matrix pre-registered when Strands' summariser bypassed its own hooks: does LangGraph's summarisation route through the same instrumentation as ordinary calls (**yes** — the middleware invokes the model properly, so the callback meter sees it), and can its trigger be driven by an application budget rather than the provider's window (**yes** — a constructor argument). The cleanest §5 story of the three.

**Conversations live in the checkpointer; beliefs live in the Store; code holds neither.** Decide and reflect share one framework-held thread per agent (`thread_id=color`) — invoking the same agent on the same thread *is* the persistent conversation, and the attempt-2 retry seeing its own rejected answer is checkpointer semantics, not harness code. Beliefs go in [`memory.py`](src/ludo_langgraph/memory.py) onto LangGraph's `Store` — the **only** framework of the three with a dedicated belief-store primitive (Strands repurposed `AgentState`; Spring AI had nothing and hand-rolled). One sharp edge, recorded: `Store.search` defaults to `limit=10`, which silently caps an unwary agent at ten beliefs.

**Session persistence is the shortest of the three answers: swap the stores, done.** [`session.py`](src/ludo_langgraph/session.py) replaces the in-memory checkpointer and Store with their sqlite twins over one session file. Both halves of agent state already live in framework stores whose write moments cover the game loop — so **no save call exists in this stack**, and a test pins that claim literally (`assert not hasattr(harness, "persist")`). Strands needed a final explicit sync; Spring AI saved beliefs by hand; LangGraph has nothing left outside the framework to save.

**Metering rides the callback system.** One [`Meter`](src/ludo_langgraph/meter.py) handler is passed per invocation and propagated by the framework to every model call underneath — the table's, the summariser's, all of them — reading usage off `AIMessage.usage_metadata`. The budget ceiling backstop is a five-line middleware using the framework's own `jump_to` mechanism. And the [scripted model](src/ludo_langgraph/scripted.py) is a `BaseChatModel` subclass (harness-contract §8) that deliberately does **not** cycle like the shipped fakes — a script running out should fail loudly, not silently replay.

**Live settings are pinned before live calls exist.** [`langgraph_client.py`](src/ludo_langgraph/langgraph_client.py) builds the ADR-0005 control seat's `ChatAnthropic` from `models.yaml` and a test reads every setting back. One genuine difference worth the matrix line: the Claude 5 depth controls are **first-class here** — `reasoning_effort` is a typed field where Strands needed a raw passthrough and Spring AI's options surface had no knob at all. Bedrock seats need `langchain-aws`, which arrives with live play.

## Status

| Piece | State |
|---|---|
| Prompt loading, validation, digest (parity with the other stacks) | ✅ [`prompts.py`](src/ludo_langgraph/prompts.py) |
| `models.yaml` profiles, budgets, inference settings, seat rotation | ✅ [`config.py`](src/ludo_langgraph/config.py) |
| Scripted model through `BaseChatModel`, tool calls + usage attached | ✅ [`scripted.py`](src/ludo_langgraph/scripted.py) |
| Turn loop: negotiate → decide (with retry) → reflect | ✅ [`harness.py`](src/ludo_langgraph/harness.py) |
| Negotiation: ADR-0009 drawn as a `StateGraph`, `pass_floor` via `ToolNode` | ✅ **Native** — [`table.py`](src/ludo_langgraph/table.py); `langgraph-swarm` rejected on evidence (see matrix) |
| Content guardrails — lenient by design, inside the tool | ✅ [`guardrails.py`](src/ludo_langgraph/guardrails.py) |
| Conversation memory (checkpointer thread per agent) | ✅ Native |
| Agent beliefs (framework `Store`, namespaced per agent) | ✅ **Native** — the only stack of the three with a dedicated primitive |
| Context compaction (`SummarizationMiddleware`, game-budget trigger) | ✅ **Native** — [`players.py`](src/ludo_langgraph/players.py) |
| Token accounting + forfeit-out budget ceiling | ✅ callbacks + `jump_to` middleware — [`meter.py`](src/ludo_langgraph/meter.py) |
| Agent events, one sequence with engine events | ✅ schema-validated [fixture](../games/scripted-langgraph-seed7.jsonl) |
| Session persistence (opt-in) | ✅ **Native ×2** — [`session.py`](src/ludo_langgraph/session.py): sqlite checkpointer + sqlite Store, no save call exists |
| Live provider settings pinned + read back (Anthropic control seat) | ✅ [`langgraph_client.py`](src/ludo_langgraph/langgraph_client.py) |
| Live calls (langchain-aws for Bedrock; Nova, DeepSeek) | ⬜ blocked on model IDs |

Everything above runs offline against the scripted model; nothing costs anything. `learning/langgraph` follows once the code stops moving, per the repo's rule against documenting half-built code.
