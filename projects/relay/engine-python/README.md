# RELAY engine (Python)

The deterministic race engine and stage generator. Standard library only — no LLM SDK, no network, no clock. Same seed, same decisions, same transcript, byte for byte.

Rules live in [game-rules.md](../../../docs/projects/relay/game-rules.md), which is normative. This is its implementation, not its definition.

## Modules

| Module | What it holds |
|---|---|
| `rng.py` | splitmix64 + xorshift64*, shared with both earlier games. Every draw order here is a contract with the Java engine |
| `track.py` | Stage generation: three families, three tiers, and the `Stage`/`PublicStage` split that keeps tiers and answers out of a runner's reach |
| `deciders.py` | The `Runner` protocol, the read-only `RunnerView`, the `EscalationDesk` that meters the anchor, and the two bots |
| `game.py` | The turn loop: the clock, the shared quota, the seal, standings |
| `events.py` | Emission to the shared schema. No timestamps — transcripts must diff cleanly |
| `conformance.py` | Vector generation and checking (ADR-0002) |
| `cli.py` | `play`, `bench`, `sweep`, `track`, `validate`, `conformance` |

## Run it

```bash
uv run --directory projects/relay/engine-python pytest
```

One race, printed:

```bash
uv run --directory projects/relay/engine-python python -m relay_engine.cli play --seed 7
```

Read a seed's track, answers and tiers included — for understanding the generators, never for playing:

```bash
uv run --directory projects/relay/engine-python python -m relay_engine.cli track --seed 7
```

The pace bench behind [open question 25](../../../docs/open-questions.md):

```bash
uv run --directory projects/relay/engine-python python -m relay_engine.cli sweep --games 200
```

Cross-engine vectors — both engines must pass, or they prove nothing:

```bash
uv run --directory projects/relay/engine-python python -m relay_engine.cli conformance --check
```

## Two things worth knowing before changing anything

**The seal is structural, not a convention.** `Stage` carries the tier and the answer; `PublicStage` is what a runner ever sees, and it has neither field. If you find yourself adding one "just for the harness", that is the game's central decision being deleted.

**Escalation is performed by the engine, not reported by the runner.** A runner calls `ctx.desk.ask()`; the desk charges the shared quota and consults whatever anchor the game was configured with. So `escalated` in the transcript is a receipt. A harness passes its real anchor model in as `GameConfig.anchor` — a plain callable taking the *public* stage, which is how the engine stays free of model SDKs.

## Related

- [Game rules](../../../docs/projects/relay/game-rules.md) — normative
- [Engine design](../../../docs/projects/relay/engine-design.md) — the reasoning, and what a Java port must preserve
- [ADR-0011](../../../docs/decisions/adr-0011-project-three-relay.md) — why this game exists
