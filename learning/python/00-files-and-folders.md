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

The `__all__` list in that file is the package's **public API** — it says "these are the names I intend people to use", and everything else is an internal detail that might move.

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

At the bottom of [`cli.py`](../../projects/ludo/engine-python/src/ludo_engine/cli.py):

```python
if __name__ == "__main__":
    raise SystemExit(main())
```

Python sets the variable `__name__` in every module. It's `"__main__"` when the file is the one being *run*, and the module's real name when it's being *imported*.

So this block means **"only do this if I'm the program, not if someone imported me."** Without it, merely importing `cli` would start a game.

---

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
