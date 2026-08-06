# Topic Roadmap

The [original brief](../roughidea.txt) lists 17 topics. No single project covers them all — each project takes a coherent subset, and the list is explicitly open-ended.

This page tracks which project covers what, so gaps are visible and projects don't accidentally duplicate each other.

## Coverage

| # | Topic | Covered by | Status |
|---|---|---|---|
| 1 | LLM invocation | LUDO — [Strands binding](../../projects/ludo/stack-strands/README.md) built, both access routes wired; no live call yet | 🔲 Partial |
| 2 | LLM comparison | LUDO — seats, routes and the dual-route control are configured ([ADR-0005](../decisions/adr-0005-model-access-control.md)); waits on model ids | 🔲 Partial |
| 3 | Guardrails | LUDO (lenient, game-scoped) | 📋 Planned |
| 4 | Cost analysis | LUDO — per-agent token accounting and a per-game ceiling built | 🔲 Partial |
| 5 | Inference analysis | LUDO (latency, cold start) | 📋 Planned |
| 6 | Observability & monitoring | LUDO | 📋 Planned |
| 7 | Prompt tuning & templates | LUDO — [shared versioned prompts](../../shared/prompts/README.md) built; tuning waits for a stack | 🔲 Partial |
| 8 | Agentic AI | LUDO — three feature-complete agent harnesses over one contract, scripted tier | 🔲 Partial |
| 9 | Agentic architectures | LUDO covers **swarm** only | 🔲 Partial |
| 10 | Voice agents | — | 🔲 Unassigned |
| 11 | RAG | — | 🔲 Unassigned |
| 12 | RAG architectures | — | 🔲 Unassigned |
| 13 | AWS Bedrock features | LUDO (invocation, Guardrails) | 🔲 Partial |
| 14 | AWS SageMaker features | — | 🔲 Unassigned |
| 15 | LLM fine-tuning | — | 🔲 Unassigned |
| 16 | Continued pre-training | — | 🔲 Unassigned |
| 17 | LLM evals | LUDO — [deterministic scoring + judge machinery built](../projects/ludo/evaluation.md#status), rubric hash-stamped; live judging waits on the judge id | 🔲 Partial |

Beyond the original list, LUDO also covers **harness engineering** — agent memory, context compaction, prompt caching — which the brief calls out separately as a requirement.

## Agentic architectures (topic 9)

The brief names four. LUDO takes one; the rest need homes:

| Architecture | Project | Notes |
|---|---|---|
| **Agent swarm** | LUDO | Four peers, no coordinator, negotiation between them |
| **Agent as tool** | — | A game where one agent can consult a specialist |
| **Graph agents** | — | Explicit state-machine flow; LangGraph's home turf |
| **Edge agent** | — | Local/small model at the edge, escalating to a larger one |

Deliberately not designed yet. Project two should be chosen from what LUDO actually teaches us, not planned in advance and then forced to fit.

## Candidate follow-ups

Ideas parked with a reason, so they aren't lost or started too early:

| Idea | Why later |
|---|---|
| **Mixed-stack game** — one game, each agent on a different framework | A genuine interoperability showcase, and it proves the shared contracts really are stack-neutral. Needs all three stacks working first, plus a decision on the fourth seat. Deferred from [open question 1](../open-questions.md#answered). |
| **Same model in all four seats** | Isolates framework effects better than anything else available, but makes for a duller game. Good as a dedicated controlled run once LUDO works — see [ADR-0005](../decisions/adr-0005-model-access-control.md). |
| **Rule-variant adaptation** | Flip a rule mid-experiment and measure whether agents adapt. Needs the engine's config seam — [open question 14](../open-questions.md). |

## AWS services

| Service | Introduced by | Purpose |
|---|---|---|
| Bedrock | LUDO | Model invocation for two of four agents; Guardrails |
| Lambda | — | Hosted game execution |
| API Gateway | — | Public API in front of a hosted game |
| AgentCore | — | Managed agent runtime; compare against self-hosted orchestration |
| SageMaker | — | Fine-tuning and continued pre-training (topics 14–16) |

LUDO runs locally against real model APIs. Deployment is a later project's subject, not a v1 requirement — see [architecture overview](../architecture/overview.md#local-first-cloud-when-it-earns-it).

## Sequencing principle

Each project should introduce **at most two genuinely new hard things**. LUDO already carries a lot: swarm agents, three-stack parity, LLM-as-judge, and the harness features. Adding deployment, RAG, or fine-tuning to it would produce something nobody could learn from.

Project two picks up where LUDO's [capability matrix](../architecture/stack-comparison.md) shows the most interesting gaps.

## Legend

📋 Planned · 🚧 In progress · ✅ Done · 🔲 Unassigned
