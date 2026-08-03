# Environment Strategy

> Goal #6 from the original brief: *"It needs to be seen how the environment is well maintained and free of conflict as we are using three different technical things to arrive at same problem."*

Two Python stacks, a JVM, and a Node UI in one repo. This is where that stays manageable.

## The rule that prevents most of the pain

**Never share a Python environment between stacks.**

LangChain pulls a large, opinionated dependency tree. Strands is deliberately lean. Put them in one virtualenv and you get a resolver fight, and worse, you stop being able to tell which framework's transitive dependency caused a behaviour. Each stack gets its own environment and its own lockfile. Always.

The two Python stacks share exactly one thing: **the same pinned Python version**, so the interpreter isn't a variable in the comparison.

## Python: `uv`, and deliberately **no** workspace

[`uv`](https://docs.astral.sh/uv/) manages both Python stacks — fast, correct resolution, real lockfiles, and it can install the interpreter itself so contributors don't have to.

**Each Python project is standalone: its own `pyproject.toml`, its own `uv.lock`, its own `.venv`.**

A `uv` *workspace* would be the obvious-looking choice and is the wrong one here. Workspace members **share a single lockfile and a single virtual environment** — exactly the merged environment the rule above forbids. The repo tried it briefly and reverted; the shared `.venv` at the root was the giveaway.

Instead, stacks depend on the engine by path:

```toml
# projects/ludo/stack-strands/pyproject.toml
dependencies = ["ludo-engine"]

[tool.uv.sources]
ludo-engine = { path = "../engine-python", editable = true }
```

`editable = true` means an engine edit is picked up immediately, with no reinstall or publish step. Each stack still resolves and locks on its own, so Strands and LangGraph never see each other's dependency tree.

Lockfiles are committed. A reader cloning this repo a year from now gets the versions we actually tested.

## Java: independent build

Spring AI builds with **Maven**, with the wrapper (`mvnw`) committed so no global Maven install is required. Pinned JDK version. It shares nothing with the Python side except the files in `shared/`.

## Node: the UI, plus one doc tool

The UI is the Node surface that matters. Its `package.json` and lockfile live in `projects/<project>/ui/` and never leak upward — a UI dependency must not become a repo-wide one.

There is one exception, and it is deliberately tiny: a root `package.json` holding `mermaid` and `jsdom` (a headless browser DOM, which mermaid needs to run outside a browser) so [`scripts/check_mermaid.mjs`](../../scripts/check_mermaid.mjs) can parse the diagrams in `docs/` with the real renderer. Mermaid is a browser library; there is no Python equivalent that parses the same grammar, and hand-rolling a second-guess of it is what let a broken diagram ship once already. The cost of the exception is one lockfile at the root; the alternative was documentation we could not verify. Node arrives regardless — [ADR-0007](../decisions/adr-0007-ui-alongside-first-stack.md) commits to React + Vite.

The two do not share a dependency tree, and the root one is dev-only: nothing shipped, nothing imported by a stack.

## One entry point: `just`

Four toolchains means four sets of commands nobody remembers. A root `justfile` gives every stack the same verbs:

```
just setup              # install all toolchains + dependencies
just test               # every engine + stack test suite
just conformance        # both engines against the shared vectors
just play strands       # run a game on one stack
just ui                 # start the UI against recorded games
```

`just` is chosen over `make` because this repo is developed on Windows as well as Unix, and `make` on Windows is a reliable source of misery. It installs via `winget`, `scoop`, `brew`, or `cargo`.

**Every command a contributor needs must exist as a `just` recipe.** If a workflow only lives in someone's shell history, it isn't documented.

## Configuration and secrets

- **Config** — `shared/models.yaml` and per-stack config files, committed. No secrets.
- **Secrets** — provider API keys and AWS credentials via environment variables only, loaded from an uncommitted `.env`. A committed `.env.example` lists every required variable.
- **AWS** — standard credential chain (profile / SSO / instance role). No credentials in config files, ever.
- **Missing-key behaviour** — a stack that starts without the keys it needs must fail immediately with a message naming the missing variable, not fail deep inside a turn loop after spending tokens.

## Determinism and cost control

Two things make this repo safe to hack on:

- **Seeded dice.** The engine's RNG is seeded and the seed is recorded in the event stream. Same seed plus same agent decisions replays exactly.
- **Recorded games replay for free.** The UI and the eval harness both run against committed `.jsonl` transcripts. You can explore, develop the UI, and iterate on eval rubrics with zero API spend and no keys configured.

Combined with per-game token budgets, the failure mode of "I left a swarm running and it burned my credits" is designed out.

## CI expectations

CI runs the free tier of everything: linting, engine unit tests, conformance vectors across both engines, schema validation of committed transcripts, and eval-harness runs against recorded games. **Live model calls are not part of the default CI path** — they're non-deterministic and cost money. A separate opt-in job exercises real providers on a small fixed scenario.

## Related

- [Repository layout](repository-layout.md)
- [Architecture overview](overview.md)
