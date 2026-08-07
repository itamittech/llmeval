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

**Provisional numbers are now in [`shared/models.yaml`](../shared/models.yaml)** so the negotiation prompt has something to render — 40 turns, 3 floor passes per conversation, and a 6 000-token per-agent context budget on the `dev` profile; 60, 6, and 30 000 on `headline` (floor passes replaced per-turn message counts under [ADR-0009](decisions/adr-0009-swarm-negotiation.md); each pass is one agent activation, i.e. one model call; the context budget is what triggers compaction). These are guesses, deliberately placed in config rather than in the prompt so that tuning them is a one-line edit and not a prompt change. Replace them with measured values after the first stack runs.

---

## 🟡 10. Repository name, GitHub org, and when it goes public

Currently `llmeval` locally. Public from the first commit, or after LUDO works?

> **Recommendation:** public early. A visible design phase — including the ADRs and this file — is itself teaching material, and it's the part most repos hide.

---

## 🟡 23. Retrieval parity — what must be pinned, and what is allowed to be the finding?

LUDO pinned prompts and inference settings so the framework was the only variable. ALIBI adds retrieval, and three frameworks with three vector-store stories will not produce identical retrievals. Pinning too little makes the comparison meaningless; pinning too much means hand-rolling one retriever three times, which [ADR-0008](decisions/adr-0008-framework-native-harness.md) forbids.

> **Recommendation:** pin the *inputs* — corpus bytes (engine-generated), embedding model id, chunking parameters, `k` — in shared config; let each stack's store and retrieval orchestration be framework-native, and record their behavioural differences as matrix findings. The scripted tier bypasses the question entirely with one shared deterministic keyword retriever, spec'd in the harness contract, so tests stay free and byte-reproducible.

---

## 🟡 26. RELAY's edge tier — which small models, hosted how, and what must be pinned?

