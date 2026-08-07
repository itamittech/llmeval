"""The portable RNG. Every value here is a contract with the Java engine."""

from relay_engine.rng import Rng, splitmix64


def test_same_seed_same_stream():
    assert [Rng(7).below(100) for _ in range(5)] == [Rng(7).below(100) for _ in range(5)]


def test_weak_seeds_are_scrambled():
    """Straight xorshift on seed 0 or 1 produces visibly patterned first draws;
    splitmix64 seeding is what stops that."""
    firsts = [Rng(s).below(1000) for s in (0, 1, 2, 3)]
    assert len(set(firsts)) == 4


def test_below_stays_in_range():
    rng = Rng(11)
    assert all(0 <= rng.below(6) < 6 for _ in range(500))


def test_between_is_inclusive_both_ends():
    rng = Rng(5)
    seen = {rng.between(2, 4) for _ in range(300)}
    assert seen == {2, 3, 4}


def test_shuffle_is_deterministic_and_a_permutation():
    a, b = list(range(10)), list(range(10))
    Rng(3).shuffle(a)
    Rng(3).shuffle(b)
    assert a == b
    assert sorted(a) == list(range(10))
    assert a != list(range(10))


def test_sample_consumes_the_whole_pool_shuffle():
    """Spec, not an accident: `sample` shuffles a copy of the entire pool and
    takes the first k, so it draws len(pool) - 1 times. A Java port that draws
    k times produces a different track from the same seed."""
    pool = list(range(8))
    one = Rng(4)
    picked = one.sample(pool, 3)

    other = Rng(4)
    shuffled = list(pool)
    other.shuffle(shuffled)
    assert picked == shuffled[:3]
    assert one.below(100) == other.below(100)


def test_splitmix64_is_64_bit():
    assert 0 <= splitmix64(12345) <= 0xFFFFFFFFFFFFFFFF
