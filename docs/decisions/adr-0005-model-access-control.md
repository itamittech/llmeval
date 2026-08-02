# ADR-0005 — One model on both access routes, as a control

**Status:** Accepted
**Date:** 2026-08-01

## Context

LUDO runs four agents: two invoked through AWS Bedrock, two through direct provider APIs. Comparing the two access routes is an explicit goal of the [brief](../roughidea.txt).

The obvious setup — four different models, two on each side — quietly makes that comparison meaningless. If the Bedrock agents behave differently from the direct-API agents, there's no way to tell whether that came from the access route or simply from the models being different. The variable of interest is confounded from the start.

## Decision

**One model is invoked through both routes**, occupying one Bedrock seat and one direct-API seat. The remaining two seats go to different model families.

```yaml
# shared/models.yaml — shape, not final selection
agents:
  red:    { access: bedrock, model: <model-X> }   # ─┐ same model,
  yellow: { access: direct,  model: <model-X> }   # ─┘ two routes  ← the control
  green:  { access: bedrock, model: <model-Y> }
  blue:   { access: direct,  model: <model-Z> }
```

Model X must be available on Bedrock *and* via a direct provider API. A fourth family is held in reserve for the [judge](../projects/ludo/evaluation.md), which should not come from a family that played.

## Consequences

**Good**
- **Bedrock vs. direct becomes measurable.** With the model held constant, differences in latency, cold start, token accounting, guardrail availability, and observability are attributable to the access route.
- Two seats still carry different families, so alliance dynamics stay interesting — four identical agents would make for a duller game and a duller demo.
- Doubles as a correctness check: the same model on two routes should play *comparably*. A large behavioural gap means a bug in one path, or a meaningful difference in how a framework configures it.
- Costs nothing structurally — access route is already config, not code.

**Bad**
- Constrains model choice: the dual-route model must exist on both Bedrock and a direct API, which rules some options out.
- The two routes may still differ in default inference parameters or system-prompt handling. These must be pinned explicitly, or the "control" silently isn't one.
- Same-model agents can converge on similar strategies, slightly reducing behavioural variety versus four distinct families.
- Region and version skew is a real risk — Bedrock may serve a different model revision than the direct API. This must be recorded in the event stream per game, not assumed.

## Alternatives

**Four different families** — maximum behavioural diversity and the liveliest game, but the Bedrock-vs-direct comparison is confounded and can only be described anecdotally. Rejected: it would leave one of the project's stated goals unmeasurable.

**Same model in all four seats** — the cleanest possible framework comparison, removing model as a variable entirely. Rejected for v1: four identical agents make alliance and deception dynamics far less interesting, and those are the phenomena under study. Worth running later as a dedicated controlled experiment — it would isolate framework effects better than anything else we can do.

**Two models, each on both routes** — two controls instead of one, and no seat left for a third family. A reasonable variation to run later.
