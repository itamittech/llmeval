# LUDO — Canonical Rule Specification

Ludo is a cross-and-circle race game descended from the Indian game *Pachisi*, played across the subcontinent and worldwide. It has **many regional variants**. Agents need one deterministic ruleset, so this document is normative: it is what `engine-python` and `engine-java` implement, and what the [conformance vectors](../../architecture/repository-layout.md) enforce.

Where a popular variant differs, it's listed under [Variants](#variants-not-adopted) with a note on whether it's worth enabling later.

## Board

The board is a cross of four arms. Each arm is three columns of eight squares.

- **Main circuit** — 52 squares, traversed **clockwise** by all players.
- **Base (yard)** — each colour has an off-track area holding its four tokens at game start.
- **Start square** — each colour's entry point onto the circuit. The four start squares are **13 squares apart**.
- **Home column** — five coloured squares forming the middle column of each arm. Only the matching colour may enter; nobody can be captured there.
- **Home triangle** — the centre of the board, reached from the end of the home column.

A token's journey from its start square is **56 steps**: 50 to reach the last circuit square, then 6 more (five home column squares, then the home triangle). Counting the start square itself, it occupies **57 distinct positions** — which is why full progress for one token scores 57, and 228 for all four.

Note it traverses only **51 of the circuit's 52 squares**, turning into its home column one square short of a complete loop.

```
Positions, per token, in engine terms:
  BASE                    not on the board
  0                       start square
  0 … 50                  main circuit (relative to this colour's start)
  51 … 55                 home column (5 squares)
  56                      home triangle — token is HOME
```

Using **colour-relative** positions rather than absolute board coordinates keeps the movement logic identical for all four players; the engine converts to absolute squares only for capture checks and rendering.

## Setup

Four players — **red, green, yellow, blue** — each with four tokens in their base.

## Turn sequence

1. Roll one six-sided die.
2. Compute the legal moves for that value.
3. If there are none, the turn ends.
4. Otherwise choose one legal move and apply it.
5. Resolve capture, if any.
6. If an extra roll was earned, go to 1. Otherwise play passes clockwise.

## Movement

**Leaving base.** A token leaves the base only on a roll of **6**, moving to its start square. Start squares are [safe](#safe-squares), so an opponent already sitting there is **not** captured — both tokens coexist.

**On the circuit.** A token advances exactly the number rolled.

**Entering home.** A token must reach the home triangle (position 56) by **exact count**. A roll that would overshoot is not a legal move for that token. With no other legal move available, the turn is forfeited.

## Extra rolls

A player rolls again after:

- rolling a **6**, or
- **capturing** an opponent's token.

**Three consecutive sixes forfeit the turn.** All three rolls are cancelled — including any movement made on the first two — and play passes on. This prevents an agent from chaining sixes indefinitely and is the standard tournament rule.

> An extra roll is not compulsory movement: if the extra roll produces no legal move, the turn simply ends.

## Capture

Landing on a square occupied by a **single opponent token** sends that token back to its base. It must roll a 6 to re-enter and starts its 57-step journey again.

Capture is impossible on:

- a **safe square**,
- any **home column**, or
- a square holding **two or more tokens of the same colour** (a stack protects itself).

## Safe squares

Eight squares are safe, marked on the board with a star:

- the **four start squares**, and
- **four star squares**, one per quadrant.

Multiple tokens of any colours may share a safe square without capture.

## Blocks

Two or more tokens of the same colour on one square form a **block**. Opponents may neither land on it nor pass through it. A move that would pass a block is not legal.

Blocks make the game meaningfully strategic — and, importantly for this project, they give agents something to negotiate about. An ally holding a block at a chokepoint is doing real work for you.

## Winning

The first player to get **all four tokens** to the home triangle wins.

Play continues after that to establish second, third, and fourth place — relevant here because the [evaluation](evaluation.md) rewards final standing, not just first place.

## The turn cap — important for this project

Real Ludo games can run long, and LLM turns are slow and expensive. Games here run under a **configurable maximum turn count**. Reaching it is a normal outcome, not a failure: the match ends and is scored on **mid-game position**. See [evaluation](evaluation.md).

## Edge cases

Popular rule descriptions leave these ambiguous. An engine can't be ambiguous, so they are resolved here — and any of them is a legitimate thing to revisit.

| Case | Ruling |
|---|---|
| Entering from base onto an occupied start square | No capture. Start squares are safe. |
| A block sitting on a safe square | Still a block. Opponents may neither land nor pass. |
| Passing your **own** block | Allowed. Blocks only obstruct opponents. |
| Two colours sharing a non-safe square | Cannot arise — landing there captures, so a non-safe square only ever holds one colour. |
| Extra roll with no legal move | Turn simply ends. The extra roll is an opportunity, not an obligation. |
| Capture during a turn later cancelled by three sixes | Reverted with everything else. Cancellation restores the state as at turn start. |
| Overshooting home with no other legal move | Turn is forfeited. Nothing is moved. |

## Determinism

- The die is engine-controlled, seeded from a value recorded in the event stream. Agents never generate their own rolls.
- The same seed and the same agent decisions replay a match exactly.
- Agents cannot roll on demand, re-roll, or observe future rolls.

## Variants not adopted

| Variant | Rule | Why not |
|---|---|---|
| Capture-to-enter-home | A player must capture at least one token before any token may enter home | Adds a long tail of stalled games; poor fit with a turn cap |
| No three-six penalty | Three sixes just ends the turn without cancelling movement | Milder, but the standard rule creates a real risk/reward decision — good for agents |
| No blocks | Same-colour stacks are safe but passable | Removes the most interesting strategic and negotiating lever |
| Six to start disabled | Tokens enter on any roll | Faster games, much less tension |
| 2–3 players | Fewer colours | The project needs exactly four agents |

Any of these can be a config flag later. Rule variation is itself an interesting eval axis — do agents adapt when the rules change? — but the baseline is fixed above.

## Sources

Rules cross-checked against:
- [Official Game Rules — Ludo](https://officialgamerules.org/game-rules/ludo-rules/)
- [Masters of Games — Ludo rules and instructions](https://www.mastersofgames.com/rules/ludo-rules-instructions-guide.htm)
- [Zupee — Ludo rules](https://www.zupee.com/ludo/ludo-rules/)
- [Blackbird — Ludo game rules for Indian players](https://blackbirdgame.com/ludo-game-rules/)
- [Party Ludo — complete rulebook](https://www.partyludo.com/ludo-rules)
