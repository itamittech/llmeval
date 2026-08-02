# LUDO Engine — Design Notes

Why the engine is shaped the way it is. [The engine README](../../../projects/ludo/engine-python/README.md) covers *how to use it*; this covers *why*, and what a Java port has to preserve.

Written for a reader who can code but hasn't necessarily written much Python.

## The shape

The engine defines 17 classes, which sounds like a lot. Only three of them are classes in the object-oriented sense — the rest are records or plug-in points.

| Kind | Classes | What they're for |
|---|---|---|
| **Records** | `Move` `Capture` `Snapshot` `TurnStart` `TurnContext` `TurnEnd` `PlayerStats` `GameConfig` `Outcome` | Named bundles of fields. No behaviour. |
| **Stateful objects** | `GameState` `Dice` `Game` | Own something that changes over time. |
| **Extension points** | `Decider` `Negotiator` `Reflector` `FirstLegal` `RandomBot` · `EventSink` `ListSink` `JsonlSink` `TeeSink` | Where other code plugs in. |

## Records

Python's `@dataclass` generates the constructor, `__repr__`, and `__eq__` from field declarations:

```python
@dataclass(frozen=True)
class Move:
    token: int
    frm: int
    to: int
```

The alternatives were a tuple `(0, 3, 5)` or a dict `{"token": 0, ...}`. The dataclass costs one line and buys readable access, typo safety, and type checking.

### `frozen=True` is load-bearing, not decoration

[`game.py`](../../../projects/ludo/engine-python/src/ludo_engine/game.py) validates a proposed move like this:

```python
allowed = set(moves)
...
if move in allowed:
    return move
```

Sets require hashable elements. `frozen=True` generates `__hash__`; a mutable dataclass is unhashable and that line raises `TypeError`. Immutability also means an agent cannot tamper with a `Move` it was handed.

### The shallow-freeze trap

**`frozen=True` freezes the *fields*, not what they point at.** `Snapshot` is frozen but holds dicts and lists, which remain mutable. That is exactly why [`state.py`](../../../projects/ludo/engine-python/src/ludo_engine/state.py) copies on both sides:

```python
def snapshot(self) -> Snapshot:
    return Snapshot(tokens={c: list(p) for c, p in self.tokens.items()}, ...)

def restore(self, snap: Snapshot) -> None:
    self.tokens = {c: list(p) for c, p in snap.tokens.items()}
```

Store the references directly and the "snapshot" would mutate along with the live board — the three-sixes rollback would silently do nothing, and no test of the *rule* would catch it because the rule code would look correct.

## Stateful objects

| Class | Owns | Why it isn't a function |
|---|---|---|
| `Dice` | 64-bit PRNG state | Each roll advances it. A function would need a global or a closure. As a class, several independent dice coexist — the game has one, and each `RandomBot` has its own. |
| `GameState` | Token positions, counters, finish order | A dict plus queries: `tokens_home()`, `progress()`, `has_finished()`. The queries belong with the data. |
| `Game` | State, dice, turn number, rotation, sink | Could be one long function, but the turn loop decomposes into `_play_turn`, `_decide`, `_apply`, which share context through `self` instead of passing six arguments around. |

## Extension points

This is where the design actually lives.

### `Decider` — a Protocol, not a base class

```python
class Decider(Protocol):
    def choose(self, ctx: TurnContext) -> Move: ...
```

`Protocol` is **structural typing**: duck typing a type checker can verify. Anything with a matching `choose` method satisfies it — no import, no inheritance:

```python
class MyLLMAgent:
    def choose(self, ctx):
        return ctx.legal_moves[0]
```

That is a valid `Decider`.

This is the whole reason the engine stays dependency-free. The Strands agent and the LangGraph agent live in separate packages with [deliberately separate dependency trees](../../architecture/environment-strategy.md); neither needs to inherit from the engine to plug in. The engine, in turn, never imports anything about agents or models.

