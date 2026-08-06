# The Tool-Form Table

Strands got a `Swarm`. LangGraph got a graph. Spring AI has **no multi-agent anything** — no orchestrator, no handoff, no concept of one agent addressing another. Yet the [fixture](../../projects/ludo/games/scripted-springai-seed7.jsonl) shows the same negotiation as the other two stacks: red proposes, a public note lands, blue answers, red closes. This page is how a framework with no table still seats one — and where the honest line runs between *our* code and *its*.

## Manual loop, Native action

The split is exact, and [ADR-0008](../../docs/decisions/adr-0008-framework-native-harness.md) is why it must be stated rather than blurred:

**The loop is ours.** [`Harness.runTable`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Harness.java) is a while-loop over floor holders: render the holder's private context (briefing + shared task + the one message addressed to them), call their client, check whether the floor moved, repeat until it lapses or the cap closes the table. A legitimate **Manual** in the [matrix](../../docs/architecture/stack-comparison.md) — the framework offers nothing here.

**The pass is the framework's.** The floor moves only through `pass_floor` — a real `FunctionToolCallback` whose schema Spring AI generates from a Java record and describes to the model itself:

```java
public record PassFloor(String to, String message, String note) {}

FunctionToolCallback.builder("pass_floor", execute)
        .description("Send one message to one named player ... This is the only way to speak; "
                + "reply without calling it to end the conversation.")
        .inputType(PassFloor.class)
        .build();
```

The model's tool call is parsed by the framework and executed by `ToolCallingManager` — inside the model call, as doc 00 explained. ADR-0009's parity boundary holds: what reaches the model about the tool is framework-authored text, and the harness never parses a spoken reply.

## The gate is the tool's body

**Before you scroll:** Strands blocked injections with a cancellable `BeforeToolCallEvent` — a hook that stops the tool before it runs. Spring AI has no such interception point. Where can the guardrail go?

The only place left — and it turns out to read *better*: inside `pass_floor` itself. The tool body is a checklist, in order: floor cap → addressee valid → length cap (budget enforcement, silently) → [`Guardrails.check`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Guardrails.java) on message and note (the same three lenient rules as both Python stacks). Only a message that clears everything is delivered — `message_sent`, inbox fan-out, floor state advanced. A blocked one returns its reason *as the tool result*:

```java
return "message not delivered: " + violation.reason();
```

That string is what the model reads next — the truth about delivery travelling the same channel as delivery itself. An injection costs the attempt, never the floor, and `guardrail_triggered` records it. In-game cunning — lies, bluffs, betrayal — passes untouched, and a test enumerates the phrases to prove it.

One design detail worth stealing: the tool is built fresh per table run and **closes over a `TableState`** — holder, pass count, delivered flag. The framework executes the action; the state the action manipulates never leaves the harness.

## What this taught the comparison

Line the three stacks up on this one phase and every rating appears:

| | Strands | LangGraph | Spring AI |
|---|---|---|---|
| The loop over holders | `Swarm` (Native) | the graph's edges (Native) | `runTable` (**Manual**) |
| The pass itself | handoff tool | `pass_floor` via `ToolNode` | `pass_floor` via `ToolCallingManager` |
| The guardrail seam | cancellable hook | tool body | tool body |
| Tool invocations visible? | every one | every one — the loop is drawn | **hidden inside the call** |

Same protocol, same events, same story in three fixtures — which is precisely what makes the differences above findings instead of vibes.

## Where to look

| To see | Read | Run |
|---|---|---|
| The loop and the tool | `Harness.runTable` / `passFloorTool` | `./mvnw -B test -Dtest=HarnessTest#theTableRunsOnTheFrameworkTool` |
| An injection bouncing inside the tool | same file | `./mvnw -B test -Dtest=HarnessTest#anInjectionIsBlockedInsideTheTool` |
| Cunning passing untouched | [`Guardrails.java`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Guardrails.java) | `./mvnw -B test -Dtest=HarnessTest#inGameCunningPasses` |

> **The line to keep: when the framework has no seam, the tool body is the seam.** Everything that must happen between "the model spoke" and "the world changed" — caps, guardrails, delivery, events — lives inside the function the model calls, and the tool's return value is the model's only truth about what happened.

That completes the Spring AI set. The assembled machine — object graph, both call traces, and the three-stack grains table — is [class-design §10](../../docs/projects/ludo/class-design.md#10-the-harness-layer-second-take-the-same-turn-on-spring-ai) and [§11.4](../../docs/projects/ludo/class-design.md#114-who-calls-whom--and-the-same-turn-on-three-grains).
