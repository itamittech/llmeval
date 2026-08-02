# Environments, `pyproject.toml`, and `uv`

How Python projects are assembled and isolated — explained against the real files in this repo.

If you come from Java: **`uv` ≈ Maven**, `pyproject.toml` ≈ `pom.xml`, `uv.lock` ≈ a resolved dependency tree, `.venv` ≈ your local `~/.m2` but *per project*. The details differ in one important way, covered at the end.

---

## 1. The problem: Python installs packages globally

Install a package the naive way and it lands in your system Python, shared by everything on the machine:

```bash
pip install jsonschema        # goes into C:\Python313\Lib\site-packages
```

Two projects on one machine now fight. Project A needs `jsonschema` 3.x, project B needs 4.x — only one can win. Worse, you can't tell which project put a package there or whether removing it breaks something else.

**This repo has that problem in an acute form.** It runs two Python agent frameworks side by side: LangChain, which pulls a large opinionated dependency tree, and Strands, which is deliberately lean. Installed together they'd fight over shared transitive dependencies — and even if they resolved, you could never tell which framework's dependency caused a behaviour you observed. That's fatal for a project whose entire purpose is comparing them. Hence the hard rule in [environment-strategy.md](../../docs/architecture/environment-strategy.md): **never share a Python environment between the two stacks.**

---

## 2. A virtual environment is just a folder

A "venv" sounds abstract. It's a directory containing its own Python and its own package folder:

```
projects/ludo/engine-python/.venv/
├── Scripts/          (Windows;  "bin/" on macOS/Linux)
│   ├── python.exe
│   └── pytest.exe
└── Lib/site-packages/
    ├── pytest/
    ├── jsonschema/
    └── ludo_engine/     <- our own package
```

Installing "into a venv" means writing to *that* `site-packages` instead of the system one. Nothing is magic and nothing is registered globally — delete the folder and it's gone without trace.

**Activating** a venv just puts its `Scripts/` directory first on your `PATH`, so `python` resolves to that one:

```bash
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS/Linux
```

You'll see this in most tutorials. **This repo never needs it**, because `uv run` picks the right environment automatically:

```bash
uv run --directory projects/ludo/engine-python pytest
```

That's why every command in the docs looks like that. Forgetting to activate is one of the most common Python papercuts, and `uv run` removes the whole category.

`.venv` is in [`.gitignore`](../../.gitignore) — it's build output, hundreds of files, platform-specific, and fully regenerable from the lockfile.

---

## 3. `pyproject.toml` — the project's identity card

One file describing what a project is, what it needs, and how to build it. It replaced an older mess of `setup.py`, `setup.cfg`, `requirements.txt`, and `MANIFEST.in`.

TOML is a config format: `key = value`, grouped into `[sections]`.

Here is the engine's, in full, annotated. Source: [`projects/ludo/engine-python/pyproject.toml`](../../projects/ludo/engine-python/pyproject.toml)

### `[project]` — metadata and runtime dependencies

```toml
[project]
name = "ludo-engine"
version = "0.1.0"
description = "Deterministic LUDO rules engine. Standard library only — no LLM dependencies."
readme = "README.md"
requires-python = ">=3.11"
dependencies = []
```

| Key | Meaning |
|---|---|
| `name` | The installable name. `uv add ludo-engine` would use this. |
| `version` | Standard practice is `MAJOR.MINOR.PATCH`. |
| `readme` | Rendered as the package description. **This must exist** — an early sync here failed with `OSError: Readme file does not exist`. |
| `requires-python` | `>=3.11` means 3.11, 3.12, 3.13… all fine. `uv` refuses to install under an older one. |
| `dependencies` | **Empty, and that's the point.** The engine uses only the standard library. |

That empty list is a design constraint made machine-checkable: [the engine must never import an LLM SDK](../../docs/architecture/repository-layout.md). Anyone adding one has to edit this line, which is visible in review.

### `[project.optional-dependencies]` — extras users opt into

```toml
[project.optional-dependencies]
validate = ["jsonschema>=4.21"]
```

Installed only on request, as `ludo-engine[validate]`. Transcript validation needs `jsonschema`, but playing a game doesn't — so the base install stays dependency-free.

`>=4.21` is a **constraint**, not an exact pin: "4.21 or newer". Section 4 covers why that's safe.

### `[dependency-groups]` — tools for developers only

```toml
[dependency-groups]
dev = ["pytest>=8.0", "jsonschema>=4.21"]
```

Needed to *work on* the engine, never to *use* it. Someone installing `ludo-engine` as a library gets neither. `uv sync` installs the `dev` group by default, which is why `pytest` is available without asking.

**The distinction in one line:**

| | Who gets it |
|---|---|
| `dependencies` | everyone, always |
| `optional-dependencies` | users who ask (`pkg[extra]`) |
| `dependency-groups` | developers of this project only |

