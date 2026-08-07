# alibi-engine (Python)

The deterministic ALIBI referee and case generator. **No LLM anywhere** — no
SDK import, no network call. Same seed, same decisions, byte-identical
transcript, which is what the [conformance vectors](../../../shared/conformance/)
hold both engines to ([ADR-0002](../../../docs/decisions/adr-0002-engine-per-language.md)).

Shared by the Strands and LangGraph stacks; the Java twin under
[`engine-java`](../engine-java/) serves Spring AI.

## Module map

| Module | What it owns |
|---|---|
| [`rng.py`](src/alibi_engine/rng.py) | Portable randomness (splitmix64 + xorshift64*) — the draw order is spec, shared with the Java engine |
| [`case.py`](src/alibi_engine/case.py) | The 19 elements, the cast, the sealed triple, the even four-exhibit deal |
| [`archive.py`](src/alibi_engine/archive.py) | The generated corpus — truthful exonerations, red herrings, counters, gossip — and the baseline integer-scored keyword retriever |
| [`deciders.py`](src/alibi_engine/deciders.py) | The `Detective` protocol, per-detective read-only views, the search budget, and the bots (`elimination-bot` is the conformance decider) |
| [`game.py`](src/alibi_engine/game.py) | The referee: suggest → refute → accuse → conclude, engine-mediated refutation, standings |
| [`events.py`](src/alibi_engine/events.py) | The shared event stream ([schema](../../../shared/schemas/alibi-event.schema.json), [ADR-0003](../../../docs/decisions/adr-0003-shared-event-stream.md)) |
| [`conformance.py`](src/alibi_engine/conformance.py) | Cross-engine vectors; the digest includes corpus bytes via `archive_generated` |
| [`cli.py`](src/alibi_engine/cli.py) | `play` · `bench` · `validate` · `conformance` |

## Run it

```bash
uv run --directory projects/alibi/engine-python pytest
```

```bash
uv run --directory projects/alibi/engine-python python -m alibi_engine.cli play --seed 7
```

```bash
uv run --directory projects/alibi/engine-python python -m alibi_engine.cli bench --games 200
```

Design rationale: [engine-design.md](../../../docs/projects/alibi/engine-design.md).
Rules it implements: [game-rules.md](../../../docs/projects/alibi/game-rules.md).
