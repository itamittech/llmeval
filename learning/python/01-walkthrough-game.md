# Walkthrough: the `Game` class, line by line

`Game` is the most concept-dense class in the engine — it's the only one that combines state, control flow, exception handling, and the plug-in protocol. If you can read this file, you can read the rest of the engine.

Source: [`projects/ludo/engine-python/src/ludo_engine/game.py`](../../projects/ludo/engine-python/src/ludo_engine/game.py) (210 lines)

Open it beside this document. Everything below quotes it exactly.

---

## The file header

```python
"""The turn loop.

Drives a game to completion or to the turn cap, emitting the shared event
stream as it goes. Knows nothing about agents beyond the `Decider` protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .board import COLORS, HOME, Color, to_square
from .deciders import Decider, TurnContext
```

| Line | What's happening |
|---|---|
| `"""The turn loop..."""` | A **docstring**. A string as the first thing in a file/class/function is documentation, retrievable at runtime as `game.__doc__`. Not a comment — it's a real object attached to the module. |
| `from __future__ import annotations` | Makes Python store type hints as *strings* instead of evaluating them. Lets you reference a class before it's defined, and costs nothing at import. Boilerplate in modern Python — see [example 06](examples/06_type_hints_and_errors.py). |
| `from dataclasses import dataclass, field` | Imports two specific names. Now you write `dataclass`, not `dataclasses.dataclass`. |
| `from .board import ...` | The **leading dot** means "the `board` module *next to this one*", not some `board` package installed globally. Relative imports keep a package self-contained. |

```python
ENGINE_VERSION = "0.1.0"

#: Consecutive sixes that forfeit the turn and revert everything done in it.
SIX_LIMIT = 3
```

`ALL_CAPS` signals a constant. Python has no `const` — nothing stops you reassigning `SIX_LIMIT`. It's a convention, like the leading underscore for "private".

The `#:` prefix is a documentation-tool convention (Sphinx) meaning "this comment documents the line below".

---

## `GameConfig` — a record with one important detail

```python
@dataclass
class GameConfig:
    seed: int = 1
    max_turns: int = 200
    ruleset: str = "baseline"
    stack: str = "none"
    players: dict[Color, dict] = field(default_factory=dict)
```

`@dataclass` is a **decorator** — a function that takes your class and returns a modified one. It reads the annotated fields and writes `__init__`, `__repr__`, and `__eq__` for you. Those five lines would be ~20 by hand.

`seed: int = 1` declares a field of type `int` defaulting to `1`. The annotation is what `@dataclass` looks at; Python itself doesn't enforce it.

`dict[Color, dict]` reads as "a dict whose keys are `Color` and whose values are dicts".

**The last line is the interesting one.** You cannot write `players: dict = {}`:

```python
def add(item, items=[]):     # a classic Python bug
    items.append(item)
    return items

add("a")   # ['a']
add("b")   # ['a', 'b']   <-- the SAME list, still there
```

Default values are evaluated **once**, when the `def` runs — not per call. So every call shares one list. `@dataclass` refuses outright:

```
ValueError: mutable default <class 'dict'> for field players is not allowed:
use default_factory
```

`field(default_factory=dict)` passes the *function* `dict`, which gets called fresh for each instance. Run [example 02](examples/02_dataclasses.py) to watch the bug happen.

---

## `Outcome` — a record with a computed attribute

```python
@dataclass
class Outcome:
    reason: str
    turns_played: int
    standings: list[dict]

    @property
    def winner(self) -> Color:
        return self.standings[0]["player"]
```

These three fields have **no defaults**, so they're required: `Outcome("turn_cap", 200, [...])`.

`@property` turns a method into something you access without parentheses:

```python
outcome.winner        # "green"   — computed on access
outcome.winner()      # TypeError — it is not callable
```

`self.standings[0]["player"]` chains two different lookups: `[0]` indexes a list, `["player"]` keys a dict. Same bracket syntax, different operations, decided by what the object is.

Why a property rather than a stored field? The winner is *derived* from standings. Storing it separately would create two sources of truth that could disagree.

---

## `__init__` — building the object

```python
class Game:
    def __init__(self, config: GameConfig, sink: EventSink) -> None:
        self.config = config
        self.sink = sink
        self.state = GameState()
        self.dice = Dice(config.seed)
        self.turn = 0
        self._rotation = -1
```

`__init__` is not a constructor in the C++/Java sense. Python creates the empty object first, then hands it to `__init__` as `self` to be filled in. It returns nothing — hence `-> None`.

**`self` is just the first parameter.** Python passes it automatically:

```python
g.play(deciders)          # what you write
Game.play(g, deciders)    # what actually happens
```

That's why every method starts with `self`. Forget it and you get a confusing arity error.

Each `self.X = ...` line *creates* the attribute. There's no separate declaration block — this method defines the object's shape.

`self._rotation = -1` starts at −1 deliberately, so the first `(−1 + 1) % 4` gives `0`, and red moves first.

---

## `play` — the outer loop

