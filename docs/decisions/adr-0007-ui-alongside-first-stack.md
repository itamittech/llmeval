# ADR-0007 — Build the UI to completion alongside the first stack, against transcript fixtures

**Status:** Accepted
**Date:** 2026-08-02

## Context

[ADR-0003](adr-0003-shared-event-stream.md) makes the event stream the only integration contract: every stack emits one schema, and the UI and eval harness consume nothing else. That settles *what* the UI reads. It does not settle **when the UI gets built**, or how we know stack-independence actually holds rather than merely being intended.

The obvious order is to build all three stacks, let the schema settle, then build the UI once against a stable target. It is wrong for two reasons.

**The UI is the strongest available test of whether the event stream is sufficient.** Nothing else forces the question *"can this transcript be fully reconstructed from events alone?"* A stack can emit an incomplete stream and never notice, because the stack already knows what it meant. Discovering a missing field after three stacks exist means a schema change plus three coordinated stack edits. Discovering it with one emitter costs one edit.

**Stack-independence decays quietly.** A UI built while three stacks exist gets tested against three transcripts and looks portable. A UI built against one stack can accumulate assumptions about that stack's event ordering, field usage, or agent-event density — and none of that surfaces until stack two, by which point the fix is a rewrite rather than a correction.

## Decision

**The UI is built to completion alongside the first stack (Strands), not after the third.** Transcript replay only; live streaming stays deferred per open question 4.

Stack-independence is enforced by a **fixture set** rather than by intent:

1. The UI's test suite renders every transcript in `projects/ludo/games/`, offline, with no API keys — a condition ADR-0003 already requires.
2. The set starts with the existing **engine-only random-bot transcript**, which contains *zero* agent events. A UI that renders it correctly cannot depend on any agent-layer event existing, which is the strongest form of the guarantee available before a second stack exists.
3. Adding a stack means adding its transcript to the fixture set. **The UI code must not change.** A diff touching UI source in the same commit that adds a stack is the signal that something leaked.
4. **The `stack` field may be displayed, never branched on.** Tested directly: re-render a fixture with `game_started.stack` mutated and assert the output is identical apart from the label. Branching on stack identity is the specific failure this whole ADR exists to prevent, and it is otherwise invisible until it's expensive.

## Consequences

**Good**
- Schema gaps surface while there is one emitter to fix rather than three.
- The project has a watchable artifact after one stack instead of after three — which matters for a repo whose purpose is teaching.
- The zero-agent-event fixture makes the guarantee testable *today*, before a second stack exists to compare against.
- Forces the harness contract to be written down as a specification while building Strands, rather than reverse-engineered from it later.

**Bad**
- **The first stack sets the template.** Whatever shape Strands gives memory, compaction, negotiation loops and event timing becomes the de facto contract the other two must match — and some of it will be Strands-shaped rather than neutral. Unavoidable, since something must go first; mitigated only by extracting a stack-neutral harness contract *as* Strands is written, and treating anything the other stacks must contort to match as a [capability-matrix](../architecture/stack-comparison.md) finding rather than a bug to hide.
- The UI is built against one real emitter, so "works for all stacks" rests on the schema being honest rather than on observation. The fixture rule converts this into a check that fires later, not one that prevents the mistake.
- Deferring stacks two and three delays the comparison that is the repo's actual point. Accepted: a complete vertical slice is worth more than three half-built ones, and it de-risks the two that follow.
- More total work before the first comparison exists.

## Alternatives

**UI after all three stacks.** Safest for portability — three real emitters to test against. Rejected: it makes schema gaps maximally expensive, and leaves the project with nothing watchable for a long stretch.

**Thin UI now, complete it later.** Lower risk of over-fitting to Strands. Rejected: "complete it later" competes with stacks two and three for attention and reliably loses, and a permanently-thin UI can't stress the schema, which is the main reason to build it early.

**Vertical slice across two stacks before completing either.** Would surface framework divergence earliest of all. Rejected for now: it doubles the in-flight work while the harness shape is still unknown, and the divergence it surfaces would be about half-built code rather than about the frameworks.
