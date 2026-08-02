# Contributing

Thanks for looking. This repo exists to teach as much as to work, so **a clear explanation is as welcome as a clean patch** — fixing a confusing paragraph counts as a real contribution here.

New to the vocabulary? Start with the [glossary](docs/glossary.md).

---

## Quick start

You need [`uv`](https://docs.astral.sh/uv/) and nothing else. No API keys, no AWS account, no cost — the engine makes no model calls.

```bash
uv sync --directory projects/ludo/engine-python
```

```bash
uv run --directory projects/ludo/engine-python pytest
```

Play a game between four random bots:

```bash
uv run --directory projects/ludo/engine-python python -m ludo_engine.cli play --seed 7
```

Everything CI checks, in one go:

```bash
uv run --directory projects/ludo/engine-python pytest && uv run --directory projects/ludo/engine-python python -m ludo_engine.cli conformance --check
```

There's a [`justfile`](justfile) wrapping these if you'd rather install [`just`](https://just.systems/).

## What needs doing

- **[Open questions](docs/open-questions.md)** — decisions still on the table. Opinions welcome, especially from people who've used these frameworks in anger.
- **[Topic roadmap](docs/topics/roadmap.md)** — what's claimed and what isn't.
- **Anything confusing.** If a doc lost you, that's a bug. Say where.

The project is early: the engine and the shared schema exist, no agent stack does yet. Large contributions are best discussed in an issue first, simply so two people don't build the same thing differently.

---

## Rule zero: docs ship with the change

Documentation updates land in the **same commit** as the change they describe. Not after, not in a follow-up.

This repo exists to teach. A doc describing code that no longer exists is worse than no doc — it misleads the reader who trusted it. A PR that changes behaviour without changing the docs that describe it is incomplete, however good the code is.

[CLAUDE.md](CLAUDE.md) opens with the map of which docs move with which kind of change. Then:

```bash
python scripts/check_docs.py
```

That validates links, anchors, and Mermaid syntax across every markdown file. **It cannot tell whether the prose is still true** — re-read what you touched. Status tables, counts, and worked examples go stale silently and no tool catches them.

## Six more rules that are easy to break by accident

These aren't style preferences. Each one, broken, quietly invalidates something the project depends on.

### 1. Parity is the whole point

The three implementations must differ **only** in the agent framework. Same rules, same prompts (they live in `shared/prompts/` and are shared verbatim), same schema, same retry behaviour.

*Why:* if the LangGraph version gets a slightly better prompt, every measured difference becomes meaningless. We'd be comparing our own inconsistency. → [architecture overview](docs/architecture/overview.md)

### 2. The engine never imports an LLM SDK

`engine-python` and `engine-java` are deterministic and dependency-free. If you need model access inside the engine, the design is wrong — the agent goes behind the `Decider` interface instead.

*Why:* it's what keeps the tests fast, free, and reproducible. → [class design §7.6](docs/projects/ludo/class-design.md#76-the-engine-must-never-import-an-llm-sdk--ports-and-adapters)

### 3. Never regenerate conformance vectors to make a test pass

If `just conformance` fails, the engine's behaviour changed. That's either a bug you just introduced, or a rule change — in which case update [game-rules.md](docs/projects/ludo/game-rules.md) *first*, then both engines, then regenerate.

*Why:* these vectors are the only thing stopping the Python and Java engines drifting apart. Regenerating to silence a failure destroys the guarantee entirely and leaves everything looking green. → [conformance](shared/conformance/README.md)

### 4. Never share a Python environment between the two Python stacks

Separate `pyproject.toml`, separate lockfile, separate `.venv`. Stacks depend on the engine by path, not through a `uv` workspace — workspaces share one environment, which is exactly what we're avoiding.

*Why:* LangChain and Strands have conflicting dependency trees, and if they shared an environment you could never tell which framework's transitive dependency caused a behaviour. → [environment strategy](docs/architecture/environment-strategy.md)

### 5. Capability-matrix ratings and judge scores must cite evidence

A rating in the [capability matrix](docs/architecture/stack-comparison.md) links to the code that justifies it. An unsourced rating is an opinion, and opinions don't go in the table.

*Why:* the matrix is this repo's headline output. Its value is entirely in being checkable.

### 6. Agent claims are claims, not facts

Agents lie deliberately — that's the experiment. Anything derived from a transcript (summaries, UI, eval) must treat `message_sent` content as an assertion by a player, never as ground truth.

*Why:* it's the single easiest way to write a subtly broken summariser. → [ADR-0004](docs/decisions/adr-0004-structural-guardrails.md)

---

## Two files you shouldn't edit

**[`docs/roughidea.txt`](docs/roughidea.txt)** — the original brief, kept verbatim for provenance. Evolved thinking goes in the docs, not here.

**Any ADR marked Accepted** — supersede it with a new one instead. The wrong turns are part of the teaching value; erasing them removes the reasoning.

---

## Docs conventions

- **Concise over verbose.** A stated goal. Padded docs work against the teaching aim as much as unexplained ones.
- **Explain on first use.** If you introduce a term, either define it inline or add it to the [glossary](docs/glossary.md).
- **Teach from the problem.** The pattern that works well here is: the problem → what you'd write first → what breaks → the fix → the name. [Section 7 of class-design](docs/projects/ludo/class-design.md#7-design-patterns-from-the-problem-up) is the model.
- **Non-obvious, expensive-to-reverse decisions get an [ADR](docs/decisions/README.md)** — with the costs written down, not just the benefits.
- **Mermaid diagrams** render on GitHub natively; locally you'll need a preview extension. Two traps worth knowing:
  - **Node IDs must avoid Mermaid's reserved words** — `call`, `click`, `class`, `classDef`, `style`, `linkStyle`, `graph`, `subgraph`, `end`, `direction`, `href`, `default`. A node named `call` parses as a click-callback directive and the whole diagram fails. This has already bitten us once.
  - **Balanced braces are not proof it parses.** Only the real parser knows. After pushing, **look at the file on GitHub** — a broken diagram shows "Unable to render rich display" with a parse error instead of the picture. GitHub renders Mermaid inside a cross-origin iframe, so scripted checks against the page will not see the failure.

## Code conventions

- Match the surrounding style. There's no linter configured yet.
- Every edge case resolved in [game-rules.md](docs/projects/ludo/game-rules.md) has a test; rule changes start there.
- Comments explain *why*. The *what* should be legible from the code.
- Keep [`learning/`](learning/python/) dependency-free — its examples must run with bare `python`.

## Pull requests

Say what changed and why. If it's a rules or schema change, say what it breaks. Run the tests and the conformance check before opening.

Small PRs get read faster than large ones, and this is a repo people read.

---

## A note on content

The agents in this project are **designed to deceive each other**. They form alliances, break promises, bluff, and betray — that's the behaviour under study, and the guardrails are deliberately lenient to allow it.

So recorded transcripts in this repository contain AI-generated lies, presented without correction. They are in-fiction moves in a board game. They are not claims about anything real, and nothing here should be read as an endorsement of deceptive AI outside a game with clearly marked walls.

What *is* blocked: prompt injection between agents, attempts to forge game state, and real-world harassment. The line is in-fiction cunning versus out-of-fiction attack. → [ADR-0004](docs/decisions/adr-0004-structural-guardrails.md)

## Licence

Contributions are accepted under the [Apache License 2.0](LICENSE), same as the rest of the project.
