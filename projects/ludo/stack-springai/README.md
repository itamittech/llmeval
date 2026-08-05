# LUDO — Spring AI Stack

The third agent harness: [harness-contract.md](../../../docs/projects/ludo/harness-contract.md) on [Spring AI](https://spring.io/projects/spring-ai), over the [Java engine](../engine-java/README.md). Same shared prompts, same `models.yaml`, same event schema as the two Python stacks — the framework is the only variable.

> **🚧 First cut.** The turn loop runs end to end against a scripted model — negotiation, decide with retry, reflect, budgets, events — and its [fixture](../games/scripted-springai-seed7.jsonl) is committed and rendered by the UI **with zero UI changes** (ADR-0007's rule, now proven against a third emitter). Context compaction, guardrails, session persistence, and live providers are not built. See [Status](#status).

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

**`implements Decider`, at last.** The Python stacks satisfy the engine's contract by shape; this one writes the line Java demands — [`Harness.SpringDecider`](src/main/java/com/llmeval/ludo/springai/Harness.java) `implements Decider`, and therefore the whole stack depends on the engine jar. The [capability matrix](../../../docs/architecture/stack-comparison.md) predicted this row before any stack existed; here is its proof.

**The scripted model is a real `ChatModel`.** [`ScriptedChatModel`](src/main/java/com/llmeval/ludo/springai/ScriptedChatModel.java) implements Spring AI's own provider seam — `call(Prompt) → ChatResponse` — so the `ChatClient`, usage metadata, and the whole loop run exactly as they would live (harness-contract §8). It is the simplest of the three stacks' fakes by a distance: one synchronous method, no stream-event choreography — a genuine point *for* Spring AI, recorded in the matrix.

**Negotiation is the honest divergence.** Spring AI has no swarm orchestrator — nothing like Strands' `Swarm` or `langgraph-swarm` — so ADR-0009's floor-passing table is orchestrated by harness code: a loop in [`Harness.runTable`](src/main/java/com/llmeval/ludo/springai/Harness.java) that delivers directed messages, fans table notes into inboxes, and enforces the pass cap. A legitimate **Manual** under [ADR-0008](../../../docs/decisions/adr-0008-framework-native-harness.md)'s rule — the framework offers nothing — and the headline capability-matrix finding this stack was always expected to produce. The observable protocol is identical to the Python stacks'.

**One stated gap:** in this first cut the floor-pass action is a parsed JSON reply. Per ADR-0009's boundary the live form should be a framework tool (`@Tool`/`ToolCallback`), whose schema is framework-authored territory; that lands with live play, and until then the scripted mechanism is ours end to end.

**Memory is hand-rolled, and recorded as such.** Spring AI's `ChatMemory` is conversation history, not a key-value belief store — there is no `AgentState` equivalent — so [`Memory`](src/main/java/com/llmeval/ludo/springai/Memory.java) is a plain class: notes with kinds, durable facts, the never-reconciled rule, rendered byte-identically to the Python stacks' `{{memory}}`.

## Status

| Piece | State |
|---|---|
| Prompt loading, validation, digest (parity with prompts.py) | ✅ [`Prompts.java`](src/main/java/com/llmeval/ludo/springai/Prompts.java) |
| `models.yaml` profiles, budgets, seat rotation (ADR-0006) | ✅ [`ModelsConfig.java`](src/main/java/com/llmeval/ludo/springai/ModelsConfig.java) |
| Scripted model through Spring AI's `ChatModel` seam | ✅ [`ScriptedChatModel.java`](src/main/java/com/llmeval/ludo/springai/ScriptedChatModel.java) |
| Turn loop: negotiate → decide (with retry) → reflect | ✅ [`Harness.java`](src/main/java/com/llmeval/ludo/springai/Harness.java) |
| Floor-passing table (harness-orchestrated — see the matrix finding) | ✅ |
| Token accounting + forfeit-out budget ceiling | ✅ usage from `ChatResponse` metadata |
| Agent events, one sequence with engine events | ✅ schema-validated [fixture](../games/scripted-springai-seed7.jsonl) |
| Floor pass as a framework tool | ⬜ with live play |
| Conversation memory (`ChatMemory`) + context compaction | ⬜ |
| Content guardrails | ⬜ |
| Session persistence | ⬜ |
| Live providers (Bedrock + Anthropic via Boot starters) | ⬜ blocked with the rest on model IDs |

Everything above runs offline against the scripted model; nothing costs anything. `learning/springai` follows once the remaining pieces exist, per the repo's rule against documenting half-built code.
