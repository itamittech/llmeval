from collections import Counter

from ludo_engine.dice import Dice


def rolls(seed: int, n: int) -> list[int]:
    """One die, rolled n times. Constructing a Dice per roll would only ever
    return the first value of each sequence."""
    die = Dice(seed)
    return [die.roll() for _ in range(n)]


def test_same_seed_replays_exactly():
    assert rolls(42, 200) == rolls(42, 200)


def test_different_seeds_diverge():
    assert rolls(1, 50) != rolls(2, 50)


def test_only_produces_faces_one_through_six():
    assert set(rolls(7, 5_000)) == {1, 2, 3, 4, 5, 6}


def test_weak_seeds_are_scrambled_not_degenerate():
    """splitmix64 seeding is what stops seed 0 producing a stuck state."""
    for seed in (0, 1, 2):
        assert len(set(rolls(seed, 60))) > 1, f"seed {seed} produced a constant sequence"


def test_distribution_is_close_to_uniform():
    counts = Counter(rolls(99, 60_000))
    assert set(counts) == {1, 2, 3, 4, 5, 6}
    for face, n in counts.items():
        assert 9_000 < n < 11_000, f"face {face} appeared {n} times"


def test_roll_count_is_tracked():
    die = Dice(3)
    for _ in range(10):
        die.roll()
    assert die.rolls == 10