### `[build-system]` — how to turn source into a package

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ludo_engine"]
```

Python doesn't have one blessed build tool; `hatchling` is a common modern choice. The last line points it at our code.

Note the **`src/` layout**: the package lives at `src/ludo_engine/` rather than `ludo_engine/` at the top. This forces tests to import the *installed* package rather than accidentally picking up the folder sitting in the working directory — so the tests exercise what users would actually get.

### `[tool.*]` — settings for other tools

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

Any tool can claim a `[tool.<name>]` section. This one tells pytest where tests live and to run quietly — which is why bare `pytest` works with no extra flags.

---

## 4. The lockfile — what you actually got

`pyproject.toml` says `jsonschema>=4.21` — a range. So what's *installed*?

That's [`uv.lock`](../../projects/ludo/engine-python/uv.lock): every package in the resolved tree, at an exact version, with hashes. Including things you never asked for — `attrs`, `rpds-py`, `referencing` — pulled in transitively.

| File | Answers |
|---|---|
| `pyproject.toml` | "what does this project *need*?" — hand-written, ranges |
| `uv.lock` | "what did we *resolve to*?" — generated, exact |

**Both are committed.** The lockfile is what makes `uv sync` reproducible: someone cloning this repo in a year gets the versions we actually tested, not whatever is newest that day. Never edit it by hand — change `pyproject.toml` and re-sync.

---

## 5. `uv` — one tool instead of five

Historically Python needed `pip` (install), `venv` (isolate), `pip-tools` (lock), `pyenv` (manage versions), and `poetry`/`pdm` (project management). [`uv`](https://docs.astral.sh/uv/) does all of it, written in Rust and typically 10–100× faster.

It even installs Python itself. Note the earlier output: `Using CPython 3.12.11` — not the 3.13 on this machine's PATH. `uv` fetched an interpreter matching `requires-python` and used that, so contributors don't have to hand-manage Python versions.

### The commands that matter

```bash
uv sync --directory projects/ludo/engine-python
```
Read `pyproject.toml`, resolve, write `uv.lock`, create `.venv`, install everything. Idempotent — safe to re-run.

```bash
uv run --directory projects/ludo/engine-python pytest
```
Run a command inside that project's environment. Syncs first if needed. **No activation required.**

```bash
uv add requests          # add a dependency (edits pyproject.toml AND the lock)
uv add --dev pytest-cov  # add to the dev group
uv lock --upgrade        # re-resolve to newer versions within the declared ranges
```

`--directory` tells `uv` which project to operate on, so you can run any command from the repo root. That's why every documented command in this repo has it.

---

## 6. Workspaces — and why this repo has none

`uv` supports **workspaces**: one root `pyproject.toml` listing several member projects, managed together. It looks perfect for a monorepo, and this repo used one at first.

It was wrong, and worth showing why.

**Workspace members share a single lockfile and a single virtual environment.** After a workspace sync, this repo had:

```
uv.lock          <- one, at the root
.venv/           <- one, at the root
```

One environment for every member. Adding `stack-strands` and `stack-langgraph` would have installed LangChain and Strands *into the same `site-packages`* — precisely the merged environment the project's own rule forbids. The comment in that root file even claimed members "resolve and lock independently", which is simply not how `uv` workspaces work.

### What the repo does instead

No workspace. Every Python project is standalone, and stacks depend on the engine **by path**:

```toml
# projects/ludo/stack-strands/pyproject.toml  (not yet written)
dependencies = ["ludo-engine"]

[tool.uv.sources]
ludo-engine = { path = "../engine-python", editable = true }
```

Result:

```
projects/ludo/engine-python/.venv/     uv.lock
projects/ludo/stack-strands/.venv/     uv.lock     <- own tree
projects/ludo/stack-langgraph/.venv/   uv.lock     <- own tree
```

Three environments. Strands and LangGraph never see each other's dependencies, while both use the same engine source.

**`editable = true`** means the engine is linked, not copied — edit `moves.py` and both stacks see the change immediately, with no reinstall. That's why the engine's own venv shows:

```
ludo-engine==0.1.0 (from file:///E:/AIProject/llmeval/projects/ludo/engine-python)
```

installed *from a path*, not downloaded.

Workspaces aren't bad — they're right when members genuinely should share one environment. Here the requirement is the exact opposite, and the requirement wins.

---

## 7. Cheat sheet

| Task | Command |
|---|---|
| Set up a project | `uv sync --directory <project>` |
| Run tests | `uv run --directory <project> pytest` |
| Run one test | `uv run --directory <project> pytest tests/test_moves.py::test_name` |
| Run a module | `uv run --directory <project> python -m ludo_engine.cli play` |
| Add a dependency | `uv add <pkg>` (from inside the project) |
| Update within ranges | `uv lock --upgrade` |
| Start over | delete `.venv`, `uv sync` again |

`python -m package.module` runs a module *inside a package*, which is how the CLI is invoked. Plain `python cli.py` would break its relative imports (`from .board import ...`).

---

## 8. If you know Maven

| Maven | Python + `uv` |
|---|---|
| `pom.xml` | `pyproject.toml` |
| `<dependencies>` | `[project] dependencies` |
| `<scope>test</scope>` | `[dependency-groups] dev` |
| `~/.m2/repository` (global cache) | `.venv/` (**per project**) |
| `mvn test` | `uv run pytest` |
| `mvn install` | `uv sync` |
| Multi-module reactor build | `uv` workspace — *not used here, see §6* |

**The key difference:** Maven has one global cache and resolves per-project at build time, so two projects can use different versions of a library without conflict. Python installs *into* an environment, so the environment itself must be per-project. That's why venvs are unavoidable in Python and have no real Maven equivalent.

`<scope>provided</scope>` has no clean analogue — Python's closest is `optional-dependencies`, which is opt-in rather than assumed-present.

---

## Related

- [environment-strategy.md](../../docs/architecture/environment-strategy.md) — the project-level rules this implements
- [Concept index](02-concept-index.md) — language syntax, rather than tooling
- [`uv` documentation](https://docs.astral.sh/uv/)
