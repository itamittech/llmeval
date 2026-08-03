# What All These Files and Folders Are For

A Java project looks like a lot of ceremony next to a Python one. Most of it is one idea repeated: **the build tool needs to find things by convention, so the layout is the configuration.**

## The tree

```
projects/ludo/engine-java/
├── pom.xml                          ← the whole build definition
├── mvnw, mvnw.cmd                   ← ✅ committed · the Maven wrapper
├── .mvn/wrapper/
│   └── maven-wrapper.properties     ← which Maven version to fetch
├── src/
│   ├── main/java/                   ← shipped code
│   │   └── com/llmeval/ludo/engine/
│   │       ├── Board.java
│   │       ├── Game.java
│   │       └── …
│   └── test/java/                   ← tests, same package, not shipped
│       └── com/llmeval/ludo/engine/
│           ├── ConformanceTest.java
│           └── …
└── target/                          ← 🚫 generated · never committed
```

Compare [learning/python/00](../python/00-files-and-folders.md): `src/ludo_engine/`, `tests/`, `pyproject.toml`, `.venv/`. Same three ideas — source, tests, build config — with more directory levels.

## `src/main/java` and `src/test/java`

Two source trees, compiled separately. `main` is what gets packaged into the jar; `test` is compiled and run but never shipped.

The split does real work: `ConformanceTest` can depend on JUnit while the engine itself has **zero** dependencies. In `pom.xml` that's `<scope>test</scope>`, which is the direct equivalent of Python's `[dependency-groups] dev`.

Both trees use the **same package**, which is why a test can reach a package-private member — how `ConformanceTest` calls `Conformance.forDigest` and how `RulesTest` reaches `Game`'s package-private constructor. Python has no such notion; a leading underscore is a request, not a boundary.

## Packages must match directories

`Board.java` declares:

```java
package com.llmeval.ludo.engine;
```

and therefore **must** live at `src/main/java/com/llmeval/ludo/engine/Board.java`. Not a convention — the compiler enforces it.

That's why the path is so deep. `com.llmeval.<project>.<stack>` is [this repo's naming rule](../../docs/architecture/repository-layout.md); the reverse-domain style exists so two unrelated libraries can both contain a `Board` without colliding.

Python's equivalent is much lighter: `from .board import ...` means "the module next door", and the package name is just the folder name.

## One public class per file

A `public class Board` must be in `Board.java`. Also compiler-enforced.

So Java tends toward many small files where Python has one module with several classes. `deciders.py` holds `StateView`, `TurnContext`, `Decider`, `FirstLegal` and `RandomBot`; the Java port spreads those across five files. Neither is better — but it's why the Java tree looks bigger for the same program.

## `pom.xml`

Maven's project file: coordinates, Java version, dependencies, plugins. The counterpart of `pyproject.toml`.

The three lines that matter most here:

```xml
<maven.compiler.release>21</maven.compiler.release>
```

The Java version to compile against. `release` rather than `source`/`target` because it also checks you aren't calling APIs that didn't exist in 21.

```xml
<scope>test</scope>
```

On the JUnit dependency: available when compiling and running tests, absent from the jar. The engine ships with no dependencies at all.

## `mvnw` — the wrapper

`mvnw` and `mvnw.cmd` are scripts that **download the right Maven version and run it**. That's why you can build this engine without installing Maven:

```bash
cd projects/ludo/engine-java && ./mvnw test
```

Committed on purpose: it pins the build tool the same way a lockfile pins dependencies, so a contributor's Maven version can't change the outcome.

`.mvn/wrapper/maven-wrapper.properties` says which version to fetch. This repo uses `distributionType=only-script`, so there's no `maven-wrapper.jar` in the tree — some projects commit one, which is a binary in source control that people reasonably object to.

Python's nearest equivalent is `uv` reading `.python-version` and `uv.lock`.

## `target/` — generated

Compiled `.class` files, the built jar, test reports. Gitignored, exactly like `__pycache__/` and `.venv/`.

Java compiles ahead of time to `.class` files containing **bytecode** — an instruction set for the JVM, not for your CPU. Python's `.pyc` files are the same idea, with one difference that matters: Python creates them silently as a cache, while `javac` is a step you run and can fail. A Python syntax error in an untouched file surfaces at import; a Java one stops the build.

Deleting `target/` is always safe. `./mvnw clean` does it for you.

## What is *not* here

**No `.venv`.** Java dependencies live in a shared cache at `~/.m2/repository`, versioned by coordinate, so two projects can use different versions of the same library without isolation. That's precisely what Python *cannot* do — it's why virtual environments are unavoidable there, and why [this repo needs three separate Python environments](../../docs/architecture/environment-strategy.md) but only one Maven cache.

**No `__init__.py`.** A Java package is a directory with matching `package` declarations. Nothing marks it.

**No `if __name__ == "__main__"`.** A class is runnable if it has `public static void main(String[])`. Here that's `Cli`, named in `pom.xml` so `./mvnw exec:java` finds it.

## Running things

| Task | Command |
|---|---|
| Tests | `./mvnw test` |
| The CLI | `./mvnw -q exec:java -Dexec.args="conformance --check"` |
| A single example in this folder | `java learning/java/examples/03_signed_shift.java` |

That last one needs no build tool at all — a JDK can run a single source file directly, compiling in memory. It's the closest Java gets to `python script.py`, and it's why these examples have no `pom.xml`.

## Related

- [The same engine, twice](01-same-engine-twice.md) — what actually changed in the port
- [learning/python/00](../python/00-files-and-folders.md) — the same tour from the Python side
- [engine-java README](../../projects/ludo/engine-java/README.md)
