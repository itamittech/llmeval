# The Flattest Seam of the Three

Here is the confusion this page exists to clear up. In the [fixture](../../projects/ludo/games/scripted-springai-seed7.jsonl)'s negotiation, three messages are delivered by a real framework tool — yet the transcript shows only **three** `llm_call` events for the whole table, and a tool round-trip is supposed to cost *two* model invocations. Where did the extra invocations go?

They happened. You just can't see them from where the harness stands. That fact is the most Spring-AI-shaped thing in this stack, and it decides how metering, scripting, and live play all work.

## One call, start to finish

```java
ChatResponse response = clients.get(color).prompt()
        .system(systemPrompt(color))
        .user(prompt)
        .call()
        .chatResponse();
```

What runs, in order:

1. `ChatClient` assembles a `Prompt` — system + user messages, plus any options.
2. The **advisor chain** runs its "before" side (doc 01 — this is where conversation memory loads).
3. The framework calls `ChatModel.call(prompt)` — the provider seam, one synchronous method.
4. Advisors run their "after" side (memory saves the exchange).
5. You hold a `ChatResponse`: the reply, **with usage attached to the object itself**.

Compare the Strands loop you may have just read about: no stream events, no lifecycle hooks, no async generator. Ask, get answer, read `response.getMetadata().getUsage()` off what you're already holding. That is why this stack's metering has no trap to fall into — there is no hook to fire at the wrong moment, because there is no hook.

## Faking the provider took forty lines

**Before you scroll:** the harness contract [§8](../../docs/projects/ludo/harness-contract.md#8-proving-a-stack-conforms) demands the fake sit at the framework's *own* extension point. From the call above — what is the minimum a fake must implement?

One method. [`ScriptedChatModel`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/ScriptedChatModel.java) implements `ChatModel.call(Prompt)` and pops the next committed reply. The Strands fake had to choreograph five stream-event shapes per reply; the LangGraph one had to implement `bind_tools` because the base class refuses to. This one returns an object. The [capability matrix](../../docs/architecture/stack-comparison.md) credits Spring AI for exactly this: for a framework aimed at enterprise Java, the flattest possible model seam is the right instinct.

## The hidden loop

Now the opening puzzle. When the model's reply is a *tool call*, the provider binding does not hand it to you — by default it runs the model↔tool loop **inside** `ChatModel.call`:

```java
ChatResponse response = respond(prompt, 0, 0);                  // invocation 1: a tool call
if (response.hasToolCalls()
        && ToolCallingChatOptions.isInternalToolExecutionEnabled(prompt.getOptions())) {
    ToolExecutionResult result = toolCallingManager.executeToolCalls(prompt, response);
    // invocation 2: the model reads the tool result and answers
    return respond(new Prompt(result.conversationHistory(), prompt.getOptions()), ...);
}
```

That snippet is from the *scripted* model — which implements internal tool execution the way the live bindings do, precisely so the harness cannot tell the difference. The consequences stack up:

- The caller sees **one** `ChatResponse` for two or more invocations, so one `llm_call` covers a whole tool round-trip. Usage is aggregated, so nothing goes unmetered — but per-invocation granularity is gone. Three floor holdings, three visible calls; the tool executions are inside them.
- No seam available to the harness observes the middle. An advisor wraps the whole call; the loop is below it.
- The escape hatch is an option, not a redesign: `setInternalToolExecutionEnabled(false)` hands the tool call back to the caller — the plan for live play, where per-invocation metering matters.

The full write-up, and what it means for anyone doing cost accounting, is a [matrix finding](../../docs/architecture/stack-comparison.md#finding-spring-ais-internal-tool-execution-hides-model-invocations-from-the-caller). LangGraph turned out to be its exact inverse: its tool executor is a visible graph node.

## Where to look

| To see | Read | Run |
|---|---|---|
| The whole seam, tools included | [`ScriptedChatModel.java`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/ScriptedChatModel.java) | `./mvnw -B test -Dtest=HarnessTest#theTableRunsOnTheFrameworkTool` |
| Usage read off the response | [`Harness.java`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Harness.java) `meter` | `./mvnw -B test -Dtest=HarnessTest#everyModelCallEmitsOneLlmCall` |
| The typed options that won't let a typo compile | [`LiveModels.java`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/LiveModels.java) | `./mvnw -B test -Dtest=HarnessTest#liveAnthropicOptionsPinTheSharedSettings` |

> **The line to keep: in Spring AI, "one call" is an interface promise, not an invocation count.** The framework will happily make three invocations behind one `ChatResponse`. When a token number looks too coarse in this stack, it isn't broken metering — it's the definition.

Next: [a conversation the framework holds](01-one-turn-and-a-conversation.md).
