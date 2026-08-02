# Concept Index

Look up a piece of syntax, see what it means, and jump to where the project uses it.

## Syntax you'll hit immediately

| Syntax | Means | Runnable | Used in |
|---|---|---|---|
| `def f(self, x):` | Method. `self` is the object it was called on — Python passes it for you. | [01](examples/01_classes_and_self.py) | everywhere |
| `__init__` | Runs when you write `Game(...)`. Fills in an already-created object. | [01](examples/01_classes_and_self.py) | `game.py:49` |
| `_name` | "Internal, please don't touch." Convention only — nothing enforces it. | [01](examples/01_classes_and_self.py) | `self._rotation` |
| `@property` | Method accessed like an attribute, no parentheses. | [01](examples/01_classes_and_self.py) | `Outcome.winner` |
| `@dataclass` | Generates `__init__`, `__repr__`, `__eq__` from annotated fields. | [02](examples/02_dataclasses.py) | `GameConfig`, `Move` |
| `field(default_factory=dict)` | Fresh default per instance. Needed because plain defaults evaluate once. | [02](examples/02_dataclasses.py) | `GameConfig.players` |
| `@dataclass(frozen=True)` | Immutable → hashable → usable in a `set`. | [02](examples/02_dataclasses.py) | `Move`, `Snapshot` |
| `x: int = 5` | Type annotation with default. **Not enforced at runtime.** | [06](examples/06_type_hints_and_errors.py) | every signature |
| `-> Move \| None` | Returns a `Move` or `None`. | [06](examples/06_type_hints_and_errors.py) | `Game._decide` |
| `dict[Color, Decider]` | A dict with `Color` keys and `Decider` values. | [06](examples/06_type_hints_and_errors.py) | `Game.play` |
| `from .board import X` | Leading dot = the module *next to this one*. Why commands need `python -m`. | [00](00-files-and-folders.md) | every module |
| `__init__.py` | Marks a folder as an importable package; ours re-exports the public API. | [00](00-files-and-folders.md) | `ludo_engine/` |
| `if __name__ == "__main__"` | "Only run this if I'm the program, not if I was imported." | [00](00-files-and-folders.md) | `cli.py` |
| `from __future__ import annotations` | Store hints as strings. Modern boilerplate. | [06](examples/06_type_hints_and_errors.py) | most modules |

## Control flow

| Syntax | Means | Runnable | Used in |
|---|---|---|---|
| `A if cond else B` | Conditional *expression* — produces a value. | — | `"six" if die == 6 else "capture"` |
| `while True:` | Loop until an explicit `return`/`break`. Python has no `do/while`. | — | `_play_turn`, `_next_player` |
| `continue` / `return` | Next iteration / leave the method. The extra-roll rule is exactly this distinction. | — | `_play_turn` |
| `if not moves:` | Truthiness — empty list is falsy. | [05](examples/05_dicts_sets_truthiness.py) | `_play_turn` |
| `if move is None:` | Identity test. Always `is` for `None`, never `==`. | [05](examples/05_dicts_sets_truthiness.py) | `_play_turn` |
| `for i, c in enumerate(x)` | Index and value together. | [05](examples/05_dicts_sets_truthiness.py) | `cli.py` |
| `range(1, n + 1)` | `1 … n`. Upper bound excluded, hence `+ 1`. | — | `_decide` |
| `try/except Exception as exc` | Catch anything; bind the exception object. | [06](examples/06_type_hints_and_errors.py) | `_decide` |
| `type(exc).__name__` | The exception's class name as a string. | [06](examples/06_type_hints_and_errors.py) | `_decide` |

## Collections

| Syntax | Means | Runnable | Used in |
|---|---|---|---|
| `d[k]` | Fetch; raises `KeyError` if missing. | [05](examples/05_dicts_sets_truthiness.py) | `deciders[color]` |
| `d.get(k, default)` | Fetch, or a fallback. No exception. | [05](examples/05_dicts_sets_truthiness.py) | `_emit_start` |
| `d.setdefault(k, v)` | Insert only if missing; never overwrites. | [05](examples/05_dicts_sets_truthiness.py) | `_emit_start` |
| `{**a, **b}` | Merge dicts into a new one; later keys win. | [05](examples/05_dicts_sets_truthiness.py) | `_emit_start` |
| `[f(x) for x in xs]` | List comprehension. | [05](examples/05_dicts_sets_truthiness.py) | `state.py`, `cli.py` |
| `{k: v for k, v in ...}` | Dict comprehension. | [05](examples/05_dicts_sets_truthiness.py) | `GameState.snapshot` |
| `set(xs)` / `x in s` | Fast membership. Elements must be **hashable**. | [05](examples/05_dicts_sets_truthiness.py) | `_decide` |
| `getattr(o, "n", default)` | Read an attribute that may not exist. Works on `None` too. | [06](examples/06_type_hints_and_errors.py) | `_decide`, `_emit_start` |
| `f"{x} and {y}"` | f-string — expressions in `{}` are interpolated. | — | throughout |

## The two ideas worth real attention

### Protocol — [example 03](examples/03_protocols_duck_typing.py)

```python
class Decider(Protocol):
    def choose(self, ctx: TurnContext) -> Move: ...
```

Anything with a matching `choose` method satisfies this. **No import, no inheritance.**

This is why the engine has zero agent-framework dependencies: the Strands and LangGraph packages have deliberately separate dependency trees, and neither needs to import the engine to plug into it. In Java the same contract would be an `interface` that each agent must explicitly `implements`.

### Mutability — [example 04](examples/04_mutability_and_copying.py)

```python
a = [1, 2, 3]
b = a          # NOT a copy — two names, one list
b.append(4)    # a is now [1, 2, 3, 4]
```

Assignment binds a name to an object; it never copies. Every copy in the engine is deliberate:

| Code | Why |
|---|---|
| `{k: list(v) for k, v in self.tokens.items()}` | `GameState.snapshot()` — without it, three-sixes rollback silently does nothing |
| `list(moves)` | `_decide` — an agent reordering the list can't corrupt the caller's |
| `dict(self.config.players.get(color, {}))` | `_emit_start` — the next line mutates it |

`frozen=True` does **not** help here: it's shallow, so a dict inside a frozen dataclass is still mutable.

## Where to look in the engine

| Read this | To see |
|---|---|
| [`board.py`](../../projects/ludo/engine-python/src/ludo_engine/board.py) | Plain functions and constants — no classes at all. The gentlest file. |
| [`state.py`](../../projects/ludo/engine-python/src/ludo_engine/state.py) | Dataclasses with methods; the snapshot/restore copying |
| [`deciders.py`](../../projects/ludo/engine-python/src/ludo_engine/deciders.py) | `Protocol`, and two tiny classes implementing it |
| [`events.py`](../../projects/ludo/engine-python/src/ludo_engine/events.py) | The one inheritance hierarchy — a template method |
| [`game.py`](../../projects/ludo/engine-python/src/ludo_engine/game.py) | Everything at once — see [the walkthrough](01-walkthrough-game.md) |

## Beyond this project

Concepts you'll meet in Python that the engine happens not to use: generators (`yield`), context managers (`with` — though `cli.py` uses one for files), decorators you write yourself, `async`/`await`, `__slots__`, metaclasses, and multiple inheritance.

The agent stacks will introduce `async`/`await` in particular, since LLM calls are I/O-bound. That's worth a follow-up note here once the first stack exists.
