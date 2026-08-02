# ADR-0003 — Shared event stream as the integration contract

**Status:** Proposed
**Date:** 2026-08-01

## Context

Three stack implementations need to feed one UI and one evaluation harness. They also need to be compared against each other. Each could expose its own API and each could get its own adapter — but that means three adapters per consumer, and comparison becomes a bespoke exercise every time.

Separately: LLM games are slow and expensive. Re-running a match to look at it again is a bad deal.

## Decision

Every implementation emits the **same append-only event stream** — dice rolls, moves, captures, messages, agent reasoning, memory writes, context compactions, token counts, latencies, costs, guardrail triggers — against a versioned JSON Schema in `shared/schemas/`.

The event stream is the **only** integration point. The UI and eval harness consume it and nothing else. Neither has any knowledge of which stack produced a given game.

## Consequences

**Good**
- One UI and one eval harness serve all three stacks, and neither needs updating when a stack changes.
- **A game becomes a file** — reproducible, diffable, shareable, replayable. Review a match without spending a token.
- Comparison becomes mechanical: diff two streams from the same seed.
- The UI and eval harness are developed and demoed offline against committed sample games, with no API keys. This is what makes the repo explorable for a casual visitor — a large deal for a teaching project.
- Evals can be revised and re-run against historical games for free.

**Bad**
- The schema is a coordination point. Changing an event type means changing all three stacks together, and the schema must be designed before much else can be built.
- Risk of the schema drifting toward whatever the first stack happened to produce. Mitigation: schema is written from the [rules spec](../projects/ludo/game-rules.md) and [agent design](../projects/ludo/agent-design.md), not reverse-engineered from an implementation.
- Some framework-native telemetry won't map cleanly and will need adapting — though that mismatch is itself a [matrix](../architecture/stack-comparison.md) finding worth having.
- Committed sample games add repository weight.

## Alternatives

**Per-stack APIs with adapters** — three adapters per consumer, no replay, comparison stays manual. Rejected.

**Direct database writes** — requires a running database for every local run; kills the zero-setup replay story.

**OpenTelemetry traces as the only record** — good for performance, poor for game semantics and replay. We use OTel *in addition*, for latency and span-level detail, not instead.
