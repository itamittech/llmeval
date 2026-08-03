# Learning Java Through This Codebase

For readers who can already program — most likely in Python, having read [learning/python](../python/) — and want to read the Java half of this repo confidently.

This folder is **standalone**. Nothing imports it, no build depends on it, and every example runs with a bare JDK: no Maven, no dependencies, no project setup.

## Run anything

```bash
java learning/java/examples/01_records_and_classes.java
```

That works because a JDK can run a single `.java` file directly — no `javac`, no class files, no build tool. Each example prints its own explanation as it runs, and editing them and re-running is the point.

You need **JDK 21+**, the same version [the engine targets](../../projects/ludo/engine-java/README.md).

## Why this folder is unusual

Most Java tutorials teach you Java. This one has something better available: **the same program, written twice.**

[`engine-python`](../../projects/ludo/engine-python/) and [`engine-java`](../../projects/ludo/engine-java/) implement identical rules, produce byte-identical transcripts from the same seed, and are held to [the same 20 conformance vectors](../../shared/conformance/README.md). So every difference between them isolates a *language property* rather than a design choice — which is exactly the comparison a tutorial can't give you.

That is what these docs are built around.

## Suggested order

**0. [What all these files and folders are for](00-files-and-folders.md)** — `src/main/java`, why packages must match directories, `pom.xml`, `target/`, and what `mvnw` is. Start here if a Java project looks like unexplained ceremony.

**1. Run the examples**, in order. About five minutes each.

| | File | Covers |
|---|---|---|
| 01 | [`01_records_and_classes.java`](examples/01_records_and_classes.java) | `record` vs class, value equality, why "frozen" is shallow in both languages |
| 02 | [`02_interfaces_and_defaults.java`](examples/02_interfaces_and_defaults.java) | `interface` vs `Protocol`, `default` methods, and the dependency consequence |
| 03 | [`03_signed_shift.java`](examples/03_signed_shift.java) | `>>` vs `>>>` — reproduces the real bug that would have broken every vector |
| 04 | [`04_null_and_boxing.java`](examples/04_null_and_boxing.java) | `Integer` vs `int`, null, the `==` trap at 128, `EnumMap` |

**2. Read [the same engine, twice](01-same-engine-twice.md)** with both engines open. Module by module, what changed and why.

**3. Keep [the concept index](02-concept-index.md) open** while reading the Java source.

## Four things that surprise people coming from Python

**`==` means the opposite thing.** In Java `==` on objects asks "same object?" — Python's `is`. For value comparison you need `.equals()`. Getting this wrong is the classic Java bug, and [example 04](examples/04_null_and_boxing.java) shows the version that only breaks above 127.

**There is no monkey-patching.** Python's tests reach a hard-to-trigger rule by writing `game.dice = ScriptedDice(...)` on a live object. Java has no equivalent, so `Game` had to be *designed* with a seam. Code that didn't anticipate the need cannot be made testable from the test.

**Structural typing is gone.** A class with exactly the right methods is not a `Decider` unless it says `implements Decider`. That single word is why every Java agent must depend on the engine jar, and no Python agent does.

**Integers are fixed-width and signed.** A `long` wraps silently at 64 bits, and `>>` drags the sign bit along. Python's integers grow instead. This is the difference the engine's dice had to be written around — [example 03](examples/03_signed_shift.java).

## Related

- [engine-java README](../../projects/ludo/engine-java/README.md) — how to build and run it
- [engine-design.md](../../docs/projects/ludo/engine-design.md) — *why* the engine is shaped this way, with the Python→Java mapping table
- [learning/python](../python/) — the same material from the other side
- [learning/strands](../strands/) — the agent harness that sits on top of the Python engine