```python
    def play(self, deciders: dict[Color, Decider]) -> Outcome:
        self._emit_start(deciders)

        while self.turn < self.config.max_turns and len(self.state.finished) < 3:
            color = self._next_player()
            self.turn += 1
            self._play_turn(color, deciders[color])

        reason = "completed" if len(self.state.finished) >= 3 else "turn_cap"
        result = standings(self.state)
        self._emit("game_ended", {
            "reason": reason,
            "turns_played": self.turn,
            "standings": result,
        })
        return Outcome(reason, self.turn, result)
```

`deciders: dict[Color, Decider]` — a dict mapping each colour to the thing that will choose its moves. **This is the entire agent interface.**

The `while` condition combines two tests with `and`. Python short-circuits: if the first is false the second isn't evaluated.

`self.turn += 1` is `self.turn = self.turn + 1`.

`deciders[color]` looks up that colour's decider. Square brackets on a dict raise `KeyError` if absent — correct here, since a missing player is a bug we want loud.

```python
reason = "completed" if len(...) >= 3 else "turn_cap"
```

A **conditional expression** (Python's ternary). Reads in value-first order: *this value* if *condition* else *that value*. It's an expression, so it can sit on the right of `=`.

The dict passed to `_emit` is a plain literal spanning lines — Python allows that freely inside brackets.

`Outcome(reason, self.turn, result)` passes arguments **positionally**, matching the field order. `Outcome(reason=reason, ...)` would be equivalent and more explicit.

---

## `_play_turn` — the core loop

This is the longest method. It's one `while True:` with several exits.

```python
    def _play_turn(self, color: Color, decider: Decider) -> None:
        self._emit("turn_started", {"player": color})

        before = self.state.snapshot()
        sixes = 0
        roll_index = 0

        while True:
            die = self.dice.roll()
            self._emit("dice_rolled", {"player": color, "value": die, "roll_index": roll_index})
            roll_index += 1
```

`before = self.state.snapshot()` saves the board in case three sixes cancel the turn. That method copies rather than handing out a reference — [example 04](examples/04_mutability_and_copying.py) shows what breaks otherwise.

`while True:` is an intentional infinite loop. Every exit is an explicit `return`. Python has no `do/while`; this is the idiom for "loop until something inside says stop".

```python
            sixes = sixes + 1 if die == 6 else 0
            if sixes == SIX_LIMIT:
                self.state.restore(before)
                self._end_turn(color, "three_sixes")
                return
```

`sixes = sixes + 1 if die == 6 else 0` — the ternary again. It parses as `sixes = ((sixes + 1) if (die == 6) else 0)`. Rolling anything but a six resets the counter to zero.

```python
            moves = legal_moves(self.state, color, die)
            if not moves:
                self._end_turn(color, "no_legal_move")
                return
```

`if not moves:` relies on **truthiness**: an empty list is falsy, a non-empty one truthy. Idiomatic Python — `if len(moves) == 0:` works but reads as noise.

```python
            move = self._decide(color, decider, die, moves)
            if move is None:
                self.state.stats[color].turns_forfeited += 1
                self._end_turn(color, "illegal_move")
                return
```

`if move is None:` uses `is`, not `==`. `is` asks "the same object?", `==` asks "equal value?". `None` is a singleton, so `is None` is the correct and conventional test.

`self.state.stats[color].turns_forfeited += 1` chains four steps: attribute → dict key → attribute → increment. Each `.` and `[]` is a separate lookup.

```python
            if die == 6 or captured:
                self._emit("extra_roll_granted", {
                    "player": color, "reason": "six" if die == 6 else "capture",
                })
                continue

            self._end_turn(color, "moved")
            return
```

`die == 6 or captured` mixes a comparison (a `bool`) with `captured` (also a `bool` here). `or` works on any truthy/falsy values.

Note the ternary **inside a dict literal** — expressions nest anywhere a value is allowed.

`continue` jumps back to the top of `while True` for the extra roll. `return` exits the method entirely, ending the turn. The distinction between these two is the whole extra-roll rule.

---

## `_apply` — emit what happened

```python
    def _apply(self, color: Color, move: Move) -> bool:
        captures = apply_move(self.state, color, move)
        ...
        for cap in captures:
            self._emit("token_captured", {...})
        if move.to == HOME:
            self._emit("token_home", {"player": color, "token": move.token})
        return bool(captures)
```

`for cap in captures:` iterates the list directly. Python has no index-based `for` loop; when you need the index you use `enumerate()`.

`return bool(captures)` converts a list to `True`/`False` — non-empty is `True`. The signature says `-> bool`, so returning the list itself would be a (silent, unenforced) lie. The explicit `bool()` makes the contract real.

---

## `_decide` — the densest method

```python
    def _decide(
        self, color: Color, decider: Decider, die: int, moves: list[Move]
    ) -> Move | None:
        """Ask for a move, rejecting illegal ones rather than correcting them."""
        allowed = set(moves)

        for attempt in range(1, MOVE_ATTEMPTS + 1):
            ctx = TurnContext(self.state, color, die, list(moves), self.turn, attempt)
            try:
                move = decider.choose(ctx)
            except Exception as exc:
                self._emit("illegal_move_rejected", {
                    "player": color, "token": None, "requested_to": None,
                    "reason": f"decider error: {type(exc).__name__}", "attempt": attempt,
                })
                continue

            if move in allowed:
                return move

            self._emit("illegal_move_rejected", {
                "player": color,
                "token": getattr(move, "token", None),
                "requested_to": getattr(move, "to", None),
                "reason": "not a legal move for this roll",
                "attempt": attempt,
            })

        return None
```

**The signature spans lines** — allowed because it's inside parentheses. `-> Move | None` means "returns a `Move`, or `None`". The `|` is the modern union syntax (older code writes `Optional[Move]`).

**`allowed = set(moves)`** — this one line is why `Move` is declared `@dataclass(frozen=True)`. Sets require hashable elements; a mutable dataclass is unhashable and this would raise `TypeError`. Immutability wasn't chosen for elegance, it was chosen for this.

**`range(1, MOVE_ATTEMPTS + 1)`** yields `1, 2`. `range` excludes its upper bound, so `+ 1` is needed to include attempt 2. Starting at 1 makes the number meaningful in the emitted event.

**`list(moves)`** hands the decider a *copy*, so an agent shuffling the list can't corrupt the caller's `moves`.

**`except Exception as exc:`** catches any error the agent raises and binds the exception object to `exc`. A broken agent forfeits its turn instead of crashing the game.

**`type(exc).__name__`** — `type(exc)` is the class (`<class 'RuntimeError'>`); `.__name__` is the string `'RuntimeError'`. The engine records the class name rather than `str(exc)` because the class name is a short stable category, while the message is long, model-dependent, and could leak prompt text into a committed transcript.

**`f"decider error: {type(exc).__name__}"`** — an **f-string**. The `f` prefix means expressions inside `{}` get evaluated and interpolated.

**`continue` inside `except`** moves to the next attempt.

**`getattr(move, "token", None)`** reads `move.token`, returning `None` if the attribute doesn't exist. Needed because a misbehaving agent might return literally anything — a string, a number — and plain `move.token` would raise, turning a logged rejection into a crash.

**`return None` at the end** is reached only when the loop finishes without returning — both attempts failed. This is the value the caller tests with `if move is None:`.

---

## `_next_player` — rotate, skipping finishers

```python
    def _next_player(self) -> Color:
        while True:
            self._rotation = (self._rotation + 1) % len(COLORS)
            color = COLORS[self._rotation]
            if not self.state.has_finished(color):
                return color
```

`% len(COLORS)` wraps 4 back to 0, so the rotation cycles forever. `COLORS` is a tuple, indexed like a list.

The loop keeps advancing past players who've finished. It's safe from spinning forever because `play` stops once three players are done, so at least one is always unfinished.

---

## `_emit_start` — the most idiom-dense few lines

```python
    def _emit_start(self, deciders: dict[Color, Decider]) -> None:
        players = []
        for color in COLORS:
            meta = dict(self.config.players.get(color, {}))
            meta.setdefault("agent", getattr(deciders.get(color), "name", "unknown"))
            players.append({"color": color, **meta})
```

Four separate idioms in three lines:

| Expression | Meaning |
|---|---|
| `.get(color, {})` | Fetch the key, or `{}` if absent — no `KeyError`. Contrast `[color]`, which raises. |
| `dict(...)` | Makes a **copy**, so the following line can't mutate the caller's config. |
| `.setdefault(k, v)` | Set the key *only if missing*. Explicit config always wins over the fallback. |
| `getattr(obj, "name", "unknown")` | Read `.name`, or `"unknown"`. Works even when `deciders.get(color)` returned `None`, so two failure cases collapse into one expression with no `if`. |
| `{"color": color, **meta}` | `**` unpacks `meta`'s keys into a new dict alongside `"color"`. |

That last one builds one flat dict — `{"color": "red", "agent": "random-bot"}` — rather than nesting metadata under a sub-key.

---

## What to take away

1. **`self` is an ordinary parameter.** `g.play(x)` is `Game.play(g, x)`.
2. **Annotations aren't enforced.** They're for humans and type checkers. The engine re-validates every move precisely because the type hint guarantees nothing.
3. **`@dataclass` removes boilerplate**, and `field(default_factory=...)` exists because Python evaluates defaults once.
4. **`frozen=True` was a functional requirement**, not a style choice — `set(moves)` demands hashability.
5. **Assignment never copies.** Every snapshot, every `list(moves)`, every `dict(...)` is deliberate.
6. **Truthiness is idiomatic** (`if not moves:`), but `None` gets `is None`.
7. **`continue` vs `return`** inside `while True:` is what encodes the extra-roll rule.

## Next

- Run the [examples](examples/) in order — each concept above, demonstrated and executable.
- [Concept index](02-concept-index.md) — look up any syntax and jump to where it's used.
