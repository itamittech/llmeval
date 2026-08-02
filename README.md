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

Along the way it demonstrates: agent swarm architecture, agent memory, context compaction, prompt caching, token and cost monitoring, observability, and LLM-based evaluation.

→ **[Read the LUDO project brief](docs/projects/ludo/brief.md)**

## Documentation

**Start here**
- [Vision & teaching philosophy](docs/vision.md) — what this repo is for and how it's written
- [Architecture overview](docs/architecture/overview.md) — the parity model that makes comparison possible
- [Open questions](docs/open-questions.md) — decisions still on the table

**Architecture**
- [Repository layout](docs/architecture/repository-layout.md)
- [Environment strategy](docs/architecture/environment-strategy.md) — how two Python stacks and a JVM coexist
- [Stack capability matrix](docs/architecture/stack-comparison.md) — the running scoreboard of framework gaps

**Project: LUDO**
- [Brief](docs/projects/ludo/brief.md) · [Game rules](docs/projects/ludo/game-rules.md) · [Agent design](docs/projects/ludo/agent-design.md) · [Evaluation](docs/projects/ludo/evaluation.md)
- [Engine design](docs/projects/ludo/engine-design.md) — how the built engine is structured, and what a Java port must preserve
- [Class design](docs/projects/ludo/class-design.md) — diagrams: the object graph, a turn traced as calls, module layering

**New to Python?**
- [learning/python/](learning/python/) — runnable examples and a line-by-line walkthrough of the engine's densest class. Standalone; no dependencies.

**Other**
- [Topic roadmap](docs/topics/roadmap.md) — the 17 topics and which project covers each
- [Architecture decisions (ADRs)](docs/decisions/) — what we chose and why
- [docs/roughidea.txt](docs/roughidea.txt) — the original napkin sketch everything grew from

## Status

🚧 **Early build.** The foundations are in; no agents yet.

| | |
|---|---|
| ✅ | [Shared event schema](shared/schemas/) — the contract all three stacks emit |
| ✅ | [Python game engine](projects/ludo/engine-python/) — full rules, 52 tests passing |
| ✅ | [Cross-engine conformance vectors](shared/conformance/) |
| ⬜ | Java engine · agent stacks · UI · eval harness |

Try it without installing anything but [uv](https://docs.astral.sh/uv/) — no API keys, no cost:

```bash
uv run --directory projects/ludo/engine-python python -m ludo_engine.cli play --seed 7
```

Settled: three parallel games (one per stack), [two shared engines](docs/decisions/adr-0002-engine-per-language.md), [one model on both access routes as a control](docs/decisions/adr-0005-model-access-control.md), React + Vite, Maven. Still undecided: [open questions](docs/open-questions.md).

## Cloud footprint

AWS Bedrock · AgentCore · Lambda · API Gateway · SageMaker — introduced as projects need them, not all at once. See the [topic roadmap](docs/topics/roadmap.md).

## License

[Apache License 2.0](LICENSE) — permissive, with an explicit patent grant. Use it, fork it, teach from it.
