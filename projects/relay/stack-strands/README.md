# RELAY on Strands

Four runner agents, one shared anchor model, one race. The simplest harness in this repo — and that is the finding, not an omission.

## Run it

```bash
uv run --directory projects/relay/stack-strands pytest
```

A full scripted race, offline and free — regenerates the committed fixture byte-identically:

```bash
uv run --directory projects/relay/stack-strands python -m relay_strands.demo out.jsonl
```

## Design

| Concern | How | Rating |
|---|---|---|
| Turn loop | The engine drives; the harness renders one template per turn and parses three lines | — |
| Runner agents | One `Agent` per lane, alive for the race, `name=color` | **Native** |
| Notebook | `agent.state`, rendered into `{{memory}}` | **Native** |
| Conversation | `SlidingWindowConversationManager`, pinned at 12 | **Native** |
| Metering + budget | Lifecycle hooks — `AfterModelCallEvent` for usage, `BeforeModelCallEvent` to cancel at the ceiling | **Native** |
| **Escalation to the anchor** | A second `Agent` over the anchor model, messages wiped before each call | **Adapter** — see below |
| Guardrails | Harness gate on the note, at the parse boundary | **Manual** |
| Orchestration | None exists. There is nothing to orchestrate | n/a |

### The anchor is where the framework runs out

RELAY needs one call to a *different* model, with no memory and no tools, chosen by policy rather than triggered by an error.

Strands has no primitive for that. `Agent` binds one model at construction; there is no fallback chain, no router, no `with_alternatives`. So the anchor is a second `Agent` whose message list the harness clears before every call — [`players.build_anchor`](src/relay_strands/players.py).

**The temptation worth naming:** `model.stream()` would call the anchor model directly, with no agent wrapped around it. It also skips the agent loop, and with it the lifecycle hooks — so the anchor's tokens would vanish from the meter in the one project where measuring them is the entire point. Same shape as [the summariser trap](../../../docs/architecture/stack-comparison.md#finding-strands-summariser-bypasses-strands-own-hook-system) LUDO recorded: the shortcut past the framework is the shortcut past the instrumentation.

### No tool, and what that removes

ALIBI's stacks disagreed about what "one call" meant, because Spring AI executed tools inside the model call and the Python stacks did not. RELAY has no tool: escalation is performed by the *engine*, which charges the shared quota and invokes whatever anchor it was configured with.

The consequence shows up in the numbers — all three stacks meter the same calls — and it is worth stating why. It is not that the frameworks converged. It is that the protocol stopped asking them to differ, which is [the lesson ALIBI already recorded](../../../docs/architecture/stack-comparison.md#finding-remove-the-protocol-and-the-orchestration-axis-vanishes) arriving from the other direction.

## The scripted tier does not use a reply list

Both earlier games scripted their models with hand-typed replies. RELAY cannot, and the reason is the seal: a fixed list is written by a human who looked at the track, so it encodes knowledge the runner is not allowed to have, and it silently becomes wrong the moment a generator changes.

So [`policies.py`](src/relay_strands/policies.py) computes each reply from **the rendered prompt alone** — the same text the real model would see. Four personalities, deliberately unalike:

| lane | policy | what it demonstrates |
|---|---|---|
| red | solves what it can, escalates the rest | the intended play |
| green | never escalates, guesses instead | what refusing the pool costs |
| yellow | escalates everything while the pool lasts | what taking the commons costs everyone |
| blue | escalates ordering puzzles only | precision on one weakness |

The anchor solves every family from the prompt — including the tier-3 ciphers that withhold their shift — so "the anchor is right" is earned in the fixture rather than asserted.

## The story in the fixture

Yellow spends the pool early on stages it could mostly have done, lying about why (`"trust me, this one is a monster"` — legal, in-fiction, and it passes the guardrail). Its second lie claims engine authority and is **blocked**, which is the whole ADR-0004 line drawn in one transcript: the lie about the puzzle stands, the lie about the system does not.

By the time red and blue meet stages they genuinely cannot do, the pool is dry.

## Related

- [Harness contract](../../../docs/projects/relay/harness-contract.md) — what this stack is held to
- [Game rules](../../../docs/projects/relay/game-rules.md) — normative
- [Capability matrix](../../../docs/architecture/stack-comparison.md) — where the ratings above live
