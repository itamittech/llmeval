# The Drawn Table

Every stack must produce ADR-0009's negotiation: directed messages, public table notes, a floor that passes until it lapses or the cap closes it. Strands handed that to a prebuilt `Swarm`. Spring AI wrote a while-loop. This stack **draws it**:

```
START → brief → speak ──tool call──→ tools ──delivered, under cap──→ brief (next holder)
                  │                    │            └──cap reached──→ END
                  │                    └──blocked: the model reads why──→ speak
                  └──plain text: the floor lapses──→ END
```

That sketch is not documentation of [`table.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/table.py) — it *is* `table.py`, node for node. In LangGraph the protocol becomes a value of the framework's central type, which is what "orchestration: Native" means in this stack's [matrix column](../../docs/architecture/stack-comparison.md).

## But the swarm package existed. Why not use it?

**Before you scroll:** `langgraph-swarm` is the family's own multi-agent package. Its agents hand off to each other with generated `transfer_to_<agent>` tools — a near-perfect match for floor passes. The whole package is ~200 lines. Predict what disqualified it before reading on.

One line of its source:

```python
class SwarmState(MessagesState):        # ONE shared messages channel
```

Every agent in a `langgraph-swarm` reads the *full shared history* on activation — every directed message, every other player's words. That is the architecture (it exists for cooperating specialists serving one user's conversation), not a setting, and it is exactly what the harness contract's MUST NOT forbids: one agent must never see another's received directed messages. Where the Strands finding led ADR-0009 to *redesign the protocol* to fit the orchestrator, that door is closed — two shipped stacks already share the protocol — so the fix was to drop one layer, to the primitive the package itself is built from. The package does not ship in this venv; the [finding](../../docs/architecture/stack-comparison.md#finding-langgraph-swarm-cannot-carry-ludos-negotiation-protocol--the-primitive-underneath-can) records the verdict. The transferable lesson: **"the framework has a swarm package" and "the swarm package fits your protocol" are different claims, and a state schema decides the second one.**

## Privacy is a wipe

How does a shared-state machine keep four adversaries out of each other's heads? The `brief` node starts every floor holding by *erasing the channel* and seeding only the holder's private context:

```python
return {
    "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), HumanMessage(context)],
    "delivered": False,
}
```

`RemoveMessage(REMOVE_ALL_MESSAGES)` is the framework's sanctioned rewrite — the *same primitive its own summarisation middleware uses* to replace history. Nothing a speaker said survives into the next holder's view except the one message `pass_floor` delivered.

## The pass is a `Command`; the gate is the tool body

`speak` makes one model call with `pass_floor` bound. If the model calls it, the framework's `ToolNode` — a *visible graph node*, the exact inverse of Spring AI's hidden internal execution — runs our function. Inside: the same checklist as the Spring AI stack (cap → addressee → length → [guardrails](../../projects/ludo/stack-langgraph/src/ludo_langgraph/guardrails.py), lenient by design), and on delivery the tool returns a `Command`:

```python
return Command(update={
    "messages": [ToolMessage(f"delivered to {to}", tool_call_id=tool_call_id)],
    "delivered": True, "holder": to, "passes": state["passes"] + 1, ...
})
```

— the same mechanism the rejected swarm package's handoffs use. A blocked message returns a plain string instead; state unchanged, and the edge routes *back to the speaker*, who reads the reason and may rephrase or give up. A delivered pass costs one metered invocation, a blocked attempt two, and every one is in the transcript. The runaway bound for a live model stuck retrying is the framework's own `recursion_limit` — no hand-rolled counter.

## Persistence: swap the stores, and there is nothing left to save

The two state holders doc 00 and 01 introduced — checkpointer for conversations, `Store` for beliefs — both have sqlite twins in one extra package. [`session.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/session.py) is the entire feature: open one file, construct `SqliteSaver` + `SqliteStore` over it, done. The checkpointer already writes every step; `put` already writes immediately; so **no save call exists in this stack**, and [`test_session.py`](../../projects/ludo/stack-langgraph/tests/test_session.py) pins the claim literally — `assert not hasattr(harness, "persist")`. Set beside the other two stacks it completes a three-way answer worth memorising whole: Strands persists everything *on its own schedule* (flush or lose the tail); Spring AI persists the conversation continuously *but beliefs by hand*; LangGraph has nothing outside the framework to save. One real seam, recorded in the finding because it cost an hour: the two components disagree about sqlite transactions when sharing a connection — autocommit reconciles them.

## Where to look

| To see | Read | Run |
|---|---|---|
| The graph, drawn | `table.py` `_draw`, `_brief`, `_speak` | `uv run --directory projects/ludo/stack-langgraph pytest -k table -q` |
| An injection bouncing, the speaker rephrasing | `table.py` `_deliver` | `... pytest -k injection -q` |
| No-save-call persistence | [`session.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/session.py) | `... pytest -k session -q` |

> **The line to keep: when the prebuilt doesn't fit, the primitive usually does.** The swarm package and this table are made of the same three parts — `StateGraph`, `Command`, `ToolNode`. What changed was one state schema. Judge frameworks by their primitives; judge prebuilts by their assumptions.

That completes the LangGraph set. The assembled machine — object graph, both call traces, the drawn graph, and the three-grains table — is [class-design §11](../../docs/projects/ludo/class-design.md#11-the-harness-layer-third-take-the-same-turn-on-langgraph).
