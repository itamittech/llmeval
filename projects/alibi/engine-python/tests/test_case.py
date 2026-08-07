"""The deal: 19 elements, 3 sealed, 16 dealt evenly."""

from alibi_engine.case import (
    ALL_ELEMENTS, COLORS, DIMENSIONS, ELEMENTS, deal, dimension_of,
)
from alibi_engine.rng import Rng


def test_deal_shape():
    case = deal(Rng(1))
    assert set(case.solution) == set(DIMENSIONS)
    for dim in DIMENSIONS:
        assert case.solution[dim] in ELEMENTS[dim]
    hands = list(case.hands.values())
    assert len(hands) == 4
    assert all(len(h) == 4 for h in hands)


def test_deal_partitions_the_non_solution_elements():
    case = deal(Rng(9))
    dealt = [e for hand in case.hands.values() for e in hand]
    assert len(dealt) == 16 == len(set(dealt))
    assert set(dealt) | set(case.solution.values()) == set(ALL_ELEMENTS)
    assert not set(dealt) & set(case.solution.values())


def test_deal_is_deterministic_and_seed_sensitive():
    assert deal(Rng(4)) == deal(Rng(4))
    assert any(deal(Rng(a)).solution != deal(Rng(b)).solution
               for a, b in [(1, 2), (2, 3), (3, 4)])


def test_hands_are_canonically_sorted():
    case = deal(Rng(2))
    order = {e: i for i, e in enumerate(ALL_ELEMENTS)}
    for hand in case.hands.values():
        assert list(hand) == sorted(hand, key=order.__getitem__)


def test_holder_of():
    case = deal(Rng(3))
    for color in COLORS:
        for element in case.hands[color]:
            assert case.holder_of(element) == color
    for element in case.solution.values():
        assert case.holder_of(element) is None


def test_dimension_of():
    assert dimension_of("curator") == "who"
    assert dimension_of("blackout") == "how"
    assert dimension_of("garden") == "where"
