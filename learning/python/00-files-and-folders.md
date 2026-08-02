# What all these files and folders are for

Every file in a Python project, explained — including the ones that appear on their own and the ones you should never commit.

Read this first if a Python repo looks like unexplained clutter. Nothing here is about the Ludo game; it's about how Python projects are shaped.

---

## The whole engine, annotated

This is the real listing, including the generated files your editor usually hides:

```
projects/ludo/engine-python/
│
├── pyproject.toml              ← what this project IS: name, deps, build config
├── uv.lock                     ← the exact versions actually installed
├── README.md                   ← required by pyproject's `readme = "README.md"`
│
├── .venv/                      ← 🚫 generated · this project's private Python
├── .pytest_cache/              ← 🚫 generated · pytest's notes from last run
│
├── src/
│   └── ludo_engine/            ← THE PACKAGE — this is what gets imported
│       ├── __init__.py         ← marks the folder as a package; ours re-exports
│       ├── board.py            ← each .py file is a "module"
│       ├── state.py
│       ├── moves.py
│       ├── dice.py
│       ├── events.py
│       ├── deciders.py
│       ├── game.py
│       ├── conformance.py
│       ├── cli.py
│       └── __pycache__/        ← 🚫 generated · compiled bytecode
│
└── tests/
    ├── test_board.py           ← pytest finds these by the `test_` prefix
    ├── test_moves.py
    ├── ...
    └── __pycache__/            ← 🚫 generated
```

🚫 = never committed. All four are in [`.gitignore`](../../.gitignore), and all four can be deleted at any time — they regenerate.

---

## `__init__.py`

**What it means:** *"this folder is a package, not just a folder with Python files in it."* Python will import `ludo_engine` because `src/ludo_engine/` contains an `__init__.py`.

It can be completely empty and still do that job. Plenty of projects have `__init__.py` files that are zero bytes.

**What ours does.** [`ludo_engine/__init__.py`](../../projects/ludo/engine-python/src/ludo_engine/__init__.py) is 22 lines, and it exists to shorten imports. Without it you'd write:

```python
from ludo_engine.game import Game
from ludo_engine.deciders import RandomBot
from ludo_engine.board import COLORS
```

Because `__init__.py` re-exports those names, you can write:

```python
from ludo_engine import Game, RandomBot, COLORS
```

**This is re-exporting, not aliasing.** An alias gives something a *different* name (`import numpy as np`). Re-exporting makes the *same* name reachable by a *shorter path* — and it really is the same object, not a copy:

```python
>>> from ludo_engine import Game
>>> from ludo_engine.game import Game as GameViaModule
>>> Game is GameViaModule
True
>>> Game.__module__
'ludo_engine.game'
```

The class is defined once, in `game.py`. `__init__.py` just puts a second signpost to it at the package's front door. Nothing is duplicated, and there's no performance cost.

The `__all__` list in that file is the package's **public API** — 24 names saying "these are what I intend you to use". Everything else is an internal detail that may move without warning. It also controls what `from ludo_engine import *` brings in.

**Why `tests/` has no `__init__.py`.** Deliberate. Test folders generally shouldn't be packages: pytest finds files by their `test_` prefix, not by importing a package. Adding one changes how pytest resolves imports and is a common source of confusing failures. If you see a repo with `tests/__init__.py`, it usually has a specific reason.

> Since Python 3.3 a folder without `__init__.py` *can* sometimes be imported (a "namespace package"). Ignore that for now — for ordinary projects, include the file.

---

## `__pycache__/` and `.pyc` files

Python compiles your source to **bytecode** — an intermediate form the interpreter actually executes — and caches it so it doesn't redo the work every run.

Look at the real filenames:

```
board.cpython-312.pyc
test_board.cpython-312-pytest-9.1.1.pyc
```

Two things are encoded there, and both explain why this is never committed:

- **`cpython-312`** — built by CPython 3.12. Run the same code under 3.13 and Python ignores these and writes new ones. The cache is tied to the interpreter.
- **`pytest-9.1.1`** on the test files — pytest *rewrites* your assertions during import, so it can show you `assert 3 == 4` with both values expanded instead of a bare "AssertionError". That rewritten form is version-specific too.

