# Learning Python Through This Codebase

For readers who can already program but haven't written much Python, and want to *read* this repo confidently.

This folder is **standalone**. It isn't imported by the engine, doesn't affect any build, and every example runs with plain `python` — no virtual environment, no dependencies, nothing installed.

## Run anything

```bash
python learning/python/examples/01_classes_and_self.py
```

Each script prints its own explanation as it runs. Editing them and re-running is the point — they're meant to be poked at.

## Suggested order

**0. [What all these files and folders are for](00-files-and-folders.md)** — if a Python repo looks like unexplained clutter, start here. `__init__.py`, `__pycache__`, `src/`, why commands use `python -m`. Numbered `00` because it comes first; no code required.

**1. Run the examples** in numerical order. About 5 minutes each.

| | File | Covers |
|---|---|---|
| 01 | [`01_classes_and_self.py`](examples/01_classes_and_self.py) | `self`, `__init__`, instance state, `_private`, `@property` |
| 02 | [`02_dataclasses.py`](examples/02_dataclasses.py) | `@dataclass`, the mutable-default trap, `frozen=True`, shallow freezing |
| 03 | [`03_protocols_duck_typing.py`](examples/03_protocols_duck_typing.py) | Duck typing, `Protocol`, why the engine avoids inheritance |
| 04 | [`04_mutability_and_copying.py`](examples/04_mutability_and_copying.py) | References vs copies, shallow vs deep, a real bug reproduced |
| 05 | [`05_dicts_sets_truthiness.py`](examples/05_dicts_sets_truthiness.py) | `.get`, `.setdefault`, `**`, comprehensions, sets, truthiness |
| 06 | [`06_type_hints_and_errors.py`](examples/06_type_hints_and_errors.py) | Type hints (and why they're not enforced), `X \| None`, `try/except`, `getattr` |

**2. Read [the `Game` walkthrough](01-walkthrough-game.md)** with [`game.py`](../../projects/ludo/engine-python/src/ludo_engine/game.py) open beside it. Every non-obvious line explained, in order.

**3. Keep [the concept index](02-concept-index.md) open** while reading the rest of the engine. Look up any syntax, see what it does and where the project uses it.

**4. Read [environments and packaging](03-environments-and-packaging.md)** when you want to know what `uv`, `.venv`, `pyproject.toml`, and `uv.lock` actually are — and why this repo needs three separate Python environments. Tooling rather than language; readable at any point.

> The numbering is file order, not difficulty. `00` and `03` are about *tooling* — what the files are and how environments work. `01` and `02` are about the *language*. Read the pair that matches what's confusing you.

## Three things that surprise people from other languages

**Type hints do nothing at runtime.** `def add(a: int, b: int) -> int` will happily accept two strings. Annotations are for humans and type checkers only — which is exactly why the engine re-validates every move an agent returns instead of trusting a signature.

**Assignment never copies.** `b = a` gives you a second name for one object, not a second object. Every copy in the engine (`list(moves)`, `{k: list(v) ...}`, `dict(...)`) is a deliberate decision, and [example 04](examples/04_mutability_and_copying.py) reproduces the bug you get without them.

**There is no `private`, and no `interface`.** A leading underscore is a polite request. A `Protocol` is satisfied by having the right method names — no `implements`, no import. Python trusts convention where other languages use the compiler.

**Packages install *into* an environment, not into a global cache.** Unlike Maven's `~/.m2`, two Python projects can't share one install directory and use different versions. That's why virtual environments are unavoidable — [doc 03](03-environments-and-packaging.md) covers it.

## Why this folder exists

Teaching is a [stated goal](../../docs/vision.md) of this repo, and the same LUDO game is being built three times — in Python twice and in Java once. A reader who can follow all three gets the comparison the project is actually about. This folder removes the Python half of that barrier.

For *why the engine is designed* the way it is — as opposed to what the syntax means — see [engine-design.md](../../docs/projects/ludo/engine-design.md).

And once this folder makes sense, [learning/java](../java/) reads the *same engine* in Java. Because both implementations produce byte-identical transcripts from the same seed, every difference between them isolates a language property rather than a design choice — which is a comparison no single-language tutorial can offer.
