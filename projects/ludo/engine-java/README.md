# LUDO Engine (Java)

Deterministic Ludo rules engine. **JDK only** — no LLM SDKs, no network, no JSON library.

The second of two engines ([ADR-0002](../../../docs/decisions/adr-0002-engine-per-language.md)): this one serves the Spring AI stack, the [Python engine](../engine-python/README.md) serves both Python stacks. They are kept from drifting by [shared conformance vectors](../../../shared/conformance/README.md), and they agree — same seed, byte-identical transcript.

> **Reading this to understand the design?** [engine-design.md](../../../docs/projects/ludo/engine-design.md) explains *why* the engine is shaped this way, with a Python→Java mapping table. This README is the practical reference.
>
> **New to Java, or reading it against the Python engine?** [learning/java](../../../learning/java/) walks the port module by module, with runnable examples for the traps — including the `>>` vs `>>>` bug reproduced end to end.

## Build and test

Maven, via the committed wrapper — no global install needed:

```bash
./mvnw test
```

The wrapper is `distributionType=only-script`, so there is no `maven-wrapper.jar` in the repo; it fetches Maven itself on first run.

## Commands

Play one random-bot game and record it:

```bash
./mvnw -q exec:java -Dexec.args="play --seed 7 --out ../games/java-seed7.jsonl"
```

Game-length statistics:

```bash
./mvnw -q exec:java -Dexec.args="bench --games 500"
```

Cross-engine conformance — the check that matters:

```bash
./mvnw -q exec:java -Dexec.args="conformance --check"
```

**`validate` is deliberately absent.** Checking a transcript against the JSON Schema needs a schema library, and this engine has no dependencies. The [Python CLI](../engine-python/README.md) owns that job; transcripts are engine-neutral, so nothing is lost by validating them there.

## Layout

| Class | Role | Python counterpart |
|---|---|---|
| `Board` | Geometry, coordinate mapping, safe squares | `board.py` |
| `Color` | The four players, in turn order | `Color = str` + `COLORS` |
| `GameState`, `PlayerStats`, `Snapshot` | State, snapshots, standings | `state.py` |
| `Moves`, `Move`, `Capture` | The rulebook | `moves.py` |
| `Dice` | Portable seeded PRNG | `dice.py` |
| `Game`, `GameConfig`, `Outcome` | Turn loop, extra rolls, three-sixes, turn cap | `game.py` |
| `Decider`, `StateView`, `TurnStart`/`TurnContext`/`TurnEnd`, `FirstLegal`, `RandomBot` | Agent plug-in points | `deciders.py` |
| `EventSink` (+ `ListSink`, `JsonlSink`, `TeeSink`) | Event emission | `events.py` |
| `Json` | Canonical serialisation and a minimal parser | `json` from the stdlib |
| `Conformance` | Cross-engine vector checking | `conformance.py` |
| `Cli` | `play`, `bench`, `conformance` | `cli.py` |

## What the port had to get exactly right

**The dice.** Python integers are arbitrary-precision and mask explicitly; Java's `long` wraps for free, so the masks vanish — but Java's `>>` is arithmetic and copies the sign bit. Every right shift in `Dice` must be `>>>`. `DiceTest` pins four sequences produced by the Python engine, so the mistake fails immediately with a readable message rather than as an opaque digest mismatch.

**Two JSON writers, not one.** `Json.canonical` sorts keys, matching Python's `sort_keys=True` — that is what digests are taken over. `Json.compact` preserves insertion order, matching Python's transcript writer, which does *not* sort. Using the sorted form for transcripts would produce a file that is equally valid, equally schema-conformant, and no longer byte-comparable with the Python engine's output.

**Standings tie-breaks.** Python's `sort(reverse=True)` reverses the *comparison*, so equal entries keep their original order. `Comparator.reversed()` on Java's stable sort behaves the same way; reversing a sorted list instead would flip ties.

**No dependencies, on purpose.** Two engines that must agree byte for byte across languages and across years should not be able to change behaviour because something upstream was bumped. That is why `Json` is hand-rolled rather than Jackson.

## Two genuine language differences

Not stylistic — they change what the code can do, and both are recorded in the [capability matrix](../../../docs/architecture/stack-comparison.md).

**`Protocol` vs `interface`.** In Python an agent satisfies `Decider` by shape alone: no import, no inheritance, no compile-time relationship between the engine and the agent package. Java needs an explicit `implements`, so every agent must depend on this jar. The Python stacks can therefore keep [genuinely separate dependency trees](../../../docs/architecture/environment-strategy.md) in a way the Java stack cannot.

**Test seams must be designed in advance.** Python's tests reach a rule like three-sixes cancellation by assigning `game.dice` on a live object. Java has no such escape hatch, so `Game` carries a package-private constructor taking an `IntSupplier`. The rule is equally testable in both — but only because the Java side anticipated the need, and code that did not anticipate it cannot be retrofitted from the test.

## Tests

```bash
./mvnw test
```

`ConformanceTest` is the one that matters: it replays all 20 shared vectors, and separately confirms the checker **fails** on a tampered vector — a check nobody has watched fail proves nothing. `RulesTest` mirrors the Python suite's edge cases so a rules divergence is caught with a readable message rather than as a digest mismatch.
