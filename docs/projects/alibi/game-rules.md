# ALIBI — Canonical Rule Specification

> **Status: normative.** [ADR-0010](../../decisions/adr-0010-project-two-alibi.md) is Accepted; this document is what `engine-python` and `engine-java` implement and what the conformance vectors enforce. Pace numbers are **measured**, not guessed — see [the numbers](#the-numbers) and answered [question 21](../../open-questions.md#-21-alibis-pace--case-dimensions-query-allowance-turn-cap).

ALIBI is a hidden-triple deduction game in the Cluedo family, redesigned as original fiction for four LLM detectives and a searchable evidence archive. Deduction games have many variants; agents need one deterministic ruleset, so this document fixes it.

## The case

During the centenary gala at the Grand Meridian hotel, the Nilgiri Sapphire vanishes. Every game is one case, generated deterministically from a seed.

The case has three dimensions:

| Dimension | Count | v0 element set (original fiction, placeholder until ratified) |
|---|---|---|
| **Who** — the thief | 6 | the curator, the magician, the heiress, the chef, the photographer, the retired inspector |
| **How** — the method | 5 | sleight of hand, a duplicate key, the service hatch, a staged blackout, a forged pass |
| **Where** — the scene | 8 | ballroom, vault room, kitchen, terrace, library, cloakroom, gallery, garden |

That is **19 elements**. At setup the engine seals one from each dimension — the **hidden triple**, the ground truth — and deals the remaining **16** to the four detectives as private **exhibits**, exactly four each. An exhibit proves its element is *not* part of the truth.

> **Before you scroll:** why 6 + 5 + 8 rather than the classic 6 + 6 + 9? Commit to a guess.
>
> Because 19 − 3 = 16 divides evenly by four. The classic deal gives some players more cards than others — a real information advantage. With seats rotating between games ([ADR-0006](../../decisions/adr-0006-seat-rotation.md)), an uneven deal would add noise to exactly the comparison this repo exists to make.

## The archive

Alongside the deal, the engine generates the **archive**: witness statements, staff logs, and records about the night — plain text documents with stable ids, produced from templates, deterministic from the seed. The engine contains no LLM, same as LUDO's.

- **Reliable documents** are consistent with the hidden triple. Only *some* non-solution elements get an archive exoneration — the archive accelerates deduction but can never complete it alone; the table always can.
- **Red herrings** "rule out" elements that are actually part of the truth, using the *same templates* as reliable documents — indistinguishable by style, on purpose. A detective who believes one eliminates the real answer.
- **Solvability guarantee:** every red herring's witness is undermined by at least one reliable document — cross-checking the witness is how a careful detective catches the lie — and the dealt exhibits alone determine the hidden triple uniquely. A perfect reader of everything always solves the case; nobody sees everything.

Detectives access the archive only through the **archivist** (see [visibility](#who-sees-what)). The generator's design — document kinds, reliability model, contradiction placement — gets its own doc when the engine is designed, as LUDO's [engine-design](../ludo/engine-design.md) did.

## Setup

Four detectives. Seats are assigned to models per [`shared/models.yaml`](../../../shared/models.yaml); the seat → detective mapping rotates between games. Each detective receives its four exhibits and the case briefing prompt. Turn order is fixed at setup, clockwise.

## Turn sequence

On its turn, a detective:

1. **Investigates** — up to **2 archive queries** through the archivist. Query content is private; that a query happened is public. In the engine this is a metered handle available throughout the turn's deliberation, because that is how an LLM agent actually uses a tool — mid-thought, not in a separate phase.
2. **Suggests** — names one element from each dimension: *"the magician, with a duplicate key, in the vault room."* A suggestion may include elements the suggester secretly holds — that is legal bluffing. Each suggestion may carry one public **table note** (spin, misdirection, or truth).
3. **Refutation** — clockwise from the suggester's left, the first detective holding at least one named element must show **exactly one** of them, of its choosing, to the suggester alone. The engine mediates the showing: it is a fact, not a claim. If nobody holds any named element, the engine announces publicly that no one could refute — the loudest information in the game.
4. **Accuses** *(optional)* — names a triple as the final answer. The engine checks it against the sealed truth. Correct: the game ends, the detective wins. Wrong: the detective is **eliminated** — it takes no further turns and makes no suggestions, but still refutes and still holds its exhibits.
5. **Reflects** — writes to its notebook (agent memory) and declares its current **belief**: a best-guess triple with a confidence per dimension. Recorded as an event; scored by the eval against ground truth.

Play passes clockwise. A skipped phase (no queries, no suggestion) is legal and recorded.

## Who sees what

The information rules are the game, so they are stated as a table — the harness contract will bind all three stacks to them, as LUDO's does.

| Information | Suggester | Refuter | Other detectives | Spectators / transcript |
|---|---|---|---|---|
| Suggestion (the triple) | — | sees it | see it | see it |
| Which exhibit was shown | sees it | — | see only *that* a refutation happened, and by whom | see it |
| "No one could refute" | hears it | — | hear it | see it |
| Archive query content and answer | own only | — | see only that a query happened | see it |
| Table notes | sees | sees | see | see |
| Exhibits dealt to each detective | own only | own only | own only | see all |
| The hidden triple | — | — | — | revealed at game end |
| Another detective's reasoning or notebook | never | never | never | see all |

Spectators see everything — the transcript is the full story, as in LUDO. No detective ever sees another's reasoning; deception would be meaningless otherwise.

## End conditions

The game ends when:

- a detective **accuses correctly** — it wins;
- **all four are eliminated** by wrong accusations — nobody wins, and the eval scores the wreckage;
- the **turn cap** is reached — 24 turns on the `dev` profile, 48 on `headline` (see [the numbers](#the-numbers)). Hitting the cap is an expected outcome, not a failure: the eval scores final beliefs against the truth, so a detective can lose the race yet demonstrably have solved the case.

## Variants not adopted

| Variant | Why not |
|---|---|
| Board movement to reach rooms (classic) | Filler between deductions; costs turns and tokens and teaches nothing about agents |
| Murder theme (classic) | A theft carries the same mechanics with less grim generated fiction; the deception under study is unaffected |
| Open refutation (exhibit shown to the whole table) | Collapses the information asymmetry that makes the game strategic |
| Uneven deal (classic 21-card deck) | Unequal information by seat — noise in the comparison; see the deal note above |
| Free-form negotiation phases (LUDO-style) | Rejected for v1 — answered [question 22](../../open-questions.md#-22-does-alibi-keep-ludos-negotiation-channels): negotiation was LUDO's biggest token cost, and ALIBI's deception lives in suggestions, table notes, and the archive |
| Detectives sharing or trading exhibits | Breaks the deal's information geometry and the solvability analysis; revisit only with a rules bump |

## The numbers

Measured over **500 elimination-bot games** (`alibi_engine.cli bench --games 500`) — strict-logic play, no archive reading, no bluffing, so a fair floor for competent play:

| | turns to a correct accusation |
|---|---|
| min | 1 |
| median | 21 |
| p90 | 36 |
| p99 | 45 |
| max | 45 |

**All 500 solved.** The deduction always converges: every refutation eliminates at least one new element for the suggester, and an unrefuted suggestion by a detective holding none of the named three *is* the solution.

The caps derive from that distribution, and live in [`shared/models.yaml`](../../../shared/models.yaml) — config, never prose:

| Number | Value | Basis |
|---|---|---|
| Turn cap (`dev`) | 24 | just above the median — cheap runs mostly end mid-game, which is what belief scoring is for |
| Turn cap (`headline`) | 48 | above the benched p99 — a full game that fails to solve is the detectives' fault, not the cap's |
| Turn cap (conformance vectors) | 60 | every vector must end `solved` so the digest covers the accusation path |
| Archive queries per turn | 2 | 2 × k=3 documents ≈ a third of the 20-document archive per turn — useful, not exhaustive |
| Archive size | 20 documents | 8 exonerations + 3 red herrings + 3 counters + 6 gossip (15% herrings) — the archive alone can never solve; the table always can |
| Table note length cap | per profile, as LUDO's `max_message_chars` | enforced by the harness, not the engine |

## Related

- [Brief](brief.md) — what this project demonstrates and why
- [Engine design](engine-design.md) — how the built engine implements this spec
- [Harness contract](harness-contract.md) — how the stacks bind to it
- [ADR-0010](../../decisions/adr-0010-project-two-alibi.md) — the decision record, including the naming question
- [LUDO game rules](../ludo/game-rules.md) — the sibling spec this one's shape follows
- [Open questions](../../open-questions.md) — 21 (pace) and 23 (retrieval parity) still open; 20 (name) and 22 (channels) answered
