# Open Questions

Decisions not yet made. Each has a recommendation so agreeing is fast and disagreeing is specific.

Ordered by how much they block: **🔴 blocks code** · **🟡 needed soon** · **🟢 can wait**.

Resolved questions move to [Answered](#answered) at the bottom, with their outcome.

---

## 🟡 6. Alliance channel design

[Agent design](projects/ludo/agent-design.md) proposes **public broadcast + private direct messages**, with the viewer seeing everything and agents seeing only what's addressed to them.

Private messages are what make deception possible — an agent can tell red and green contradictory things, invisible in-game but visible to the viewer. Public-only makes betrayal trivially detectable and much less interesting.

> **Recommendation: hybrid, as documented.** Confirm the viewer-omniscience choice explicitly — it's what turns the UI into a good story.

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

---

## 🟡 8. Python version

Both Python stacks must pin the *same* version so the interpreter isn't a variable. Constrained by whatever Strands and LangChain both support.

> **Recommendation:** newest version both frameworks fully support — verify at setup time rather than guessing now.

---

## 🟡 10. Repository name, GitHub org, and when it goes public

Currently `llmeval` locally. Public from the first commit, or after LUDO works?

> **Recommendation:** public early. A visible design phase — including the ADRs and this file — is itself teaching material, and it's the part most repos hide.

---

## 🟡 15. Should deciders get a read-only view of game state?

[ADR-0004](decisions/adr-0004-structural-guardrails.md) claims cheating is structurally impossible. That holds against the **LLM** — it only returns a move choice, and the engine rejects anything illegal.

It is not enforced against the decider *code* wrapping the LLM. `TurnContext.state` is a live reference to the mutable `GameState`, so a decider could simply write `ctx.state.tokens["red"] = [56]*4`. See [engine design](projects/ludo/engine-design.md#one-honest-limit-on-the-guardrail).

That code is ours, so today it's a code-review boundary rather than an enforced one. Three options: leave it and narrow the ADR's wording; hand deciders a read-only view; or defensively copy the state per turn.

Worth settling **before the stacks are written**, since it changes the agent-facing API.

> **Recommendation:** a read-only view. The ADR's claim is one of the more transferable lessons in the project, and it's worth having the code actually back it. A defensive copy per turn is simpler but silently costs an allocation on every decision.

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

### ✅ 1. Three parallel games, or one mixed game?

**Decided: three parallel games.** Each stack runs its own complete 4-agent game (2 Bedrock + 2 direct API); the three games are compared against each other. Matches goal #5 of the brief and keeps "which stack is better" separable from "which model played better".

A **mixed game — four agents each on a different stack — is explicitly deferred, not rejected.** It's a strong interoperability showcase once all three stacks work, and would need a fourth seat assignment. Tracked as a candidate follow-up in the [roadmap](topics/roadmap.md).

### ✅ 2. Is the shared engine acceptable?

**Decided: yes — two engines.** One Python engine shared by Strands and LangGraph, one Java engine for Spring AI, both held to shared conformance vectors. Ratified as [ADR-0002](decisions/adr-0002-engine-per-language.md) (**Accepted**).

This makes Strands vs. LangGraph a genuinely controlled experiment — same language, same engine, same prompts, same models, with the agent framework as the only variable.

### ✅ 3. Which four models, and which two on Bedrock?

**Decided: one model runs on both access routes, plus two other families.** One model is invoked via *both* Bedrock and a direct API, so the access route is isolated from the model — without that control, Bedrock-vs-direct differences are uninterpretable. The remaining two seats go to different model families for behavioural variety in alliance dynamics.

Ratified as [ADR-0005](decisions/adr-0005-model-access-control.md). **Concrete model IDs are still to be chosen** — constrained by Bedrock availability for the dual-route model, and by keeping one family in reserve for the [judge](projects/ludo/evaluation.md#judge-bias--and-what-we-do-about-it).

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
