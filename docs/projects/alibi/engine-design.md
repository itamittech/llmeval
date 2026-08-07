# ALIBI Engine Design

How the built engine is structured, and what the Java port must preserve. Read the [rules](game-rules.md) first — this doc is about *how*, that one is *what*.

## The shape, against LUDO's

Same skeleton on purpose — a reader who walked LUDO's engine should recognise every room:

| LUDO | ALIBI | What changed |
|---|---|---|
| `dice.py` — one seeded die | [`rng.py`](../../../projects/alibi/engine-python/src/alibi_engine/rng.py) — same algorithm, widened to `below(n)` + a specified Fisher–Yates shuffle | A deal needs picks and shuffles, not rolls. Draw order is spec: a Java loop that shuffles upward would consume the same draws and produce a different case |
| `board.py` + `state.py` | [`case.py`](../../../projects/alibi/engine-python/src/alibi_engine/case.py) | The board is gone; the *deal* is the state that matters. 19 elements, 3 sealed, 16 dealt — evenly, which the classic game doesn't do |
| — (no counterpart) | [`archive.py`](../../../projects/alibi/engine-python/src/alibi_engine/archive.py) | The genuinely new organ — see below |
| `deciders.py` — one shared `StateView` | [`deciders.py`](../../../projects/alibi/engine-python/src/alibi_engine/deciders.py) — a **per-detective** `DetectiveView` | LUDO's board is public; ALIBI's state is mostly private. Privacy is by construction: another detective's hand isn't guarded by a check, it simply isn't in the object |
| `game.py` — roll loop | [`game.py`](../../../projects/alibi/engine-python/src/alibi_engine/game.py) — suggest → refute → accuse → conclude | The engine *mediates* refutation: it finds the refuter, validates the shown exhibit, records it. The table stays facts |
| `events.py` / `conformance.py` / `cli.py` | same names, same jobs | The conformance digest now covers **corpus bytes**, because the archive rides in the transcript |

## The archive, mechanically

Generated from templates by the shared RNG — the engine rule (**no LLM, no network**) holds even though the output is prose. The truth model is three lists and a guarantee:

- **8 exonerations** — truthfully rule out 8 of the 16 non-solution elements (which 8 is an RNG draw). Deliberately *not* all 16: the archive accelerates deduction but can never finish it, so table play stays load-bearing.
- **3 red herrings** — the *same templates*, aimed at the three solution elements, attributed to three witnesses the RNG picked as liars. Style never leaks truth; only cross-checking does.
- **3 counters** — each liar is undermined by one truthful staff log. This is the solvability guarantee from the rules, implemented as data.
- **6 gossip** — assertion-free noise, so retrieval has something to rank against.

One final shuffle, then ids `doc-001`…`doc-020`. Which documents lied is engine-private until `game_ended.red_herrings`.

**The baseline retriever is integer-only:** score = overlap of unique query tokens with document tokens; ties break to shorter documents, then id order. No floats, no library — because the retriever is on the conformance path and two languages must rank identically. Embedding retrieval never enters the engine; it's a live-tier harness concern ([question 23](../../open-questions.md)).

## The decider seam

```
suggest(TurnContext)  -> Suggestion | None     may search mid-thought
show(ShowContext)     -> element id            compelled; invalid falls back to engine choice
accuse(TurnContext)   -> Triple | None         sees this turn's refutation first
conclude(TurnContext) -> Belief                required — the eval's raw material
reflect(TurnEnd)                               optional, like LUDO's
```

Two deliberate departures from LUDO's seam:

1. **The archive handle lives inside the context.** An LLM agent uses a tool mid-deliberation, not in a separate phase — so the engine meters searches wherever the detective thinks, and the stacks wire the same handle to the archivist tool.
2. **`show` cannot be forfeited.** A LUDO agent that fails twice loses its move — a real outcome. Refutation is compulsory under the rules, so an invalid `show` falls back to the canonical first option, *visibly*: `refutation_made.chosen_by: "engine"`.

`conclude` is required rather than optional because belief calibration is the eval's primary deterministic score; a detective that declares nothing scores zero, and the engine records that silence honestly.

## Floats on the conformance path

`belief_declared.confidence` is the one floating-point field engine bots emit. Computed division (`1/3`) would put float-formatting parity between Python and Java on the critical path — so bot confidences come from a **literal table** (`1: 1.0, 2: 0.5, 3: 0.3333, …`) and both engines carry the same constants. LLM detectives may declare any value in [0, 1]; their events are outside the conformance digest anyway.

## What the Java port must preserve

- The RNG algorithm **and draw order**: deal (solution picks, one shuffle), then archive (sample shuffle, witness shuffle, spot picks in build order, gossip picks, final shuffle). One consumed draw out of order shifts every case.
- Template output **byte for byte** — punctuation included. The conformance digest covers `archive_generated`, which is the point: a comma is a rules violation.
- Canonical JSON: sorted keys, no spaces, same float literals.
- The standings sort key, including its canonical-colour tiebreak.
- `elimination-bot` behaviour exactly — it is the conformance decider.

Same lesson as LUDO's port: Java test seams are designed in advance, not monkey-patched later. The bench (`cli bench`) answered [question 21](../../open-questions.md#-21-alibis-pace--case-dimensions-query-allowance-turn-cap); the vectors run at cap 60 so every one ends `solved`.

## Related

- [Game rules](game-rules.md) — the normative spec this implements
- [Brief](brief.md) · [ADR-0010](../../decisions/adr-0010-project-two-alibi.md)
- [LUDO engine design](../ludo/engine-design.md) — the sibling this deliberately rhymes with
- [Schemas README](../../../shared/schemas/README.md) — the event contract
