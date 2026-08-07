# Project 02 — ALIBI

**Four LLM detectives race to solve a theft. The truth is sealed in an envelope; the evidence is split between private exhibits and a public archive that can only be searched — and the archive contains lies.**

This is the repo's second project, chosen by [ADR-0010](../../decisions/adr-0010-project-two-alibi.md) from what LUDO's [capability matrix](../../architecture/stack-comparison.md) revealed. It introduces exactly two new hard things — **retrieval** and the **agent-as-tool** architecture — and inherits everything else from LUDO on purpose: same event stream, same engine-per-language pattern, same parity discipline, same eval split.

> The mechanics are inspired by the classic deduction-game family (Cluedo and its relatives). The name, cast, and setting are original fiction — the mechanics are common property; the trade dress is not. See [ADR-0010](../../decisions/adr-0010-project-two-alibi.md).

## What it demonstrates

| Topic | How it shows up |
|---|---|
| RAG | The archive is the evidence source; retrieval quality is measurable by deduction accuracy |
| RAG architectures | The same game replayed under different retrieval profiles — naive, hybrid, reranked |
| Agent-as-tool | The archivist: a non-playing specialist agent each detective invokes as a tool |
| Grounded citation | The archivist must cite document ids; ungrounded answers are the failure mode under study |
| Belief calibration | Each detective declares its current best guess with confidence; scored against ground truth over time |
| Deception, continued | Bluff suggestions, spin in table notes, and unreliable testimony in the archive itself |
| Three-stack comparison | Same game, three frameworks — and this time the RAG story inverts the standings |

## Why a deduction game

- **Ground truth exists.** LUDO's games mostly end at the turn cap and are judged from position. ALIBI's engine *knows who did it*, so accusation accuracy, time-to-solve, and belief calibration are deterministic scores — the judge is reserved for interrogation craft.
- **Information asymmetry is the board.** No dice, no movement: what each detective knows, and what it reveals by asking, is the entire game state that matters.
- **Asking teaches the table; searching teaches only you.** A suggestion compels evidence but leaks your line of inquiry to every rival. An archive query is private — but the archive is testimony, not fact. That tension is the strategy.
- **The table is facts; the archive is claims.** A refutation is engine-mediated — an exhibit actually shown, impossible to fake. An archive document is a witness's *claim*, and some witnesses are wrong or lying. Agents must live by this repo's own rule: claims are claims, not facts.
- **Deception is native, not bolted on.** Suggesting elements you secretly hold is legal bluffing with real strategic value. Nothing about cunning had to be invented for this project; the mechanics supply it.

## The case

A theft at a gala. The engine seals a hidden triple — **who** (one of six suspects), **how** (one of five methods), **where** (one of eight places) — and deals the remaining sixteen elements to the four detectives as private **exhibits**, four each. Full mechanics in the [rules](game-rules.md).

Alongside the deal, the engine generates the **archive**: witness statements, staff logs, and records, produced deterministically from the game seed by templates — no LLM anywhere in the engine, same as LUDO. Reliable documents are consistent with the truth; **red herrings** are not, and cross-checking is how a careful detective tells them apart.

## The archivist — agent-as-tool

Detectives never search the archive directly. They ask the **archivist**: a fifth, non-playing agent that owns retrieval and answers questions with citations to document ids. One archivist serves the whole game — its model pinned in `shared/models.yaml`, its cost metered separately, its answers grounded or they are wrong.

Why an agent and not a bare search call? Because that *is* the architecture under study: the specialist encapsulates retrieval strategy and summarisation behind a tool interface, and each framework expresses "an agent used as a tool" differently — or fails to, which is a matrix finding. Query content is private to the asking detective; that a query happened is public, like a visit to the library everyone can see.

The scripted tier runs a deterministic retriever with no embeddings, so every test stays free, offline, and byte-reproducible — the same discipline as LUDO's scripted models. Embedding-based retrieval profiles are live-tier.

## What carries over from LUDO

| Inherited | From |
|---|---|
| Shared event stream; UI and eval consume only transcripts | [ADR-0003](../../decisions/adr-0003-shared-event-stream.md) |
| One engine per language, cross-checked by conformance vectors — now covering corpus bytes too | [ADR-0002](../../decisions/adr-0002-engine-per-language.md) |
| Framework-native harnesses over one behavioural contract | [ADR-0008](../../decisions/adr-0008-framework-native-harness.md) |
| One model on both access routes as the control | [ADR-0005](../../decisions/adr-0005-model-access-control.md) |
| Seat → detective assignment rotates between games | [ADR-0006](../../decisions/adr-0006-seat-rotation.md) |
| Prompts shared verbatim, no template logic | [shared/prompts](../../../shared/prompts/README.md) |
| Lenient in-fiction guardrails; cheating structurally impossible | [ADR-0004](../../decisions/adr-0004-structural-guardrails.md) |
| UI proven stack-independent by transcript fixtures | [ADR-0007](../../decisions/adr-0007-ui-alongside-first-stack.md) |
| Agent memory — LUDO's beliefs become, literally, the detective's notebook | [harness contract](../ludo/harness-contract.md) |

The guardrail line is unchanged: in-fiction cunning — bluff suggestions, spin, misdirection — is the phenomenon under study. Out-of-fiction attacks — prompt injection at the archivist or rivals, forged exhibits, fabricated engine state — are blocked. Refutations are engine-mediated, so **cheating stays structurally impossible and deception stays safely permitted**.

## Scoring

Deterministic first: accusation correctness, rounds-to-solve, and calibration of each turn's declared belief against the sealed truth. The judge scores what metrics can't: quality of questioning, use and abuse of the archive, bluff craft, and whether a detective's notebook actually drove its decisions. Same machinery as [LUDO's eval](../ludo/evaluation.md), pointed at a game with an answer key.

## Scope boundaries

**In scope** — the case engine and generator (both languages), the archivist, four detective agents in all three stacks, retrieval profiles, evaluation, UI.

**Out of scope for v1** — voice, fine-tuning, AWS deployment, graph- and edge-agent architectures, cross-game memory. These stay on the [roadmap](../../topics/roadmap.md).

## Status

✅ **Built at the scripted tier.** Both engines (20 conformance vectors, corpus bytes included), three feature-complete scripted stacks whose fixtures share one engine-event spine, the deterministic eval, and the UI. Pace was benched (answered [question 21](../../open-questions.md#-21-alibis-pace--case-dimensions-query-allowance-turn-cap)); [question 23](../../open-questions.md#-23-retrieval-parity--what-must-be-pinned-and-what-is-allowed-to-be-the-finding) — retrieval parity — is the live tier's question, gated like everything live on the model ids. The findings so far are in [the matrix's second act](../../architecture/stack-comparison.md#alibi-the-second-act).

## Related

- [Game rules](game-rules.md) — the normative spec
- [Engine design](engine-design.md) — the built engine, read against LUDO's
- [Harness contract](harness-contract.md) — what all three stacks must make observable
- [ADR-0010](../../decisions/adr-0010-project-two-alibi.md) — why this project, this name, these two new hard things
- [LUDO brief](../ludo/brief.md) — the template this project inherits from
- [Capability matrix](../../architecture/stack-comparison.md) — the scoreboard ALIBI's RAG columns will join
- [Open questions](../../open-questions.md)
