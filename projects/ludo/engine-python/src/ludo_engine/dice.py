"""Portable seeded dice.

Deliberately *not* Python's `random`. The Java engine must produce an identical
dice sequence from the same seed or the conformance vectors of ADR-0002 are
worthless, and no two languages' standard RNGs agree.

So the algorithm is specified here rather than borrowed:

    state  = splitmix64(seed)          # scrambles weak seeds like 0, 1, 2
    x     ^= x >> 12                   # xorshift64*
    x     ^= x << 25
    x     ^= x >> 27
    value  = x * 0x2545F4914F6CDD1D
    die    = (value >> 33) % 6 + 1

All arithmetic is unsigned 64-bit, discarding overflow. A Java port is a direct
transcription using `long` with `>>>` for the right shifts — signedness does not
affect the result because every operation is bitwise or wrapping multiplication.

Using the top 31 bits leaves a modulo-6 bias below 1e-8, which is irrelevant to
gameplay and a fair trade for exact cross-language reproducibility.
"""

from __future__ import annotations

MASK64 = 0xFFFFFFFFFFFFFFFF
MULTIPLIER = 0x2545F4914F6CDD1D


def splitmix64(seed: int) -> int:
    z = (seed + 0x9E3779B97F4A7C15) & MASK64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return (z ^ (z >> 31)) & MASK64


class Dice:
    """A seeded six-sided die."""

    def __init__(self, seed: int) -> None:
        self.seed = seed
        state = splitmix64(seed)
        # xorshift64* cannot recover from an all-zero state.
        self._state = state or 0x9E3779B97F4A7C15
        self.rolls = 0

    def roll(self) -> int:
        x = self._state
        x ^= x >> 12
        x = (x ^ (x << 25)) & MASK64
        x ^= x >> 27
        self._state = x
        self.rolls += 1
        return (((x * MULTIPLIER) & MASK64) >> 33) % 6 + 1
