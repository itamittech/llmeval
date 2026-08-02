# ADR-0002 — One game engine per language, not per stack

**Status:** Accepted
**Date:** 2026-08-01

## Context

Goal #5 of the [brief](../roughidea.txt) says the same task is implemented three times. Taken literally, that means three Ludo engines.

But a Ludo engine is deterministic, LLM-free code: board state, dice, legal move generation, capture, win detection. Writing it three times teaches nothing about agent frameworks — and if the three engines diverge even slightly, every downstream difference in agent behaviour becomes uninterpretable. We would no longer know whether LangGraph "played worse" or just got a subtly different rulebook.

## Decision

**Two engines, one per language.**

- `engine-python` — shared by both Strands and LangGraph.
- `engine-java` — for Spring AI.
- Both must reproduce a shared set of **conformance vectors** (seed + move sequence → exact resulting state) stored in `shared/conformance/`.

"Three versions of the same task" is honoured at the **agent and orchestration layer**, which is what the project is actually comparing.

## Consequences

**Good**
- Strands and LangGraph become a genuinely controlled experiment: same language, same engine, same prompts, same models. The *only* variable is the agent framework. This is the cleanest comparison in the repo.
- Rule drift between the Python stacks is impossible.
- One less engine to write, test, and keep correct.
- Conformance vectors catch Python/Java divergence mechanically, in CI, without model calls.

**Bad**
- Reduces the "three full implementations" claim — the engine is shared, and the README should be honest about that rather than implying otherwise.
- The Python↔Java comparison is still exposed to engine divergence. Conformance vectors reduce this but only cover the cases we thought to write.
- Cross-language conformance is real ongoing work: every rule change means regenerating vectors and updating two engines.

## Alternatives

**Three engines (one per stack)** — literal reading of the brief. Rejected: triples the rule-drift surface and the maintenance cost while teaching nothing about the frameworks under study.

**One engine as a service, all stacks call it over HTTP** — perfect rule parity and eliminates the Java engine entirely. Rejected for v1: adds a network hop and a running process to every local run, complicates setup for a teaching repo, and makes the Java implementation less genuinely "Java". Worth reconsidering if cross-language conformance becomes a burden.

**One engine, Java stack calls Python via a bridge** — worst of both; awkward and unidiomatic.
