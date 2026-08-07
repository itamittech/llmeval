"""The portable RNG — determinism is the whole contract."""

from alibi_engine.rng import Rng


def test_same_seed_same_sequence():
    a = [Rng(7).below(19) for _ in range(1)]
    r1, r2 = Rng(7), Rng(7)
    assert [r1.below(19) for _ in range(50)] == [r2.below(19) for _ in range(50)]
    assert a[0] == Rng(7).below(19)


def test_different_seeds_differ():
    r1, r2 = Rng(1), Rng(2)
    assert [r1.below(100) for _ in range(20)] != [r2.below(100) for _ in range(20)]


def test_below_stays_in_range():
    r = Rng(3)
    for n in (1, 2, 6, 19, 100):
        for _ in range(200):
            assert 0 <= r.below(n) < n


def test_shuffle_is_a_permutation_and_deterministic():
    items = list(range(16))
    a, b = list(items), list(items)
    Rng(11).shuffle(a)
    Rng(11).shuffle(b)
    assert a == b
    assert sorted(a) == items
    assert a != items  # astronomically unlikely to be identity


def test_sample_unique_and_deterministic():
    pool = [f"e{i}" for i in range(16)]
    s1 = Rng(5).sample(pool, 8)
    s2 = Rng(5).sample(pool, 8)
    assert s1 == s2
    assert len(s1) == 8 == len(set(s1))


def test_weak_seeds_are_scrambled():
    # Seeds 0 and 1 must not produce near-identical streams.
    assert [Rng(0).below(6) for _ in range(10)] != [Rng(1).below(6) for _ in range(10)]
