# ADR-0011 — Project three is RELAY: an escalation race between small models and one big one

**Status:** Proposed — the direction (an edge-agent game as project three) is the maintainer's (2026-08-07); the name, shape, and mechanics below are proposals and have **not** been ratified
**Date:** 2026-08-07

## Context

Two projects are complete at the scripted tier. LUDO filled the [matrix](../architecture/stack-comparison.md)'s orchestration and harness-memory rows; ALIBI filled its tool and retrieval rows and produced the finding that reframes what comes next — [remove the protocol and the orchestration axis vanishes](../architecture/stack-comparison.md#finding-remove-the-protocol-and-the-orchestration-axis-vanishes): *which* framework differences you experience is decided by your protocol, not by the framework list. Picking a third game is therefore picking which rows get filled.

Read the matrix with that in mind and the gap is not subtle. Its whole back half is still `—`: cost attribution, retry/backoff/fallback model, rate limiting, and **every row in Model access** — Bedrock invocation, direct provider API, provider swap without code change. Three built stacks, and not one number about what a call costs or how long it takes, because every game so far has been played by scripted models.

The [roadmap](../topics/roadmap.md) offered two candidates for this slot. **Werewolf/Mafia** was the named one, but [ADR-0010](adr-0010-project-two-alibi.md) already recorded that LangGraph's table-as-`StateGraph` partly claimed the graph story, and ALIBI's finding predicts the rest: a phase-machine game re-runs the axis LUDO already measured. The other unclaimed architecture — **edge agent** — has sat on the roadmap since the beginning with nothing in it.

One more thing forced the timing. Both existing games are stopped at the same wall: the Nova, DeepSeek, and judge model ids are `TBD`, so **no live game has ever been played**, and the operations rows cannot be filled without one. A game whose players run *on this machine* needs no undecided id and no key at all.

## Decision

Project three is **RELAY** — four small models race along a track of engine-generated stages. Any runner may **escalate** a stage to one shared frontier model, and every escalation spends from a **shared quota** the whole table watches drain.

