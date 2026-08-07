# 01 — Fallback is not escalation

## The problem, before the solution

You need your agent to call a different, larger model for one request, then go back to the small one. Every agent framework advertises support for this. Search their docs for "fallback" and you get a first-class primitive in each.

None of them does what you need, and the reason is worth more than the workaround.

## Before you scroll

Look at LangChain's `Runnable.with_fallbacks`, Spring's `RetryTemplate`, and Strands' model configuration. **What triggers each one?**

## What they actually do

| Framework | The primitive | Fires when |
|---|---|---|
| LangChain | `Runnable.with_fallbacks([...])` | the primary raises an **exception** |
| Spring AI | `RetryTemplate` / `spring-retry` | the call **threw** |
| Strands | — no fallback primitive at all | n/a |

Every one of them is an **error handler**. They exist because provider APIs rate-limit, time out, and 500, and a production system should survive that.

RELAY's escalation is not that. The small model is working perfectly. It has read the stage, consulted its own record, and *judged* that this one is beyond it. Nothing failed. There is no exception to catch, and manufacturing one — raising on purpose so the fallback chain routes the call — would be a lie in the shape of a design pattern.

**The handle: every framework has a fallback for failure; none has one for judgement.**

## So what do the stacks do?

All three rate **Adapter** in [the matrix](../../docs/architecture/stack-comparison.md#relay-the-third-act), and the code is short in each.

**Strands** — a second `Agent` over the anchor model, messages wiped before each call:

```python
def ask_anchor(anchor: Agent, prompt: str) -> str:
    anchor.messages = []  # statelessness the framework will not enforce for us
    return str(anchor(prompt)).strip()
```

**LangGraph** — the `BaseChatModel` seam, invoked once, with the meter attached:

```python
reply = model.invoke([HumanMessage(content=prompt)], config={"callbacks": [meter]})
```

**Spring AI** — a second `ChatClient`, built without the memory advisor the runners get:

```java
this.anchorClient = ChatClient.builder(anchorModel).build();
```

Three frameworks, three lines, one shape. Under [ADR-0008](../../docs/decisions/adr-0008-framework-native-harness.md) that is a legitimate Manual-ish rating rather than a rule broken, because the frameworks genuinely offer nothing for a *chosen* model swap.

## The trap, which is the actual lesson

There is a shorter way to call a second model in every one of these frameworks: reach past the agent and call the model object directly.

It works. It also skips the agent loop — and with it the lifecycle hooks, the callback handler, the advisor chain. **The anchor's tokens vanish from the meter**, in the one project whose entire purpose is measuring what the anchor costs.

That is the same shape as [the Strands summariser trap](../../docs/architecture/stack-comparison.md#finding-strands-summariser-bypasses-strands-own-hook-system) LUDO recorded, and it generalises past both:

> **The shortcut past the framework is the shortcut past the instrumentation.**

Frameworks earn their keep at the seams — metering, budgets, tracing all hang off the call path. Anything that bypasses the call path bypasses those too, silently, and the resulting transcript looks complete.

## What a chooser should take from this

"Does it support model fallback?" is the wrong question to ask a framework. All three say yes; all three mean *when the call fails*.

The right question is: **does your application choose between models on purpose?** If it routes by cost, by confidence, by request class, or by a policy of any kind — that is your code, in all three frameworks, and you should budget for writing it rather than expecting to configure it.

## Check yourself

1. Why is raising an exception to trigger `with_fallbacks` a bad idea, beyond being ugly?
2. The Strands anchor wipes `anchor.messages` before every call. What breaks if it doesn't?
3. You add a third model tier. Which of the three stacks needs the most new code, and why is the answer "none of them, particularly"?
4. Name one thing you would lose by calling `model.stream()` directly, other than tokens.

## Next

[02 — the seal](02-the-seal.md): how to hide a fact from an agent when your own code is holding it.
