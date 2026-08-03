# Glossary

Every term this repo uses as shorthand, in plain English. Skim it once, or come back when a doc uses a word you don't recognise.

Definitions are short on purpose — each links to the doc that goes deeper.

---

## This project's own vocabulary

**Stack** — one of the three agent frameworks: Strands (Python), LangChain/LangGraph (Python), Spring AI (Java). "The Strands stack" means the full implementation built on it. Not to be confused with a call stack.

**Parity** — the rule that the three implementations must differ *only* in the agent framework. Same rules, same prompts, same schema. Without it, any difference we measure could be caused by something other than the framework, and the comparison means nothing. → [architecture overview](architecture/overview.md)

**Capability gap** — something one framework can't do, or makes painful, that another does easily. Deliberately treated as a **result to publish**, not a problem to hide. → [capability matrix](architecture/stack-comparison.md)

**Engine** — the deterministic Ludo rules code: board, dice, legal moves, capture, win detection. Contains no LLM code at all and makes no network calls, so it runs in milliseconds and costs nothing. → [engine design](projects/ludo/engine-design.md)

**Decider** — anything that can answer "what's your move?". A random bot, a fixed-strategy bot, or an LLM agent. It's a one-method contract, and it's the *entire* interface between the engine and an agent. → [class design](projects/ludo/class-design.md#71-four-players-four-different-brains--strategy)

**Event stream / transcript** — the append-only log of everything that happened in a game: rolls, moves, captures, messages, agent reasoning, token counts, costs. Written as a `.jsonl` file, one event per line. All three stacks emit the same format, which is what lets one UI and one evaluator serve all of them. → [ADR-0003](decisions/adr-0003-shared-event-stream.md)

**Conformance vector** — a recorded test case proving the Python and Java engines behave identically. Each stores a seed plus the exact expected outcome; both engines must reproduce it. This is what stops the two engines silently drifting apart. → [conformance](../shared/conformance/README.md)

**Access route** — *how* a model is called: through **AWS Bedrock**, or through a provider's **direct API**. Comparing the two is a project goal, so one model deliberately runs on both. → [ADR-0005](decisions/adr-0005-model-access-control.md)

**Control** (experimental sense) — a deliberately held-constant variable, so a difference can be attributed to one cause. Running the same model on both access routes is a control: because the model is fixed, any difference must come from the route.

**Turn cap** — the maximum number of turns a game may run. LLM turns are slow and expensive, so most games will hit the cap rather than finish. That's expected, not a failure. → [evaluation](projects/ludo/evaluation.md)

**Turn** — one player's go, not a full round. Four turns is roughly one lap of the table.

---

## LLM engineering vocabulary

**Token** — the unit models read and write, roughly ¾ of a word. Billing, context limits, and speed are all measured in tokens.

**Context window** — the maximum tokens a model can consider at once — prompt and reply together. When a game transcript outgrows it, something has to be dropped or summarised.

**Inference** — one run of a model producing output. "Inference latency" is how long that takes.

**Agent** — an LLM that can take actions through tools and run over multiple steps, rather than answering once. Here, each Ludo player is an agent.

**Agent swarm** — several peer agents with their own goals sharing an environment, with no single coordinator. Ludo's four players are a swarm; they negotiate rather than being directed. → [agent design](projects/ludo/agent-design.md)

**Agents-as-tools** — a multi-agent pattern where one agent invokes another as a callable tool and reads its reply, keeping every exchange directed and pairwise. Ludo evaluated it for negotiation, then [ADR-0009](decisions/adr-0009-swarm-negotiation.md) went the other way: the protocol was redesigned to fit the swarm orchestrator instead. → [capability matrix](architecture/stack-comparison.md)

**Floor / table note** — how Ludo's negotiation works after [ADR-0009](decisions/adr-0009-swarm-negotiation.md). The *floor* is the right to speak: the active player opens holding it, each speaker passes it by addressing one player with a directed message, and the conversation ends when a holder says nothing or the pass cap is hit. A *table note* is a public remark attached to a pass — every player sees it; directed-message content is seen only by its addressee.

**Tool / tool calling** — a function the model can invoke, described to it in the prompt. The model emits a request to call it; your code runs it and returns the result. It's how an agent affects anything outside its own text.

**Harness** — the scaffolding around the model that makes an agent work: memory, context management, retries, budgets, tool wiring. "Harness engineering" is the craft of building it well, and how much of it each framework gives you free is one of this project's main questions — which is why each stack must build its harness from the framework's own parts. → [ADR-0008](decisions/adr-0008-framework-native-harness.md)

**Hook (lifecycle)** — a callback a framework fires at named points in its own loop: before a model call, after a message is added, when a tool runs. Hooks let you meter tokens, enforce budgets, or emit events without rewriting the loop — and how rich a framework's hook surface is decides how much of that you can do at all.

**Agent memory** — what an agent remembers across turns beyond the raw conversation: opponent behaviour, promises made, standing plans. Here it's deliberately private and *unreliable* — it records what an agent believes, including things it was successfully lied to about.

**Context compaction** — summarising older conversation into something shorter so the important parts survive when history outgrows the context window. Also called compression or summarisation. Watching an agent play worse after compaction is a genuine, visible failure mode.

**Prompt caching** — reusing the model's processing of an unchanged prompt prefix across calls, cutting cost and latency. It works best when a large stable part (the rules) sits ahead of a small changing part (the board). [`shared/prompts/`](../shared/prompts/) is split into `system/` and `turn/` for exactly this reason.

**Prompt set** — the whole collection of prompts a game was played with, versioned and hashed together. The hash is recorded in `game_started`, because prompts change and two transcripts recorded under different prompts are not comparable — nothing else about a JSONL file would reveal that. → [shared/prompts](../shared/prompts/README.md)

**Seat** — a numbered player slot (1–4) with a fixed model and access route. Distinct from **colour**, which is the in-game identity. The seat→colour mapping rotates between games so no model permanently occupies one colour. → [ADR-0006](decisions/adr-0006-seat-rotation.md)

**Profile** — a named set of models and budgets in [`shared/models.yaml`](../shared/models.yaml): `dev` for cheap harness shakedown runs, `headline` for real ones. All three stacks always run the same profile; it varies per experiment, never per stack.

**Confounding** — when two things change together, so a measured difference can't be attributed to either one. Running different models on different access routes would confound model with route: if the Bedrock agents did better, you could never say why. Most of this repo's odder-looking decisions exist to prevent it. → [ADR-0005](decisions/adr-0005-model-access-control.md)

**Guardrail** — a check on what a model may say or do. Here they're deliberately **lenient**: in-game lying and betrayal are permitted because they're the phenomenon being studied. Only out-of-fiction attacks are blocked. → [ADR-0004](decisions/adr-0004-structural-guardrails.md)

**Prompt injection** — text crafted to make a model ignore its instructions and follow the attacker's instead. In a multi-agent game, one agent trying this on another is an attack on the system, not clever play — so it *is* blocked.

**LLM-as-judge** — using a model to score things a metric can't capture, like whether a move was strategically sound. Powerful and biased; the biases are named and mitigated rather than assumed away. → [evaluation](projects/ludo/evaluation.md#judge-bias--and-what-we-do-about-it)

**Eval** — short for evaluation: measuring how well a model or agent performs, ideally with a rubric and evidence rather than a vibe.

**Observability / tracing** — recording what a system did in enough detail to explain its behaviour afterwards. A *trace* follows one operation end to end; a *span* is one step within it.

**RAG** (retrieval-augmented generation) — fetching relevant documents and putting them in the prompt so the model can answer from them. Not used in LUDO; on the [roadmap](topics/roadmap.md).

**Fine-tuning** — further training a model on your own examples to change its behaviour. **Continued pre-training** goes further, training on large unlabelled domain text. Both are on the roadmap, neither is in LUDO.

---

## Ludo vocabulary

Full detail in [game rules](projects/ludo/game-rules.md).

**Token** (Ludo sense) — a playing piece. Each player has four. *Unrelated to the LLM sense above* — an unfortunate collision the board game had first.

**Base** — where a player's tokens start, off the board. A 6 is needed to bring one out.

**Start square** — where a colour joins the main track. The four start squares are 13 apart.

**Circuit** — the shared 52-square loop all players travel clockwise.

**Home column** — the five private squares leading to the centre. Only the matching colour may enter; nobody can be captured there.

**Home** — the centre triangle. Reaching it requires an *exact* roll; overshooting isn't allowed.

**Capture** — landing on a lone opponent token sends it back to its base to start over. Worth roughly the whole journey it had made.

**Safe square** — one of eight squares (marked with stars) where no capture can happen.

**Block** — two tokens of the same colour on one square. Opponents can neither land on it nor pass it.

**Colour-relative position** — the engine's coordinate system. Every colour counts from its *own* start square, so movement logic is identical for all four players: `-1` base, `0`–`50` circuit, `51`–`55` home column, `56` home.

---

## Missing something?

If a doc used a term that isn't here, that's a bug in the docs — [open an issue](https://github.com/itamittech/llmeval/issues). Explaining as we go is a [stated goal](vision.md), not a nice-to-have.
