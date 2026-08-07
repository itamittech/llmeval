"""Portable seeded randomness.

Byte-for-byte the same algorithm as LUDO's dice and ALIBI's deal (splitmix64
seeding + xorshift64*). Repeated here rather than shared because `shared/` holds
contracts and data only — never executable code — and because the Java engine
must reproduce every draw exactly or the conformance vectors of ADR-0002 are
worthless.

    state  = splitmix64(seed)          # scrambles weak seeds like 0, 1, 2
    x     ^= x >> 12                   # xorshift64*
    x     ^= x << 25
    x     ^= x >> 27
    value  = x * 0x2545F4914F6CDD1D
    pick   = (value >> 33) % n

All arithmetic is unsigned 64-bit, discarding overflow.

The shuffle is Fisher-Yates driven by `below`, iterating from the last index
down to 1 and drawing `below(i + 1)` each step. That iteration order is part of
the spec: a Java port that loops upward consumes the same draws and produces a
different track. `sample` shuffles a copy of the WHOLE pool and takes the first
k — so it consumes len(pool) - 1 draws, not k. Also spec.
"""

from __future__ import annotations

MASK64 = 0xFFFFFFFFFFFFFFFF
MULTIPLIER = 0x2545F4914F6CDD1D


def splitmix64(seed: int) -> int:
    z = (seed + 0x9E3779B97F4A7C15) & MASK64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return (z ^ (z >> 31)) & MASK64


class Rng:
    """A seeded source of small uniform picks."""

    def __init__(self, seed: int) -> None:
        self.seed = seed
        state = splitmix64(seed)
        # xorshift64* cannot recover from an all-zero state.
        self._state = state or 0x9E3779B97F4A7C15

    def below(self, n: int) -> int:
        """Uniform integer in [0, n)."""
        if n <= 0:
            raise ValueError("n must be positive")
        x = self._state
        x ^= x >> 12
        x = (x ^ (x << 25)) & MASK64
        x ^= x >> 27
        self._state = x
        return (((x * MULTIPLIER) & MASK64) >> 33) % n

    def between(self, low: int, high: int) -> int:
        """Uniform integer in [low, high]."""
        return low + self.below(high - low + 1)

    def shuffle(self, items: list) -> None:
        """In-place Fisher-Yates, high index down — iteration order is spec."""
        for i in range(len(items) - 1, 0, -1):
            j = self.below(i + 1)
            items[i], items[j] = items[j], items[i]

    def sample(self, items: list, k: int) -> list:
        """First k of a shuffled copy. Order of the result is the shuffle's."""
        pool = list(items)
        self.shuffle(pool)
        return pool[:k]
