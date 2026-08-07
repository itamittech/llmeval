# alibi-springai

ALIBI's third harness: four `ChatClient`s on Spring AI over the Java engine,
the archivist as a `FunctionToolCallback` executed by the framework's own
tool-calling machinery. Binds to the
[harness contract](../../../docs/projects/alibi/harness-contract.md).

**The grain LUDO recorded holds in game two, now visible in a fixture:** Spring
AI executes tools *inside* the model call, so a consultation is two model
invocations the caller sees as one response — this stack's fixture carries
**20** `llm_call` events for the same story the Python stacks metered as
**22**, with usage aggregated so nothing goes uncounted. And the notebook is
still hand-rolled ([`Notebook.java`](src/main/java/com/llmeval/alibi/springai/Notebook.java)):
the framework has conversation memory, not a belief store — LUDO's Manual,
unchanged.

## Class map

| Class | What it owns |
|---|---|
| `Prompts` | The shared set, loaded verbatim; digest byte-identical to the Python loaders (a test proves it against the committed fixtures) |
| `ModelsConfig` | Seats from `models.yaml` profiles; ALIBI budgets + archivist from its `alibi` section |
| `ScriptedChatModel` | The scripted model through the `ChatModel` seam — including internal tool execution via `ToolCallingManager`, the part a naive fake would skip |
| `Notebook` | The hand-rolled notebook — the missing-primitive finding, second game running |
| `Guardrails` | The same three rules as the Python stacks: injection, authority, forged citations |
| `Harness` | `ChatClient` per colour, conversation memory via the framework's advisor, the consult tool, one `llm_call` per client call |
| `Demo` | The same seed-7 story as the other two fixtures |

## Run it

Build the engine into the local repository once, then test (both from `projects/alibi`):

```bash
cd engine-java && ./mvnw -q -B install -DskipTests
```

```bash
cd stack-springai && ./mvnw -B test
```

Regenerate the committed fixture:

```bash
./mvnw -q -B exec:java -Dexec.args="../games/scripted-springai-seed7.jsonl"
```