[Question 3](#-3-which-four-models-and-which-two-on-bedrock) picked LUDO's families; RELAY needs the same decision one tier down, plus a new one LUDO never faced. A locally hosted model has knobs no hosted API exposes — quantisation, context length, the runtime's own version — and it runs on *this* machine, so latency and cold start are properties of the hardware as much as the model. [Question 23](#-23-retrieval-parity--what-must-be-pinned-and-what-is-allowed-to-be-the-finding)'s shape, moved from retrieval to hosting: pin too little and the comparison means nothing, pin too much and [ADR-0008](decisions/adr-0008-framework-native-harness.md) is broken.

> **Recommendation:** pin the *inputs* — model id, quantisation, context length, sampling settings, and the runtime version — in shared config, and record the host (CPU/GPU, RAM, runtime build) in `game_started` beside the existing `framework` block, since a latency number without a machine attached is not a result. Let each stack bind to the local runtime with its own native model provider and record the binding differences as matrix findings. Three small open-weight families across four lanes, one of them on both a local and a hosted route, per [ADR-0005](decisions/adr-0005-model-access-control.md)'s control.

**Half-built already:** the schema carries `game_started.host` and per-player `quantisation`, and `access` gained a third value, `local`. What is undecided is which models go in, not where the facts go. This is now the *only* thing between RELAY and a live game — no model id in it is TBD.

---

## 🟢 11. Does LUDO deploy to AWS?

The brief lists Lambda, API Gateway, AgentCore, and SageMaker. [Architecture](architecture/overview.md#local-first-cloud-when-it-earns-it) and the [roadmap](topics/roadmap.md) assume LUDO runs locally against real model APIs, with deployment as a later project's subject.

> **Recommendation:** keep LUDO local. It already carries swarm agents, three-stack parity, LLM-as-judge, and the harness features. Deployment is a strong project-two topic on its own.

---

## 🟢 14. Rule variants as config flags

[Game rules](projects/ludo/game-rules.md) fixes one ruleset and lists rejected variants. Making them toggleable would enable a genuinely interesting eval: *do agents adapt when the rules change mid-experiment?*

> **Recommendation:** build the engine with the config seam in place, ship only the baseline ruleset for v1.

---

## 🟢 18. Should a game ever inherit an earlier game's memory?

The mechanism now exists — `FileSessionManager` persists each agent's beliefs and conversation across processes, opt-in via `session_dir` — but the *semantics* of using it across games are genuinely undecided, and harder than they look:

- **Independence.** Games are currently independent samples; the eval compares them. A "campaign" where game 3's play depends on games 1–2 is a different experiment, not a free upgrade.
- **Identity.** Seats rotate colours per game ([ADR-0006](decisions/adr-0006-seat-rotation.md)), but memories are *written about colours* — "blue betrayed me" points at a different model next game. Cross-game memory would need seat-keyed identity and belief rewriting, or it actively misleads.
- **Restore scope.** The persisted conversation is the appended history — table fragments included — not the curated one (see the [session-sync finding](architecture/stack-comparison.md)). Restoring beliefs without conversation is probably the honest unit.

> **Recommendation:** keep games independent by default (persistence stays opt-in and off). If a campaign mode is ever wanted, it is an ADR — new seat-keyed identity, beliefs-only restore, and its own eval treatment — not a flag flip.

---

## Answered

### ✅ 25. RELAY's difficulty ladder — can a small model tell what it can't do?

**Answered by the bench, and it found something the question did not ask for.** The experiment was the one the recommendation described, sharpened: rather than measuring solve rates in isolation, four runners of equal skill and *unequal insight* race each other, with the insight-to-lane assignment rotating per seed so turn order is not what gets measured ([ADR-0006](decisions/adr-0006-seat-rotation.md)'s logic).

The mechanic survives: over 300 races per row, win share runs 17% → 32% against a 25% baseline — a runner that knows its own limits wins about twice as often as one that doesn't ([the numbers](projects/relay/game-rules.md#does-the-escalation-decision-actually-matter)).

**And for weak runners the effect runs backwards** — 27% at zero insight, 21% at perfect. Spending a scarce pool precisely on the hardest stages is a losing move if you also fail the easy ones, because an indiscriminate escalation lands on a tier-1 stage you would have missed anyway and rescues you. The right escalation threshold is a function of your own competence, not the stage's difficulty. That inversion is now the headline teaching result of project three.

The same runs sized the rest: shared quota **8** (above ~12 the pool stops binding at all — quota 12 and quota 20 play identically), turn caps **48** `dev` and **104** `headline`, both recorded in [game-rules.md → The numbers](projects/relay/game-rules.md#the-numbers).

### ✅ 24. What is project three?

**Answered: RELAY — an escalation race between four small local models and one shared frontier model.** Direction chosen by the maintainer 2026-08-07 and written up as [ADR-0011](decisions/adr-0011-project-three-relay.md), which stays **Proposed** until the game's shape is ratified. Chosen the same way project two was — after the [matrix](architecture/stack-comparison.md) existed, from what it showed — and what it shows now is an empty back half: cost attribution, fallback and retry, rate limiting, and every model-access row, none of which a scripted game can ever fill. It takes the last unclaimed agentic architecture (edge agent) plus topics 4 and 5, and it is the only candidate **not blocked on an undecided model id**, because local runners need no key. The roadmap's named candidate, Werewolf/Mafia, was deferred to project four for the reason [ADR-0010](decisions/adr-0010-project-two-alibi.md) already recorded and ALIBI's own finding sharpened. **Ratified the same day** under the maintainer's delegation of the remaining decisions, together with the name, the mechanics, and the benched numbers. Successors: [25](#-25-relays-difficulty-ladder--can-a-small-model-tell-what-it-cant-do) (answered by the bench), [26](#-26-relays-edge-tier--which-small-models-hosted-how-and-what-must-be-pinned).

### ✅ 21. ALIBI's pace — case dimensions, query allowance, turn cap

**Answered by the bench, exactly as recommended.** Over 500 elimination-bot games (`alibi_engine.cli bench --games 500`): min 1, median 21, p90 36, p99 45, max 45 turns to a correct accusation — **all 500 solved**, because every refutation teaches the suggester at least one new elimination and an unrefuted suggestion by a non-holder *is* the solution. Caps derived and recorded in [game-rules.md → The numbers](projects/alibi/game-rules.md#the-numbers) and `shared/models.yaml`: **24** turns on `dev` (just above median — mid-game belief scoring does the rest), **48** on `headline` (above p99), **60** for conformance vectors (every vector must end `solved`). The 6+5+8 element split and 2-queries-of-3-documents allowance survived the bench unchanged.

### ✅ 20. ALIBI's name, theme, and cast

**Answered: ratified as proposed, under the maintainer's delegation** (2026-08-07, "whatever is best you can take those decisions"). The project is **ALIBI**, original theft-at-a-gala fiction, because Cluedo's name and cast are Hasbro's protected expression while the deduction mechanics are common property. The v0 cast in the [rules](projects/alibi/game-rules.md) is now load-bearing: element and cast names are baked into corpus bytes the moment the first conformance vector is recorded, and renaming after that is a vector regeneration, not a search-and-replace.

### ✅ 22. Does ALIBI keep LUDO's negotiation channels?

**Answered: no — v1 ships without directed messages or floor passing.** One public table note per suggestion is the only free-text channel. Decided under the same delegation, on the recommendation's own grounds: negotiation phases were LUDO's biggest token cost, and ALIBI's deception already lives in bluff suggestions, table-note spin, and the archive's unreliable testimony. The consequence taken knowingly: detective alliances (sharing eliminations is rational) cannot form in v1 — if that turns out to matter, it reopens as an ADR, not a flag. This is also what removes the swarm orchestrator from ALIBI's stacks entirely: each detective is a single-agent loop with tools, which is exactly the contrast with LUDO the comparison wants.

### ✅ 12. What is project two?

**Answered: ALIBI — a hidden-triple deduction game built on retrieval.** Chosen by the maintainer 2026-08-07 and recorded as [ADR-0010](decisions/adr-0010-project-two-alibi.md) (Proposed until ratified). It takes the two biggest unclaimed topics — RAG (+architectures) and the agent-as-tool architecture — and inherits everything else from LUDO. The question's own rule was honoured: it was chosen *after* the capability matrix existed, from what the matrix showed — Spring AI, weakest at multi-agent orchestration, has the strongest RAG story of the three, so the comparison gets a second act instead of a rematch. Successor questions: [20](#-20-alibis-name-theme-and-cast), [21](#-21-alibis-pace--case-dimensions-query-allowance-turn-cap), [22](#-22-does-alibi-keep-ludos-negotiation-channels), [23](#-23-retrieval-parity--what-must-be-pinned-and-what-is-allowed-to-be-the-finding).

### ✅ 17. Should the transcript record the framework version?

**Answered: yes — `game_started` now carries `framework: {name, version}`,** read from each stack's resolved dependency (importlib metadata in the Python stacks, the jar manifest in Java), so two games played under different framework builds are distinguishable from the files alone — the thing [ADR-0008](decisions/adr-0008-framework-native-harness.md) made necessary. Done in one coordinated bump with question 19: both engines' `GameConfig` grew optional provenance fields that are **omitted when absent**, which is what kept the conformance vectors and every engine-only transcript byte-stable.

### ✅ 19. game_started promises prompt provenance nobody emits

**Answered: it emits now.** The schema had defined `prompt_set` (and `profile`) all along; no emitter filled them. After the coordinated bump, all three stacks record `profile`, `prompt_set: {version, hash}`, and `framework` — and the three regenerated fixtures carry **the same prompt-set hash from three independent loaders in two languages**, which upgraded the LangGraph digest test from "deterministic" to the cross-stack equality it originally went looking for. The loader docstrings say "recorded in `game_started`" again, and this time it is true.

### ✅ 6. Alliance channel design

**Decided: both channels, active-agent-driven, no cross-reading of reasoning.** Implemented in [`shared/prompts/ludo/system/negotiation.md`](../shared/prompts/ludo/system/negotiation.md).

- **Public and private both exist.** Private messages are what make deception observable: an agent can tell two players contradictory things, invisible in-game and perfectly visible to the viewer.
- **Spectators see everything; players see only what's addressed to them.** Confirmed explicitly — it's what turns the UI into a story rather than a board animation.
- **Only the active agent opens a conversation.** An agent that receives a direct message may reply once; nobody broadcasts on someone else's turn. The alternative — all four free to speak every turn — costs roughly 4× the negotiation tokens and lets negotiation swamp play.
- **No agent sees another's reasoning.** Reading an opponent's private deliberation would make deception meaningless.

The consequence worth knowing: **an alliance takes at least two turns to form** — one to propose, one to accept. The prompt says so, so agents can plan around it.

**Revised 2026-08-03 by [ADR-0009](decisions/adr-0009-swarm-negotiation.md).** The maintainer chose to run negotiation on the framework's swarm orchestrator and redesign the protocol to fit it, after [source-level analysis](architecture/stack-comparison.md) showed the original protocol and the orchestrator's semantics could not both survive. What changed: the active agent now *opens* a floor-passing conversation rather than driving it; the private channel became a **directed message** (content pairwise, existence public, not guaranteed to be remembered past the phase); the public channel became a **table note** riding on a floor pass; reply-exactly-once became a hard `max_floor_passes` cap. What survived: both channels in revised form, spectators-see-everything, no cross-reading of reasoning, and deception as the phenomenon under study. The original decision above is kept as written — the repo records its reversals.

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

**The Anthropic pair is pinned** — `claude-sonnet-5` on `dev`, `claude-opus-5` on `headline`, each spelled `anthropic.`-prefixed on the Bedrock seat. Nova, DeepSeek, and the OpenAI judge remain `TBD`; [`check_prompts.py`](../scripts/check_prompts.py) verifies the control by provider until every ID is pinned, and by exact ID afterwards, comparing with the Bedrock prefix stripped.

**A correction worth keeping.** This entry previously said model IDs must be *dated snapshots, not floating aliases*. That is wrong for the current Claude family: `claude-opus-5` and `claude-sonnet-5` are complete IDs with no dated variant, and appending a date returns a 404. The underlying goal — a transcript that names exactly what produced it — is served instead by **recording the model the API actually served** in `game_started`, which is stronger than pinning a string in config because it cannot drift from reality.

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
