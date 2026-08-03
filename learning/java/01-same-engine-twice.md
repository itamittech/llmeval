# The Same Engine, Twice

Two implementations of identical rules, producing byte-identical transcripts from the same seed. Every difference between them is therefore a *language* difference, not a design one — which makes this the most useful Java-vs-Python comparison in the repo.

Read with both open:

- [`engine-python/src/ludo_engine/`](../../projects/ludo/engine-python/src/ludo_engine/)
- [`engine-java/src/main/java/com/llmeval/ludo/engine/`](../../projects/ludo/engine-java/src/main/java/com/llmeval/ludo/engine/)

## The map

| Python | Java | Why |
|---|---|---|
| `board.py` | `Board.java`, `Color.java` | Java has no module-level functions; they become `static` members of a final class |
| `state.py` | `GameState`, `PlayerStats`, `Snapshot` | one public class per file |
| `moves.py` | `Moves`, `Move`, `Capture` | same split |
| `dice.py` | `Dice.java` | same algorithm, different integer arithmetic |
| `deciders.py` | `Decider`, `StateView`, `TurnStart`, `TurnContext`, `TurnEnd`, `FirstLegal`, `RandomBot` | one module → seven files |
| `events.py` | `EventSink.java` (+ nested sinks) | |
| `json` (stdlib) | `Json.java` | Java has no JSON in the JDK, and the engine takes no dependencies |
| `conformance.py` | `Conformance.java` | |
| `cli.py` | `Cli.java` | `argparse` → hand-rolled; no stdlib parser |

## 1. `Color` — a string became an enum

Python:

```python
Color = str
COLORS: Final[tuple[Color, ...]] = ("red", "green", "yellow", "blue")
```

Java:

```java
public enum Color {
    RED("red"), GREEN("green"), YELLOW("yellow"), BLUE("blue");
    public String label() { return label; }
}
```

The one place the port is deliberately *less* literal. `Color = str` is an alias with no enforcement — `to_square("purple", 3)` is a `KeyError` at runtime. The enum makes it a compile error.

The cost is a permanent two-way conversion: the event stream carries `"red"`, so every emission calls `.label()`. Forgetting one gives you `"RED"` in a transcript and a conformance failure — which is how you find out.

## 2. `Move` — frozen dataclass became a record

```python
@dataclass(frozen=True)
class Move:
    token: int
    frm: int
    to: int
```

```java
public record Move(int token, int frm, int to) {}
```

Both generate a constructor, equality, a hash and a readable `toString`. Both are needed for the same reason: `Game` validates an agent's choice with a set membership test, which requires value equality *and* a matching hash.

`frm` rather than `from` in both — `from` is a Python keyword. Java would allow `from`, but the name is carried across so the two read alike.

**Both are shallowly frozen.** A record field can't be reassigned; what it points at can still be mutated. Same trap as a frozen dataclass holding a list, and the reason `snapshot()` copies in both engines rather than storing references.

## 3. `Decider` — Protocol became interface

The most consequential line in the port.

```python
class Decider(Protocol):
    def choose(self, ctx: TurnContext) -> Move: ...
```

```java
public interface Decider {
    String name();
    Move choose(TurnContext ctx);
    default void negotiate(TurnStart start) {}
    default void reflect(TurnEnd end) {}
}
```

**Before you scroll:** translate `FirstLegal` to Java word for word — right methods, right signatures — but forget to write `implements Decider`. Is the result a `Decider`? And in Python, would the same omission even *be* an omission?

In Python an agent satisfies this **by shape**: no import, no inheritance, no compile-time relationship between the engine package and the agent package at all. In Java it satisfies it **by declaration**, so every agent needs `ludo-engine` on its classpath — the forgetful translation above is just a class that happens to resemble one.

That is why the two Python stacks can share one engine while keeping [genuinely separate dependency trees](../../docs/architecture/environment-strategy.md), and the Java stack cannot. It's a [capability-matrix](../../docs/architecture/stack-comparison.md) finding, not trivia. [Example 02](examples/02_interfaces_and_defaults.java) demonstrates it.

**The optional hooks diverge too.** Python uses two extra `@runtime_checkable` Protocols and the engine asks `isinstance(decider, Negotiator)` — a method-presence check. Java uses `default` methods, so the method always exists and there's nothing to ask. The Java version is tidier; the Python version is more flexible, because a `Decider` there needn't know the hooks exist.

