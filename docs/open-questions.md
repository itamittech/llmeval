# Open Questions

Decisions not yet made. Each has a recommendation so agreeing is fast and disagreeing is specific.

Ordered by how much they block: **🔴 blocks code** · **🟡 needed soon** · **🟢 can wait**.

Resolved questions move to [Answered](#answered) at the bottom, with their outcome.

---

## 🟡 7. Turn cap, negotiation budget, and game length

Needs real numbers: maximum turns, messages per turn, max message length, per-agent and per-game token ceilings.

These determine cost per game more than anything else, and they can't be chosen well in the abstract.

**Measured**, over 500 random-bot games (`ludo_engine.cli bench --games 500`):

| | turns to finish |
|---|---|
| min | 273 |
| median | 400 |
| p90 | 474 |
| p99 | 550 |
| max | 599 |

All 500 completed. A "turn" is one player's turn, so the median game is ~100 rounds.

**This settles the design question even though the number isn't picked yet.** A 400-turn LLM game means roughly 400+ agent decisions plus negotiation — far beyond a sane per-game budget. Any affordable cap will be a small fraction of that, so **the overwhelming majority of LLM games will end at the cap, not by someone winning.** Mid-game evaluation isn't a fallback; it's the primary scoring path.

Strong agents should finish faster than random bots, but not by the order of magnitude that would change this.

> **Recommendation:** set the cap from a per-game token budget rather than from game length — decide what a game may cost, then derive the cap. Needs a measured per-turn token cost, so it stays open until the first stack runs.

**Provisional numbers are now in [`shared/models.yaml`](../shared/models.yaml)** so the negotiation prompt has something to render — 40 turns and 1 message per turn on the `dev` profile, 60 and 2 on `headline`. These are guesses, deliberately placed in config rather than in the prompt so that tuning them is a one-line edit and not a prompt change. Replace them with measured values after the first stack runs.

---

## 🟡 10. Repository name, GitHub org, and when it goes public

Currently `llmeval` locally. Public from the first commit, or after LUDO works?

> **Recommendation:** public early. A visible design phase — including the ADRs and this file — is itself teaching material, and it's the part most repos hide.

---

## 🟢 11. Does LUDO deploy to AWS?

The brief lists Lambda, API Gateway, AgentCore, and SageMaker. [Architecture](architecture/overview.md#local-first-cloud-when-it-earns-it) and the [roadmap](topics/roadmap.md) assume LUDO runs locally against real model APIs, with deployment as a later project's subject.

> **Recommendation:** keep LUDO local. It already carries swarm agents, three-stack parity, LLM-as-judge, and the harness features. Deployment is a strong project-two topic on its own.

---

## 🟢 12. What is project two?

Should be chosen from what LUDO's [capability matrix](architecture/stack-comparison.md) actually reveals, not planned now. Unclaimed topics: RAG, voice, fine-tuning, and three of the four agentic architectures.

---

## 🟢 14. Rule variants as config flags

[Game rules](projects/ludo/game-rules.md) fixes one ruleset and lists rejected variants. Making them toggleable would enable a genuinely interesting eval: *do agents adapt when the rules change mid-experiment?*

> **Recommendation:** build the engine with the config seam in place, ship only the baseline ruleset for v1.

---

## Answered

### ✅ 6. Alliance channel design

**Decided: both channels, active-agent-driven, no cross-reading of reasoning.** Implemented in [`shared/prompts/ludo/system/negotiation.md`](../shared/prompts/ludo/system/negotiation.md).

- **Public and private both exist.** Private messages are what make deception observable: an agent can tell two players contradictory things, invisible in-game and perfectly visible to the viewer.
- **Spectators see everything; players see only what's addressed to them.** Confirmed explicitly — it's what turns the UI into a story rather than a board animation.
- **Only the active agent opens a conversation.** An agent that receives a direct message may reply once; nobody broadcasts on someone else's turn. The alternative — all four free to speak every turn — costs roughly 4× the negotiation tokens and lets negotiation swamp play.
- **No agent sees another's reasoning.** Reading an opponent's private deliberation would make deception meaningless.

The consequence worth knowing: **an alliance takes at least two turns to form** — one to propose, one to accept. The prompt says so, so agents can plan around it.

### ✅ 8. Python version

**Decided: 3.12**, pinned identically for both Python stacks.

Matches what the engine already builds against, supported by both Strands and LangChain, and mature enough that transitive dependencies are unlikely to lag. 3.13 offered nothing this project needs in exchange for a higher chance of a dependency without wheels. To be verified against both frameworks at stack setup rather than trusted.

### ✅ 16. Does the seat-to-colour mapping stay fixed?

**Decided: it rotates**, recorded per game. [ADR-0006](decisions/adr-0006-seat-rotation.md).

Notable for how it was settled: the ADR was drafted asserting a first-mover advantage, that assumption was **measured across 4000 games and found to be false** (χ² = 3.56 and 1.54, against a 5% critical value of 7.81), and the decision was kept on different grounds — colour-linked effects in *prompts*, which bot games cannot detect at all. Reproduce it with [`examples/turn_order.py`](../projects/ludo/engine-python/examples/turn_order.py).

### ✅ 1. Three parallel games, or one mixed game?

**Decided: three parallel games.** Each stack runs its own complete 4-agent game (2 Bedrock + 2 direct API); the three games are compared against each other. Matches goal #5 of the brief and keeps "which stack is better" separable from "which model played better".

A **mixed game — four agents each on a different stack — is explicitly deferred, not rejected.** It's a strong interoperability showcase once all three stacks work, and would need a fourth seat assignment. Tracked as a candidate follow-up in the [roadmap](topics/roadmap.md).

### ✅ 2. Is the shared engine acceptable?

**Decided: yes — two engines.** One Python engine shared by Strands and LangGraph, one Java engine for Spring AI, both held to shared conformance vectors. Ratified as [ADR-0002](decisions/adr-0002-engine-per-language.md) (**Accepted**).

This makes Strands vs. LangGraph a genuinely controlled experiment — same language, same engine, same prompts, same models, with the agent framework as the only variable.

### ✅ 3. Which four models, and which two on Bedrock?

**Decided: one model runs on both access routes, plus two other families.** One model is invoked via *both* Bedrock and a direct API, so the access route is isolated from the model — without that control, Bedrock-vs-direct differences are uninterpretable. The remaining two seats go to different model families for behavioural variety in alliance dynamics.

Ratified as [ADR-0005](decisions/adr-0005-model-access-control.md).

**Families settled**, in [`shared/models.yaml`](../shared/models.yaml):

| Seat | Family | Route |
|---|---|---|
| 1 | Anthropic | Bedrock |
| 2 | Amazon Nova | Bedrock |
| 3 | Anthropic | direct ← control pair with seat 1 |
| 4 | DeepSeek | direct |
| judge | OpenAI reasoning | direct — not seated |

An earlier draft seated GPT and DeepSeek on the direct side with no dual-route model, which would have confounded route with model exactly as the ADR warns; GPT moved to the judge seat, which also removed the self-scoring problem. The trade taken knowingly: **three playing families instead of four**, spending one seat on the control.

**Concrete model IDs are still to be chosen** — the only thing here still open. They should be *dated snapshots*, not floating aliases: an alias changes under you and a transcript stops being reproducible. Marked `TBD` in the file; [`check_prompts.py`](../scripts/check_prompts.py) verifies the control by provider until they're pinned, and by exact ID afterwards.

### ✅ 15. Should deciders get a read-only view of game state?

**Decided: yes — implemented as `StateView`**, before the first stack, since it changes the agent-facing API.

`TurnContext.state` is now a `StateView` rather than the live `GameState`. Positions come back as tuples, `board()` returns a fresh dict of tuples, `stats()` returns a copy, and attribute assignment raises. The rejected alternatives were leaving it (and weakening ADR-0004's wording) or copying the whole state each turn — the latter simpler, but silently allocating on every decision.

Deliberately *not* claimed as a hard boundary: Python has no in-process equivalent, and code reaching for the private `_state` still gets through. What it buys is that cheating requires obviously-wrong code rather than a plausible typo. See [engine design](projects/ludo/engine-design.md#one-honest-limit-on-the-guardrail).

### ✅ 13. Contribution guidelines

**Written: [CONTRIBUTING.md](../CONTRIBUTING.md).**

Built around the six rules that are easy to break by accident — parity, no LLM SDK in the engine, never regenerating conformance vectors to silence a failure, never sharing a Python environment between stacks, evidence-cited matrix ratings, and treating agent claims as claims. Each states *why*, because a rule without a reason gets worked around.

It also carries the content note this repo needs: recorded transcripts contain deliberate AI-generated deception, presented without correction, as in-fiction moves in a board game.

A separate code of conduct is **not** included yet — worth adding if the project attracts outside contributors.

### ✅ 9. License

**Decided: Apache-2.0**, landed in the initial commit. Permissive like MIT, plus an explicit patent grant — the default expectation for anything AWS-adjacent, and the safer choice for corporate readers who may want to adopt a pattern from here.

Chosen *before* the first public push deliberately: without a licence a public repo is all-rights-reserved by default, which would have contradicted the brief's "usable by anyone" goal for anyone who cloned it in the meantime.

### ✅ 5. Java build tool

**Decided: Maven**, with the wrapper (`mvnw`) committed so no global install is needed.

Chosen on readability grounds rather than speed: this is a teaching repo, `pom.xml` needs no explanation, and it's what a Spring developer expects to find.

### ✅ 4. UI framework

**Decided: React + Vite**, static build, transcript-replay first with live streaming added later.

Chosen for reach rather than elegance: the UI is a teaching artifact, and the largest number of readers can follow React. The [event-stream architecture](decisions/adr-0003-shared-event-stream.md) keeps the UI a pure transcript player, so it runs with no backend and no API keys — and the framework choice stays cheap to revisit.
