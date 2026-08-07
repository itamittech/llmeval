# Project 01 — LUDO

**Four LLM agents play Ludo. Two reach their models through AWS Bedrock, two through direct provider APIs. They are allowed to form alliances, and allowed to break them.**

This is the repo's first project and its template: whatever we learn about structuring a three-stack comparison here carries into everything after.

> New to any of this vocabulary — *swarm*, *harness*, *guardrail*, *LLM-as-judge*? The [glossary](../../glossary.md) explains every term in plain English.

## What it demonstrates

| Topic | How it shows up |
|---|---|
| Agent swarm architecture | Four peer agents taking turns, negotiating between moves |
| Bedrock vs. direct API | Two agents each way, same game, measured side by side |
| LLM-as-judge evaluation | Judge scores strategic quality, not just the win |
| Mid-game evaluation | Turn cap means most games are scored from position, not completion |
| Agent memory | Agents remember who betrayed them, and act on it |
| Context compaction | The transcript outgrows the window; something has to give |
| Prompt caching | Big stable rules prompt, small volatile state — the ideal cache shape |
| Token & cost monitoring | Per-agent, per-turn, enforced budgets |
| Observability | Full trace of every turn, decision, and message |
| Guardrails | Lenient by design — see below |
| Three-stack comparison | Same game, three frameworks, [one matrix](../../architecture/stack-comparison.md) |

## Why Ludo

It's an unusually good testbed, and not only because it's fun:

- **Simple rules, real strategy.** An agent can learn it in one prompt, but playing well needs planning under uncertainty.
- **Genuinely four-player.** Most game benchmarks are two-player zero-sum. Four players make *coalitions* possible — and coalitions are where interesting agent behaviour lives.
- **Luck provides cover.** Dice mean a betrayal can be disguised as bad luck. Agents have to reason about intent under noise, which is a far richer problem than perfect-information chess.
- **Naturally observable.** Board position is a clean progress metric at any moment, which is exactly what mid-game evaluation needs.
- **Culturally rooted.** Ludo comes from *Pachisi*; it's a household game across India. Teaching material lands better when it's built on something people already love.

## The alliance mechanic

This is the heart of the project.

Between rolls, agents can talk — publicly at the table, or privately to one other agent. They can propose coordinated play ("both of us target yellow, they're two tokens from winning"), promise restraint, threaten retaliation, and lie about all of it.

Nothing enforces an agreement. There is no binding-contract mechanism, deliberately. A promise is worth exactly what the other agent's judgement says it's worth, which means agents must model each other's reliability — and **that** is the behaviour we're actually here to observe.

Because only one player wins, every alliance must eventually break. The interesting question is *when* each agent chooses to break it, and whether it saw the other's betrayal coming.

## Guardrails: lenient on purpose

> From the brief: *"We need to make guardrails but lenient enough as there will be cunningness and cleverness which agent can show."*

The line is **in-fiction versus out-of-fiction**.

**Allowed** — bluffing, misdirection, broken promises, forming a coalition against the leader, exaggerating threats, feigning weakness, opportunistic betrayal.

**Blocked** — prompt injection aimed at other agents or the harness, attempts to forge game state or claim illegal moves, real-world harassment or slurs, and anything that breaks character to attack the system rather than the players.

This distinction is enforceable because of the [tool contract](../../architecture/overview.md): agents cannot touch game state directly, so a lying agent is still only ever *lying* — the engine validates every move regardless. **Cheating is structurally impossible, so deception can be safely permitted.** That's a genuinely useful lesson about where guardrails belong.

## Bedrock vs. direct API

Two agents are invoked through Bedrock, two through direct provider APIs, and the differences get measured rather than asserted: authentication and credential handling, latency and cold-start, cost accounting granularity, guardrail availability (Bedrock Guardrails have no direct-API equivalent), observability hooks, and how much of this each of the three frameworks abstracts away.

**One model runs on both routes** — occupying one Bedrock seat and one direct seat — so route differences can't be confused with model differences ([ADR-0005](../../decisions/adr-0005-model-access-control.md)). The other two seats go to different model families, to keep the alliance dynamics interesting.

The families are settled: **Anthropic on both routes** as the control, **Amazon Nova** on the remaining Bedrock seat, **DeepSeek** on the remaining direct seat, and an **OpenAI** reasoning model as the judge — which is why OpenAI does not play. A judge scoring its own family is the first thing a reader would attack.

Assignment is config, not code — [`shared/models.yaml`](../../../shared/models.yaml), and the seat→colour mapping [rotates between games](../../decisions/adr-0006-seat-rotation.md). Concrete model IDs are still an [open question](../../open-questions.md).

## Scoring and the turn cap

Games run to a configurable turn cap. Most won't finish, and that's fine — the match is scored on **position plus play quality** by a combination of deterministic metrics and an LLM judge. Full detail in [evaluation](evaluation.md).

## The UI

The UI carries as much of the teaching load as the code.

**During the game** — the board, whose turn it is, the dice, and each agent's reasoning as it decides. Public table notes and (revealed to the *viewer*, not to other players) directed messages. Live token and cost counters. Memory writes and context compactions shown as they happen.

**After the game** — a well-presented summary: final standing, the turning points, which alliances formed and how they ended, who read the game best, and the judge's reasoning.

**Always** — an architecture layer that explains what the reader is looking at: the swarm design, the harness features in play, and where each framework fell short. A reader who has never opened the source should still leave understanding how it works.

Framework choice is an [open question](../../open-questions.md); the architecture assumes the UI consumes recorded event streams so it runs with no backend and no API keys.

## Scope boundaries

**In scope** — the game, four agents, alliances, three stack implementations, evaluation, UI, local execution against real model APIs.

**Out of scope for v1** — human players, AWS deployment (Lambda/API Gateway come later), AgentCore, SageMaker and fine-tuning, voice, RAG. These belong to later projects on the [roadmap](../../topics/roadmap.md).

## Related

- [Game rules](game-rules.md) — the normative spec
- [Engine design](engine-design.md) — how the built engine is structured · [class diagrams](class-design.md)
- [Agent design](agent-design.md) — swarm, prompts, memory, negotiation
- [Evaluation](evaluation.md) — judging an unfinished game
- [Architecture overview](../../architecture/overview.md)
- [Open questions](../../open-questions.md)
- [Project 02 — ALIBI](../alibi/brief.md) — the successor that inherits this template ([ADR-0010](../../decisions/adr-0010-project-two-alibi.md))
