# LUDO — Agent Design

> Terms like *swarm*, *harness*, *context compaction*, and *prompt injection* are all defined in the [glossary](../../glossary.md).

## Swarm shape

Four peer agents, no coordinator. Each owns one colour, sees the same public board, and acts only on its own turn. There is no manager agent deciding who moves — the engine's turn order does that, and the agents are otherwise autonomous peers.

This is the "agent swarm" pattern from the brief, and Ludo is a good fit for it: peers with private goals, a shared environment, and a communication channel. What distinguishes it from a hierarchical or graph-routed system is that **no agent has authority over another** — influence has to be earned through negotiation.

```
        ┌──────────────── shared board state (public) ────────────────┐
        │                                                             │
   ┌────▼────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐
   │   RED   │◄────►│  GREEN  │◄────►│ YELLOW  │◄────►│  BLUE   │
   │ bedrock │      │ bedrock │      │ direct  │      │ direct  │
   └────┬────┘      └────┬────┘      └────┬────┘      └────┬────┘
        │                │                │                │
        └────────────────┴──── engine (tools) ─────────────┘
                              ▲
                    validates every action
```

## Turn protocol

Each turn runs a fixed sequence, identical across all three stacks:

1. **Observe** — the agent receives the board state, the recent event log, and its own memory.
2. **Negotiate** *(optional)* — it may send public or private messages, and read messages addressed to it. Bounded by a message budget so negotiation can't run forever.
3. **Roll** — the engine rolls. The agent does not control this.
4. **Decide** — given the legal moves for that roll, the agent picks one and states its reasoning.
5. **Resolve** — the engine applies the move, handles capture, and determines whether an extra roll was earned.
6. **Reflect** — the agent may write to its memory: an observation about an opponent, a plan, a grudge.

Every step emits events. The reasoning captured at step 4 and the memory writes at step 6 are what make the UI worth watching.

**Failure handling.** An agent that returns an illegal move is told why and asked once more. A second failure forfeits the turn. Timeouts and provider errors forfeit the turn too. Forfeits are recorded as events and count against the agent in evaluation — reliability is part of what we're measuring, not something to paper over with retries.

## Communication

