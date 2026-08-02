# LUDO Engine (Python)

Deterministic Ludo rules engine. **Standard library only** — no LLM SDKs, no network, no I/O beyond writing transcripts.

Shared by both Python stacks (Strands and LangGraph) so the agent framework is the only variable between them — [ADR-0002](../../../docs/decisions/adr-0002-engine-per-language.md).

> **New here?** [docs/projects/ludo/engine-design.md](../../../docs/projects/ludo/engine-design.md) explains *why* the engine is shaped this way — the class taxonomy, the Python idioms it leans on, and what a Java port must preserve. This README is the practical reference.

## Design

**Colour-relative positions.** Every colour measures from its own start square, so movement logic is identical for all four players. Absolute circuit squares appear only where colours interact — capture and blocking.

```
-1  base        0  start      0..50  circuit      51..55  home column      56  home
```

**The engine validates; it never corrects.** An agent proposing an illegal move gets it rejected and one retry, then forfeits the turn. This is the structural guardrail that makes lenient content policy safe — an agent can lie, but it cannot cheat ([ADR-0004](../../../docs/decisions/adr-0004-structural-guardrails.md)).

**Deciders plug in.** The engine asks a `Decider` to pick from moves it has already validated. That's the entire agent interface, and it's why the engine needs no knowledge of LLMs.

**Portable dice.** [`dice.py`](src/ludo_engine/dice.py) specifies its own xorshift64\* PRNG rather than using Python's `random`, because the Java engine must produce an identical sequence from the same seed.

**Events are the only output.** Conforms to [`shared/schemas/event.schema.json`](../../../shared/schemas/event.schema.json). No timestamps, so same-seed transcripts diff cleanly.

## Usage

```python
from ludo_engine import COLORS, Game, GameConfig, ListSink, RandomBot

sink = ListSink()
outcome = Game(GameConfig(seed=7, max_turns=300), sink).play(
    {c: RandomBot(seed=i) for i, c in enumerate(COLORS)}
)
print(outcome.reason, outcome.winner, len(sink.events))
```

A custom agent is anything with a `choose(ctx) -> Move` method:

```python
class MyAgent:
    name = "my-agent"

    def choose(self, ctx):          # ctx.legal_moves is already validated
        return ctx.legal_moves[0]
```

A complete worked version — a heuristic bot playing against random bots — is in
[`examples/custom_agent.py`](examples/custom_agent.py). It's the template each
agent stack will follow:

```bash
uv run --directory projects/ludo/engine-python python examples/custom_agent.py
```

## Commands

Play one random-bot game and record it:

```bash
uv run --directory projects/ludo/engine-python python -m ludo_engine.cli play --seed 7 --out game.jsonl
```

Measure game length across many games — how the turn cap gets sized from data rather than guesswork:

```bash
uv run --directory projects/ludo/engine-python python -m ludo_engine.cli bench --games 500
```

Validate a transcript against the shared schema:

```bash
uv run --directory projects/ludo/engine-python python -m ludo_engine.cli validate game.jsonl
```

Check cross-engine conformance vectors:

```bash
uv run --directory projects/ludo/engine-python python -m ludo_engine.cli conformance --check
```

## Tests

```bash
uv run --directory projects/ludo/engine-python pytest
```

Every edge case listed in [game-rules.md](../../../docs/projects/ludo/game-rules.md#edge-cases) has a test. Rule changes should start there.

## Layout

| Module | Role |
|---|---|
| `board.py` | Geometry, coordinate mapping, safe squares |
| `state.py` | Game state, snapshots, standings |
| `moves.py` | The rulebook: legal move generation and application |
| `dice.py` | Portable seeded PRNG |
| `game.py` | Turn loop, extra rolls, three-sixes cancellation, turn cap |
| `deciders.py` | `Decider` protocol, `FirstLegal`, `RandomBot` |
| `events.py` | Event sinks and canonical serialisation |
| `conformance.py` | Cross-engine vector generation and checking |
| `cli.py` | `play`, `bench`, `validate`, `conformance` |
