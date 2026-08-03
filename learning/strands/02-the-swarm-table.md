# The Swarm Table

Negotiation is the one phase where the framework, not the harness, drives the agents. This doc explains the `Swarm` orchestrator's actual mechanics — verified in the pinned `strands-agents 1.50.2` source — and the one non-obvious trick the harness builds on them. It will also make [ADR-0009](../../docs/decisions/adr-0009-swarm-negotiation.md) click: the protocol looks the way it does *because* these are the mechanics.

## What a Swarm is

```python
table = Swarm(
    nodes=[self.players[c] for c in COLORS],   # our four agents; node id = agent name = colour
    entry_point=self.players[start.color],     # the active player opens
    max_handoffs=self.budgets.max_floor_passes,
    max_iterations=self.budgets.max_floor_passes + 1,
)
table(task)
```

`Swarm` takes a team of agents and one **task**, activates the entry agent, and from then on the *models* steer: into every member it injects a tool called `handoff_to_agent(agent_name, message, context)`. When the current agent's model calls that tool, control moves to the named agent. When an agent finishes **without** calling it, the swarm is done — every member is told, verbatim:

> *"If you don't hand off to another agent, the swarm will consider the task complete."*

That sentence is the floor-passing protocol's enforcement, for free: speak-and-address passes the floor; silence ends the conversation; `max_handoffs` caps it. The harness never counts messages or manages turn-taking — the orchestrator does.

Each activated agent receives a built-up **node input**: the handoff message addressed to it (shown once, then cleared), the shared task, the list of who has spoken (`red → blue → red`), and any shared context. Which is exactly the visibility model of the game: *directed content is pairwise, who-talked-to-whom is public*.

## The reset semantics — the part nobody expects

**Before you scroll:** red opens the conversation, blue replies, and the floor comes back to red. When red is activated the second time — what does it remember of its own first message? Commit to an answer.

Three facts from the source, and they change everything:

1. When a `Swarm` is constructed, it **snapshots** every agent's conversation and `AgentState` (`SwarmNode.__post_init__`).
2. Before **every** activation, it **resets** the agent to that snapshot (`reset_executor_state`, called in the execution loop).
3. So an agent activated twice in one conversation starts its second activation having *forgotten its first* — everything it learned mid-phase is gone unless it travelled in the handoff message, the shared context, or the node history.

`Swarm` is built for stateless specialist workers over a shared blackboard. LUDO's players are the opposite — stateful, private, secretive. This mismatch is why the original negotiation protocol had to be redesigned ([the full analysis](../../docs/architecture/stack-comparison.md), kept in the matrix), and it leaves two problems the harness must solve.

**Problem 1: how does a player's private context get in at all?** The reset is the answer, not the obstacle. `_run_table` seeds each agent's messages *before* constructing the swarm:

```python
agent.messages = [
    {"role": "user", "content": [{"text": briefing}]},      # turn/briefing.md:
    {"role": "assistant", "content": [{"text": "Noted."}]}, #   memory + inbox
]
table = Swarm(nodes=..., ...)   # <- construction snapshots THIS
```

Timeline for one phase, red active, red → blue → red:

| Step | What the swarm does | What the agent sees |
|---|---|---|
| seed | — | red's briefing placed in its history |
| construct | snapshot all four agents | briefing is now *in* the snapshot |
| activate red | reset red → snapshot | briefing + the task |
| red's model calls `handoff_to_agent("blue", ...)` | control moves | |
| activate blue | reset blue → *blue's* snapshot | blue's own briefing + red's message |
| blue hands back | | |
| activate red again | reset red → snapshot **again** | briefing + blue's reply — but *not* red's own first activation |

The reset that would have destroyed per-agent context becomes the mechanism that delivers it: every activation starts from exactly briefing-plus-what-was-addressed-to-you. Framework-native design is sometimes this — not fighting the primitive's behaviour, but finding the reading of your problem under which the behaviour is the feature.

**Problem 2: nothing said at the table survives the phase.** By design, now: retention within a phase is framework behaviour, and anything a player wants to keep it must write to memory at **reflect** — which runs *outside* the swarm, on the agent's real, un-reset state. The prompt tells players so explicitly: *"If a deal matters, write it down."* A deal the other side genuinely forgot is an observable outcome of this architecture, and one worth watching for in real games.

## How spoken words become events

The harness never parses negotiation replies. The *model's tool calls* are the messages, and [`hooks.py`](../../projects/ludo/stack-strands/src/ludo_strands/hooks.py) captures them at `AfterToolCallEvent`:

| The model called | Events emitted |
|---|---|
| `handoff_to_agent(agent_name="blue", message=m)` | `message_sent {player, to: "blue", text: m}` |
| … with `context={"table_note": n}` | plus `message_sent {player, to: null, text: n}` |
| … naming a player that doesn't exist | nothing — the tool already told the model; nothing was delivered |

The same hook feeds each recipient's **inbox**, which surfaces in their *next* briefing — that is the only bridge a directed message has across phases, and it goes through the transcript-visible event first. Nothing reaches a player that a spectator cannot see.

## Why two script entries per handoff

In tests and the demo, a scripted floor pass looks like:

```python
"red": [
    {"handoff": {"to": "blue", "message": "ally against yellow?",
                 "note": "I want a quiet table"}},
    "(floor passed)",        # <- the answer AFTER the tool result
    "nothing further",       # <- second activation: silence ends the phase
]
```

Doc 00's loop explains the middle entry: after a tool runs, the framework always asks the model again. The scripted model refuses to hide that mechanical second call, so scripts state honestly how many model invocations a conversation costs — red's three entries plus blue's two are the five `llm_call` events the test asserts.

## Watch it run

```bash
uv run --directory projects/ludo/stack-strands pytest -k table -q
```

Then read `test_the_table_runs_on_the_swarm` in [`test_turnloop.py`](../../projects/ludo/stack-strands/tests/test_turnloop.py) against this doc — every mechanism above is asserted there: the message order, the five calls, the inboxes, the note fan-out.

> **The line to keep: the reset is the delivery.** Swarm wipes each agent back to its construction snapshot on every activation — so put the briefing *in* the snapshot, and the wipe becomes the mechanism that guarantees every activation starts from exactly the private context you intended.

## Related

- [ADR-0009](../../docs/decisions/adr-0009-swarm-negotiation.md) — the protocol redesigned to these mechanics, and what that traded away
- [Capability matrix](../../docs/architecture/stack-comparison.md) — the original couldn't-fit analysis, kept as a finding
- [class-design.md §9](../../docs/projects/ludo/class-design.md#9-the-harness-layer-the-same-turn-on-strands) — the phase as a sequence diagram
