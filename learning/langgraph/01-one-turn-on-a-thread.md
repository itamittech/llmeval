# One Turn on a Thread

The engine calls `choose`. In the Strands stack that became `agent(prompt)`; in Spring AI, a `ChatClient` call with an advisor. Here:

```python
state = self.players[ctx.color].invoke(
    {"messages": [HumanMessage(prompt)]},
    {"configurable": {"thread_id": ctx.color}, "callbacks": [self.meter]})
reply = state["messages"][-1].text
```

Three things ride that one call — the player, the memory, and the meter — and each is a different framework seam. This page takes them in turn.

## The player is `create_agent`, with two riders

[`players.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/players.py) builds each colour once:

```python
create_agent(
    model=model,
    tools=[],                      # decide/reflect are plain calls; the table has the tool
    system_prompt=system_prompt,
    middleware=[BudgetGate(meter), Compactor(...)],
    checkpointer=checkpointer,     # one saver, four thread ids (doc 00)
    store=store,                   # beliefs — the framework's own shelf
    name=color,
)
```

**Middleware is where hooks and advisors were.** Strands fired lifecycle events at you; Spring AI let you wrap calls you made; LangGraph's agent runs *your subclass methods* at named points inside its loop. `BudgetGate` is the whole idea in five lines — the same `jump_to` mechanism the framework's own `ModelCallLimitMiddleware` uses:

```python
@hook_config(can_jump_to=["end"])
def before_model(self, state, runtime):
    if self._meter.exhausted:
        return {"jump_to": "end"}      # the model call never happens
    return None
```

The harness still checks the ceiling *between* calls (and `choose` raises `BudgetExceeded` so the engine records a forfeit) — the gate is the backstop *inside* the framework's loop, where harness code isn't running. Same division of labour as Strands' cancellable hook, expressed as a return value instead of an event.

## Compaction: configured, subclassed for observation only

**Before you scroll:** Strands' summariser turned out to bypass its own hook system — the summary call was invisible to metering until the harness routed it through a full agent invocation. The matrix pre-registered the question for this stack. Look at the wiring below and predict: can this summariser dodge the meter?

```python
SummarizationMiddleware(
    model=model,                                  # the agent's OWN model — contract §5
    trigger=("tokens", max_context_tokens),       # the GAME's budget, not the provider's window
    keep=("messages", 4),
    token_counter=parity_token_counter(...),      # chars//4 — the same ruler as the other stacks
    summary_prompt=SUMMARY_PROMPT,
)
```

It cannot — **by construction**. The middleware summarises by *invoking the model normally*, and callbacks propagate to every model call under an invoke (next section), so the summary call lands in the meter like any other. Both pre-registered questions came back yes — budget-driven trigger, instrumented summariser — and that's the [finding](../../docs/architecture/stack-comparison.md#finding-langgraphs-summariser-answers-the-questions-strands-raised--native-on-both-counts).

What the framework doesn't do, the [`Compactor`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/players.py) subclass adds — *observation, not behaviour*: flip the meter to `purpose: "compact"` around the summary call, fold the summary into durable memory (the `Store`), emit `context_compacted`. Thirty lines, both at documented override points. One mechanic to respect: `keep=("messages", 4)` is a **target** — a safe-boundary rule picks the actual cutoff, and the pinned version will happily summarise a single opening message. The test pins the observed behaviour rather than the wished-for one.

## Metering is subscription

[`meter.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/meter.py) is a `BaseCallbackHandler` passed once per invoke. The framework propagates it to *every* model call underneath — the player's, the summariser's, every table node's — and `on_llm_end` reads `usage_metadata` off the reply message itself. Contrast all three stacks, because the progression is the lesson:

| | The seam | Failure mode designed out |
|---|---|---|
| Strands | hook fires per invocation | *had* a trap: totals update after the hook — per-call usage rides the message |
| Spring AI | usage on the `ChatResponse` you hold | none — but internal tool execution coarsens what "one call" means |
| LangGraph | callback propagated to every call | none — usage is per-message, and nothing runs below the callbacks |

Beliefs, meanwhile, go in the framework's `Store` — `("beliefs", color)` namespaces, written at reflect, rendered into `{{memory}}` byte-identically to the other stacks. The only dedicated belief-store primitive among the three frameworks, with one sharp edge worth repeating everywhere: **`Store.search` defaults to `limit=10`**. Forget the limit and an agent silently stops learning at ten beliefs.

## Where to look

| To see | Read | Run |
|---|---|---|
| Agent construction, both middleware | [`players.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/players.py) | `uv run --directory projects/ludo/stack-langgraph pytest -k compacts -q` |
| The budget backstop and the forfeit | [`meter.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/meter.py), `harness.choose` | `... pytest -k budget -q` |
| Beliefs on the Store | [`memory.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/memory.py) | `... pytest -k llm_call -q` |

> **The line to keep: extension points beat call sites.** Everything cross-cutting in this stack — budget, compaction, metering — lives where the framework promises to call it, not where the harness remembers to. The turn loop stays four lines because it carries nothing.

Next: [the drawn table](02-the-drawn-table.md).