**Do you ever need to care?** Almost never. Delete `__pycache__` freely; Python rebuilds it. The one time it matters: if you delete a `.py` file but its `.pyc` lingers, an old import can occasionally still resolve. If a project behaves impossibly, clearing caches is a legitimate thing to try.

**`.pytest_cache/`** is unrelated to bytecode — it's pytest's own notebook, remembering which tests failed last time so `pytest --lf` can rerun just those. Also disposable.

---

## Why `src/ludo_engine/` and not just `ludo_engine/`

Both work. The `src/` layout is chosen deliberately, and the reason is worth knowing.

Without `src/`, the package folder sits next to your tests. Python puts the current directory on the import path, so `import ludo_engine` finds the **local folder** — whether or not the package is properly installed. Your tests then pass while testing something users could never install.

With `src/`, the local directory contains no importable `ludo_engine`, so the import can only resolve to the **installed** package. Tests exercise what a user would actually get. A packaging mistake fails loudly instead of hiding.

That's why [`pyproject.toml`](../../projects/ludo/engine-python/pyproject.toml) says:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/ludo_engine"]
```

---

## Modules, packages, and the leading dot

- A **module** is one `.py` file. `board.py` is the `board` module.
- A **package** is a folder of modules with `__init__.py`. `ludo_engine` is a package.

Inside a package, modules refer to each other with a **leading dot**:

```python
from .board import COLORS, to_square      # the `board` module NEXT TO THIS ONE
```

The dot means "relative to this package". Without it, `from board import ...` would search the whole import path and might find something entirely different.

### The consequence: `python -m`, not `python file.py`

Relative imports only work when the file is loaded *as part of a package*. Running the file directly doesn't do that:

```bash
python src/ludo_engine/cli.py play
```
```
ImportError: attempted relative import with no known parent package
```

Run it as a module instead, and Python loads the package properly:

```bash
python -m ludo_engine.cli play --seed 1
```
```
seed=1 reason=turn_cap turns=400
```

That's the entire reason every documented command in this repo uses `python -m`. It isn't style — the direct form genuinely cannot work.

---

## `if __name__ == "__main__":`

Python sets a variable called `__name__` inside **every** module. Its value depends entirely on *how that file got loaded*:

| How the file was loaded | `__name__` is |
|---|---|
| You **ran** it (`python greeter.py`) | `"__main__"` |
| Something **imported** it (`import greeter`) | `"greeter"` — its module name |

So the line reads: **"only do this if I'm the program being run, not if someone imported me."**

### See it happen

Two tiny files:

```python
# greeter.py
print(f"[greeter.py] loading.  __name__ is {__name__!r}")

def greet():
    return "hello from greeter"

if __name__ == "__main__":
    print("[greeter.py]   -> I am the program being RUN. Doing work:", greet())
else:
    print("[greeter.py]   -> I was IMPORTED. Defining things only, running nothing.")
```

```python
# app.py
print(f"[app.py]     loading.  __name__ is {__name__!r}")
import greeter
print("[app.py]     calling greeter.greet() ->", greeter.greet())
```

Run `greeter.py` directly and it's the program:

```
$ python greeter.py
[greeter.py] loading.  __name__ is '__main__'
[greeter.py]   -> I am the program being RUN. Doing work: hello from greeter
```

Run `app.py` instead, and `greeter` is now a library:

```
$ python app.py
[app.py]     loading.  __name__ is '__main__'
[greeter.py] loading.  __name__ is 'greeter'
[greeter.py]   -> I was IMPORTED. Defining things only, running nothing.
[app.py]     calling greeter.greet() -> hello from greeter
```

Three things that output makes obvious:

1. **`greeter.py` ran either way.** Importing a module *executes it top to bottom* — that's how `def` and `class` statements come into existence. The guard doesn't stop the file running; it stops the guarded block.
2. **`__name__` changed** from `'__main__'` to `'greeter'` purely because of how it was loaded.
3. **`app.py` is now the `'__main__'` one.** The name always belongs to whichever file you launched.

### Why it matters here

At the bottom of [`cli.py`](../../projects/ludo/engine-python/src/ludo_engine/cli.py):

```python
if __name__ == "__main__":
    raise SystemExit(main())
