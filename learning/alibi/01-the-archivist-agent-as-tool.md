# The Archivist, Three Ways

The three committed fixtures replay the same story — same seed, same scripted decisions, engine-event spines proven identical by [the eval](../../projects/alibi/eval/README.md). Yet count their `llm_call` events: **22, 22, 20**.

**Before you scroll:** two model invocations went missing from one stack. Which framework, and where did they go? (If you read LUDO's [capability matrix](../../docs/architecture/stack-comparison.md), you have already met the answer wearing different clothes.)

## The pattern, and what v1 actually builds

**Agent-as-tool** is the multi-agent pattern where one agent invokes another as a callable tool and reads its reply — the specialist encapsulated behind a function signature. ALIBI's specialist is the archivist: detectives never search the archive; they *ask*, mid-deliberation, through a tool the framework executes.

Honesty about scope, because this repo records gaps rather than implying parity: at the scripted tier the tool's *body* is the engine's baseline retriever ([doc 00](00-retrieval-before-embeddings.md)) — no second model answers. What v1 builds and tests in all three frameworks is the **seam**: declaration, invocation, execution, metering. The live archivist — a real sub-agent with its own model and [its own prompts](../../shared/prompts/alibi/archivist/) — drops into that seam without the seam changing shape, which is precisely what makes it a seam.

## One tool, three declarations

The body is ten lines and effectively identical everywhere: take the query, spend the turn's metered `SearchBudget`, format `[doc-id] (kind) text` lines. What differs is everything *around* it:

| | Strands | LangGraph | Spring AI |
|---|---|---|---|
| Declared as | `@tool` function — [players.py](../../projects/alibi/stack-strands/src/alibi_strands/players.py) | `@tool` function — [players.py](../../projects/alibi/stack-langgraph/src/alibi_langgraph/players.py) | `FunctionToolCallback` + input record — [Harness.java](../../projects/alibi/stack-springai/src/main/java/com/llmeval/alibi/springai/Harness.java) |
| Executed by | the agent loop, between lifecycle hooks | `ToolNode` — a **graph step** | `ToolCallingManager`, **inside** `ChatModel.call()` |
| One consultation is | 2 invocations, both hooked | 2 invocations, both in the callback | 2 invocations, **1 response** — usage aggregated |
| The transcript shows | 2 `llm_call`s | 2 `llm_call`s | 1 `llm_call` |

That last row is the missing two calls: Spring AI executes tools *internally* — the provider binding loops model → tool → model and hands the caller one `ChatResponse` for the whole chain. Nothing is unmetered (the scripted model carries the chain's usage forward, [ScriptedChatModel.java](../../projects/alibi/stack-springai/src/main/java/com/llmeval/alibi/springai/ScriptedChatModel.java)), but per-invocation granularity is gone. LUDO recorded this as a finding with an escape hatch (`setInternalToolExecutionEnabled(false)`); ALIBI turned it into something better — **a number you can produce by diffing two committed files**.

The deep lesson is not "Spring AI is wrong". It is that *"one call" is a framework opinion*. Strands and LangGraph think a call is one model invocation; Spring AI thinks it is one answered request. Every cost dashboard, budget gate, and latency chart you ever build inherits some framework's opinion on this question — better to know whose.

> **A tool is a seam, not a feature.** All three frameworks "have tools"; what you are choosing is what happens around the seam — and what a "call" means to your meter.

## Two boundaries worth noticing at the seam

**The description is prompt text you don't fully own.** The tool's docstring/`.description(...)` reaches the model as part of the tool schema — the same parity boundary [ADR-0009](../../docs/decisions/adr-0009-swarm-negotiation.md) drew for the swarm's handoff tool: authored prompts stay shared and byte-identical; tool schemas are each framework's territory. The three stacks keep the *wording* identical by hand, but the rendered schema around it differs, and no rule can make it not.

**The quota lives behind the seam, not in it.** The engine's `SearchBudget` meters and emits `archive_searched`; the tool body merely spends it. A detective who consults past the quota gets a polite refusal *and* an `invalid_action` in the transcript — enforcement stayed with the referee, so no framework's tool machinery had to be trusted with a game rule.

**Named and killed:** the archivist is NOT "RAG added to an agent". The retrieval is the engine's; what the stacks add is *delegation* — an agent choosing, mid-thought, to consult a specialist and reason about the reply. Watch red's turn 5: consult, read `doc-009`, *decline to suggest*, accuse. The tool result changed the plan. That is the agent-as-tool phenomenon, and it is visible only because the seam is real.

## Run it

The same seam, tested in each stack's own idiom:

```bash
uv run --directory projects/alibi/stack-strands pytest -k archivist -q
```

```bash
uv run --directory projects/alibi/stack-langgraph pytest -k archivist -q
```

From `projects/alibi/stack-springai` (engine installed first — see its [README](../../projects/alibi/stack-springai/README.md)):

```bash
./mvnw -B test -Dtest=HarnessTest
```

## Check yourself

1. Which stack's fixture has 51 events instead of 53, and what exactly are the missing two? ([answer](#one-tool-three-declarations))
2. Where is the search quota enforced, and why there? ([answer](#two-boundaries-worth-noticing-at-the-seam))
3. What changes in the tool's *shape* when the live archivist sub-agent replaces the baseline body? ([answer](#the-pattern-and-what-v1-actually-builds))

Next: [scoring with an answer key](02-scoring-with-an-answer-key.md) — how the eval turns all of this into arithmetic.
