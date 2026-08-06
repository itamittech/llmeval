# Learning the Spring AI Harness

The [engine walkthrough](../python/01-walkthrough-game.md) ends where the engine hands a turn to a `Decider` and waits. This folder explains the *Java* answer to that call — the [Spring AI stack](../../projects/ludo/stack-springai/), where the same four agents run on `ChatClient`, `ChatMemory`, and a real framework tool. If you read [learning/strands](../strands/) first, watch what changes when the framework stops calling you and starts being called.

Everything here is checked against **Spring AI 1.1.2**, the exact version pinned in the stack's pom. Where a claim depends on framework internals, it came from reading that version's resolved jars (`javap`, the shipped SQL, the module poms), not its docs.

## What Spring AI is, in one paragraph

Spring AI is a toolkit, not a loop: it hands you objects and you call them. A `ChatModel` turns a `Prompt` into a `ChatResponse` (that interface *is* the provider seam); a `ChatClient` wraps one with a fluent API and an **advisor** chain that can rewrite requests and reactions around every call — conversation memory is just an advisor; tools are callbacks the model may name and the framework will execute, *inside* the call by default. There is no agent loop to decorate and no graph to draw: whatever loop your application needs — ours is a floor-passing table — you write, and the framework supplies the pieces it runs through.

## Read in this order

| Doc | Question it answers |
|---|---|
| [00 — the flattest seam](00-the-chat-client-seam.md) | What happens inside one `ChatClient` call — and why faking this provider took forty lines when Strands' took two hundred |
| [01 — a conversation the framework holds](01-one-turn-and-a-conversation.md) | How decide/retry/reflect share one `ChatMemory` conversation, why compaction is hand-rolled here, and which half of persistence came free |
| [02 — the tool-form table](02-the-tool-form-table.md) | How ADR-0009's negotiation runs when there is no orchestrator: a Manual loop around a Native tool, with the guardrail gate inside it |

The reference diagrams — object graph, both call traces, the grains tables — are [class-design §10](../../docs/projects/ludo/class-design.md#10-the-harness-layer-second-take-the-same-turn-on-spring-ai).

## The Spring AI classes this stack touches

| Spring AI class | What it is | Who calls whom | Where in this stack |
|---|---|---|---|
| `ChatModel` | The provider seam: `call(Prompt) → ChatResponse` | We call (via `ChatClient`); the scripted model implements it | [`ScriptedChatModel.java`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/ScriptedChatModel.java) |
| `ChatClient` | Fluent wrapper: `.prompt().system().user().advisors().call()` | We call — every model interaction in the harness | [`Harness.java`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Harness.java) |
| `MessageChatMemoryAdvisor` | The interception seam: loads history before a call, saves the exchange after | Framework runs it around calls **we** make | wired in `Harness`, one conversation per colour |
| `ChatMemory` / `MessageWindowChatMemory` | Conversation storage behind the advisor; window = silent truncation | We built it; the advisor calls it | `Harness` (window pinned far above the game budget) |
| `ChatMemoryRepository` / `JdbcChatMemoryRepository` | The persistence seam *behind* the memory; JDBC backend + 8 SQL dialects | The memory calls it on every read/write | [`Session.java`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Session.java), over embedded H2 |
| `FunctionToolCallback` | A Java function wrapped as a model-callable tool, schema generated from a record | We build it; the **framework executes it** | `pass_floor` in `Harness.passFloorTool` |
| `ToolCallingManager` | Runs the model↔tool loop inside `ChatModel.call` | Framework-internal — the hidden loop of doc 00 | invoked by `ScriptedChatModel`, exactly like live bindings |
| `ToolCallingChatOptions` | Per-call options; `internalToolExecutionEnabled` is the escape hatch | We will set it `false` for live play | the metering finding |
| `AnthropicChatOptions` | The control seat's pinned settings — a typed builder, so a typo won't compile | We build, test reads back | [`LiveModels.java`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/LiveModels.java) |
| `Usage` (on `ChatResponse`) | Token counts attached to the response object itself | We read, synchronously — no hook, no trap | `Harness.meter` |

## Running things

Same rule as [learning/strands](../strands/README.md#running-things): no dependency-free examples are possible for a framework, so **the stack's tests are the examples**. Build the engine into the local repository once, then:

```bash
cd projects/ludo/engine-java && ./mvnw -q -B install -DskipTests
```

```bash
cd projects/ludo/stack-springai && ./mvnw -B test
```

One test by name — the tool-form table, say:

```bash
cd projects/ludo/stack-springai && ./mvnw -B test -Dtest=HarnessTest#theTableRunsOnTheFrameworkTool
```

And a full scripted game, free and offline, byte-identical to the committed [fixture](../../projects/ludo/games/scripted-springai-seed7.jsonl):

```bash
cd projects/ludo/stack-springai && ./mvnw -q -B exec:java -Dexec.args="../games/scripted-springai-seed7.jsonl"
```

## Check yourself

1. One floor pass = two model invocations. How many `ChatResponse` objects does the caller see, and what does that do to `llm_call`? → [00](00-the-chat-client-seam.md)
2. The harness never prepends conversation history to a prompt. Who does, and keyed by what? → [01](01-one-turn-and-a-conversation.md)
3. Spring AI *has* a conversation-management strategy. Why does contract §5 forbid using it as compaction? → [01](01-one-turn-and-a-conversation.md)
4. A blocked injection never becomes `message_sent` — but the attacker learns why it bounced. Where does that text travel? → [02](02-the-tool-form-table.md)
5. After a crash with no save call ever made, which half of agent state survived, and why exactly that half? → [01](01-one-turn-and-a-conversation.md)

## Related

- [Stack README](../../projects/ludo/stack-springai/README.md) — design decisions and status
- [Harness contract](../../docs/projects/ludo/harness-contract.md) — the behaviour every stack must produce
- [Python for the Spring developer](../python/04-for-spring-developers.md) — the same bridge, walked the other way
- [Capability matrix](../../docs/architecture/stack-comparison.md) — what building this taught us about Spring AI