Settled in [open question 6](../../open-questions.md#-6-alliance-channel-design); the protocol agents actually receive is [`system/negotiation.md`](../../../shared/prompts/ludo/system/negotiation.md).

Two channels, both fully logged:

- **Public** — broadcast to all four agents. Table talk, open threats, public offers.
- **Private** — directed to exactly one agent. Where real alliances get made, and where deception becomes possible.

The distinction matters: with only a public channel, everyone sees every deal and betrayal is trivially detectable. Private messages let an agent tell red one thing and green the opposite — and that contradiction is invisible in-game while being perfectly visible to the *viewer* in the UI. Watching a lie land is the single best demo this project has.

**Who may speak.** Only the agent whose turn it is opens a conversation. An agent that receives a direct message may reply **once**. There are no unprompted broadcasts on someone else's turn.

The alternative — all four free to talk every turn — costs roughly 4× the negotiation tokens and lets negotiation swamp the game. The cost of this choice is one that agents are told about explicitly: **forming an alliance takes at least two turns**, one to propose and one to accept.

**Nobody sees anyone else's reasoning.** An agent's private deliberation is never shown to another agent — reading an opponent's mind would make deception pointless. Spectators see all of it.

Messages are bounded per turn (count and length). The numbers live in [`shared/models.yaml`](../../../shared/models.yaml) per profile, not in the prompt, so tuning them costs a config edit rather than a prompt change and a new prompt-set hash.

## Memory

Each agent keeps private, persistent memory across turns — not just conversation history, but a structured record of what it has concluded:

- **Opponent models** — "blue promised not to capture and did anyway on turn 12."
- **Commitments** — what it has promised, to whom, and whether it intends to honour it.
- **Strategy notes** — standing plans that survive the context window.

Memory is deliberately implemented as an explicit subsystem rather than left to whatever each framework does implicitly. That's the only way to compare frameworks on it fairly — and the memory implementation is one of the [matrix](../../architecture/stack-comparison.md) rows most likely to separate them.

Memory is **private and unreliable by design**: an agent's memory reflects what it *believes*, including things it was successfully deceived about. We do not correct it.

## Context management

A four-agent game with negotiation generates a lot of transcript. Somewhere past the early turns, the full history stops fitting.

The prompt is layered by volatility, which is also what makes it cacheable:

| Layer | Changes | Cacheable |
|---|---|---|
| Rules + role + strategy guidance | Never | ✅ Ideal |
| Long-term memory | Occasionally | Partially |
| Recent event window | Every turn | ❌ |
| Current board + legal moves | Every turn | ❌ |

When history exceeds its budget, older turns are **compacted** — summarised into durable facts and folded into memory, then dropped from the window. Compaction events are emitted and shown in the UI, because "the agent forgot something and played worse afterwards" is a real, visible, teachable failure mode.

## Prompts

Built: [`shared/prompts/ludo/`](../../../shared/prompts/README.md), versioned, shared verbatim by all three stacks. If Strands and Spring AI ran different prompts, the comparison would be meaningless.

Each agent gets the same base prompt, differing only in the `{{color}}` variable. **We do not hand-code personalities** — no "you are the aggressive one." Whether distinct playing styles emerge from identical prompts and different models is one of the more interesting things to watch, and pre-assigning personas would destroy that observation. [`check_prompts.py`](../../../scripts/check_prompts.py) fails the build on a per-colour prompt file, because this is exactly the rule that erodes while debugging one agent's bad play.

The prompt states the objective, the consequences of the rules, the negotiation protocol, and that deception is permitted. It does not tell an agent whether to deceive.

**It does not teach legality.** The engine validates every move and only ever offers choices that are already legal, so an agent never needs to work out whether it may leave base on a 3 — that option simply isn't in the list. [ADR-0004](../../decisions/adr-0004-structural-guardrails.md) is usually described as making lenient content policy safe; it also makes the prompt substantially smaller, which is a second dividend worth naming.

Which prompts played a given game is recorded in `game_started` as a version and a hash, since a transcript recorded under an older prompt set isn't comparable with a newer one and nothing else in the file would show it.

## Guardrails

Enforcement sits at three levels:

1. **Structural** — the engine validates every move. Illegal moves are rejected, not corrected. Cheating is impossible regardless of what an agent says or intends.
2. **Content** — blocks out-of-fiction attacks: prompt injection at other agents or the harness, forged state claims, real-world harassment or slurs.
3. **Budget** — per-agent and per-game token ceilings; message rate limits; turn timeouts.

Level 1 is what makes the lenient content policy safe. Because an agent physically cannot cheat, letting it lie costs nothing. Detail in the [brief](brief.md#guardrails-lenient-on-purpose).

Bedrock agents can use Bedrock Guardrails natively; direct-API agents need an equivalent implemented in-harness. **That asymmetry is itself a finding** — one of the clearest concrete differences between the two access routes — and gets recorded rather than smoothed over.

## Open design questions

Settled since this doc was first written: the [channel design](../../open-questions.md#-6-alliance-channel-design), reasoning privacy, and the model families. Seat assignment [rotates between games](../../decisions/adr-0006-seat-rotation.md), so a colour is not a stable identity across transcripts.

Still open in [open-questions.md](../../open-questions.md): concrete model IDs, and negotiation budget sizing — which needs a measured per-turn token cost and therefore can't be settled until the first stack runs.

## Related

- [Game rules](game-rules.md) · [Brief](brief.md) · [Evaluation](evaluation.md)
- [Engine design](engine-design.md) — the `Decider` protocol an agent implements, and how one turn executes
- [Architecture overview](../../architecture/overview.md) — the tool contract these agents bind to
