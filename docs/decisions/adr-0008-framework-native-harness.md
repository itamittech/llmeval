# ADR-0008 — Harness primitives are framework-native; the shared layer is contracts only

**Status:** Accepted
**Date:** 2026-08-03

## Context

The first cut of `stack-strands` was built the way a cautious production system would be: the framework treated as a risk to contain rather than the subject to exhibit. Memory, token accounting, and the model boundary were hand-rolled, framework-independent Python (`memory.py`, `budget.py`, `model.py`), with Strands confined to one adapter file. The motives were individually sound — behavioural parity across stacks, testability without API keys, insulation from framework churn.

The design fails this repo's own constitution, on two counts that have been in CLAUDE.md from the start:

- *"The three implementations must differ only in the agent framework."* If every stack ships the same hand-rolled harness, the implementations differ in almost nothing — the framework, the one intended variable, is reduced to a model-invocation detail.
- *"Never quietly hand-roll a substitute and imply parity."* A framework-independent core hand-rolls substitutes for **every** framework primitive at once, before ever asking whether the primitive exists.

The cost lands on the [capability matrix](../architecture/stack-comparison.md) — the repo's headline output. Rows like *short-term memory*, *context compaction*, and *state persistence* would have compared our own code with itself three times, and the frameworks would never have been exercised on exactly the capabilities the matrix exists to compare.

It also works against the stated concision goal. Framework-native is *less* code: Strands' context compaction is a constructor argument; the hand-rolled equivalent is a subsystem with its own tests.

[ADR-0007](adr-0007-ui-alongside-first-stack.md) already warned that "the first stack sets the template." A framework-independent core is the worst version of that risk: the template it sets isn't even a framework's shape — it's ours.

## Decision

**The shared layer is contracts and data only. Everything between prompt-in and event-out is the framework's job, done the framework's way.**

Shared and identical across stacks, as before: prompt text (`shared/prompts/`), model ids, inference settings and budget *numbers* (`shared/models.yaml`), the event schema (`shared/schemas/`), and the engines. The [harness contract](../projects/ludo/harness-contract.md) stays normative but is re-scoped by this ADR to **observable behaviour only** — phases, event obligations, budget limits, failure rules. It no longer mandates any internal structure.

Each stack MUST meet the harness responsibilities with its framework's native primitives wherever they exist. Hand-rolling is reserved for what the framework cannot do, and every hand-rolled piece is recorded in the capability matrix — a *Manual* rating beside an existing framework feature now means we broke our own rule.

For Strands, the mapping — each primitive verified to exist in the pinned `strands-agents 1.50.2` source rather than taken from its documentation:

| Harness responsibility | Strands primitive |
|---|---|
| Agent loop | `Agent` |
| Memory across turns | `AgentState` + a `SessionManager` for persistence |
| Context compaction | `SummarizingConversationManager` |
| Token metering | `AfterModelCallEvent` hook + per-call usage metrics |
| Budget enforcement | `BeforeModelCallEvent` hook |
| Event emission → shared schema | hooks (`MessageAddedEvent`, model-call events) |
| Scripted model for conformance | a custom `Model` implementation |
| Negotiation | agents-as-tools — see below |

Reading the source to build that table produced the policy's first finding before any turn-loop code exists: **Strands' `Swarm` cannot express LUDO's private channels.** Everything a swarm agent contributes goes into a `SharedContext` — the class docstring reads "Shared context between swarm nodes" — visible to every agent. Negotiation requires pairwise messages other players never see; deception depends on them. Negotiation therefore uses the agents-as-tools pattern, and the gap is recorded in the matrix.

## Consequences

**Good**

- The capability matrix gets real rows with real evidence — the repo's stated purpose. One finding already exists as a direct product of this decision.
- Less code per stack, and each stack reads like its framework — the teaching surface this repo promises.
- The comparison finally measures the frameworks rather than our own harness three times.

**Bad**

- Built, tested code gets retired: `memory.py`, `budget.py`, and the `ModelClient` seam; roughly half of the stack's 40 tests get rewritten against Strands primitives. This ADR exists partly to record that the rework was chosen, not drifted into.
- Behavioural divergence *inside* the contract becomes possible: three frameworks summarising differently will play different games from the same seed. That is a result, not a flaw — but it narrows what scripted-model conformance can compare to event order and obligations, never summary text.
- Framework version becomes an experimental variable — a Strands upgrade can change how compaction summarises and therefore how a game goes. Each stack's lockfile pins it; whether the transcript should also record it is now [open question 17](../open-questions.md).
- The failure-handling boundary needs a line drawn: retries inside the SDK's transport are now framework behaviour under test, while application-level re-prompting stays forbidden. The contract's §6 draws it.

## Alternatives

**The framework-independent core (as built).** Maximum behavioural parity, minimum framework risk. Rejected for the reasons in Context: it measures our code, not the frameworks, and empties the matrix.

**A shared harness library for the two Python stacks.** Stronger still on parity. Rejected harder: it couples the stacks, violates the never-share-an-environment rule, and doubles down on the same mistake — Spring AI would be compared against a library the Python stacks share.

**Framework-native with no behavioural contract.** The purest exhibition of each framework. Rejected: with no fixed observable surface, divergence stops being measurable. The contract is what turns "different" into *comparably* different.
