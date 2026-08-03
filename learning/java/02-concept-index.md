# Concept Index

Look up a piece of Java syntax, see what it means, what the Python equivalent is, and where the engine uses it.

## Declarations

| Java | Means | Python | Used in |
|---|---|---|---|
| `public record Move(int a, int b) {}` | Immutable data carrier; generates constructor, accessors, `equals`, `hashCode`, `toString` | `@dataclass(frozen=True)` | `Move`, `Capture`, `Snapshot` |
| `public final class Board` | Cannot be subclassed | *(no equivalent)* | `Board`, `Dice`, `Game` |
| `private Board() {}` | Private constructor = "never instantiate this, it's a namespace" | a module | `Board`, `Moves`, `Json` |
| `static` | Belongs to the class, not an instance | a module-level function | `Board.toSquare` |
| `public enum Color { RED("red") }` | Fixed set of instances, with fields | `Color = str` + a tuple | `Color` |
| `interface Decider` | Contract that must be **declared** with `implements` | `Protocol` (satisfied by shape) | `Decider` |
| `default void negotiate(…) {}` | Interface method with a body — optional to override | an optional Protocol method | `Decider` |
| `@Override` | "I mean to replace an inherited method." Compiler error if not | *(no equivalent)* | the sinks |

## Types and null

| Java | Means | Python | Used in |
|---|---|---|---|
| `int` | 32-bit primitive. **Cannot be null** | `int` | positions, dice |
| `Integer` | Boxed object. Can be null | `int \| None` | `Board.toSquare` |
| `long` | 64-bit signed, wraps silently on overflow | `int` (grows instead) | `Dice` |
| `Object` | Any reference type | `object` / `Any` | event payload values |
| `var x = new ArrayList<Move>()` | Infer the type from the right side | just a name | throughout |
| `List<Move>` | Generic — a list *of* moves, checked at compile time | `list[Move]` | `Moves.legalMoves` |

## Collections

| Java | Means | Python | Used in |
|---|---|---|---|
| `List.of(a, b)` | **Immutable** list | `(a, b)` | `Moves.applyMove` returns |
| `new ArrayList<>()` | Mutable list | `[]` | move accumulation |
| `Map<K,V>` / `new LinkedHashMap<>()` | Map, insertion-ordered | `dict` | event payloads |
| `new EnumMap<>(Color.class)` | Map keyed by enum; array-backed, ordered by declaration | `dict[Color, …]` | `GameState.tokens` |
| `new HashSet<>(moves)` | Set; needs `hashCode`/`equals` | `set(moves)` | `Game.decide` validation |
| `map.forEach((k, v) -> …)` | Iterate with a lambda | `for k, v in d.items()` | `Snapshot.copyTokens` |
| `array.clone()` | Shallow copy of an array | `list(xs)` | `StateView.tokens` |

## Control flow and operators

| Java | Means | Python | Used in |
|---|---|---|---|
| `==` on objects | **Same object?** | `is` | never, on boxed values |
| `.equals(other)` | Same value? | `==` | `Moves.applyMove` |
| `>>` | Arithmetic shift — **copies the sign bit** | *(no equivalent)* | never — see below |
| `>>>` | Logical shift — shifts in zeros | `>>` on a masked value | `Dice`, every right shift |
| `cond ? a : b` | Conditional expression | `a if cond else b` | `Game.rollLoop` |
| `switch (x) { case A -> … }` | Switch **expression**, arrow form, no fall-through | `match` / if-chain | `Cli.main`, `Json.write` |
| `case String s ->` | Pattern matching: test and bind in one | `isinstance` + assign | `Json.write` |
| `for (int p : positions)` | Iterate values | `for p in positions` | throughout |

## Text

| Java | Means | Python | Used in |
|---|---|---|---|
| `"""…"""` | Text block — multi-line string literal | `"""…"""` | `Cli` usage text |
| `String.format("%02x", b)` | Format a string | f-string / `%` | `Conformance.digest` |
| `System.out.printf(…)` | Print with a format | `print(f"…")` | `Cli` |
| `sb.append(x)` on `StringBuilder` | Efficient string building | `"".join(parts)` | `Json`, `Dice` tests |

## The three that repay real attention

### `interface` vs `Protocol` — [example 02](examples/02_interfaces_and_defaults.java)

```java
class LooksRight { public Move choose(TurnContext ctx) { … } }   // NOT a Decider
```

Right methods, right signatures, still not a `Decider` — it never wrote `implements`. The identical Python class *is* a `Decider`.

The consequence is architectural, not cosmetic: every Java agent must depend on the engine jar, and no Python agent does. → [same engine, twice §3](01-same-engine-twice.md)

### `>>` vs `>>>` — [example 03](examples/03_signed_shift.java)

```java
x ^= x >>> 27;   // correct
x ^= x >> 27;    // compiles, runs, produces a different game
```

Java's `long` is signed and there is no unsigned variant, so `>>` drags the sign bit in. In a PRNG, hash, or checksum that is always a bug — and a silent one, because the output still looks fine. → [same engine, twice §4](01-same-engine-twice.md)

### `Integer` vs `int` — [example 04](examples/04_null_and_boxing.java)

```java
Integer square = Board.toSquare(color, position);   // null when off the circuit
if (square != null && …)                            // check before using
```

`int` has no spare value meaning "absent" — 0 is a real square. Boxing brings null back, and with it the `==` trap: boxed `Integer`s are cached from −128 to 127, so `==` accidentally works for small values and silently stops above 127.

## Where to look in the engine

| Read this | To see |
|---|---|
| [`Color.java`](../../projects/ludo/engine-java/src/main/java/com/llmeval/ludo/engine/Color.java) | The smallest file. An enum with a field. |
| [`Board.java`](../../projects/ludo/engine-java/src/main/java/com/llmeval/ludo/engine/Board.java) | Static methods and constants — a Python module, translated |
| [`Move.java`](../../projects/ludo/engine-java/src/main/java/com/llmeval/ludo/engine/Move.java) | A one-line record |
| [`Decider.java`](../../projects/ludo/engine-java/src/main/java/com/llmeval/ludo/engine/Decider.java) | The interface, with two `default` hooks |
| [`Dice.java`](../../projects/ludo/engine-java/src/main/java/com/llmeval/ludo/engine/Dice.java) | Bit manipulation, and why every shift is `>>>` |
| [`Json.java`](../../projects/ludo/engine-java/src/main/java/com/llmeval/ludo/engine/Json.java) | Pattern-matching `switch`, recursion, `StringBuilder` |
| [`Game.java`](../../projects/ludo/engine-java/src/main/java/com/llmeval/ludo/engine/Game.java) | Everything at once — the turn loop |

## Beyond this engine

Java features the engine deliberately doesn't use: inheritance beyond `EventSink`'s one hierarchy, generics you declare yourself (`<T>`), streams beyond a couple of one-liners, `Optional`, threads, annotations you write, and reflection.

`Optional<Integer>` is the interesting omission — it's the modern answer to nullable returns, and `Board.toSquare` uses a nullable `Integer` instead. The reason is the wire format: that value becomes JSON `null`, and `Optional` would need unwrapping at every call site for no gain. Worth knowing it exists and why it wasn't used.
