# Conformance Vectors

[ADR-0002](../../docs/decisions/adr-0002-engine-per-language.md) keeps **one engine per language** — Python shared by both Python stacks, Java for Spring AI — rather than one per stack. These vectors are what stop the two engines drifting apart.

## How they work

Each vector records a **seed** and the result of playing that game with the deterministic `first-legal` decider (always take the first legal move, ordered by token index).

Because both the dice and the decider are deterministic, the seed alone reproduces the entire game — a vector needs no move list. Both engines must produce:

- the same `digest` — SHA-256 over every event in canonical form
- the same `reason`, `turns_played`, `events` count, and `standings`

The digest covers the full event stream, so any divergence in rules, ordering, or dice shows up immediately.

This only works because [`dice.py`](../../projects/ludo/engine-python/src/ludo_engine/dice.py) specifies its own portable PRNG. Python's `random` and Java's `Random` produce different sequences from the same seed, which would have made cross-language conformance impossible.

## Checking

```bash
just conformance
```

Runs in CI. No model calls, no cost.

## Regenerating

```bash
just conformance-generate
```

**Only after a deliberate rule change.** An unexpected diff in `vectors.json` is a bug, not a refresh — regenerating to make a failing check pass destroys the guarantee these vectors exist to provide.

When rules do change: update [game-rules.md](../../docs/projects/ludo/game-rules.md) first, then both engines, then regenerate.
