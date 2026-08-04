# What Happens When You Call `agent("...")`

Here is the confusion this page exists to clear up. In the [fixture transcript](../../projects/ludo/games/scripted-strands-seed7.jsonl)'s negotiation, agents hold the floor **three** times — red, blue, red again — yet the transcript shows **five** `llm_call` events for that one conversation. Where did the extra two come from?

The answer is the one framework behaviour everything in the harness rests on. Get this loop into your head before reading a line of `harness.py`.

## The loop

```python
from strands import Agent

agent = Agent(model=some_model, system_prompt="You are red.")
result = agent("It's your turn.")
```

That single call runs a loop:

1. Your prompt is appended to `agent.messages` as a user message.
2. **`BeforeModelCallEvent`** fires — hooks may inspect, or cancel the call.
3. The framework calls `model.stream(messages, tool_specs, system_prompt)` and consumes the streamed response.
4. **`AfterModelCallEvent`** fires, success or failure.
5. Now it depends on how the model stopped:
   - **`end_turn`** — the text answer is final. The loop ends; you get an `AgentResult`.
   - **`tool_use`** — the model asked to run a tool. The framework executes it (**`AfterToolCallEvent`** fires), appends the result to the conversation, and **goes back to step 2**. The model sees its tool's result and answers again.

So one `agent(...)` call can mean *several* model invocations — one per tool round plus the final answer. That multiplier matters everywhere in this project: it is why the harness meters `llm_call` per **invocation** (step 4 fires once each), never per `agent(...)` call, and why a scripted floor pass costs two script entries (a tool round, then the answer after it).

What you get back:

```python
result = agent(prompt)
str(result)          # the final text (with a trailing newline)
result.stop_reason   # "end_turn", "max_tokens", ...
result.metrics       # accumulated token usage and latency
```

The harness's `choose` and `reflect` are exactly this: render a prompt, `agent(prompt)`, parse `str(result)`.

## What an `Agent` is made of

The constructor arguments this stack actually uses, from [`players.py`](../../projects/ludo/stack-strands/src/ludo_strands/players.py):

```python
Agent(
    model=model,                 # who answers — a provider binding or the scripted model
    system_prompt=system_prompt, # the shared templates, rendered once per game
    name=color,                  # load-bearing: becomes the Swarm node id (doc 02)
    state={"notes": [], "durable": []},  # AgentState — memory lives here
    callback_handler=None,       # no console streaming; the transcript is the record
    hooks=[self.hooks],          # our GameHooks subscribes to the lifecycle events
)
```

`state` is an `AgentState`: a key-value store that validates everything is JSON-serialisable and **deep-copies on every `get`**. That last part changes how you write to it — mutating what `get` returned changes a copy, so memory writes are read-modify-**set**:

```python
notes = agent.state.get("notes") or []
notes.append(note)
agent.state.set("notes", notes)     # without this line, nothing happened
```

## The `Model` seam — and how to fake one honestly

A provider binding is a subclass of `strands.models.Model` with four methods; the one that matters is `stream()`, an async generator yielding the response as **events** — the same shapes Bedrock's streaming API uses:

```python
{"messageStart": {"role": "assistant"}}
{"contentBlockDelta": {"delta": {"text": "hello"}}}
{"contentBlockStop": {}}
{"messageStop": {"stopReason": "end_turn"}}
{"metadata": {"usage": {"inputTokens": 42, "outputTokens": 7, "totalTokens": 49},
              "metrics": {"latencyMs": 180}}}
```

A tool call is the same dance with a `toolUse` block and `"stopReason": "tool_use"`.

[`scripted.py`](../../projects/ludo/stack-strands/src/ludo_strands/scripted.py) implements exactly this interface and replays committed replies. That is the [harness contract §8](../../docs/projects/ludo/harness-contract.md#8-proving-a-stack-conforms) seam, and the *placement* is the point: because the fake sits at the framework's own extension point, the entire loop above — tools, hooks, metrics, the swarm — runs identically with and without a network. The first test in [`test_turnloop.py`](../../projects/ludo/stack-strands/tests/test_turnloop.py) is one line of proof: a bare `Agent` runs on it with no special casing at all.

The scripted usage numbers are fake but deliberately **nonzero** (chars/4 — the same heuristic Strands falls back to). All-zero usage would have let a broken token meter pass every test. It nearly did:

## The trap this loop hid

**Before you scroll:** you need per-call token counts inside `AfterModelCallEvent`, and the agent object exposes *accumulated* totals. Design your metering in one sentence — then look for the flaw in it.

The obvious design — read the accumulated metrics, diff against last time — is the flawed one. It reads zeros: the event loop fires the hook **before** it adds the call's usage to the totals. The per-call numbers are attached to the assistant message itself (`message["metadata"]["usage"]`), put there *for* hooks, and that is what [`hooks.py`](../../projects/ludo/stack-strands/src/ludo_strands/hooks.py) reads.

Caught only because a scripted-loop test asserted a nonzero `llm_call`. Against a live provider, every transcript would have carried plausible-looking, uniformly stale token counts — no error, no warning, wrong data forever. The full write-up is a [capability-matrix finding](../../docs/architecture/stack-comparison.md), with the question the other two stacks now have to answer.

## Where to look

| To see | Read | Run |
|---|---|---|
| The fake model's stream events | [`scripted.py`](../../projects/ludo/stack-strands/src/ludo_strands/scripted.py) | `uv run --directory projects/ludo/stack-strands pytest -k real_strands_model -q` |
| Per-call metering off the hook | [`hooks.py`](../../projects/ludo/stack-strands/src/ludo_strands/hooks.py) `_after_model` | `... pytest -k picks_the_scripted_move -q` |
| Agent construction | [`players.py`](../../projects/ludo/stack-strands/src/ludo_strands/players.py) `build_player` | |

> **The line to keep: one agent call is not one model call.** Every tool round is another invocation, another `llm_call`, another chance for the budget hook to fire. If a number in this stack ever looks wrong by a small integer factor, suspect this first.

Next: [one turn through the harness](01-one-turn-through-the-harness.md).
