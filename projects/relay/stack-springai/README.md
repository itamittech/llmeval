# RELAY on Spring AI

Four runner `ChatClient`s, one shared anchor, on the Java engine. Same race, same seed, same events as [Strands](../stack-strands/README.md) and [LangGraph](../stack-langgraph/README.md) — proven by a test that reads their Python-written fixtures.

## Run it

The stack depends on the engine by coordinates, so install it once:

```bash
cd ../engine-java && ./mvnw -q -B install -DskipTests
```

```bash
./mvnw -B test
```

```bash
./mvnw -q -B compile exec:java -Dexec.args="../games/scripted-springai-seed7.jsonl"
```

## Design

| Concern | How | Rating |
|---|---|---|
| Runner agents | One `ChatClient` per lane | **Native** |
| Conversation | `ChatMemory` behind a `MessageChatMemoryAdvisor`, one conversation id per lane | **Native** |
| Notebook | [`Notebook.java`](src/main/java/com/llmeval/relay/springai/Notebook.java), a plain class | **Manual** — third game, third time |
| Metering | Usage read off the `ChatResponse`, synchronously | **Native** |
| **Escalation to the anchor** | A second `ChatClient` with no memory advisor | **Adapter** |
| Guardrails | Harness gate on the note | **Manual** |
| Orchestration | None. There is nothing to orchestrate | n/a |

### The finding that did *not* happen

ALIBI's Spring AI stack metered **20 calls where the Python stacks metered 22**, because Spring AI executes tools inside the `ChatModel` and hands the caller one response for what was two invocations. It was the sharpest per-framework difference in that game.

RELAY has **no tool**. Escalation is a model swap the *engine* performs, so there is no model→tool→model loop to fold, nothing to aggregate, and nothing hidden. All three stacks meter the same calls.

That is worth stating precisely, because the wrong reading is available: the frameworks did not converge. The protocol stopped asking them to differ. Same lesson [ALIBI recorded about orchestration](../../../docs/architecture/stack-comparison.md#finding-remove-the-protocol-and-the-orchestration-axis-vanishes), now reproduced on the tool axis.

### Two Java traps, one root

The engine hit it and so did this stack: **`Map.of` is not merely unordered — its iteration order is randomised per JVM run.** A payload assembled from one is byte-reproducible within a process and different the next time.

- In the engine it broke `track_generated` key order against Python's. Conformance still passed, because the digest sorts keys. Only a file diff found it.
- Here it broke the `players` block, and the fixture test found it immediately — regenerate, compare, fail.

Both are now built key by key, and both carry the reason in the source. The lesson generalises past Java: **a guarantee that only holds when someone remembers to check it is not a guarantee**, so the check belongs in a test.

## The numbers

Same race, three stacks, measured from the committed fixtures:

| | Strands | LangGraph | Spring AI |
|---|---|---|---|
| `llm_call` events | 56 | 55 | 55 |
| Tokens sent (chars//4 est.) | 75,626 | **123,067** | **123,067** |

LangGraph and Spring AI land on the *identical* token count, from two different memory primitives — an unbounded checkpointer thread and a 24-message window that never fills in a 24-turn race. Strands differs only because its window is pinned at 12.

So the 1.6× spread is a **configuration choice, not a framework property**, and the proof is that two unrelated frameworks agree to the token. Both also cross the per-game ceiling and lose their final reflect call to it, which is the same choice showing up as behaviour rather than as a bill.

## Related

- [Harness contract](../../../docs/projects/relay/harness-contract.md) · [Game rules](../../../docs/projects/relay/game-rules.md)
- [Capability matrix](../../../docs/architecture/stack-comparison.md)
