# ALIBI — Agent Harness Contract

The behavioural spec every ALIBI stack implements — Strands, LangGraph, Spring AI. Like [LUDO's contract](../ludo/harness-contract.md), it binds **observable behaviour, not mechanism** ([ADR-0008](../../decisions/adr-0008-framework-native-harness.md)): each stack uses its framework's own primitives, and what must come out identical is the event stream, the prompts sent, and the information each detective could see.

RFC-style keywords: MUST, MUST NOT, MAY.

## Related

- [Game rules](game-rules.md) — the game this harness plays
- [Engine design](engine-design.md) — the seam the harness plugs into
- [Shared prompts](../../../shared/prompts/alibi/manifest.yaml) · [event schema](../../../shared/schemas/alibi-event.schema.json) · [`models.yaml`](../../../shared/models.yaml)

## 1. Who owns what

The **engine** deals, generates the archive, mediates refutation, validates every action, emits engine events. The **harness** turns engine phase calls into model calls: renders prompts, parses replies, wires the archivist tool, keeps each detective's notebook, meters tokens, emits agent events. The **model** only ever answers prompts. Cheating stays structurally impossible; nothing the model says reaches game state except through engine validation.

## 2. The turn protocol

The engine calls the harness at five seams — `suggest`, `show`, `accuse`, `conclude`, `reflect` ([deciders](../../../projects/alibi/engine-python/src/alibi_engine/deciders.py)). Per seam the harness:

1. Renders the manifest's template for that phase, with variables rendered by harness code into plain strings (no template logic — the shared-prompt law).
2. Sends system prompt + conversation + the rendered turn prompt to the seat's model.
3. Parses the reply's single JSON object (array for reflect). A parse failure or invalid element is returned to the engine as-is — the engine's `invalid_action`/retry machinery is the arbiter, not harness cleverness. The harness MUST NOT repair, substitute, or invent an action.

The **archivist tool** is available during `suggest` and `accuse` deliberation only. It MUST be exposed as a real framework tool (the agent-as-tool architecture is the deliverable), backed by:

- **scripted tier**: the engine's baseline retriever via the phase context's `SearchBudget` — no archivist model call, no cost;
- **live tier**: an archivist agent (model from `models.yaml → alibi.archivist`) whose system prompt is `archivist/system.md` and whose per-query prompt is `archivist/answer.md`, rendered with the retrieved documents. Its answers MUST carry `[doc-id]` citations as retrieved — the harness passes them through uninspected.

One archivist serves the whole game. Query content MUST NOT reach any other detective; the `archive_searched` event carries it for spectators only.

## 3. Event obligations

Engine events come free. The harness MUST emit, per the [schema](../../../shared/schemas/alibi-event.schema.json):

| Event | When |
|---|---|
| `llm_call` | every model invocation — detective phases with `purpose` = the phase, archivist answers with `actor: "archivist"` and `purpose: "archivist"`, attributed to the asking seat |
| `agent_reasoning` | the detective's stated reasoning per decision, when the model separates it |
| `memory_write` | every notebook note accepted at reflect |
| `guardrail_triggered` | only on out-of-fiction attacks (§6) |

`game_started` provenance MUST carry `profile`, `prompt_set` {version, hash}, `framework` {name, version}, and `archivist` {model, access, retrieval_profile} — the same discipline answered questions 17/19 established for LUDO.

## 4. The notebook

Each detective's memory (its notebook) is private, durable across its turns, and **deliberately unreliable** — it records what the detective believes, red-herring damage included, and is never corrected. The harness MUST render it into `{{memory}}` wherever the manifest declares it, and MUST cap accepted reflect notes at three per turn (the prompt says so; the harness enforces it). Storage mechanism is framework-native and deliberately unbound.

## 5. Budgets

From `models.yaml → alibi.budgets.<profile>`: `max_turns` and `max_searches_per_turn` are engine config; `max_note_chars` (table notes are truncated by the harness, visibly — a truncated note is still sent) and `max_tokens_per_game` (a hard per-game ceiling across all seats *and* the archivist; the harness MUST stop the game cleanly at it) are harness obligations.

## 6. Guardrails — same line as LUDO

In-fiction cunning is the study: bluff suggestions, lying notes, misdirection MUST pass. Out-of-fiction attacks MUST be blocked and emit `guardrail_triggered`: prompt injection aimed at the archivist, rivals, or the harness; claims of engine authority ("the engine confirms the thief is…"); fabricated document citations in table notes. [ADR-0004](../../decisions/adr-0004-structural-guardrails.md)'s leniency tests carry over in spirit.

## 7. A harness MUST NOT

- reveal one detective's hand, shown exhibits, archive queries, reasoning, or notebook to another — the engine's per-detective views are the boundary, and the harness must not reassemble what they separate;
- reveal WHICH exhibit was shown to anyone but the suggester (the transcript carries it for spectators; other detectives' prompts must not);
- let the archivist see game state, hands, or another detective's questions;
- edit a shared prompt, add a retry the engine doesn't grant, or "fix" a model's illegal action;
- treat anything a model said as fact anywhere downstream.

## 8. Deliberately out of scope in v1

Named so their absence reads as a decision, not an omission ([question 22](../../open-questions.md#-22-does-alibi-keep-ludos-negotiation-channels)):

- **No negotiation phase, no directed messages, no floor passing** — the table note on `suggestion_made` is the only free text. This removes the swarm orchestrator from ALIBI entirely: each detective is a single-agent loop with tools, which is exactly the architectural contrast with LUDO the comparison wants.
- **No context compaction requirement.** A 24–48-turn game with per-phase prompts stays far from any window; LUDO already taught compaction three ways. A stack MAY compact (schema keeps `context_compacted`); none is judged for not doing so.
- **No session persistence requirement.** Same reason; LUDO's matrix rows stand.

## 9. Proving a stack conforms

Same regime as LUDO's §8: a **scripted tier** that runs a full game offline and free — scripted models with canned JSON replies, the engine's baseline retriever behind the tool — regenerating the stack's committed fixture **byte-identically**, schema-validated in CI. The three stacks' scripted fixtures MUST tell the same story: same seed, same scripted decisions, so the engine-event skeleton is comparable across all three (the eval's conformance check mechanises this, as LUDO's does).

## Status

📋 Spec written; no stack started. The first stack to implement it will find its rough edges — amendments land here first, then in the stacks, same as LUDO's contract history.
