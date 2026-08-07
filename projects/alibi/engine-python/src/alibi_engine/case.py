"""The case: elements, cast, and the deal.

Element ids are the normative vocabulary — they appear in events, prompts, and
corpus text, and the shared schema enumerates them. Renaming one regenerates
the conformance vectors (answered question 20). Display names exist so the
archive reads as fiction rather than as ids.

19 elements, 3 sealed, 16 dealt: exactly four exhibits per detective. The even
deal is deliberate — see game-rules.md for why the classic uneven deal was
rejected.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .rng import Rng

Color = Literal["red", "green", "yellow", "blue"]
COLORS: tuple[Color, ...] = ("red", "green", "yellow", "blue")

Dimension = Literal["who", "how", "where"]
DIMENSIONS: tuple[Dimension, ...] = ("who", "how", "where")

WHO: tuple[str, ...] = (
    "curator", "magician", "heiress", "chef", "photographer", "inspector",
)
HOW: tuple[str, ...] = (
    "sleight-of-hand", "duplicate-key", "service-hatch", "blackout", "forged-pass",
)
WHERE: tuple[str, ...] = (
    "ballroom", "vault-room", "kitchen", "terrace", "library", "cloakroom",
    "gallery", "garden",
)

ELEMENTS: dict[Dimension, tuple[str, ...]] = {"who": WHO, "how": HOW, "where": WHERE}

#: Canonical order over all 19 elements: who, then how, then where.
ALL_ELEMENTS: tuple[str, ...] = WHO + HOW + WHERE

#: How the fiction names each element. Original cast — see ADR-0010.
DISPLAY: dict[str, str] = {
    "curator": "Curator Meera Joshi",
    "magician": "the magician Vikram Rao",
    "heiress": "the heiress Tara Kapoor",
    "chef": "Chef Antoine D'Souza",
    "photographer": "the photographer Zoya Khan",
    "inspector": "retired Inspector Balbir Singh",
    "sleight-of-hand": "sleight of hand",
    "duplicate-key": "a duplicate key",
    "service-hatch": "the service hatch",
    "blackout": "a staged blackout",
    "forged-pass": "a forged pass",
    "ballroom": "the ballroom",
    "vault-room": "the vault room",
    "kitchen": "the kitchen",
    "terrace": "the terrace",
    "library": "the library",
    "cloakroom": "the cloakroom",
    "gallery": "the gallery",
    "garden": "the garden",
}


def dimension_of(element: str) -> Dimension:
    for dim in DIMENSIONS:
        if element in ELEMENTS[dim]:
            return dim
    raise ValueError(f"unknown element: {element!r}")


@dataclass(frozen=True)
class Case:
    """One game's sealed truth and dealt hands."""

    solution: dict[Dimension, str]
    hands: dict[Color, tuple[str, ...]]

    def holder_of(self, element: str) -> Color | None:
        for color, hand in self.hands.items():
            if element in hand:
                return color
        return None


def deal(rng: Rng) -> Case:
    """Seal one element per dimension, shuffle the rest, deal four each.

    Draw order is spec: solution picks in who/how/where order, then one
    shuffle of the 16 remaining elements in canonical order, dealt
    round-robin red, green, yellow, blue. Hands are then sorted back to
    canonical order — presentation only, the information is identical.
    """
    solution: dict[Dimension, str] = {
        dim: ELEMENTS[dim][rng.below(len(ELEMENTS[dim]))] for dim in DIMENSIONS
    }

    remaining = [e for e in ALL_ELEMENTS if e not in solution.values()]
    rng.shuffle(remaining)

    dealt: dict[Color, list[str]] = {c: [] for c in COLORS}
    for i, element in enumerate(remaining):
        dealt[COLORS[i % len(COLORS)]].append(element)

    order = {e: i for i, e in enumerate(ALL_ELEMENTS)}
    hands = {c: tuple(sorted(h, key=order.__getitem__)) for c, h in dealt.items()}
    return Case(solution=solution, hands=hands)
