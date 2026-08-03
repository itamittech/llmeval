# One Turn Through the Harness

The engine owns the turn. It calls three hooks — `negotiate`, `choose` (once per roll), `reflect` — and validates every move itself. [`harness.py`](../../projects/ludo/stack-strands/src/ludo_strands/harness.py) is the answer to those three calls, and this doc traces one turn through it. Keep the [engine's own trace](../../docs/projects/ludo/class-design.md#3-one-turn-as-calls) in the other window: this is the same diagram, seen from the far side of the `Decider` arrow.

The cast, built once per game in `LudoHarness.__init__`:

- four `Agent`s (doc 00), one per colour
- one `GameHooks`, shared by all four — metering, budget, message capture
- one `TeeSink` wrapping the caller's sink, so **engine events and agent events share one sequence** — the transcript is a single ordered record, per [ADR-0003](../../docs/decisions/adr-0003-shared-event-stream.md)
- an `_EventWindow` riding that tee — a rolling last-30-events view that becomes the `{{recent_events}}` prompt variable

## Negotiate

One line of orchestration — set the phase, skip if the budget is spent, run the table:

```python
self.hooks.turn = start.turn
self.hooks.purpose = "negotiate"
if self.hooks.exhausted:
    return
try:
    self._run_table(start)
except Exception:
    ...  # abandoned phase; the turn goes on to the roll
```

Two contract rules hide in those lines. `purpose` stamps every `llm_call` the phase produces, which is what lets the eval later ask "what does negotiation cost?". And the bare `except` is **required**: the engine deliberately lets hook exceptions crash the run ([harness-contract §2.1](../../docs/projects/ludo/harness-contract.md#21-the-hooks-the-engine-provides)), because a provider failure mid-conversation has no in-game meaning — so the harness must absorb it, and whatever was said before the failure is already in the transcript.

`_run_table` itself — the swarm — is [doc 02](02-the-swarm-table.md).

## Choose — the only call that changes the game

The engine asks once per roll, with the legal moves already computed. Attempt 1 starts a **fresh conversation**:

```python
agent.messages = []
prompt = self.prompts.turn["decide"].render(
    turn=..., color=..., die=...,
    board=render_board(ctx.state),
    legal_moves=render_moves(ctx.legal_moves),
    recent_events=self._window.render(),
    memory=render_memory(agent),
)
```

Every variable is rendered by code — `render_board`, `render_moves`, and friends at the top of `harness.py` — because the [prompt language has no loops](../../shared/prompts/README.md), deliberately. The prompt carries everything; nothing depends on what the agent happens to have in its message history.

Then the model answers, and three things happen in order:

```python
reply = str(agent(prompt))
data = extract_json(reply)              # ValueError here costs the ATTEMPT, not the run
# reasoning -> agent_reasoning event
token, to = int(data["token"]), int(data["to"])
for move in ctx.legal_moves:
    if move.token == token and move.to == to:
        return move
return Move(token, frm, to)             # not legal — returned anyway
```

That last line is the one students argue with. The harness *knows* the move is illegal — why return it? Because **rejecting is the engine's job** ([ADR-0004](../../docs/decisions/adr-0004-structural-guardrails.md)). The engine emits `illegal_move_rejected`, asks again with `attempt=2`, and the harness renders `turn/retry.md` — *into the same conversation*, so the model is looking at its own rejected answer when it retries:

```python
prompt = self.prompts.turn["retry"].render(
    reason="not a legal move for this roll",
    rejected=self._last_reply.get(ctx.color, ...),
    legal_moves=render_moves(ctx.legal_moves),
)
```

A second failure and the engine forfeits the turn. The harness adds no retries of its own — reliability is part of what is being measured ([contract §6](../../docs/projects/ludo/harness-contract.md#6-budgets-and-failure)).

## Reflect

Render `turn/reflect.md` (the turn's engine events arrive pre-packaged in `TurnEnd.events` — the harness never reconstructs them from the sink), parse `{"notes": [...]}`, and for each note:

```python
note = write_note(agent, text, end.turn, raw.get("kind"), about)
self.sink.emit("memory_write", {...}, turn=end.turn)
```

`write_note` is the read-modify-set dance from doc 00, landing in `AgentState`. An unknown `kind` becomes `observation` — defaulting, never guessing, because an invented `commitment` would be a fabricated fact about the game. The whole phase sits in a `try/except` and gives up silently on any failure: reflection is best-effort by contract — a failed write loses a note, never the game.

## The hooks, firing underneath all of it

Nothing above emitted an `llm_call`. That happens in [`hooks.py`](../../projects/ludo/stack-strands/src/ludo_strands/hooks.py), fired by the framework at its own lifecycle points:

| Framework fires | GameHooks does |
|---|---|
| `BeforeModelCallEvent` | budget spent? → `event.cancel = "..."` — the call never happens |
| `AfterModelCallEvent` | read per-call usage off the message metadata → emit `llm_call` |
| `AfterToolCallEvent` | a `handoff_to_agent` call → `message_sent` events (doc 02) |

The division of labour is the ADR-0008 point in miniature: the turn loop *narrates the game*; the framework's hook system carries the cross-cutting concerns. Neither knows the other's details.

## When the money runs out

The per-game ceiling stops **calls**, not the game:

- `negotiate` and `reflect` return without doing anything
- `choose` raises `BudgetExceeded` — which the engine catches as a decider error and **forfeits the turn**, a defined in-game outcome
- `BeforeModelCallEvent.cancel` backstops mid-phase, where a swarm conversation could cross the line between checks

So a spent game fast-forwards through instant forfeits to its turn cap and ends normally: `game_ended` is emitted, the transcript validates, and every skipped call is visible as a forfeit. The alternative — aborting mid-turn — would leave a `turn_started` with no `turn_ended` and a transcript that lies by omission.

## Watch it run

```bash
uv run --directory projects/ludo/stack-strands pytest -k "retry or budget or reflect" -q
```

and the full scripted game, which exercises everything on this page in one transcript:

```bash
uv run --directory projects/ludo/stack-strands python -m ludo_strands.demo out.jsonl
```

Next: [the swarm table](02-the-swarm-table.md) — the phase this doc skipped over.
