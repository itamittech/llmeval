# LUDO — Spring AI Stack

The third agent harness: [harness-contract.md](../../../docs/projects/ludo/harness-contract.md) on [Spring AI](https://spring.io/projects/spring-ai), over the [Java engine](../engine-java/README.md). Same shared prompts, same `models.yaml`, same event schema as the two Python stacks — the framework is the only variable.

> **🚧 Nearly feature-complete against scripted models.** Turn loop, tool-driven floor passing, conversation memory, compaction, guardrails, budgets, events — the [fixture](../games/scripted-springai-seed7.jsonl) is committed and rendered by the UI **with zero UI changes** (ADR-0007's rule, proven against a third emitter). Session persistence and live provider calls remain. See [Status](#status).

## Build and test

Standalone Maven project. It depends on the engine by coordinates, so build the engine into your local repository once first:

```bash
cd projects/ludo/engine-java && ./mvnw -q -B install -DskipTests
```

```bash
cd projects/ludo/stack-springai && ./mvnw -B test
```

A full scripted game, offline and free — regenerates the committed fixture byte-identically:

```bash
cd projects/ludo/stack-springai && ./mvnw -q -B exec:java -Dexec.args="../games/scripted-springai-seed7.jsonl"
```

No Spring Boot yet, deliberately: the scripted harness needs only the Spring AI chat-client library. Boot and the provider starters (Bedrock, Anthropic) arrive with live play.

## Design

The reference diagrams for this whole layer — the object graph, one `choose` as calls, one table round with its hidden invocation, and the Strands-vs-Spring-AI two-grains table — are [class-design §10](../../../docs/projects/ludo/class-design.md#10-the-harness-layer-second-take-the-same-turn-on-spring-ai). What follows states the decisions those diagrams draw.

**`implements Decider`, at last.** The Python stacks satisfy the engine's contract by shape; this one writes the line Java demands — [`Harness.SpringDecider`](src/main/java/com/llmeval/ludo/springai/Harness.java) `implements Decider`, and therefore the whole stack depends on the engine jar. The [capability matrix](../../../docs/architecture/stack-comparison.md) predicted this row before any stack existed; here is its proof.

**The scripted model is a real `ChatModel`.** [`ScriptedChatModel`](src/main/java/com/llmeval/ludo/springai/ScriptedChatModel.java) implements Spring AI's own provider seam — `call(Prompt) → ChatResponse` — so the `ChatClient`, usage metadata, and the whole loop run exactly as they would live (harness-contract §8). It is the simplest of the three stacks' fakes by a distance: one synchronous method, no stream-event choreography — a genuine point *for* Spring AI, recorded in the matrix.

**Negotiation is the honest divergence — orchestration Manual, the action Native.** Spring AI has no swarm orchestrator — nothing like Strands' `Swarm` or `langgraph-swarm` — so ADR-0009's floor-passing *loop* is harness code in [`Harness.runTable`](src/main/java/com/llmeval/ludo/springai/Harness.java): a legitimate **Manual** under [ADR-0008](../../../docs/decisions/adr-0008-framework-native-harness.md)'s rule, and the headline matrix finding this stack was always expected to produce. But the floor-pass **action** is a real framework tool — `pass_floor`, a `FunctionToolCallback` whose schema reaches the model as framework-authored text, exactly ADR-0009's boundary — executed by the framework's own `ToolCallingManager` even under the scripted model, which implements internal tool execution the way real provider bindings do. **The guardrail gate lives inside the tool**: the same three deterministic rules as the Python stacks ([`Guardrails.java`](src/main/java/com/llmeval/ludo/springai/Guardrails.java)); a blocked message never delivers, `guardrail_triggered` is recorded, and the model reads why. Cunning passes, and a test asserts it.

**Conversation memory is Native; compaction is not.** Decide and reflect share one framework-held conversation per agent — `ChatMemory` through a `MessageChatMemoryAdvisor`. But Spring AI's only management strategy is a sliding window — *silent truncation, exactly what the contract's §5 forbids substituting for summarisation* — so the compactor is harness code: past the game's context budget, the oldest exchanges are summarised by the agent's own model (metered as `purpose: "compact"`), folded into durable memory, and the `ChatMemory` rebuilt as summary + recent. Native conversation, Manual compaction — the exact inverse of nothing: the matrix row where Strands and Spring AI split cleanly.

**Beliefs are hand-rolled, and recorded as such.** `ChatMemory` is conversation history, not a key-value belief store — there is no `AgentState` equivalent — so [`Memory`](src/main/java/com/llmeval/ludo/springai/Memory.java) is a plain class: notes with kinds, durable facts, the never-reconciled rule, rendered byte-identically to the Python stacks' `{{memory}}`.

**Live settings are pinned before live calls exist.** [`LiveModels`](src/main/java/com/llmeval/ludo/springai/LiveModels.java) builds the ADR-0005 control seat's `AnthropicChatOptions` from `models.yaml` and a test reads every setting back — the same discipline as the Strands stack's `strands_client.py`, and for the same reason: an unpinned parameter is a parity break that never announces itself. Bedrock, Nova, and DeepSeek bindings arrive with live play.

## Status

| Piece | State |
|---|---|
| Prompt loading, validation, digest (parity with prompts.py) | ✅ [`Prompts.java`](src/main/java/com/llmeval/ludo/springai/Prompts.java) |
| `models.yaml` profiles, budgets, inference settings, seat rotation | ✅ [`ModelsConfig.java`](src/main/java/com/llmeval/ludo/springai/ModelsConfig.java) |
| Scripted model through Spring AI's `ChatModel` seam, **with internal tool execution** | ✅ [`ScriptedChatModel.java`](src/main/java/com/llmeval/ludo/springai/ScriptedChatModel.java) |
| Turn loop: negotiate → decide (with retry) → reflect | ✅ [`Harness.java`](src/main/java/com/llmeval/ludo/springai/Harness.java) |
| Floor pass as a framework tool (`pass_floor`, `FunctionToolCallback`) | ✅ orchestration remains Manual — see the matrix finding |
| Content guardrails — lenient by design, inside the tool | ✅ [`Guardrails.java`](src/main/java/com/llmeval/ludo/springai/Guardrails.java) |
| Conversation memory (`ChatMemory` + `MessageChatMemoryAdvisor`) | ✅ Native |
| Context compaction | ✅ **Manual** — the framework only truncates; `Harness.maybeCompact` summarises |
| Token accounting + forfeit-out budget ceiling | ✅ usage from `ChatResponse` metadata |
| Agent events, one sequence with engine events | ✅ schema-validated [fixture](../games/scripted-springai-seed7.jsonl) |
| Live provider settings pinned + read back (Anthropic control seat) | ✅ [`LiveModels.java`](src/main/java/com/llmeval/ludo/springai/LiveModels.java) |
| Session persistence | ⬜ |
| Live calls (Boot + provider starters; Bedrock, Nova, DeepSeek) | ⬜ blocked on model IDs |

Everything above runs offline against the scripted model; nothing costs anything. `learning/springai` follows once the code stops moving, per the repo's rule against documenting half-built code.
