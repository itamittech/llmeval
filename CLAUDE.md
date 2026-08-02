# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## ⚠️ Rule #1 — docs ship with the change

**This overrides every other priority in this repo, including finishing the code.**

This project exists to teach. A doc describing code that no longer exists is *worse than no doc*: it misleads the reader who trusted it, and it costs us the thread of our own reasoning. Stale docs don't degrade this repo gradually — they defeat its purpose outright.

**Documentation updates land in the SAME commit as the change they describe.** Not "after", not "in a follow-up PR", not "once it settles". There is no after.

### Before any task is done, walk this map

| If you changed… | You must update |
|---|---|
| Game rules or engine behaviour | [game-rules.md](docs/projects/ludo/game-rules.md) **first** (it's the normative spec), then the engines, then regenerate conformance vectors |
| Engine classes, methods, or structure | [engine-design.md](docs/projects/ludo/engine-design.md) · [class-design.md](docs/projects/ludo/class-design.md) — the **diagrams AND** the class-reference and who-calls-what tables · the engine README module map |
| The event schema | [shared/schemas/README.md](shared/schemas/README.md) · [ADR-0003](docs/decisions/adr-0003-shared-event-stream.md) if the contract itself changed · every stack that emits |
| Dependencies, tooling, environment layout | [environment-strategy.md](docs/architecture/environment-strategy.md) · [repository-layout.md](docs/architecture/repository-layout.md) · [learning/python/03](learning/python/03-environments-and-packaging.md) |
| Prompts, `models.yaml`, or anything in `shared/` | [shared/prompts/README.md](shared/prompts/README.md) · [agent-design.md](docs/projects/ludo/agent-design.md) · re-run `check_prompts.py` · a rule-number change means [game-rules.md](docs/projects/ludo/game-rules.md) first |
| Introduced any term a reader might not know | [glossary.md](docs/glossary.md) — no exceptions; this is how the repo stays readable |
| Settled an open question | Move it to **Answered** in [open-questions.md](docs/open-questions.md) with the outcome; write an [ADR](docs/decisions/) if it was expensive to reverse |
| Learned what a framework can or can't do | [stack-comparison.md](docs/architecture/stack-comparison.md) — with a link to the code that proves it |
| Started or finished a component | Status tables in [README.md](README.md) **and** this file · [repository-layout.md](docs/architecture/repository-layout.md) |
| A project claimed a topic | [topics/roadmap.md](docs/topics/roadmap.md) |
| Added a new doc | Link it from [README.md](README.md) and from the Related section of any sibling doc |

### Then verify

```bash
python scripts/check_docs.py
```

Checks links, anchors, and Mermaid syntax across every markdown file. **It cannot check whether the prose is still true** — that part is on you. Re-read every section that touches what you changed.

If you touched anything in `shared/`, also:

```bash
uv run scripts/check_prompts.py
```

Checks the invariants that make the comparison mean anything — no template logic, declared variables match used ones, prompt rule numbers match the engine's constants, one model on both access routes, judge not seated, no secrets in `models.yaml`. Every one of these fails *silently* if unchecked.

### If you can't fix a doc in the same commit

Say so explicitly in your response, naming the file and what's now wrong. An acknowledged gap is recoverable; a silent one is not.

---

## Repository status

The **shared event schema**, the **Python engine**, and the **shared prompt set + model config** are built and tested. No agent stack, UI, or eval harness exists yet.

| Component | State |
|---|---|
| `shared/schemas/` — event contract | ✅ Built |
| `projects/ludo/engine-python/` | ✅ Built, 60 tests passing |
| `shared/prompts/ludo/` — prompts all stacks send | ✅ 7 templates |
| `shared/models.yaml` — seats, routes, profiles | ✅ Built; **model IDs still `TBD`** |
| `shared/conformance/` — cross-engine vectors | ✅ 20 vectors |
| `engine-java`, `stack-*`, `ui/`, `eval/` | ❌ Not started |
| Judge prompt | ❌ Waits for the eval harness |

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

**Settled:** three parallel games (each stack runs its own full 4-agent game); two engines, one per language ([ADR-0002](docs/decisions/adr-0002-engine-per-language.md)); one model invoked via *both* Bedrock and direct API as a control ([ADR-0005](docs/decisions/adr-0005-model-access-control.md)); seat→colour rotates between games ([ADR-0006](docs/decisions/adr-0006-seat-rotation.md)); React + Vite for the UI; Maven for the Java stack; Apache-2.0; **Python 3.12** for both stacks; model *families* (Anthropic ×2 routes, Amazon Nova, DeepSeek; OpenAI judges and therefore does not play); negotiation uses both channels, active-agent-driven, no cross-reading of reasoning.

**Still open:** concrete model IDs (families are fixed; the IDs must be *dated snapshots*, not floating aliases), turn/token budgets — provisional values sit in `shared/models.yaml` and get replaced by measured ones after the first stack runs. ADRs 0001, 0003, and 0004 remain **Proposed** — they encode reasoning from the brief but haven't been explicitly confirmed.

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

**Parity is the point.** The three implementations must differ *only* in the agent framework. Anything that lets one stack diverge — a different prompt, a tweaked rule, an extra retry, an unpinned sampling parameter — invalidates the comparison. Prompts live in [`shared/prompts/`](shared/prompts/README.md) and are sent verbatim; no stack may edit them for itself. Templates use literal `{{name}}` substitution with **no conditionals or loops**, because two languages would implement template logic differently and the disagreements would be silent.

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
