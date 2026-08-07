# RELAY Harness Contract

What every stack must do, stated as **observable behaviour** rather than as a class design. That framing is [ADR-0008](../../decisions/adr-0008-framework-native-harness.md)'s: each framework builds this from its own primitives, and where a framework has none, the gap is the [matrix](../../architecture/stack-comparison.md) finding rather than a licence to hand-roll quietly.

This is normative for the stacks the way [game-rules.md](game-rules.md) is normative for the engines.

## 1. One agent per lane, and that is the whole architecture

Four runners, each a **single-agent loop** with no sub-agents, no swarm, and no orchestrator — the same shape ALIBI settled on ([question 22](../../open-questions.md)) and for the same reason: this project's comparison is not about orchestration.

A stack MUST NOT introduce a coordinator, a planner, or an agent-as-tool anywhere in the turn path. If a framework makes single-agent loops awkward, *that* is the finding.

## 2. The turn

Once per turn the harness MUST:

1. render the shared prompts for this lane and this stage, verbatim from [`shared/prompts/relay/`](../../../shared/prompts/README.md);
2. call **the runner's own model** to produce a decision;
3. if the decision is to escalate, call `ctx.desk.ask()` — **and nothing else**;
4. return one `Attempt` to the engine.

The engine adjudicates. The harness never scores an answer, never advances a position, and never touches the tick clock.

## 3. Escalation is the framework's fallback seam

Step 3 is the one place the frameworks are expected to differ, and it is why this project exists.

- The anchor MUST be reached through whatever the framework offers for **swapping or falling back to another model** — a fallback chain, a second client, a router. A stack that constructs a raw HTTP call beside its framework has broken ADR-0008.
- The anchor MUST be a **model call, not an agent invocation**: no tools, no memory, no multi-step loop. It sees the stage prompt and returns text. A stack that wraps the anchor in an agent is measuring something else.
- The anchor's reply MUST be committed as given. A harness that post-processes, retries on a wrong-looking answer, or falls back to its own model has invented a strategy the rules do not have.

**MUST NOT:** call the anchor without going through `ctx.desk.ask()`. The desk is what charges the shared quota; a side call is theft from the other three lanes and would not appear in the transcript.

## 4. The seal

**MUST NOT**, under any circumstance:

- put a stage's tier in a prompt, a memory, a log line, or a tool result;
- put any stage's answer in front of a runner before it has answered;
- read `game_ended.track_key` during play, including from a previously committed transcript of the same seed.

The engine makes the first two structurally hard — a harness is handed `PublicStage`, which has no such fields. The third is a discipline, and it is the one a fixture-driven test suite can actually catch: a stack whose runners suddenly escalate perfectly on the tier-3 stages of a known seed is a stack that read the key.

## 5. Memory

Each runner MUST have a private store that survives its own turns and is invisible to the other three. It holds whatever the runner writes; the interesting content in this game is **self-knowledge** — which families it keeps missing — and the engine already hands it the raw material through `view.own_history()`.

Framework-native, per ADR-0008: an agent-state store, a memory abstraction, or a documented equivalent. If a framework has none, `Manual` is the honest rating — it was in both earlier games.

**MUST NOT** write a tier or an unrevealed answer into memory. See §4.

## 6. Metering

Every model invocation MUST emit `llm_call` with the lane's colour, the model, the access route, and token counts.

- Anchor calls carry `actor: "anchor"` and the **anchor's** model id, on the **escalating lane's** colour — cost lands where it was spent.
- `latency_ms` is REQUIRED on live runs. This is the one project where latency is the subject; a transcript without it cannot answer the question the project was built to ask.
- `cold_start: true` on a lane's first local call. It is the measurement a hosted API cannot produce, and it is easy to lose by warming the model before the game starts.

Where a framework aggregates several invocations into one reported call — [Spring AI's internal tool execution](../../architecture/stack-comparison.md#finding-spring-ais-internal-tool-execution-hides-model-invocations-from-the-caller) did exactly this in both earlier games — the stack MUST record what it can see and the divergence goes in the matrix. It must not be smoothed over.

## 7. Guardrails

Lenient, per [ADR-0004](../../decisions/adr-0004-structural-guardrails.md). Same three structural rules as both earlier games, applied at the message boundary.

A note that lies about a stage's difficulty, talks a rival into wasting quota, or claims an escalation that never happened is **in-fiction cunning and MUST pass**. Only out-of-fiction attacks — prompt injection, forged state, abuse — may be blocked, and blocking MUST emit `guardrail_triggered`.

## 8. Deliberately out of scope

Stated so that a missing feature reads as a decision rather than an oversight:

- **Context compaction.** A stage prompt plus a short history does not outgrow a window. Inventing pressure to exercise a primitive would be dishonest; the `context_compacted` event exists for schema symmetry and stays unused.
- **Session persistence.** Races are independent samples, as games are in both earlier projects.
- **Negotiation.** One public note per turn is the entire channel.

All three were exercised thoroughly by LUDO and are not re-litigated here.

## 9. The scripted tier

Every stack MUST run a full race against **scripted models** — no keys, no daemon, no cost — and commit the resulting transcript as a fixture. Both the runner models and the anchor are scripted at this tier.

The fixtures are what let the UI and the eval be built and tested offline ([ADR-0007](../../decisions/adr-0007-ui-alongside-first-stack.md), [ADR-0003](../../decisions/adr-0003-shared-event-stream.md)), and what let three stacks be compared before a single live call is made. A stack's engine-event spine MUST match the other stacks' on the same seed: same stages attempted, same clears, same ticks. Where the *agent* events differ — how many calls the framework made to produce one turn — that difference is the comparison.

## Related

- [Game rules](game-rules.md) — normative, and the source of every number here
- [Engine design](engine-design.md) — what the engine guarantees the harness
- [ADR-0008](../../decisions/adr-0008-framework-native-harness.md) — why this file describes behaviour and not classes
- [Shared prompts](../../../shared/prompts/README.md) — sent verbatim, no stack may edit them
