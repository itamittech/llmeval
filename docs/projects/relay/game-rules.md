# RELAY — Canonical Rule Specification

The normative rules. Both engines implement exactly this; the prompts describe exactly this; a disagreement between this file and the code is a bug in the code.

Numbers marked **provisional** are guesses until [question 25](../../open-questions.md) benches them. Everything else is settled.

---

## The race

Four **runners** race along one **track** of numbered **stages**. A stage is a self-contained puzzle with a single checkable answer, generated deterministically from the game's seed.

Each runner has its own position on the track and its own clock. There is no board interaction: you cannot block, capture, or overtake anyone. **The only thing you share is the quota.**

## The two currencies

| | Whose | Spent on | Runs out? |
|---|---|---|---|
| **Ticks** | yours alone | every action | no — it is your clock, and low is good |
| **Quota** | the table's, one pool | escalating only | yes, and then nobody may escalate |

Ticks are the race clock: deterministic costs charged by the engine, standing in for wall-clock latency so that the same seed replays exactly. Real latency is *measured* beside them and never decides anything ([engine design](engine-design.md#why-ticks-and-not-milliseconds)).

Quota is a **commons**. One pool serves all four runners, its level is public, and spending it denies it to everyone else for the rest of the game.

## The stage

Every stage carries three things. The runner sees one of them.

| | Visible to the runner? | Why |
|---|---|---|
| **Prompt** — the puzzle text | **yes** | it is the puzzle |
| **Answer** — the checkable solution | no, until `game_ended` | it is the answer |
| **Tier** — 1, 2, or 3 | **no, ever, to anyone in play** | deciding difficulty *is* the move |

Tiers are drawn from a fixed multiset and **shuffled**, so position on the track tells a runner nothing about what it is facing. A runner that could see the tier would be playing a different, trivial game: escalate on 3, answer otherwise.

Tier is revealed in `game_ended` alongside the answers, which is what lets the eval score escalation decisions against the truth without a judge ([evaluation](evaluation.md)).

### Stage families

Three families, each with a difficulty ladder. All text is ASCII and all arithmetic is integer, because the Python and Java generators must produce **byte-identical prompts** or the conformance vectors fail.

| Family | The puzzle | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|---|
| `chain` | apply a sequence of integer operations to a start value | 2 steps | 4 steps | 6 steps, including a multiply |
| `cipher` | decode a Caesar-shifted word | shift given, short word | shift given, long word | **shift withheld**, inferred from a crib |
| `order` | put items in order from pairwise constraints, then name one position | 3 items | 4 items | 5 items, one constraint negative |

The answer is always a short token — an integer or a single lowercase word — compared after trimming and lowercasing. Nothing here needs a judge, a tolerance, or a regex.

## Turn sequence

Turns rotate in fixed colour order: red, green, yellow, blue. A runner that has finished the track takes no further turns.

On your turn you face the stage at your own position, and you do exactly one of three things:

1. **Answer** — submit an answer produced by your own model. Costs `TICK_ANSWER`.
2. **Escalate** — submit an answer produced by the **anchor**, the one shared frontier model. Costs `TICK_ESCALATE` **and one unit of quota**.
3. **Pass** — submit nothing. Costs `TICK_PASS`, and you stay where you are.

Then the engine adjudicates:

- **Correct** → you advance one stage.
- **Wrong** → you stay, and `TICK_WRONG` is added on top.
- **Passed** → you stay.

Escalating with an empty quota is an invalid action: the engine refuses it, records `invalid_action`, and asks again. A runner that keeps insisting is treated as having passed.

You may attach one public **note** to your turn — free text, everyone sees it, and it may be a lie. It is the only channel between runners, and nothing downstream treats it as fact.

## Who sees what

| | The runner | Other runners | The transcript |
|---|---|---|---|
| Its own stage prompt | yes | yes | yes |
| Any stage's tier or answer | **no** | **no** | only in `game_ended` |
| The quota level | yes | yes | yes |
| Who escalated, and when | yes | yes | yes |
| Another runner's notes | yes | yes | yes |
| Another runner's reasoning or memory | **no** | **no** | yes (spectator) |

The MUSTs a stack has to honour are in the [harness contract](harness-contract.md). The one that matters most: **a runner must never be told a tier or an unearned answer**, and the transcript's spectator view is not permission to feed it back into play.

## Escalation is performed, not reported

`escalated` is not a claim anybody makes. A runner asks the engine's desk; the **engine** charges the quota and consults the anchor. So the flag in the transcript is a receipt.

That closes both holes at once: a runner cannot secretly use the anchor, because it never holds one, and it cannot claim to have when it didn't, because the engine kept the count. The same structural honesty [ADR-0004](../../decisions/adr-0004-structural-guardrails.md) applies everywhere in this repo — lie all you like in a note, but you cannot forge a fact.

One consequence worth stating plainly: **you are charged for asking, not for using.** Ask the desk and the quota moves, whatever you do with the answer.

## End conditions

The race ends when any of these is true:

- **`finished`** — a runner clears the last stage. Others still get no further turns; the clock decides the rest of the podium.
- **`turn_cap`** — the turn budget is spent. A normal outcome, exactly as in LUDO: progress is scored, not just victory.
- **`all_stalled`** — every runner is out of quota **and** has failed its current stage more than `MAX_STALLS` times. Prevents a table of weak runners burning the whole cap on one stage they will never solve.

Standings rank by: stages cleared (more is better), then ticks (fewer is better), then colour order to settle a dead heat.

## Variants not adopted

- **Wall-clock racing.** Truer to the theme, and it makes every result unreproducible. Ticks decide; real latency is recorded beside them.
- **Per-runner quota.** Simpler to score, and it deletes the only adversarial pressure in the game — see [ADR-0011](../../decisions/adr-0011-project-three-relay.md).
- **Visible tiers.** Turns the central decision into a lookup.
- **The anchor as a consultable agent.** That is ALIBI's archivist. Here the anchor is a model swap, so that escalation cost is not confounded with sub-agent overhead.
- **Stealing quota / bidding for it.** A real game design, and a third hard thing. Out of scope for v1.

## The numbers

**Benched**, not chosen — the discipline [question 7](../../open-questions.md) set for LUDO and [question 21](../../open-questions.md) for ALIBI.

| Constant | Value | Why |
|---|---|---|
| stages on the track | 10 | a perfect runner finishes on turn 37; the floor is visible in every bench row |
| tier multiset | 4×1, 4×2, 2×3 | shuffled, so position leaks nothing |
| escalation quota (shared) | 8 | **sized by sweep.** Above ~12 the pool stops binding — quota 12 and quota 20 play identically. At 8 it binds, sharper runners win more, and the inversion below is still visible |
| max stalls per stage | 3 | ends a hopeless table instead of burning the cap on one stage |
| tick: answer | 2 | your own model is the fast one |
| tick: escalate | 5 | the anchor is slower, and that must cost something besides quota |
| tick: wrong | 4 | added on top of the action's own cost |
| tick: pass | 3 | cheaper than being wrong, dearer than being right |
| attempts per action before the engine decides for you | 2 | same as both earlier games |
| turn cap | 48 `dev` · 104 `headline` | see below |

### Pace

500 games per row, four equal runners, insight 66% (`relay_engine.cli bench --games 500 --skill …`):

| Runner skill | finished | min | median | p90 | p99 | max |
|---|---|---|---|---|---|---|
| weak (70/35/10 % by tier) | 94% | 37 | 59 | 79 | 101 | 114 |
| middle (90/60/25) | 100% | 37 | 43 | 52 | 63 | 76 |
| strong (98/85/55) | 100% | 37 | 38 | 41 | 45 | 47 |

`dev` sits at **48** — just above the middle profile's median, so cheap runs mostly end mid-race, which progress scoring covers. `headline` sits at **104**, above the *weakest* profile's p99, so an unfinished headline race is the runners' fault and not the cap's.

A generous cap is affordable here in a way it never was in LUDO, and the reason is the whole project: **runner calls are local and free, so the paid surface of a game is the quota — 8 anchor calls — however long the race runs.** Doubling the cap does not double the bill.

### Does the escalation decision actually matter?

[Question 25](../../open-questions.md) in one experiment. Four runners of equal skill and *unequal insight* — how often each correctly senses that a stage is beyond it — race each other, with the insight-to-lane assignment rotating per seed for the reason [ADR-0006](../../decisions/adr-0006-seat-rotation.md) rotates seats. 300 races per row, share of races won:

| Runner skill | insight 0% | 33% | 66% | 100% |
|---|---|---|---|---|
| weak | **27%** | 27% | 26% | 21% |
| middle | 17% | 24% | 29% | **30%** |
| strong | 17% | 22% | **32%** | 29% |

Chance is 25%. The mechanic discriminates — a middling runner that knows its own limits wins nearly twice as often as one that doesn't.

**And the weak row runs backwards, which is the finding.** For a runner that fails everywhere, spending the pool *precisely* on the two hardest stages is worse than spraying it: an indiscriminate escalation lands on a tier-1 stage it would also have failed, and the anchor rescues it anyway. Knowing what you can't do only pays once you can do most things. The right escalation threshold is a function of your own competence, not of the stage's difficulty — which is exactly the judgement RELAY exists to measure, and it is not the judgement anyone would have guessed.

## Related

- [Brief](brief.md) — what the project is for
- [Engine design](engine-design.md) — how the rules are implemented, and what a Java port must preserve
- [Harness contract](harness-contract.md) — what every stack must do
- [Evaluation](evaluation.md) — how a game is scored
- [ADR-0011](../../decisions/adr-0011-project-three-relay.md) — why this game
