# RELAY on LangGraph

Four runner agents on checkpointer threads, one shared anchor model. Same race, same seed, same events as [the Strands stack](../stack-strands/README.md) — which is what makes the differences below meaningful rather than decorative.

## Run it

```bash
uv run --directory projects/relay/stack-langgraph pytest
```

```bash
uv run --directory projects/relay/stack-langgraph python -m relay_langgraph.demo out.jsonl
```

## Design

| Concern | How | Rating |
|---|---|---|
| Runner agents | `create_agent`, one per lane, no tools | **Native** |
| Conversation | Checkpointer thread per lane (`thread_id=color`) — the harness holds none of it | **Native** |
| Notebook | Framework `Store`, namespace `("notebook", color)`, `limit` footgun honoured | **Native** |
| Metering + budget | Callback handler propagated by the framework; `BudgetGate` middleware jumps past the model | **Native** |
| **Escalation to the anchor** | A bare `BaseChatModel` invocation with the meter attached | **Adapter** — see below |
| Guardrails | Harness gate on the note | **Manual** |
| Orchestration | None. There is nothing to orchestrate | n/a |

### No graph, and that is the finding

LUDO drew ADR-0009's negotiation table as a `StateGraph`, because there was a protocol to draw: private per-holder context, floor routing, a pass cap. RELAY has none of that. Runners never address each other, and escalation is a model swap the *engine* performs.

So the framework's headline primitive has nothing to do here, and this stack is four ordinary agent loops. Third game, and the lesson [ALIBI recorded](../../../docs/architecture/stack-comparison.md#finding-remove-the-protocol-and-the-orchestration-axis-vanishes) arrives again from a new direction: **which framework differences you meet is decided by your protocol.** RELAY's protocol asks for almost nothing, so almost nothing differs.

### `with_fallbacks` is not this

LangChain *does* ship a fallback primitive — `Runnable.with_fallbacks` — and it is the closest thing in any of the three frameworks to what RELAY needs. It still does not fit, and the mismatch is worth the paragraph.

`with_fallbacks` triggers on an **exception**: the primary model errored, so try the next one. RELAY's escalation is a *deliberate choice*, made while the primary model is working perfectly and has just decided it cannot do this stage. Routing that through an error handler would mean raising on purpose to select a model — a lie in the shape of a design pattern.

So the anchor is a second model invoked directly through `BaseChatModel`, with the meter's callback attached. **Adapter**, and the same verdict Strands reached by a different road: every framework here has a fallback for *failure*, and none has one for *judgement*.

## Cross-stack equality

[`tests/test_cross_stack.py`](tests/test_cross_stack.py) reads the Strands fixture and asserts this stack's engine events are identical to it — same stages attempted, same clears, same ticks, same standings. Only the agent-layer events may differ.

That test is the reason the comparison means anything. Two stacks that disagree about the race are not comparable at all, and a difference reported without it would be indistinguishable from a bug.

## Related

- [Harness contract](../../../docs/projects/relay/harness-contract.md) · [Game rules](../../../docs/projects/relay/game-rules.md)
- [Capability matrix](../../../docs/architecture/stack-comparison.md)
