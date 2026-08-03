# ADR-0009 — Negotiation runs on the swarm orchestrator; the protocol is redesigned to fit it

**Status:** Accepted — supersedes the negotiation choice in [ADR-0008](adr-0008-framework-native-harness.md); revises [answered question 6](../open-questions.md#-6-alliance-channel-design)
**Date:** 2026-08-03

## Context

[ADR-0008](adr-0008-framework-native-harness.md) mapped negotiation to the agents-as-tools pattern after a source-level reading showed Strands' `Swarm` could not carry the question-6 protocol: `Swarm` resets each agent's private state on every activation, gives the floor to whoever spoke last, and its durable carriers are broadcast. The [capability-matrix finding](../architecture/stack-comparison.md) records the mechanics with line numbers.

The maintainer's direction, given with the finding in hand: **the swarm orchestrator is the architecture this project should showcase, and earlier protocol decisions yield to it.** That direction has force beyond preference. ADR-0008's own principle is *native primitives wherever they exist* — and a protocol invented before any framework was consulted is not itself sacred. Redesigning the protocol to ride the framework's first-class multi-agent orchestrator is the more native move; keeping the invented protocol and routing around the orchestrator was the less native one. The comparison also sharpens: LangGraph has a direct counterpart (`langgraph-swarm`, tool-based handoffs), so two of three stacks implement the *same orchestration pattern* natively and Spring AI's answer — whatever it is — becomes a headline matrix row.

There was a genuine conflict to resolve, not a misunderstanding: question 6's protocol and `Swarm`'s semantics could not both survive. Question 6 lost.

## Decision

**Negotiation is a floor-passing table conversation, designed to `Swarm`'s semantics and specified framework-neutrally in the [harness contract](../projects/ludo/harness-contract.md).**

| Question 6 (v1) | This ADR (v2) |
|---|---|
| Active agent drives the whole phase | Active agent **opens**; the floor then passes to whomever the current speaker addresses |
| Private pairwise channel | **Directed message** — content seen by its addressee; *that it happened* is visible to all |
| Public broadcast | **Table note** — rides on a floor pass; visible to every later speaker in the phase |
| Recipient may reply exactly once | Hard cap instead: `budgets.max_floor_passes` per phase |
| No cross-reading of reasoning | **Unchanged** |
| Conversation retained in-head | Retention within a phase is framework behaviour; durable conclusions are written at **reflect**, outside the swarm run |

Mechanics, in Swarm terms — each also stated framework-neutrally in the contract so the other stacks implement the same observable behaviour:

- One floor-holding = one activation; the directed message is the handoff message, the table note is the handoff's shared-context contribution, the cap is `max_handoffs`.
- A floor-holder with nothing to say declines to pass; the orchestrator treats that as the end of the phase. Floor control, caps, and completion are **enforced by the orchestrator, not by harness code**.
- Per-agent private context (own memory, messages received since its last turn) is seeded into each agent's history at phase start, *before* the swarm is constructed — Swarm snapshots state at construction and resets each activation to that snapshot, which turns the reset semantics into the delivery mechanism for the briefing rather than a bug to fight.
- Events: a floor pass emits `message_sent` with `to: <colour>`; a table note emits `message_sent` with `to: null`. The schema is unchanged.

Deception — the phenomenon under study — survives: false table notes, contradictory directed messages to different players across floor holdings, feigned alliances. An alliance can now form inside a single phase (propose → floor passes → accept), which v1 needed two turns for.

## Consequences

**Good**

- The most framework-native negotiation available, in the two stacks that have an orchestrator for it — exactly what this repo exists to compare. The harness stops enforcing floor control, message caps, and phase termination; the framework does.
- "Who is whispering to whom" is public while content is not — visible drama for spectators, real information asymmetry for players.
- Faster alliance dynamics: propose and accept within one phase.

**Bad — the honest losses against v1, accepted knowingly**

- **Directed content is ephemeral.** The addressee sees it during that activation; nothing guarantees it survives to their next turn unless they write it into memory at reflect. Deals can be genuinely forgotten by the agent that made them. That is now a *feature under observation*, not a defect — but it is a real change to the game.
- **The active agent can lose its own phase.** Once the floor passes, other agents may redirect the conversation; the opener may never get it back. The cap bounds cost, not fairness.
- **In-phase retention is framework behaviour**, so stacks may diverge in how much agents remember mid-phase — accepted divergence under ADR-0008, recorded in the matrix, visible in transcripts.
- **The handoff tool's own description is framework-authored text** (Strands' `handoff_to_agent` docstring reaches the model). The prompt-parity boundary moves: authored prompts stay shared and identical; tool schemas are framework territory under test. Recorded in the matrix; the contract requires each stack to expose an equivalently-purposed floor-passing action.
- **Spring AI has no swarm orchestrator** (to be verified when that stack starts): floor-passing would be hand-built there — a *Manual* rating that is legitimate under ADR-0008's rule, and a significant comparison result either way.
- Recorded games and the prompt set from v1 are historical: `manifest.yaml` bumps to version 2, and the negotiation prompts are rewritten.

## Alternatives

**Agents-as-tools, preserving the v1 protocol** (ADR-0008's original mapping). Rejected by direction: it preserves a protocol nobody's framework expresses natively at the cost of never exercising the orchestrator this project wants to showcase.

**Hybrid — `Swarm` for public talk, agents-as-tools for private.** Preserves the strongest v1 property (durable private channels) while still using the orchestrator. Rejected: two transports for one conversation doubles the machinery in every stack, and complexity is explicitly not a goal of this repo.

**Bend `Swarm` to v1 with hooks** — intercept handoffs, force return-to-sender, re-inject wiped state. Rejected: fighting the primitive at every step is the opposite of framework-native, and every intercept is harness code pretending to be the framework.