```

Without the guard, `from ludo_engine import cli` — or anything that imported it indirectly — would **start playing a game of Ludo**. With it, importing gives you the functions and nothing more.

The pattern is so common that "main guard" is just what people call it.

---

## How another project uses this package

`ludo_engine` is a **library**. It isn't an application — it has no server, no entry point anyone runs in production. Other projects depend on it and call into it.

### Step 1 — declare the dependency

A consumer names it in its own `pyproject.toml`. Here, the agent stacks will point at the folder rather than a published release:

```toml
# projects/ludo/stack-strands/pyproject.toml   (not written yet)
[project]
dependencies = ["ludo-engine"]

[tool.uv.sources]
ludo-engine = { path = "../engine-python", editable = true }
```

`editable = true` links rather than copies, so editing `moves.py` is picked up immediately with no reinstall. If the engine were published to PyPI instead, the `[tool.uv.sources]` block would simply disappear and `uv add ludo-engine` would fetch it — nothing else about the consumer would change.

Note the two spellings: the **distribution** is `ludo-engine` (hyphen, what you install) and the **package** is `ludo_engine` (underscore, what you import). Different things, and they're allowed to differ.

### Step 2 — import and use it

```python
from ludo_engine import COLORS, Game, GameConfig, ListSink, RandomBot

sink = ListSink()
outcome = Game(GameConfig(seed=7, max_turns=300), sink).play(
    {c: RandomBot(seed=i) for i, c in enumerate(COLORS)}
)
print(outcome.winner, len(sink.events))
```

### Step 3 — plug in your own behaviour

The engine asks exactly one question — *"what's your move?"* — so a consumer supplies an object with a `choose` method. **No base class, no import of `Decider`, no registration:**

```python
class GreedyBot:
    name = "greedy-bot"

    def choose(self, ctx):
        for move in ctx.legal_moves:          # already validated by the engine
            if would_capture(ctx.state, ctx.color, move):
                return move
        return max(ctx.legal_moves, key=lambda m: m.to)
```

A complete, runnable version is committed at
[`examples/custom_agent.py`](../../projects/ludo/engine-python/examples/custom_agent.py):

```bash
uv run --directory projects/ludo/engine-python python examples/custom_agent.py
```

```
reason=completed  turns=501  events=2311
  1. red     home=4 progress=228 captures=12  <- heuristic
  2. yellow  home=4 progress=228 captures=8
  3. blue    home=4 progress=228 captures=7
  4. green   home=3 progress=227 captures=3
```

**That file is the template every agent stack will follow.** A stack replaces the body of `choose` with an LLM call and keeps everything around it. The engine never learns the difference — which is the [Strategy pattern](../../docs/projects/ludo/class-design.md#71-four-players-four-different-brains--strategy) doing its job.

## Naming conventions

| Thing | Style | Here |
|---|---|---|
| Module (file) | `snake_case.py` | `game.py`, `state.py` |
| Package (folder) | `snake_case` | `ludo_engine` |
| Directory (non-package) | `kebab-case` | `engine-python`, `stack-strands` |
| Class | `PascalCase` | `GameState`, `TeeSink` |
| Function, variable | `snake_case` | `legal_moves`, `to_square` |
| Constant | `UPPER_CASE` | `SIX_LIMIT`, `COLORS` |
| Internal | `_leading_underscore` | `_play_turn`, `_state` |
| Test file | `test_*.py` | `test_moves.py` |

Note `engine-python` (hyphen) versus `ludo_engine` (underscore). **Directory names can use hyphens; importable package names cannot** — a hyphen would parse as minus. That's why the folder and the package it contains are spelled differently.

---

## What's safe to delete

| Path | Safe to delete? | Comes back |
|---|---|---|
| `__pycache__/` | ✅ always | on next run |
| `.pytest_cache/` | ✅ always | on next `pytest` |
| `.venv/` | ✅ always | `uv sync` |
| `uv.lock` | ⚠️ regenerable, but **don't** | `uv sync` — with possibly different versions |
| `pyproject.toml`, `src/`, `tests/` | ❌ never | it's the project |

`uv.lock` is the interesting one: deleting it isn't destructive, but re-resolving may pick newer versions than the ones this project was tested against. See [doc 03](03-environments-and-packaging.md).

---

## Related

- [Environments and packaging](03-environments-and-packaging.md) — `uv`, `.venv`, `pyproject.toml`, lockfiles in depth
- [Concept index](02-concept-index.md) — language syntax
- [Repository layout](../../docs/architecture/repository-layout.md) — how the whole repo is organised, beyond Python
