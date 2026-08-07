# ADR-0010 — Project two is ALIBI: a deduction game built on retrieval

**Status:** Accepted — the deduction-game direction is the maintainer's (2026-08-07); the maintainer then delegated the remaining decisions ("whatever is best"), and the name, theme, and rules baseline were ratified under that delegation the same day
**Date:** 2026-08-07

## Context

LUDO is feature-complete at the scripted tier: three harnesses over one contract, the UI, and the eval machinery all built. The [roadmap](../topics/roadmap.md) sets two rules for what comes next: a project introduces **at most two genuinely new hard things**, and project two is chosen from what LUDO's [capability matrix](../architecture/stack-comparison.md) actually revealed — not planned in advance. The unclaimed topics: RAG and its architectures, three of the four agentic architectures (agent-as-tool, graph, edge), voice, fine-tuning, and deployment.

The maintainer chose the direction: a **Cluedo-style deduction game**. Two things still needed deciding beyond that — what exactly the game is, and what it may be called in a public repository.

On the second: Cluedo's *mechanics* (hidden triple, suggestion, compelled refutation) are game mechanics, which are not protectable and appear across the whole deduction-game family. Its **name, characters, rooms, and board art are protected expression** owned by Hasbro. A public teaching repo that named its project "Cluedo" and seated Colonel Mustard in the library would be borrowing exactly the parts it must not.

## Decision

Project two is **ALIBI** — four LLM detectives race to solve a theft. A hidden triple (who · how · where) is sealed at game start; the remaining case elements are dealt to the detectives as private exhibits; a public **archive** of generated witness statements and records is searchable only through retrieval. Detectives interrogate the table with suggestions that compel refutation, search the archive privately, and win by accusing correctly.

The theme is an **original fiction** — a theft at a gala, with an invented cast — inspired by the deduction-game family's mechanics and using none of Cluedo's protected expression. The name continues the house pun anyway: an *alibi* is the thing every suspect claims and every detective must break.

**The two new hard things:**

1. **RAG** (topics 11 and 12) — the archive is the game's evidence source. Retrieval is not plumbing bolted onto a chatbot; it is gameplay, and retrieval quality is measurable by deduction accuracy against ground truth. Retrieval *architectures* become comparable experiments: the same game replayed under different retrieval profiles.
2. **Agent-as-tool** (topic 9) — the archive is consulted through the **archivist**, a non-playing specialist agent the detectives invoke as a tool. This is the pattern LUDO evaluated for negotiation and [ADR-0009](adr-0009-swarm-negotiation.md) set aside; it finds its natural home here.

**Everything else is inherited from LUDO, deliberately:** the shared event stream ([ADR-0003](adr-0003-shared-event-stream.md)), one engine per language held together by conformance vectors ([ADR-0002](adr-0002-engine-per-language.md)), framework-native harnesses over a behavioural contract ([ADR-0008](adr-0008-framework-native-harness.md)), seat rotation ([ADR-0006](adr-0006-seat-rotation.md)), one model on both access routes ([ADR-0005](adr-0005-model-access-control.md)), shared verbatim prompts, lenient in-fiction guardrails ([ADR-0004](adr-0004-structural-guardrails.md)), UI built against transcript fixtures ([ADR-0007](adr-0007-ui-alongside-first-stack.md)), and the eval harness's deterministic-plus-judge split. A reader who understood LUDO should navigate ALIBI without re-learning anything.

The normative rules live in [game-rules.md](../projects/alibi/game-rules.md); the project's shape in the [brief](../projects/alibi/brief.md).

## Consequences

**Good**

- **Ground truth exists.** Someone did it, and the engine knows who. Deterministic evaluation gets sharper than LUDO's position scoring: accusation accuracy, time-to-solve, and **belief calibration over time** are all computable without a judge. The judge is reserved for what only a judge can score — interrogation craft, bluffing, retrieval discipline.
- **Deception carries over with a twist.** Bluff suggestions (naming exhibits you hold) are native to the mechanics, and the archive contains unreliable testimony — so *the table is facts, the archive is claims*, and "agent claims are claims, not facts" becomes a rule the agents themselves must live by.
- **The matrix gets a second act.** LUDO's matrix shows Spring AI weakest at multi-agent orchestration. RAG inverts the standings: Spring AI has vector store abstractions, an ETL pipeline, and `QuestionAnswerAdvisor`; LangChain is RAG's birthplace; Strands leans on Bedrock Knowledge Bases (deepening topic 13). Three different grains again, with the underdog changed.
- Everything inherited is a cost *not* paid twice: schema, engines pattern, eval split, UI fixture rules, guardrail stance.

**Bad — accepted knowingly**

- **Retrieval parity is genuinely hard.** Three frameworks with three vector-store stories will not produce byte-identical retrievals. What must be pinned (corpus, embedding model, chunking, k) versus what is allowed to vary *as the finding* is a real open question ([question 23](../open-questions.md)) — and if the stacks cannot be made comparable at all, that is itself the headline result, honestly recorded.
- **The case generator ports twice.** ADR-0002's one-engine-per-language rule means the deterministic case and corpus generator is written in Python and Java, and the conformance vectors must now cover **corpus bytes**, not just game mechanics — a larger surface for silent divergence than LUDO's dice ever were.
- **Offline-and-free needs a design.** Embeddings cost money and call APIs, which the scripted tier must not. The scripted tier therefore runs a shared deterministic retriever (no embeddings) so tests stay free and byte-reproducible; embedding-based retrieval is live-tier only. Two retrieval tiers is real complexity LUDO never had.
- **Deduction pace is unmeasured.** A game that random play solves in six rounds is too easy; one that never converges busts the budget. The dimensions and caps in the rules are provisional until benched ([question 21](../open-questions.md)) — the same discipline as LUDO's question 7.
- **The doc surface doubles.** A second project means a second brief, rules spec, harness contract, and eval doc, all held to Rule #1. That cost is the price of the repo's structure and is paid deliberately.

## Alternatives

- **Name it Cluedo.** Rejected on trademark grounds above. The mechanics-inspired original design keeps everything the project needs and nothing it must not have.
- **Werewolf/Mafia** (graph agents' natural home — day/night phases are a state machine). Deferred, not rejected: deception is ground LUDO already owns, LangGraph's table-as-StateGraph has partially claimed the graph story, and RAG is the largest unclaimed topic. A strong project-three candidate.
- **The arena** (deployment: Lambda, API Gateway, AgentCore). [Question 11](../open-questions.md) already names deployment a strong standalone project — but it teaches infrastructure, not agent behaviour, and the games themselves would be reruns.
- **A retrieval quiz** (trivia over a corpus). Rejected: no adversarial pressure, no deception, no reason to keep reading — the [vision](../vision.md) argues nobody finishes a tutorial about document summarisation, and a quiz is that tutorial with a scoreboard.
- **Voice commentary over LUDO transcripts.** A fine mini-project any time — it consumes only the event stream — but it introduces one new thing (voice) while exercising no agent architecture. Parked on the [roadmap](../topics/roadmap.md).