The tests demonstrate it — `Cheater` and `Broken` in [`test_game.py`](../../../projects/ludo/engine-python/tests/test_game.py) are plain classes with one method and no relationship to `Decider`.

#### Two optional siblings

An agent harness also needs to talk to other players and to write memory, and neither belongs inside `choose`. Two further Protocols mark those call sites:

```python
@runtime_checkable
class Negotiator(Protocol):
    def negotiate(self, start: TurnStart) -> None: ...

@runtime_checkable
class Reflector(Protocol):
    def reflect(self, end: TurnEnd) -> None: ...
```

| Hook | Frequency | Required |
|---|---|---|
| `negotiate` | once per **turn**, before the first roll | no |
| `choose` | once per **roll** | **yes** |
| `reflect` | once per **turn**, after it resolves | no |

**The per-turn / per-roll split is the point.** A six or a capture earns another roll, so `choose` can run several times in one turn. If negotiation ran with it, an agent on a hot streak would get a free multiplier on both influence and cost — see the [harness contract](harness-contract.md).

`runtime_checkable` makes `isinstance(decider, Negotiator)` a method-presence check, which is how the engine decides whether to call. Optional matters: `RandomBot` and `GreedyBot` have no model behind them, and keeping them valid is what keeps the engine fast to test and [`turn_order.py`](../../../projects/ludo/engine-python/examples/turn_order.py) runnable.

**Neither hook is wrapped in try/except, unlike `choose`.** The engine absorbs a failure only where it has a defined in-game meaning: a bad `choose` forfeits the turn, and a forfeit is a real outcome that gets recorded and scored. A provider erroring mid-negotiation has no such meaning, so it belongs to the harness that made the call — swallowing it here would produce a transcript that lies about what happened.

### `EventSink` — the one real inheritance hierarchy

A template method. The base class owns sequence numbering; subclasses choose only a destination:

```python
class EventSink:
    def emit(self, type_, payload, turn=0):
        event = {"seq": self._seq, "turn": turn, "type": type_, "payload": payload}
        self._seq += 1
        self._write(event)          # subclasses implement this

    def _write(self, event):
        raise NotImplementedError
```

`ListSink` appends to a list, `JsonlSink` writes a line, `TeeSink` fans out to several sinks.

**`TeeSink` calls `sink._write(event)`, not `sink.emit(...)`** — a subtlety worth preserving in any port. Routing through `emit` would make each child assign its own sequence number, and the outputs would drift apart. The CLI tees to a list and a file at once, and contiguous `seq` is a schema requirement.

## How one turn executes

```
Game._play_turn(color, decider)
  ├─ emit turn_started
  ├─ decider.negotiate(TurnStart)         ← optional; ONCE per turn, before any roll
  └─ Game._roll_loop(color, decider, view)
     ├─ snapshot = state.snapshot()       ← for possible three-sixes rollback
     └─ loop:
          ├─ die = dice.roll()            ← engine controls this, never the agent
          ├─ emit dice_rolled
          ├─ if third consecutive six → state.restore(snapshot); RETURN three_sixes
          ├─ moves = legal_moves(state, color, die)
          ├─ if none → RETURN no_legal_move
          ├─ move = decider.choose(ctx)   ← the ONLY point an agent influences the GAME
          │    └─ not in legal set? emit illegal_move_rejected, retry once, else forfeit
          ├─ apply_move → emit move_made [+ token_captured] [+ token_home]
          ├─ if six or capture → emit extra_roll_granted; CONTINUE
          └─ RETURN moved
  ├─ emit turn_ended(reason)
  └─ decider.reflect(TurnEnd)             ← optional; ONCE per turn, after it resolves
```

The agent's entire influence over the *game* is still one line: choosing from a list the engine already validated. `negotiate` and `reflect` change nothing on the board — they exist so a harness can talk and remember at the right moments, and everything they produce reaches the world as events, not as state.