- **The runners.** Three small open-weight families across four lanes, hosted locally (Ollama or equivalent), with one family running in two lanes — one local, one hosted — the same control [ADR-0005](adr-0005-model-access-control.md) built for LUDO, pointed at a new question: what "edge" actually buys, in latency, cold start, and cost. Concrete ids are deferred to [question 26](../open-questions.md#-26-relays-edge-tier--which-small-models-hosted-how-and-what-must-be-pinned) and `shared/models.yaml`, exactly as LUDO's were.
- **The anchor** is the pinned Anthropic model, and it is **a model, not an agent**: escalating swaps the model for one call. That is what keeps RELAY out of ALIBI's territory — no sub-agent, no tool seam, the archivist keeps the agent-as-tool architecture to itself.
- **The stage** is a deterministically generated puzzle with a checkable answer and an engine-side difficulty tier. **The tier is never shown.** Deciding whether you can solve it *is* the move — the edge-agent architecture's central question stated as a game rule.
- **The quota is a commons.** One pool for the table, visible to everyone. Escalating denies rivals the same option later, which is the adversarial pressure ADR-0010 demanded when it rejected a retrieval quiz for lacking it. Cheap-and-wrong versus expensive-and-right becomes a move opponents can read and exploit.
- **Time is ticks, not seconds.** The engine charges deterministic tick costs for escalating, answering wrongly, and passing; real wall-clock latency is *measured and recorded beside them* but never decides an outcome. That is what keeps the engine deterministic and the scripted tier byte-reproducible while latency remains the thing the project is about.
- **Winning** is reaching the finish line, or standing furthest along it at the cap — the same mid-game-scoring reality [question 7](../open-questions.md) established for LUDO.

**The two new hard things:**

1. **Edge hosting** (topic 9's last unclaimed architecture, and topic 2 extended into open-weight small models) — a model running as a local process, bound three different ways, with no API key in sight.
2. **Escalation policy under a shared budget** (topics 4 and 5) — when to spend, measured. This is where the matrix's empty operations rows get filled: cost attribution because cost is the currency, fallback-model machinery because escalation *is* a fallback chain, rate limiting because the quota is one.

**Everything else is inherited, deliberately:** the shared event stream ([ADR-0003](adr-0003-shared-event-stream.md)), one engine per language held together by conformance vectors ([ADR-0002](adr-0002-engine-per-language.md)), framework-native harnesses over a behavioural contract ([ADR-0008](adr-0008-framework-native-harness.md)), seat rotation ([ADR-0006](adr-0006-seat-rotation.md)) with lanes in place of colours, shared verbatim prompts, lenient in-fiction guardrails ([ADR-0004](adr-0004-structural-guardrails.md)), the UI built against transcript fixtures ([ADR-0007](adr-0007-ui-alongside-first-stack.md)), and the eval's deterministic-first split. Normative rules will live at `docs/projects/relay/game-rules.md` and the project's shape at `docs/projects/relay/brief.md`; neither is written, and neither should be until this ADR is ratified.

The name follows the house pun: a relay is what you run, and what you do when the small model can't. It is a generic sports term with no cast, no board, and nothing owned — the trademark care [ADR-0010](adr-0010-project-two-alibi.md) had to spend on Cluedo costs nothing here.

## Consequences

**Good**

- **It can actually be played.** RELAY is the only candidate whose live tier is not blocked on an undecided model id: the runners need no key, and the anchor is the already-pinned Anthropic model. The remaining requirement is an API key and a machine, not a decision. Two games have been built and never run; this one could produce the repo's first live numbers.
- **The empty half of the matrix gets filled.** Cost attribution, retry/backoff/fallback, rate limiting, per-provider config, both access routes — rows that no amount of scripted play could ever populate, because they are about what a real call costs and how it fails.
- **The judge stays optional, for the second game running.** Puzzle answers are ground truth, so accuracy, escalation efficiency (correct answers per quota token), and commons behaviour are all deterministic — the property ALIBI proved out.
- **Counterfactual scoring is free, because the model is local.** For every stage a runner escalated, the eval can afterwards ask the runner anyway, off the record, and score the decision against what would have happened: *did you escalate exactly when you were about to be wrong?* Belief calibration's cousin, and the sharpest possible measure of an agent knowing what it doesn't know. It costs one extra local inference and no money.
- **A third grain, and probably a third leader.** LUDO's differences were orchestration-shaped, ALIBI's tool-shaped; RELAY's should be model-binding-shaped — local-model providers, fallback chains, retry policy. Which framework comes out ahead is a genuine prediction, and it is recorded in the matrix either way.

**Bad — accepted knowingly**

- **The difficulty ladder is unmeasured, and the game dies without it.** If the runners solve every stage or none, escalation is trivial and there is no game. This is LUDO's pace question and ALIBI's again, but harder: the answer depends on *model competence*, not on rules arithmetic, so it must be benched against real small models before the rules can be written ([question 25](../open-questions.md#-25-relays-difficulty-ladder--can-a-small-model-tell-what-it-cant-do)).
- **Determinism ends at the model.** Every number this repo has published so far is byte-reproducible. Live local inference is not: sampling, quantisation, hardware, and daemon version all move it. The scripted tier stays exactly as reproducible as before, but RELAY's live results are the first this repo cannot regenerate exactly — so the transcript must record the host and the build, or the numbers mean nothing later.
- **A daemon is a new environment axis.** [Environment strategy](../architecture/environment-strategy.md) covers two venvs and a JVM; it does not cover a model server. CI cannot run one, so scripted-tier tests must never need it, and "offline and free" acquires a second meaning: no keys **and** no daemon.
- **Latency is the headline mechanic and it does not decide the game.** Ticks decide; wall-clock is recorded beside them. A variant where wall-clock decides would be truer to the theme and unreproducible, and it is deliberately not v1 — the honest compromise, stated rather than hidden.
- **A third generator ports twice.** ADR-0002's rule means the stage generator is written in Python and Java and its bytes join the conformance vectors — a known cost since ALIBI's corpus, but a cost.
- **The doc surface triples.** A third brief, rules spec, harness contract, and eval doc, all held to Rule #1. Paid deliberately, as before.

## Alternatives

- **Werewolf/Mafia** — the roadmap's named project-three candidate, and the natural home for graph agents. Deferred to project four, not rejected: ADR-0010 recorded that LangGraph's `StateGraph` table already claimed part of that story, ALIBI's finding predicts a phase machine would re-run LUDO's orchestration axis, and deception is ground LUDO owns. It becomes a stronger project once a fourth framework or a live tier changes what a state machine would reveal.
- **The blitz quiz as parked** — trivia answered fast, escalating when stuck. Rejected on ADR-0010's own precedent: a quiz is no more a game than a retrieval quiz was, and the [vision](../vision.md) argues nobody finishes a tutorial with a scoreboard bolted on. RELAY keeps that entry's escalation mechanic and adds the thing it lacked — a scarce shared resource opponents compete for.
- **A per-lane quota instead of a commons.** Simpler to explain and to score, and it removes exactly the adversarial pressure that killed the two quiz proposals. Rejected for the same reason both times.
- **The anchor as an agent-as-tool sub-agent.** Tempting — the machinery already exists in three stacks. Rejected: it re-runs an architecture project two has claimed, and it confounds what RELAY is measuring, since escalation cost and sub-agent overhead would become one number.
- **Hosted small models as "the edge"** (a small frontier-vendor model instead of a local one). Cheaper to operate and needs no daemon, but then "edge" means nothing: cold start, hardware sensitivity, and the no-key property — the three findings the project exists to produce — all vanish. Kept as the degraded fallback if local hosting proves impractical on the target machine, and recorded as such rather than silently substituted.
- **The arena** (deployment: Lambda, API Gateway, AgentCore). Still a strong standalone project ([question 11](../open-questions.md)), still teaching infrastructure rather than agent behaviour, and the games it hosts would be reruns.
- **The apprentice** (fine-tune a small model on committed transcripts). Still blocked on a live corpus that does not exist. Worth noting the direction of the dependency: RELAY's runners are precisely the models the apprentice would fine-tune, so building RELAY brings that project closer rather than competing with it.
