# A Conversation the Framework Holds

The engine calls `choose` on turn 12. The prompt the model receives contains this turn's board and legal moves — but the model also remembers turn 8's betrayal, and nothing in [`Harness.choose`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Harness.java) prepends any history. Where does the past come from?

## The advisor is the memory

```java
ChatResponse response = clients.get(color).prompt()
        .system(systemPrompt(color))
        .user(user)
        .advisors(memoryAdvisor)
        .advisors(a -> a.param(ChatMemory.CONVERSATION_ID, color.label()))
        .call()
        .chatResponse();
```

`MessageChatMemoryAdvisor` wraps the call: before the model sees anything it loads the named conversation from `ChatMemory` and prepends it; after the reply it saves the new exchange. The harness's entire contribution is a *name* — `CONVERSATION_ID = "red"` — the same move as a `@Qualifier` picking a bean. Four agents, one `ChatMemory`, four conversation ids.

Two turn-loop behaviours fall out with no code:

- **The retry sees its own rejected answer.** Attempt 2 renders `retry.md` into the *same conversation*, so the model is looking at what it just said. Checkpointing? Threading? No — the advisor loaded the same id.
- **decide and reflect share a life.** Both go through `askInConversation`; the table and the compactor deliberately don't (`askOneShot` — no advisor), because the negotiation is ephemeral by contract.

## Compaction: the framework only truncates

**Before you scroll:** `MessageWindowChatMemory` keeps the last N messages and silently drops the rest. Contract [§5](../../docs/projects/ludo/harness-contract.md#5-compaction) requires summarising the oldest turns into memory. Can the window satisfy the contract?

No — and that "no" is a matrix rating. Truncation *loses* the deals and grudges §5 exists to preserve; the contract names silent truncation as exactly the thing summarisation must not be replaced with. Spring AI ships no summarising memory (Strands does; LangGraph does), so [`maybeCompact`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Harness.java) is harness code — the recorded **Manual**:

1. Estimate the conversation (chars/4, the parity counter) against the *game's* budget.
2. Over it? Summarise the oldest exchanges — `askOneShot`, the agent's own model, metered as `purpose: "compact"`.
3. Fold the summary into durable [`Memory`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Memory.java) — the belief store, which is *also* hand-rolled, because `ChatMemory` is conversation history and Spring AI has no `AgentState` equivalent.
4. Rebuild the framework's conversation as summary + recent four, and emit `context_compacted`.

The window stays configured — at 400 messages, far above the game budget, so *our* compactor always fires first and the framework's truncation never silently eats a game.

## Persistence: the split runs all the way down

Give the harness a session directory and the two memory boxes persist **differently**, and the difference is the finding:

- **Conversations — free.** [`Session.java`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Session.java) swaps the in-memory store behind `ChatMemory` for the framework's `JdbcChatMemoryRepository` over an embedded H2 file. The repository *is* the memory's backing store, so every exchange writes through as it happens. No sync moment exists to forget.
- **Beliefs — by hand.** `Memory` never touches the framework, so nothing the framework offers can save it: `beliefs.json`, written by `persist()` in `play()`'s finally.

[`SessionTest`](../../projects/ludo/stack-springai/src/test/java/com/llmeval/ludo/springai/SessionTest.java) pins the asymmetry: kill the process before the save and the conversations survive while every note vanishes. (Strands was the mirror image — one store holds everything, but on the framework's sync schedule.) One more thing the test teaches: without Spring Boot, the repository's table doesn't create itself — `Session.open` runs the module's own `schema-h2.sql`, the two lines the starter would have hidden.

## The budget, and the exit

`choose` checks the per-game ceiling first and, once spent, throws `BudgetSpent`. That exception crosses the `implements Decider` boundary and the *engine* turns it into the defined in-game outcome — a forfeited turn, a game that runs to its cap, a schema-valid transcript. The ceiling stops calls, never the game.

## Where to look

| To see | Read | Run |
|---|---|---|
| The advisor + conversation id | `Harness.askInConversation` | `./mvnw -B test -Dtest=HarnessTest#theConversationPersistsAndCompacts` |
| Hand-rolled compaction | `Harness.maybeCompact` | same test — 40-token budget forces it |
| The persistence split | [`Session.java`](../../projects/ludo/stack-springai/src/main/java/com/llmeval/ludo/springai/Session.java) | `./mvnw -B test -Dtest=SessionTest` |
| Budget → forfeit | `Harness.choose` | `./mvnw -B test -Dtest=HarnessTest#aSpentBudgetForfeitsInsteadOfCrashing` |

> **The line to keep: Spring AI gives you the conversation and nothing above it.** Memory of *messages* is Native and even persists itself; memory of *beliefs*, summarisation, and everything else an agent's mind needs is yours to build — and the matrix records each one.

Next: [the tool-form table](02-the-tool-form-table.md).
