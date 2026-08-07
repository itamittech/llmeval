# llmeval — Learning LLM Engineering by Building Games

> Three stacks. One problem. Watch what changes.

This is a public, open repository of **gamified LLM experiments**. Every project here is a game that LLM agents play — and every project is built **three times**, once in each of three different agent frameworks, so you can see exactly where the frameworks diverge.

The games are the fun part. The comparison is the point.

## Why three implementations?

Pick any LLM tutorial and it teaches you one framework. You learn *that framework's* opinion about what an agent is, and you never find out which parts were essential and which were just that library's taste.

So we build the same thing three times:

| Stack | Language | Why it's here |
|---|---|---|
| [Strands Agents SDK](https://strandsagents.com/) | Python | AWS-native, model-driven agent loop, deliberately minimal |
| [LangChain + LangGraph](https://www.langchain.com/) | Python | The incumbent; explicit graph-based orchestration |
| [Spring AI](https://spring.io/projects/spring-ai) | Java | Enterprise JVM reality — where a lot of production AI actually lives |

When one framework can do something the others can't — or makes something painful that others make trivial — **that gap is a headline result, not an inconvenience.** We document it and show it in the UI.

## The first project: LUDO

Four LLM agents play [Ludo](docs/projects/ludo/game-rules.md), the classic Indian board game. **Two agents are invoked through AWS Bedrock, two through direct provider APIs** — another controlled comparison baked into the game.

The agents don't just roll dice. They can **form alliances**, gang up on whoever's winning, and betray each other when it suits them. Guardrails are deliberately lenient: cunning is the phenomenon under study.

The game may not even finish — there's a turn cap, and we evaluate **mid-game position** with an LLM-as-judge to decide who actually played best.

Along the way it demonstrates the machinery that turns a language model into an agent:

| | |
|---|---|
| **Agent swarm** | four peers with their own goals, negotiating, no coordinator |
| **Agent memory** | what each agent recalls about the others between turns — including things it was lied to about |
| **Context compaction** | the transcript outgrows what the model can read; something has to be summarised away |
| **Prompt caching** | reusing the unchanged part of a prompt to cut cost and latency |
| **Token & cost monitoring** | per agent, per turn, with enforced budgets |
| **Observability** | a full trace of every decision, so behaviour can be explained afterwards |
| **LLM-as-judge** | scoring the quality of play that no simple metric captures |

Not sure what some of those mean? That's expected — **[the glossary](docs/glossary.md) explains every term this repo uses**, in plain English.

→ **[Read the LUDO project brief](docs/projects/ludo/brief.md)**

## The second project: ALIBI

Four LLM detectives race to solve a theft. The truth is sealed at game start; the evidence is split between **private exhibits** and a **public archive of witness statements** that can only be *searched* — and some witnesses are lying. Asking the table compels real evidence but leaks your line of inquiry; searching the archive is private but returns claims, not facts.

ALIBI introduces exactly two new hard things — **RAG** (retrieval as gameplay, measurable against ground truth) and the **agent-as-tool** architecture (the archivist, a retrieval specialist the detectives consult) — and inherits everything else from LUDO. Design phase: brief and rules exist, code doesn't.

→ **[Read the ALIBI project brief](docs/projects/alibi/brief.md)**

## Documentation

**[📖 Glossary](docs/glossary.md)** — every term this repo uses, in plain English. Start here if anything above was unfamiliar.

### Where to start, depending on who you are

| If you're… | Read, in this order |
|---|---|
| **New to LLM engineering** | [Glossary](docs/glossary.md) → [Vision](docs/vision.md) → [LUDO brief](docs/projects/ludo/brief.md) |
| **Here for the framework comparison** | [Architecture overview](docs/architecture/overview.md) → [Capability matrix](docs/architecture/stack-comparison.md) |
| **New to Python** | [What the files and folders are](learning/python/00-files-and-folders.md) → [learning/python](learning/python/) → [`Game` walkthrough](learning/python/01-walkthrough-game.md) |
| **New to Java, or curious how it compares** | [learning/java](learning/java/) → [the same engine, twice](learning/java/01-same-engine-twice.md) — identical rules in both languages, so every difference isolates a language property |
| **Coming from Java/Spring to Python** | [Python for the Spring developer](learning/python/04-for-spring-developers.md) — `implements`, the container, `@Qualifier`, all mapped side by side onto this codebase |
| **Trying to read the agent harness** | [learning/strands](learning/strands/) — the agent loop, one turn traced, the swarm table, then [the full picture](learning/strands/03-the-full-picture.md) → [class-design §9](docs/projects/ludo/class-design.md#9-the-harness-layer-the-same-turn-on-strands) for the reference diagrams, [§10](docs/projects/ludo/class-design.md#10-the-harness-layer-second-take-the-same-turn-on-spring-ai) for the same turn on Spring AI, [§11](docs/projects/ludo/class-design.md#11-the-harness-layer-third-take-the-same-turn-on-langgraph) for the same turn on LangGraph — ending in the three-grains table |
| **Curious about design patterns** | [Class design §7](docs/projects/ludo/class-design.md#7-design-patterns-from-the-problem-up) — each one taught from the problem up |
| **Interested in experiment design** | [ADR-0005](docs/decisions/adr-0005-model-access-control.md) → [ADR-0006](docs/decisions/adr-0006-seat-rotation.md) — how to keep a comparison from quietly meaning nothing |
| **About to write code** | [Engine design](docs/projects/ludo/engine-design.md) → [Class design](docs/projects/ludo/class-design.md) → [Open questions](docs/open-questions.md) |
| **Just want to see it run** | the [command below](#status) — no keys, no cost |

### Everything else

**Foundations**
- [Vision & teaching philosophy](docs/vision.md) — what this repo is for and how it's written
- [Architecture overview](docs/architecture/overview.md) — the parity model that makes comparison possible
- [Open questions](docs/open-questions.md) — decisions still on the table

**Architecture**
- [Repository layout](docs/architecture/repository-layout.md)
- [Shared prompts](shared/prompts/README.md) — the prompts all three stacks send, and why the template language has no `if`
- [Environment strategy](docs/architecture/environment-strategy.md) — how two Python stacks and a JVM coexist
- [Stack capability matrix](docs/architecture/stack-comparison.md) — the running scoreboard of framework gaps

**Project: ALIBI** (design phase)
- [Brief](docs/projects/alibi/brief.md) · [Game rules (draft)](docs/projects/alibi/game-rules.md) · [ADR-0010](docs/decisions/adr-0010-project-two-alibi.md) — why this game, and why it isn't called Cluedo

**Project: LUDO**
- [Brief](docs/projects/ludo/brief.md) · [Game rules](docs/projects/ludo/game-rules.md) · [Agent design](docs/projects/ludo/agent-design.md) · [Evaluation](docs/projects/ludo/evaluation.md)
- [Harness contract](docs/projects/ludo/harness-contract.md) — the normative spec all three agent stacks implement
- [Engine design](docs/projects/ludo/engine-design.md) — how the built engine is structured, and what a Java port must preserve
- [Class design](docs/projects/ludo/class-design.md) — diagrams: the object graph, a turn traced as calls, module layering, and all three harness layers (§§9–11)

**New to a language or framework here?**
- [learning/python/](learning/python/) — runnable examples and a line-by-line walkthrough of the engine's densest class. Standalone; no dependencies.
- [learning/java/](learning/java/) — the same engine in Java, read against the Python one. Examples run with a bare JDK: `java learning/java/examples/03_signed_shift.java`.
- [learning/strands/](learning/strands/) — the first agent harness: what the framework does when you call an agent, how a turn flows through it, and how the swarm negotiation actually works. Its examples are the stack's own tests.
- [learning/springai/](learning/springai/) — the Java harness: the flattest model seam of the three, the advisor that *is* the conversation memory, and the tool-form table with the guardrail gate inside it.
- [learning/langgraph/](learning/langgraph/) — the graph-shaped harness: state that belongs to the runtime, middleware where hooks used to be, and ADR-0009's protocol literally drawn as nodes and edges. Read all three folders and you've read the capability matrix in prose.

**Other**
- [Contributing](CONTRIBUTING.md) — setup, and the six rules that are easy to break by accident
- [Topic roadmap](docs/topics/roadmap.md) — the 17 topics and which project covers each
- [Architecture decisions (ADRs)](docs/decisions/) — what we chose and why
- [docs/roughidea.txt](docs/roughidea.txt) — the original napkin sketch everything grew from

## Status

🚧 **Scripted era — all three stacks now play.** The comparison is complete at the scripted tier: every stack runs full games end to end — negotiation, memory, compaction, guardrails, session persistence — against *scripted* models, so every run is free and byte-reproducible, and the capability matrix has all three columns filled. **No live model call has been made yet:** the last blocker is two model IDs ([open questions](docs/open-questions.md)).

| | |
|---|---|
| ✅ | [Shared event schema](shared/schemas/) — the contract all three stacks emit |
| ✅ | [Python game engine](projects/ludo/engine-python/) — full rules + agent hooks, 68 tests passing |
| ✅ | [Java game engine](projects/ludo/engine-java/) — same rules, 20 tests; byte-identical transcripts to Python |
| ✅ | [Shared prompts](shared/prompts/README.md) + [model config](shared/models.yaml) — identical across all three stacks, invariants enforced in CI |
| ✅ | [CI](.github/workflows/ci.yml) — tests, conformance, schema, docs, mermaid diagrams, prompt invariants. No model calls, no cost. |
| ✅ | [Cross-engine conformance vectors](shared/conformance/) |
| ✅ | [Strands stack](projects/ludo/stack-strands/) — feature-complete on scripted models: turn loop, swarm negotiation, compaction, lenient guardrails, session persistence, events. 40 tests, [schema-valid fixture](projects/ludo/games/scripted-strands-seed7.jsonl). **No live game yet** — waiting only on Nova + DeepSeek model IDs. |
| ✅ | [UI](projects/ludo/ui/) — transcript player + eval-report panel (React + Vite), offline against the committed fixtures and their `.eval.json` results; [ADR-0007](docs/decisions/adr-0007-ui-alongside-first-stack.md)'s rules **proven three times**: each new stack's fixture landed and the suite grew (now 29 tests) with zero UI changes |
| ✅ | [Spring AI stack](projects/ludo/stack-springai/) — feature-complete on scripted models: tool-driven floor passing, conversation memory, hand-rolled compaction, guardrails, split session persistence (conversations through the framework's JDBC repository, beliefs by hand), [fixture committed](projects/ludo/games/scripted-springai-seed7.jsonl). Its predicted findings all recorded — no orchestrator, no belief store, truncation-only memory, the simplest model seam of the three. **No live game yet** — waiting only on model IDs |
| ✅ | [LangGraph stack](projects/ludo/stack-langgraph/) — feature-complete on scripted models: the negotiation table **drawn as a StateGraph** (the family's own swarm package rejected on the privacy rule — a headline matrix finding), checkpointer threads, beliefs in the framework Store, compaction on its summarisation middleware, sqlite session persistence with **no save call at all**, [fixture committed](projects/ludo/games/scripted-langgraph-seed7.jsonl). **No live game yet** — same two model IDs |
| ✅ | [Eval harness](projects/ludo/eval/) — deterministic scoring on every committed game (its replay self-verifies against the engine's own standings), the LLM-judge machinery with its bias mitigations built as code (anonymisation, citation enforcement, multi-run spread), the [judge rubric](shared/prompts/ludo/judge/scoring.md) written and hash-stamped into every result. **Live judging waits on the judge model ID** |
| ⬜ | live games — two player model IDs and one judge ID away |
| 📋 | [ALIBI](docs/projects/alibi/brief.md) — project two, chosen and documented ([ADR-0010](docs/decisions/adr-0010-project-two-alibi.md)): brief + draft rules. RAG and agent-as-tool are its two new hard things. No code yet |

Try it without installing anything but [uv](https://docs.astral.sh/uv/) — no API keys, no cost:

```bash
uv run --directory projects/ludo/engine-python python -m ludo_engine.cli play --seed 7
```

Or *watch* a recorded game in the browser (needs node):

```bash
npm ci --prefix projects/ludo/ui
```

```bash
npm run dev --prefix projects/ludo/ui
```

Settled: three parallel games (one per stack), [two shared engines](docs/decisions/adr-0002-engine-per-language.md), [one model on both access routes as a control](docs/decisions/adr-0005-model-access-control.md), [framework-native harnesses over a shared behavioural contract](docs/decisions/adr-0008-framework-native-harness.md), React + Vite, Maven. Still undecided: [open questions](docs/open-questions.md).

## Cloud footprint

AWS Bedrock · AgentCore · Lambda · API Gateway · SageMaker — introduced as projects need them, not all at once. See the [topic roadmap](docs/topics/roadmap.md).

## License

[Apache License 2.0](LICENSE) — permissive, with an explicit patent grant. Use it, fork it, teach from it.
