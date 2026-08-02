# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status

The **shared event schema** and the **Python engine** are built and tested. No agent stack, UI, or eval harness exists yet.

| Component | State |
|---|---|
| `shared/schemas/` — event contract | ✅ Built |
| `projects/ludo/engine-python/` | ✅ Built, 52 tests passing |
| `shared/conformance/` — cross-engine vectors | ✅ 20 vectors |
| `engine-java`, `stack-*`, `ui/`, `eval/` | ❌ Not started |

## Commands

`just` is the entry point ([justfile](justfile)) but is **not currently installed** on this machine — the underlying `uv` commands below are what actually run.

```bash
uv sync --directory projects/ludo/engine-python
```

```bash
uv run --directory projects/ludo/engine-python pytest
```

A single test:

```bash
uv run --directory projects/ludo/engine-python pytest tests/test_moves.py::test_no_capture_on_a_safe_square
```

Cross-engine conformance, plus a random-bot game and transcript validation:

```bash
uv run --directory projects/ludo/engine-python python -m ludo_engine.cli conformance --check
```

```bash
uv run --directory projects/ludo/engine-python python -m ludo_engine.cli play --seed 7 --out ../games/g.jsonl
```

```bash
uv run --directory projects/ludo/engine-python python -m ludo_engine.cli validate ../games/g.jsonl
```

No linter or formatter is configured yet. Nothing above makes a model call or costs anything.

## Still undecided

Some foundational decisions are still open — read [docs/open-questions.md](docs/open-questions.md) before proposing or writing code.

**Settled:** three parallel games (each stack runs its own full 4-agent game); two engines, one per language ([ADR-0002](docs/decisions/adr-0002-engine-per-language.md)); one model invoked via *both* Bedrock and direct API as a control ([ADR-0005](docs/decisions/adr-0005-model-access-control.md)); React + Vite for the UI; Maven for the Java stack.

**Still open:** concrete model IDs, Python version pin for the stacks, turn/token budgets, license. ADRs 0001, 0003, and 0004 remain **Proposed** — they encode reasoning from the brief but haven't been explicitly confirmed.

## Orientation

Read in this order:

0. [docs/glossary.md](docs/glossary.md) — the repo's vocabulary; keep it to hand
1. [docs/vision.md](docs/vision.md) — what this repo is for
2. [docs/architecture/overview.md](docs/architecture/overview.md) — **the most important doc**; the parity model everything else follows from
3. [docs/projects/ludo/brief.md](docs/projects/ludo/brief.md) — the first project
4. [docs/projects/ludo/engine-design.md](docs/projects/ludo/engine-design.md) — how the built engine is structured, before changing any of it
5. [docs/open-questions.md](docs/open-questions.md) — what's undecided

[docs/roughidea.txt](docs/roughidea.txt) is the original brief and the source of authority for scope and intent. It is preserved verbatim for provenance — **do not edit it**; capture evolved thinking in the docs instead.

## What this project is

A public, teaching-oriented repository of **gamified LLM experiments**. Every project is a game played by LLM agents, built three times — Strands (Python), LangChain/LangGraph (Python), Spring AI (Java) — so the frameworks can be compared directly.

First project: **LUDO**, four LLM agents playing the Indian board game, two invoked via AWS Bedrock and two via direct provider APIs, allowed to form and break alliances.

## Constraints that are easy to violate

**Parity is the point.** The three implementations must differ *only* in the agent framework. Anything that lets one stack diverge — a different prompt, a tweaked rule, an extra retry — invalidates the comparison. Prompts live in `shared/prompts/` and are shared verbatim.

**Capability gaps are deliverables, not bugs.** When a framework can't do something (e.g. Spring AI lacking a harness primitive the Python stacks get free), record it in [the capability matrix](docs/architecture/stack-comparison.md) and surface it in the UI. Never quietly hand-roll a substitute and imply parity.

**Never share a Python environment between the two Python stacks.** Separate venvs, separate lockfiles, same pinned interpreter version. See [environment strategy](docs/architecture/environment-strategy.md).

**Guardrails are lenient by design.** Agent deception, bluffing, and betrayal are the phenomena under study. Guardrails block *out-of-fiction* attacks (prompt injection, forged state, abuse), never in-game cunning. See [ADR-0004](docs/decisions/adr-0004-structural-guardrails.md).

**The engine never imports an LLM SDK.** `engine-*` is deterministic, testable at speed, with zero API calls.

**Agent claims are claims, not facts.** Agents lie deliberately. Anything deriving from transcripts — summaries, UI, eval — must not treat agent statements as ground truth.

**Everything flows through the event stream.** All three stacks emit one shared schema; the UI and eval harness consume only that, and must work offline against committed sample games with no API keys. See [ADR-0003](docs/decisions/adr-0003-shared-event-stream.md).

**Concise over verbose.** A stated goal. Over-commented code and padded docs both work against the teaching aim.

## Layout

Full planned structure is in [docs/architecture/repository-layout.md](docs/architecture/repository-layout.md). Directories not listed in the status table above do not exist yet.

Two conventions the engine already relies on: positions are **colour-relative** (`-1` base, `0`–`50` circuit, `51`–`55` home column, `56` home), and `shared/` holds contracts and data only — never executable code.

`learning/` is standalone teaching material for readers new to Python — not imported by anything, not part of any build. Its examples must stay dependency-free so they run with bare `python`.

## Docs conventions

- Non-obvious, expensive-to-reverse decisions get an [ADR](docs/decisions/README.md). Accepted ADRs are never edited — supersede them instead.
- Ratings in the capability matrix and scores from the LLM judge must cite evidence. Unsourced claims don't go in.
- Keep [docs/topics/roadmap.md](docs/topics/roadmap.md) current when a project claims a topic.