## 4. `Dice` — the same algorithm, different arithmetic

```python
x = (x ^ (x << 25)) & MASK64      # Python ints grow; mask them back down
```

```java
x ^= x << 25;                      // long wraps at 64 bits for free
x ^= x >>> 27;                     // but >> would drag the sign bit in
```

**Before you scroll:** dice state is a signed `long`, negative about half the time. If a port writes `>>` where it needed `>>>`, what happens — a compile error, an exception, or something worse?

Python's integers are arbitrary-precision, so the algorithm needs `& MASK64` after anything that could grow, and its `>>` is always logical. Java's `long` wraps for free — the masks vanish — but it is *signed*, so every right shift must be `>>>`.

The answer is *something worse*: nothing happens. One `>>` compiles, runs, and produces plausible 1–6 dice — just a different game, discovered only when every conformance vector fails. [Example 03](examples/03_signed_shift.java) reproduces it. That silence is the lesson: the bugs worth designing tests around are the ones with no symptom.

## 5. `Json` — the stdlib gap

`import json` has no Java equivalent, and the engine takes no dependencies, so `Json.java` is hand-rolled: a canonical writer, a compact writer, and a small parser.

That is not asceticism. Two engines that must agree byte for byte, across languages and across years, should not be able to change behaviour because something upstream was bumped.

**Two writers, not one** — and this is the subtle part. `canonical()` sorts keys (matching Python's `sort_keys=True`) and is what digests are taken over. `compact()` preserves insertion order, matching Python's transcript writer, which does *not* sort. Using the sorted form everywhere still passes conformance — the digest sorts anyway — while silently making transcripts non-comparable between engines.

## 6. Standings — where a tie-break nearly diverged

```python
rest.sort(key=lambda c: (state.tokens_home(c), state.progress(c)), reverse=True)
```

```java
rest.sort(Comparator.comparingInt(this::tokensHome)
        .thenComparingInt((Color c) -> progress(c))
        .reversed());
```

Python's `reverse=True` reverses the **comparison**, not the list, so equal entries keep their original order. `Comparator.reversed()` on Java's stable sort behaves identically.

Reversing a sorted list instead — the obvious-looking translation — would flip ties and produce different standings in exactly the games where two players are level.

## 7. Testing — the difference that changes the design

Python:

```python
game = Game(GameConfig(seed=1, max_turns=1), sink)
game.dice = ScriptedDice([6, 6, 6])          # replace it on a live object
```

Java can't do that. So `Game` carries a package-private constructor:

```java
Game(GameConfig config, EventSink sink, IntSupplier die) { … }
```

The rule is equally testable in both — **but only because the Java side anticipated the need.** A production class written without that seam cannot be made testable from the test, and that constraint will reappear when the Spring AI stack needs to inject a scripted model client, which is exactly what [the harness contract](../../docs/projects/ludo/harness-contract.md) requires.

This is the deepest lesson in the port: in Python, testability can be retrofitted; in Java, it is a design decision made in advance.

## What the port taught the repo

Three things surfaced only because a second engine existed — the argument for building one:

1. **The conformance vectors were unsatisfiable by any engine but the one that wrote them.** `game_started` records `engine.language`, the digest covered it, and a perfect Java port failed all twenty vectors on one string. See [the conformance README](../../shared/conformance/README.md).
2. **One serialiser wasn't enough** — see §5.
3. **Test seams must be designed in advance** — see §7.

## Check yourself

Answers are one click back — a surprising link marks the section to reread.

1. Two byte-for-byte-identical agent classes, one Python, one Java. Why can one be a `Decider` while the other is not? → [§3](#3-decider--protocol-became-interface)
2. One `>>` slips into `Dice`. What fails, and how loudly? → [§4](#4-dice--the-same-algorithm-different-arithmetic)
3. Python reverses a sort with `reverse=True`, Java with `.reversed()`. What property must both preserve for the standings to agree? → [§6](#6-standings--where-a-tie-break-nearly-diverged)
4. Why does the Java `Game` need a constructor the Python one never wrote? → [§7](#7-testing--the-difference-that-changes-the-design)

## Related

- [engine-design.md](../../docs/projects/ludo/engine-design.md) — why these shapes were chosen
- [class-design.md](../../docs/projects/ludo/class-design.md) — the object graph as diagrams
- [Concept index](02-concept-index.md) — syntax lookup
