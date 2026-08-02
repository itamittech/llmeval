## The board

Each player has their own numbered path. Position `0` is your start square, `50` is the last shared square, `51`–`55` are your private home column, and `56` is home. A token waiting in your base sits at `-1`.

Numbering is **relative to you**. Your `12` and another player's `12` are different physical squares. Only positions `0`–`50` are on the shared circuit where players can collide; your home column belongs to you alone and cannot be entered or attacked by anyone else.

## What happens when you move

**Leaving base** costs a 6. Until then a token stays at `-1` and cannot be touched.

**Landing on a lone opponent** on the shared circuit sends that token back to its base — it loses all its progress — and earns you another roll. This is the fastest way to hurt someone and the main reason to keep talking to people.

**Safe squares** cannot be used to capture. A token standing on one is untouchable, and landing on an occupied safe square is allowed rather than a capture. They are spaced evenly around the circuit, so there is always one within reach.

**Rolling a 6** earns another roll — but three sixes in a row cancels the entire turn. Everything you did during it is undone, captures included. A long chain of sixes is a gamble, not a gift.

**Reaching home needs an exact roll.** Overshooting `56` is not a legal move, so a token close to home may have nothing to do for several turns.

## The numbers

These are checked against the engine, so they are not approximate.

| | |
|---|---|
| tokens per player | 4 |
| base position | -1 |
| start square | 0 |
| last shared square | 50 |
| first home-column square | 51 |
| home | 56 |
| safe squares on the circuit | 8 |
| consecutive sixes that cancel a turn | 3 |
| attempts to name a legal move before forfeiting | 2 |
