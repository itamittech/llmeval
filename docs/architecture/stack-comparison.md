# Stack Capability Matrix

The running scoreboard. This file is the repo's headline output — the thing a reader comes for.

> From the brief: *"If any framework suppose Spring AI doesnt have the corresponding harness functionality that should be also highlighted."*

Gaps are results. When a framework can't do something, we record it here, build the workaround, note what it cost, and surface it in the UI.

## How to read it

| Rating | Meaning |
|---|---|
| **Native** | First-class feature. Idiomatic, documented, a few lines. |
| **Adapter** | Achievable via a supported extension point, but we wrote glue. |
| **Manual** | No framework support; we implemented it ourselves from scratch. |
| **Absent** | Not reasonably achievable within the framework's model. |
| **—** | Not yet evaluated. |

Every rating must link to the code that justifies it. **An unsourced rating is an opinion, and opinions don't go in this table.**

## Matrix

> ⏳ Empty pending implementation. Populated as LUDO is built in each stack.

### Core agent mechanics

| Capability | Strands | LangGraph | Spring AI | Notes |
|---|---|---|---|---|
| Tool / function calling | — | — | — | |
| Structured output | — | — | — | |
| Multi-agent orchestration | — | — | — | |
| Agent-to-agent messaging | — | — | — | Alliance negotiation |
| Streaming responses | — | — | — | |
| Turn/step control & interruption | — | — | — | |

### Harness engineering

| Capability | Strands | LangGraph | Spring AI | Notes |
|---|---|---|---|---|
| Short-term / conversation memory | — | — | — | |
| Long-term agent memory | — | — | — | Cross-turn recall of opponents |
| Context compaction / summarisation | — | — | — | Explicit goal of the project |
| Prompt templating & versioning | — | — | — | |
| Prompt caching | — | — | — | Provider- and framework-dependent |
| State persistence / resume | — | — | — | |
| Human-in-the-loop interrupt | — | — | — | |

### Operations

| Capability | Strands | LangGraph | Spring AI | Notes |
|---|---|---|---|---|
| Token accounting | — | — | — | |
| Cost attribution | — | — | — | |
| OpenTelemetry tracing | — | — | — | |
| Retry / backoff / fallback model | — | — | — | |
| Guardrails integration | — | — | — | Bedrock Guardrails vs. framework-native |
| Rate limiting / concurrency control | — | — | — | |

### Model access

| Capability | Strands | LangGraph | Spring AI | Notes |
|---|---|---|---|---|
| Bedrock invocation | — | — | — | |
| Direct provider API | — | — | — | |
| Agent needs a compile-time dep on the engine | no | no | **yes** | Python `Protocol` is structural; Java `interface` needs `implements`. See the finding below |
| Provider swap without code change | — | — | — | Driven by `shared/models.yaml` |
| Bedrock-native guardrails | — | — | — | |
| Per-provider inference config | — | — | — | See the finding below — settings are **not** uniform across families |

### Finding: Strands accepts a wrong config keyword, warns, and ignores it

First real observation from building a stack, and a cautionary one for the other two.

`BedrockModel` and `AnthropicModel` take their configuration as **keyword arguments**. Passing `model_config={...}` — a plausible reading, since `update_config` takes exactly that name — is accepted, emits a `UserWarning`, and is then **discarded**. Every pinned setting reverts to a default.

That failure is invisible in the worst way: the model still answers, the game still plays, the transcript still validates, and the claim that all three stacks run identical inference settings is quietly false. It was caught only because the settings were asserted rather than assumed — `test_strands_client.py` now constructs each seat's model and reads `get_config()` back.

**The two providers also disagree within the same framework.** `BedrockConfig` has `temperature` and `top_p` as first-class keys; `AnthropicConfig` has neither and takes a `params` passthrough instead. So even inside one stack, "pin the inference settings" is per-provider plumbing rather than one call — the same asymmetry already recorded below for `models.yaml`, now confirmed at the SDK layer.

**What to check in LangGraph and Spring AI:** whether a mistyped or misplaced config key fails loudly, warns, or is silently dropped. A framework that fails loudly deserves credit for it in this matrix.

### Finding: the Java agent must depend on the engine; the Python agents need not

Recorded from the engine port, before any stack exists.

In Python, `Decider` is a `Protocol`. An agent satisfies it by having a `choose` method of the right shape — no import, no inheritance, no compile-time relationship between the engine package and the agent package at all. That is what lets the Strands and LangGraph stacks keep [genuinely separate dependency trees](environment-strategy.md) while sharing one engine.

Java's `interface` needs an explicit `implements`, so every Spring AI agent must have `ludo-engine` on its compile classpath. Nothing breaks — but the isolation the Python stacks get for free has to be arranged deliberately on the JVM, and a future change to `Decider` is a recompile for the Java stack and a no-op for the Python ones.

A second, smaller one from the same port: **Java test seams must be designed in advance.** Python's engine tests reach three-sixes cancellation by assigning `game.dice` on a live object; Java has no equivalent, so `Game` carries a package-private constructor taking an `IntSupplier`. Expect the same asymmetry wherever the Spring AI stack needs to substitute a model client — which is exactly what the harness contract's [scripted-model conformance](../projects/ludo/harness-contract.md) will require.

### Finding: inference settings are not uniformly pinnable

Recorded before any stack exists, because it changes what "identical configuration" can mean.

The plan was to pin `temperature`, `top_p`, and `max_output_tokens` in [`shared/models.yaml`](../../shared/models.yaml) so that no framework's defaults could leak into the comparison. **That is not achievable across these four families.** The Claude 5 models reject `temperature`, `top_p`, and `top_k` with a 400 and control reasoning depth with an `effort` level instead; Amazon Nova and DeepSeek take the sampling parameters and have no equivalent effort knob.

So `models.yaml` pins settings **per provider** — the honest shape — rather than asserting a single number that two of the four seats would reject.

**What this costs, precisely:** nothing in the [ADR-0005](../decisions/adr-0005-model-access-control.md) control. Seats 1 and 3 are the same model with the same settings, so Bedrock-vs-direct stays clean. What's lost is the weaker claim that *all four seats* were configured identically — which was never a controlled comparison to begin with, since the models differ in every other respect too. The value of writing it down is that the limitation is now visible rather than assumed.

A related consequence: on Claude 5, thinking is on by default and its tokens count against `max_output_tokens`, so a budget sized for the answer alone truncates mid-response. `max_output_tokens` is set with that headroom included.

## Quantitative comparison

Filled from recorded games. Same seeds, same models, same rules — so these numbers mean something.

| Metric | Strands | LangGraph | Spring AI |
|---|---|---|---|
| Lines of code (agent + orchestration layer) | — | — | — |
| Direct dependencies | — | — | — |
| Cold start to first move | — | — | — |
| Median agent turn latency | — | — | — |
| Tokens per game (same seed) | — | — | — |
| Cache hit rate | — | — | — |
| Cost per game | — | — | — |

Engine and UI code are excluded from the LOC count — they're shared, so counting them would flatter everyone equally and tell you nothing.

## Narrative findings

> Populated during implementation. This is where the actual insight lives — the table above is just the index.

Each entry: what we tried, what happened, what it cost, and what we'd tell someone choosing a framework.

## Related

- [Architecture overview](overview.md) — why parity makes these numbers comparable
- [Vision](../vision.md) — why negative results get equal billing
