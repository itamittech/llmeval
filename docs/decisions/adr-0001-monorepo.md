# ADR-0001 — Single repository for all three stacks

**Status:** Proposed
**Date:** 2026-08-01

## Context

Every project is built three times — Strands (Python), LangChain/LangGraph (Python), Spring AI (Java) — plus a shared engine, a UI, and an eval harness. These could live in one repository or several.

They are tightly coupled by design: all three stacks must conform to the same tool contract, event schema, and prompts. When a shared contract changes, all three change together.

## Decision

One repository containing all stacks, shared contracts, docs, UI, and infrastructure.

## Consequences

**Good**
- A contract change lands atomically. Split repos would make every schema revision a multi-repo dance, and drift would be inevitable.
- Reader can see all three implementations side by side — which is the entire point of the project.
- One clone, one setup, one issue tracker. For a teaching repo, the barrier to a curious visitor is the metric that matters most.
- Conformance vectors can span both engines in a single CI run.

**Bad**
- Four toolchains in one tree (Python ×2, JVM, Node). Mitigated by [environment strategy](../architecture/environment-strategy.md) and a `just`-based entry point.
- Repository grows large as projects accumulate. Acceptable — a per-project directory structure keeps it navigable.
- CI must be path-filtered or it will rebuild everything on every commit.
- A contributor interested only in Spring AI still clones the Python stacks.

## Alternatives

**One repo per stack** — clean isolation, but shared contracts would need publishing as versioned artifacts across three language ecosystems, and side-by-side comparison would be impossible. Fatal for a comparison project.

**Repo per project (LUDO, project-2, …)** — reasonable, and worth revisiting if the tree gets unwieldy. Rejected for now because cross-project learning is an explicit goal and `platform/` needs somewhere to grow.
