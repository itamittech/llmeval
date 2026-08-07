# alibi-langgraph

ALIBI's second harness: four `create_agent` loops on LangGraph, the archivist
as a **real framework tool** run by the tool executor — a consultation is two
visible, metered model invocations, never a hidden round-trip. Conversations
live in the checkpointer under `thread_id=color`; notebooks on the framework
`Store` (explicit `limit`, honouring LUDO's footgun); metering in a callback
the framework propagates to every call. Binds to the
[harness contract](../../../docs/projects/alibi/harness-contract.md).

**No `StateGraph` of our own this time, and that is the finding in miniature:**
answered [question 22](../../../docs/open-questions.md#-22-does-alibi-keep-ludos-negotiation-channels)
removed the multi-agent protocol, so the machinery that made LUDO's LangGraph
stack distinctive — the table drawn as a graph — has nothing to draw. ALIBI
stresses tools and retrieval, where the frameworks' differences are grain, not
capability.

## Module map

| Module | What it owns |
|---|---|
| `prompts.py` / `config.py` / `guardrails.py` | Same contracts as every stack: verbatim prompts, `models.yaml`, the lenient line |
| `scripted.py` | The scripted model through `BaseChatModel` — no cycling, usage attached |
| `memory.py` | The notebook on `Store`, namespace `("notebook", color)` |
| `players.py` | `create_agent` + the `consult_archivist` tool + the BudgetGate middleware |
| `meter.py` | One `llm_call` per invocation via the propagated callback |
| `harness.py` | The engine-facing adapter — render → invoke on the colour's thread → parse |
| `demo.py` | **The same seed-7 story as the Strands fixture** — cross-stack comparability is the point |

## Run it

```bash
uv run --directory projects/alibi/stack-langgraph pytest
```

```bash
uv run --directory projects/alibi/stack-langgraph python -m alibi_langgraph.demo out.jsonl
```