`_roll_loop` returns the reason rather than emitting `turn_ended` itself, so the turn has exactly one exit and `reflect` cannot be skipped down some branch. That restructure is behaviour-preserving: the regenerated seed-7 transcript is byte-identical to the committed sample.

## What makes replay work

Three properties, all of which a port must keep:

1. **Seeded, engine-owned dice.** Agents never roll. The seed is recorded in `game_started`.
2. **Stable move ordering.** `legal_moves` returns moves ordered by token index. `FirstLegal` and the [conformance vectors](../../../shared/conformance/README.md) depend on it.
3. **No timestamps in engine events.** Same seed plus same decisions produces a byte-identical transcript, so two runs can be diffed mechanically.

## One honest limit on the guardrail

[ADR-0004](../../decisions/adr-0004-structural-guardrails.md) says cheating is structurally impossible, which lets content guardrails stay lenient. That is unambiguously true **of the LLM** — it only ever returns a move choice, and the engine rejects anything illegal.

The decider *code* wrapping the LLM used to be a different story. `TurnContext.state` was a live reference to the mutable `GameState`, so a decider could simply write the board:

```python
ctx.state.tokens["red"] = [56, 56, 56, 56]     # once possible; no longer
```

**Closed** by handing deciders a `StateView` instead ([open question 15](../../open-questions.md)). Collections come back as tuples, attribute assignment raises, and `stats()` returns a copy:

```python
ctx.state.tokens("red")      # -> (0, 5, -1, 56)   a tuple; item assignment fails
ctx.state.board()            # -> a fresh dict of tuples
ctx.state.tokens = {}        # -> AttributeError
```

**Still honest about what this is.** It stops mistakes, not determined attackers. Python offers no hard in-process boundary, and code reaching for the private `_state` still gets through. What changed is that cheating now requires obviously-wrong code a reviewer will spot, rather than a plausible-looking typo. The guarantee that carries the real weight is unchanged: the LLM can only return a move choice, and the engine validates it regardless.

## Porting to Java

| Python | Java |
|---|---|
| `@dataclass(frozen=True)` | `record` |
| `@dataclass` (mutable) | mutable class |
| `Protocol` | `interface` — but Java needs an explicit `implements` |
| `EventSink` base class | `abstract class` |
| `dict[Color, list[int]]` | `EnumMap<Color, int[]>` |

The `Protocol` → `interface` difference is a genuine framework-comparison data point, not just trivia: in Python an agent satisfies the contract by shape alone, so the engine and the agent packages need no compile-time relationship at all.

### Traps

**The dice are the sharpest one.** Python ints are arbitrary-precision and need explicit `& MASK64`; Java's `long` wraps for free. But Java's `>>` is *signed* — you must use `>>>`:

```java
long x = state;
x ^= x >>> 12;
x ^= x << 25;
x ^= x >>> 27;
state = x;
return (int) (((x * 0x2545F4914F6CDD1DL) >>> 33) % 6) + 1;
```

One `>>` instead of `>>>` and every conformance vector fails — which is precisely what the vectors exist to catch.

**Everything else that must match exactly:** move ordering (token index ascending), event type names and payload field names, and the colour-relative position encoding (`-1` base, `0`–`50` circuit, `51`–`55` home column, `56` home). JSON key *order* does not matter — the digest sorts keys — but names and values do.

## Related

- [Class design](class-design.md) — the same structure as diagrams: object graph, call flow, module layering
- [Harness contract](harness-contract.md) — what an agent stack must do around this engine. The `negotiate` / `reflect` hooks above exist because that spec requires them; the Java engine must match before `stack-springai`
- [Engine README](../../../projects/ludo/engine-python/README.md) — usage and module map
- [Game rules](game-rules.md) — the normative spec, including resolved edge cases
- [Event schema](../../../shared/schemas/README.md) — the output contract
- [Conformance vectors](../../../shared/conformance/README.md) — how the two engines are kept honest
