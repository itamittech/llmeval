# The Graph Is the Program

Here is the confusion this page exists to clear up. Search [`harness.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/harness.py) for the field that stores red's conversation. There isn't one — no list of messages, no agent object holding history, nothing. Yet red's second turn provably remembers its first, and the retry after an illegal move sees the rejected answer. Where does a conversation live when no object holds it?

## Declare, compile, invoke

A LangGraph program is three declarations and a handoff:

```python
class TableState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]   # field + MERGE RULE
    holder: str
    passes: int

builder = StateGraph(TableState)
builder.add_node("brief", self._brief)          # node: state -> partial update
builder.add_node("speak", self._speak)
builder.add_edge(START, "brief")
builder.add_conditional_edges("speak", tools_condition, {...})
graph = builder.compile()

graph.invoke({"holder": "red", "passes": 0, ...})
```

Three ideas carry everything:

1. **Nodes return updates, not state.** `_brief` returns `{"messages": [...], "delivered": False}` — a *diff*. The framework merges it using each field's rule: plain fields overwrite; `Annotated[..., add_messages]` appends (and understands `RemoveMessage` as deletion — doc 02 builds the table's privacy on exactly that).
2. **Edges are the control flow.** A conditional edge is a function from state to a node name. Your `while` loop, your `if` — drawn, not written. The engine-side of this repo made the same trade once: [the rules became data](../../docs/projects/ludo/engine-design.md) so they could be checked; here the control flow becomes data so the framework can run, checkpoint, and resume it.
3. **The runtime owns the state.** Which is the answer to the opening riddle —

## The checkpointer, or: conversations without an object

Compile a graph with a checkpointer and every invocation runs under a **thread id**:

```python
agent.invoke({"messages": [prompt]}, {"configurable": {"thread_id": "red"}})
```

After every step, the framework saves the whole graph state under that id. Invoke the same id again and it loads first. So "red's conversation" is not a thing the harness holds — it is *what the checkpointer replays for `thread_id="red"`*. Four agents means four thread ids over one checkpointer; the retry sees the rejected answer because it arrives on the same thread; and session persistence (doc 02) will be nothing more than making the checkpointer durable.

If you came from the Spring AI docs: this is `CONVERSATION_ID`, one storey lower — there an advisor loaded history *into your call*; here the runtime loads state *around your graph*.

## The seam, and two reasons the shipped fake wasn't good enough

**Before you scroll:** langchain-core ships `FakeMessagesListChatModel`, which replays canned messages. The contract [§8](../../docs/projects/ludo/harness-contract.md#8-proving-a-stack-conforms) wants a fake at the framework's own extension point — that *is* one. Why did this stack write its own anyway?

Read the shipped fake's source and two facts disqualify it:

1. **It cycles.** Past the end of the script it wraps back to the start — so a harness calling the model more often than its author believed *silently replays old answers* instead of failing. A script running out should be a loud error; [`ScriptedChatModel`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/scripted.py) raises.
2. **`bind_tools` raises `NotImplementedError` in the base class.** Tool support is the provider's job, and the shipped fake never implemented it — so it cannot sit under the table graph, where the model must be offered `pass_floor`. Ours does what `ChatAnthropic` does: convert the tools and bind them (then, being a script, ignore them).

Everything else is the seam working as designed: implement `_generate`, attach `usage_metadata` to each reply (chars//4, nonzero — an all-zero fake would let a broken meter pass every test, the lesson the Strands stack learned the hard way), and the whole machine above runs identically offline.

## Where to look

| To see | Read | Run |
|---|---|---|
| A real graph, drawn small | [`table.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/table.py) `_draw` | `uv run --directory projects/ludo/stack-langgraph pytest -k table -q` |
| Threads carrying the conversation | [`harness.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/harness.py) `_thread`, `conversation` | `... pytest -k retry -q` |
| The scripted seam | [`scripted.py`](../../projects/ludo/stack-langgraph/src/ludo_langgraph/scripted.py) | `... pytest -k llm_call -q` |

> **The line to keep: in LangGraph, state belongs to the runtime and identity is a thread id.** If you're looking for the object that holds something, you're holding the wrong mental model — look for the id it's stored under.

Next: [one turn on a thread](01-one-turn-on-a-thread.md).
