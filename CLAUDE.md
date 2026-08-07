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
| Engine classes, methods, or structure | [engine-design.md](docs/projects/ludo/engine-design.md) · [class-design.md](docs/projects/ludo/class-design.md) — the **diagrams AND** the class-reference and who-calls-what tables · the engine README module map · **[learning/python/01](learning/python/01-walkthrough-game.md) if you touched `game.py`** — it quotes that file line by line, so a rename silently makes it teach code that no longer exists · **[learning/java/01](learning/java/01-same-engine-twice.md) if the two engines diverged** — it is a side-by-side, so it goes stale from either side |
| Anything a stack does — turn loop, events, memory, budgets | [harness-contract.md](docs/projects/ludo/harness-contract.md) **first** (it's the normative spec all three stacks bind to), then the stack |
| `stack-strands` harness classes or call flow | [class-design.md §9](docs/projects/ludo/class-design.md) diagrams · **[learning/strands](learning/strands/)** — 00 quotes the agent construction, 01–02 trace the turn and the swarm, 03 is the assembled map (wiring, turn flowchart, memory stores, cast lifetimes), and the README's class table names what's wired vs pending · the stack README module map · [learning/python/04](learning/python/04-for-spring-developers.md) quotes the `_Decider` wiring |
| `stack-springai` harness classes or call flow | [class-design.md §10](docs/projects/ludo/class-design.md) — the object graph, both call traces, and the two-grains table · its [README](projects/ludo/stack-springai/README.md) design section + status table · **[learning/springai](learning/springai/)** — 00 quotes the scripted seam and the hidden tool loop, 01 the advisor/compaction/persistence story, 02 the tool-form table; the README's class table names what's wired · the [matrix](docs/architecture/stack-comparison.md) springai column and its finding |
| `stack-langgraph` harness classes or call flow | [class-design.md §11](docs/projects/ludo/class-design.md) — the object graph, both call traces, the drawn table graph, and the three-grains table · its [README](projects/ludo/stack-langgraph/README.md) design section + status table · **[learning/langgraph](learning/langgraph/)** — 00 quotes the state/thread model, 01 the middleware and meter, 02 draws the table and the no-save persistence; the README's class table names what's wired · the [matrix](docs/architecture/stack-comparison.md) langgraph column and its findings |
| The event schema | [shared/schemas/README.md](shared/schemas/README.md) · [ADR-0003](docs/decisions/adr-0003-shared-event-stream.md) if the contract itself changed · every stack that emits |
| Dependencies, tooling, environment layout | [environment-strategy.md](docs/architecture/environment-strategy.md) · [repository-layout.md](docs/architecture/repository-layout.md) · [learning/python/03](learning/python/03-environments-and-packaging.md) |
| Prompts, `models.yaml`, or anything in `shared/` | [shared/prompts/README.md](shared/prompts/README.md) · [agent-design.md](docs/projects/ludo/agent-design.md) · re-run `check_prompts.py` · a rule-number change means [game-rules.md](docs/projects/ludo/game-rules.md) first |
| Introduced any term a reader might not know | [glossary.md](docs/glossary.md) — no exceptions; this is how the repo stays readable |
| Settled an open question | Move it to **Answered** in [open-questions.md](docs/open-questions.md) with the outcome; write an [ADR](docs/decisions/) if it was expensive to reverse |
| Learned what a framework can or can't do | [stack-comparison.md](docs/architecture/stack-comparison.md) — with a link to the code that proves it |
| Started or finished a component | Status tables in [README.md](README.md) **and** this file · [repository-layout.md](docs/architecture/repository-layout.md) |
| A project claimed a topic | [topics/roadmap.md](docs/topics/roadmap.md) |
| The UI | [its README](projects/ludo/ui/README.md) · ADR-0007's rules are UI **tests** — if adding a stack's transcript forces a UI source change, that is the failure the fixture set exists to catch, not something to code around |
| Eval scoring, judge machinery, or the rubric | [evaluation.md](docs/projects/ludo/evaluation.md) Status · the eval [README](projects/ludo/eval/README.md) design + status table · [schemas README](shared/schemas/README.md) if the result shape changed · the judge prompt's hash makes rubric edits visible — bump nothing, the hash IS the version |
| ALIBI's rules, case model, or archive design | [docs/projects/alibi/game-rules.md](docs/projects/alibi/game-rules.md) **first** (normative once ratified — element names will be baked into corpus bytes), then [the brief](docs/projects/alibi/brief.md) if the project's shape moved; a change to the two-new-hard-things scope means revisiting [ADR-0010](docs/decisions/adr-0010-project-two-alibi.md) |
| Added a new doc | Link it from [README.md](README.md) and from the Related section of any sibling doc |

### Then verify

```bash
python scripts/check_docs.py
```

Checks links, anchors, and Mermaid *structure* across every markdown file.

If you touched a Mermaid diagram, that structural pass is not enough — it only knows the mistakes we have already made. Parse the diagrams for real:

```bash
node scripts/check_mermaid.mjs
```

This hands every ```` ```mermaid ```` block to mermaid's own parser, which is the only thing that can answer *does this diagram render*. We added it after shipping a diagram with a node called `call` — a click-callback directive, not a node id — and hearing about it from a reader. Needs `npm ci` once.

**Run both.** Neither subsumes the other, in either direction: `check_docs.py` runs without node and flags reserved-word node ids that mermaid *currently* tolerates but that break the moment an edge is reordered; `check_mermaid.mjs` catches every malformed diagram nobody thought to hand-code a rule for.

**Neither can check whether the prose is still true** — that part is on you. Re-read every section that touches what you changed.

If you touched anything in `shared/`, also:

```bash
uv run scripts/check_prompts.py
```

Checks the invariants that make the comparison mean anything — no template logic, declared variables match used ones, prompt rule numbers match the engine's constants, one model on both access routes, judge not seated, no secrets in `models.yaml`. Every one of these fails *silently* if unchecked.

### If you can't fix a doc in the same commit

Say so explicitly in your response, naming the file and what's now wrong. An acknowledged gap is recoverable; a silent one is not.

---

## Repository status

The **shared event schema**, **both engines** (Python and Java, cross-checked by conformance vectors), and the **shared prompt set + model config** are built and tested. The **Strands stack is feature-complete against scripted models** — swarm negotiation, memory in agent state, budgets and events in lifecycle hooks, context compaction via each agent summarising itself, lenient content guardrails at the message boundary, opt-in session persistence — all Strands-native per [ADR-0008](docs/decisions/adr-0008-framework-native-harness.md)/[0009](docs/decisions/adr-0009-swarm-negotiation.md). The **Spring AI stack is feature-complete against scripted models** — the floor-passing loop is harness code (its predicted Manual finding) but the pass is a real framework tool with the guardrail gate inside it; conversation memory on `ChatMemory`; compaction hand-rolled because the framework only truncates; opt-in session persistence split down the memory line (conversations through the framework's JDBC repository over embedded H2, beliefs saved by the harness); live Anthropic options pinned and read back. The **LangGraph stack is feature-complete against scripted models** — ADR-0009's table drawn as a `StateGraph` (the family's own swarm package rejected on the contract's privacy rule — a matrix finding), conversation threads on the checkpointer, beliefs in the framework `Store`, compaction on the framework's `SummarizationMiddleware` with the game budget as trigger, session persistence by swapping both stores for their sqlite twins (no save call exists) — all LangGraph-native per [ADR-0008](docs/decisions/adr-0008-framework-native-harness.md). The **UI transcript player is built** (plus an eval-report panel rendering each game's committed `.eval.json`), and ADR-0007's rules are proven three times over: each new stack's fixture landed and the suite grew (now 29 tests) with zero source changes. The **eval harness is built** — deterministic scoring whose fold self-verifies against `game_ended.standings`, judge machinery (anonymisation down to colour words in message text, citation enforcement, multi-run spread, outcome agreement) tested through scripted callers, every result validated against its shared schema; the judge prompt is written and hash-stamped into results. **No live game has been played**, and none can be until the Nova and DeepSeek model ids are filled in — the judge's OpenAI id gates live judging the same way. **Project two is in build: ALIBI** ([ADR-0010](docs/decisions/adr-0010-project-two-alibi.md), Accepted) — a deduction game whose two new hard things are RAG and agent-as-tool. Its [rules are normative](docs/projects/alibi/game-rules.md) with benched pace numbers (500 games: median 21, p99 45, all solved), **both engines are built and agree on all 20 conformance vectors — corpus bytes included**, since the generated archive rides inside the transcript. Stacks, eval, and UI are not started.

| Component | State |
|---|---|
| `shared/schemas/` — event contract | ✅ Built |
| `projects/ludo/engine-python/` | ✅ Built, 68 tests passing |
| `projects/ludo/engine-java/` | ✅ Built, 20 tests passing; matches Python on all 20 vectors |
| `docs/projects/ludo/harness-contract.md` | ✅ Spec written, re-scoped to observable behaviour ([ADR-0008](docs/decisions/adr-0008-framework-native-harness.md)); §§2–6 running scripted in `stack-strands` |
| `shared/prompts/ludo/` — prompts all stacks send | ✅ 8 templates, v2 (floor-passing negotiation, ADR-0009) |
| `shared/models.yaml` — seats, routes, profiles | ✅ Built; **model IDs still `TBD`** |
| `shared/conformance/` — cross-engine vectors | ✅ 20 vectors |
| `projects/ludo/stack-strands/` | ✅ Feature-complete scripted — turn loop, swarm negotiation, compaction, guardrails, session persistence, events; 40 tests, schema-valid fixture. **No live game** (model IDs TBD) |
| `projects/ludo/ui/` | ✅ Transcript player + eval-report panel (React + Vite), 29 tests; ADR-0007's fixture rules enforced in CI — the transcript AND eval-result suites both walk `games/` and grow with zero source changes |
| `projects/ludo/stack-springai/` | ✅ Feature-complete scripted — tool-driven floor passing, conversation memory, hand-rolled compaction, guardrails, split session persistence, pinned live options; 12 tests, schema-valid fixture. **No live game** (model IDs TBD) |
| `projects/ludo/stack-langgraph/` | ✅ Feature-complete scripted — table as a StateGraph, checkpointer threads, Store beliefs, middleware compaction, sqlite session persistence, pinned live options; 16 tests, schema-valid fixture. **No live game** (model IDs TBD) |
| `projects/ludo/eval/` | ✅ Built — deterministic scoring on every committed game (fold self-verifies against `game_ended`), judge machinery tested through scripted callers, schema-validated results, `score`/`compare`/`conformance` CLI (§8 mechanised — the Python-engine and Java-engine games agree event for event); 37 tests. **Live judge call** ⬜ blocked on the judge model ID |
| Judge prompt | ✅ [`shared/prompts/ludo/judge/scoring.md`](shared/prompts/ludo/judge/scoring.md) — 7 dimensions with anchors, outside the manifest (single consumer), hash recorded per judged result |
| `docs/projects/alibi/` — project two design | ✅ [Brief](docs/projects/alibi/brief.md) · [normative rules](docs/projects/alibi/game-rules.md) with benched numbers · [engine design](docs/projects/alibi/engine-design.md) ([ADR-0010](docs/decisions/adr-0010-project-two-alibi.md), Accepted) |
| `projects/alibi/engine-python/` | ✅ Built — deal, archive generator, referee, baseline retriever, CLI, 37 tests; 500-game bench answered question 21 |
| `projects/alibi/engine-java/` | ✅ Built, 9 tests; **matches Python on all 20 vectors, corpus bytes included** |
| `shared/prompts/alibi/` — prompts + archivist pair | ✅ 8 templates v1 + fixed-contract archivist prompts; invariants in `check_prompts.py` cover both games |
| `docs/projects/alibi/harness-contract.md` | ✅ Spec written — archivist-as-tool binding, privacy MUSTs, scripted tier; compaction/persistence/negotiation deliberately out (§8) |
| `shared/schemas/alibi-event.schema.json` | ✅ Built — element enums normative; archive rides in the transcript |
| `projects/alibi/stack-strands/` | ✅ Feature-complete scripted — archivist as a real framework tool, notebooks on `AgentState`, hook metering, lenient guardrails; 21 tests, schema-valid fixture ([the story](projects/alibi/stack-strands/README.md): red is fooled by both red herrings, cross-checks the witness, solves) |
| `projects/alibi/stack-langgraph/` | ✅ Feature-complete scripted — `create_agent` + archivist tool in the graph, checkpointer threads, Store notebooks, callback metering; 16 tests incl. cross-stack engine-skeleton equality with the Strands fixture |
| `projects/alibi/stack-springai/` | ✅ Feature-complete scripted — archivist as `FunctionToolCallback` (internal tool execution aggregates the consult round: 20 metered calls where Python stacks emit 22, the finding refixtured), hand-rolled notebook again, prompt digest matched across languages; 11 tests |
| `projects/alibi/eval/` | ✅ Built — deterministic only, no judge needed (ground truth exists): Brier calibration, red-herring exposure, standings self-verification, `score`/`compare` CLI proving the three fixtures share one engine spine (22/22/20 calls, the tool-grain finding in numbers); 10 tests, committed `.eval.json` per fixture |
| `projects/alibi/ui/` | ✅ Transcript player (React + Vite, own package.json) — case panel, investigation feed, archive with post-game herring reveal, eval panel; 18 tests: ADR-0007's three rules plus the seal rule (solution and herrings never render before `game_ended`) |

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

The Strands stack (own venv — never shared with LangGraph):

```bash
uv run --directory projects/ludo/stack-strands pytest
```

A full scripted game, offline and free — regenerates the committed fixture byte-identically:

```bash
uv run --directory projects/ludo/stack-strands python -m ludo_strands.demo out.jsonl
```

The LangGraph stack (its own venv and lockfile — the two Python stacks never share one):

```bash
uv run --directory projects/ludo/stack-langgraph pytest
```

```bash
uv run --directory projects/ludo/stack-langgraph python -m ludo_langgraph.demo out.jsonl
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

The eval harness (own venv; consumes transcripts only — free, no keys):

```bash
uv run --directory projects/ludo/eval pytest
```

```bash
uv run --directory projects/ludo/eval python -m ludo_eval score projects/ludo/games/scripted-strands-seed7.jsonl
```

```bash
uv run --directory projects/ludo/eval python -m ludo_eval compare projects/ludo/games/scripted-strands-seed7.jsonl projects/ludo/games/scripted-langgraph-seed7.jsonl projects/ludo/games/scripted-springai-seed7.jsonl
```

The ALIBI UI (own package.json under `projects/alibi/ui`):

```bash
npm ci --prefix projects/alibi/ui
```

```bash
npm test --prefix projects/alibi/ui
```

The UI (own package.json under `projects/ludo/ui` — the root one is repo tooling only):

```bash
npm ci --prefix projects/ludo/ui
```

```bash
npm test --prefix projects/ludo/ui
```

```bash
npm run dev --prefix projects/ludo/ui
```

The ALIBI engine (own venv, same pattern):

```bash
uv run --directory projects/alibi/engine-python pytest
```

```bash
uv run --directory projects/alibi/engine-python python -m alibi_engine.cli play --seed 7
```

```bash
uv run --directory projects/alibi/engine-python python -m alibi_engine.cli conformance --check
```

The ALIBI Strands stack (own venv, never shared):

```bash
uv run --directory projects/alibi/stack-strands pytest
```

```bash
uv run --directory projects/alibi/stack-strands python -m alibi_strands.demo out.jsonl
```

The ALIBI LangGraph stack (own venv and lockfile):

```bash
uv run --directory projects/alibi/stack-langgraph pytest
```

```bash
uv run --directory projects/alibi/stack-langgraph python -m alibi_langgraph.demo out.jsonl
```

The ALIBI eval (own venv; transcripts only — free, no keys):

```bash
uv run --directory projects/alibi/eval pytest
```

```bash
uv run --directory projects/alibi/eval python -m alibi_eval compare projects/alibi/games/scripted-strands-seed7.jsonl projects/alibi/games/scripted-langgraph-seed7.jsonl projects/alibi/games/scripted-springai-seed7.jsonl
```

The ALIBI Java engine, from `projects/alibi/engine-java`:

```bash
./mvnw -B test
```

The Java engine builds with the committed Maven wrapper — no global Maven needed, and Java 21 is already installed here. Run from `projects/ludo/engine-java`:

```bash
./mvnw -B test
```

```bash
./mvnw -q -B exec:java -Dexec.args="conformance --check"
```

The ALIBI Spring AI stack follows the same install-then-test pattern from `projects/alibi`: `cd engine-java && ./mvnw -q -B install -DskipTests`, then `cd stack-springai && ./mvnw -B test`; the fixture regenerates with `./mvnw -q -B exec:java -Dexec.args="../games/scripted-springai-seed7.jsonl"`.

The Spring AI stack depends on the engine by coordinates — install the engine locally once, then test (both from `projects/ludo`):

```bash
cd engine-java && ./mvnw -q -B install -DskipTests
```

```bash
cd stack-springai && ./mvnw -B test
```

**Both engines must pass conformance.** Running only one defeats the point — the vectors exist to catch them disagreeing ([ADR-0002](docs/decisions/adr-0002-engine-per-language.md)).

Mermaid diagrams are parsed by node, not by uv. Once per checkout:

```bash
npm ci
```

```bash
node scripts/check_mermaid.mjs
```

The root [package.json](package.json) exists only for this — repo tooling, not the UI, which gets its own under `ui/` ([ADR-0007](docs/decisions/adr-0007-ui-alongside-first-stack.md)).

No linter or formatter is configured yet. Nothing above makes a model call or costs anything.

## Still undecided

Some foundational decisions are still open — read [docs/open-questions.md](docs/open-questions.md) before proposing or writing code.

**Settled:** three parallel games (each stack runs its own full 4-agent game); two engines, one per language ([ADR-0002](docs/decisions/adr-0002-engine-per-language.md)); one model invoked via *both* Bedrock and direct API as a control ([ADR-0005](docs/decisions/adr-0005-model-access-control.md)); seat→colour rotates between games ([ADR-0006](docs/decisions/adr-0006-seat-rotation.md)); React + Vite for the UI, built to completion *alongside the first stack* and proven stack-independent by transcript fixtures ([ADR-0007](docs/decisions/adr-0007-ui-alongside-first-stack.md)); Maven for the Java stack; Apache-2.0; **Python 3.12** for both stacks; model *families* (Anthropic ×2 routes, Amazon Nova, DeepSeek; OpenAI judges and therefore does not play); negotiation is a **floor-passing table conversation designed to fit the swarm orchestrator** — directed messages + public table notes, opened by the active agent, capped by floor passes, no cross-reading of reasoning ([ADR-0009](docs/decisions/adr-0009-swarm-negotiation.md) revising question 6); harness primitives are **framework-native** — the shared layer is contracts and data only, and hand-rolling where the framework has a primitive breaks the comparison ([ADR-0008](docs/decisions/adr-0008-framework-native-harness.md)).

**Still open:** concrete model IDs for Nova, DeepSeek, and the OpenAI judge (the Anthropic pair is pinned — `claude-sonnet-5` on `dev`, `claude-opus-5` on `headline`), turn/token budgets — provisional values sit in `shared/models.yaml` and get replaced by measured ones after the first stack runs. For ALIBI: pace numbers and retrieval parity (questions 21 and 23) — the name and the no-negotiation decision are ratified (answered questions 20 and 22). ADRs 0001, 0003, and 0004 remain **Proposed** — they encode reasoning from the brief but haven't been explicitly confirmed.

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

`learning/` is standalone teaching material — not imported by anything, not part of any build. `learning/python` and `learning/java` examples must stay dependency-free so they run with a bare interpreter/JDK. The three framework folders — `learning/strands`, `learning/springai`, `learning/langgraph` — have **no examples folders for exactly that reason**: a framework example needs the framework, so each teaches against its stack's own tests, which run in the stack's environment.

## Docs conventions

- Non-obvious, expensive-to-reverse decisions get an [ADR](docs/decisions/README.md). Accepted ADRs are never edited — supersede them instead.
- Teaching material follows the techniques in [vision.md → How the teaching is done](docs/vision.md#how-the-teaching-is-done): problem before solution, **Before you scroll** predictions, named-and-killed misconceptions, one handle per concept, check-yourself retrieval at the end. A few lines each — verbosity is not pedagogy.
- Ratings in the capability matrix and scores from the LLM judge must cite evidence. Unsourced claims don't go in.
- Keep [docs/topics/roadmap.md](docs/topics/roadmap.md) current when a project claims a topic.
