# RELAY engine (Java)

The same race engine as [engine-python](../engine-python/README.md), in Java. JDK only — no LLM SDKs, no network, no JSON library. Held to the same [conformance vectors](../../../shared/conformance/README.md), which is the entire reason there are two ([ADR-0002](../../../docs/decisions/adr-0002-engine-per-language.md)).

Rules live in [game-rules.md](../../../docs/projects/relay/game-rules.md), which is normative for both engines.

## Run it

```bash
./mvnw -B test
```

```bash
./mvnw -q -B compile exec:java -Dexec.args="conformance --check"
```

```bash
./mvnw -q -B compile exec:java -Dexec.args="play --seed 7"
```

Vector *generation* lives only in Python. This engine is held to the expectations; it does not get to write them.

## What the port had to preserve

Everything on [engine-design's list](../../../docs/projects/relay/engine-design.md#what-a-port-must-preserve), and two of them bit:

**Unsigned shifts.** Python's ints are unbounded and Java's `long` is signed, so every `>>` in the RNG is `>>>` here. A signed shift sign-extends and the two engines diverge on roughly half of all states — silently, and only for some seeds.

**`Map.of` is unordered.** The first version built each `track_generated` stage from `Map.of(...)` and copied it into a `LinkedHashMap`, which preserves whatever arbitrary order the factory happened to produce. Conformance still passed, because the digest sorts keys — and the raw transcript stopped matching Python's byte for byte. Found by diffing the two files, not by the vectors, and now pinned by a test that asserts key *order*.

## The proof

Same seed, both engines, one command each:

```bash
./mvnw -q -B compile exec:java -Dexec.args="play --seed 7 --out ../../../seed7-java.jsonl"
```

```bash
uv run --directory projects/relay/engine-python python -m relay_engine.cli play --seed 7 --out seed7-python.jsonl
```

The two files differ on **one line and one field**: `game_started.engine.language`. That is the field the digest deliberately excludes, and every other byte — 139 events, ten generated stage prompts, forty turns of arithmetic — is identical.

## Related

- [engine-python](../engine-python/README.md) — the reference implementation and the module map
- [Engine design](../../../docs/projects/relay/engine-design.md) — the reasoning both engines implement
- [Conformance vectors](../../../shared/conformance/README.md) — what stops the two drifting apart
