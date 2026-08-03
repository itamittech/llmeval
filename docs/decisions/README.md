# Architecture Decision Records

Short records of decisions that were **not obvious** and would otherwise get silently re-litigated six months later.

## Format

One file per decision, `adr-NNNN-short-title.md`:

```markdown
# ADR-NNNN — Title
**Status:** Proposed | Accepted | Superseded by ADR-NNNN
**Date:** YYYY-MM-DD

## Context      — what forced a decision
## Decision     — what we chose
## Consequences — what this costs us, including the bad parts
## Alternatives — what else was considered and why it lost
```

## Rules

- **Never edit an accepted ADR's decision.** Write a new one that supersedes it. The wrong turns are part of the teaching value.
- **Record the cost.** An ADR with no downsides listed hasn't been thought through.
- Only for decisions that are expensive to reverse or non-obvious. Not every choice needs one.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](adr-0001-monorepo.md) | Single repository for all three stacks | Proposed |
| [0002](adr-0002-engine-per-language.md) | One game engine per language, not per stack | **Accepted** |
| [0003](adr-0003-shared-event-stream.md) | Shared event stream as the integration contract | Proposed |
| [0004](adr-0004-structural-guardrails.md) | Structural enforcement enables lenient content guardrails | Proposed |
| [0005](adr-0005-model-access-control.md) | One model on both access routes, as a control | **Accepted** |
| [0006](adr-0006-seat-rotation.md) | Rotate the seat-to-colour assignment between games | **Accepted** |
| [0007](adr-0007-ui-alongside-first-stack.md) | Build the UI alongside the first stack, against transcript fixtures | **Accepted** |
| [0008](adr-0008-framework-native-harness.md) | Harness primitives are framework-native; the shared layer is contracts only | **Accepted** |

0002, 0005, 0006, 0007 and 0008 are ratified. The rest encode reasoning from the [original brief](../roughidea.txt) but have not been explicitly confirmed — see [open questions](../open-questions.md).

**0006 is worth reading even if you don't care about seat assignment.** It was drafted asserting that moving first is an advantage in Ludo, that assumption was measured, and it turned out to be false. The decision survived on different grounds, and the record of the wrong turn stayed in.
