"""The generators. Every assertion here is a byte the Java port must match."""

from relay_engine.deciders import _solve_chain, _solve_cipher
from relay_engine.rng import Rng
from relay_engine.track import (
    TIER_MULTISET, TRACK_STAGES, generate, normalise,
)


def test_same_seed_same_track():
    a = generate(Rng(7))
    b = generate(Rng(7))
    assert [s.prompt for s in a] == [s.prompt for s in b]
    assert [s.answer for s in a] == [s.answer for s in b]


def test_different_seeds_differ():
    assert generate(Rng(7))[0].prompt != generate(Rng(8))[0].prompt


def test_track_shape():
    track = generate(Rng(3))
    assert len(track) == TRACK_STAGES
    assert [s.id for s in track] == [f"stage-{i:02d}" for i in range(1, TRACK_STAGES + 1)]
    assert sorted(s.tier for s in track) == sorted(TIER_MULTISET)


def test_tiers_are_shuffled_not_ramped():
    """If tier tracked position, a runner could read difficulty off the board
    and the game's only decision would evaporate."""
    seen = {tuple(s.tier for s in generate(Rng(seed))) for seed in range(1, 40)}
    assert len(seen) > 20, "tier order barely varies — position would leak difficulty"


def test_prompt_never_mentions_the_tier():
    for seed in range(1, 30):
        for stage in generate(Rng(seed)):
            lowered = stage.prompt.lower()
            assert "tier" not in lowered
            assert "difficult" not in lowered and "easy" not in lowered


def test_chain_answers_are_arithmetic():
    for seed in range(1, 40):
        for stage in generate(Rng(seed)):
            if stage.family == "chain":
                assert _solve_chain(stage.prompt) == stage.answer


def test_cipher_answers_decode():
    """Only the stages that state their shift; tier 3 withholds it on purpose."""
    checked = 0
    for seed in range(1, 40):
        for stage in generate(Rng(seed)):
            if stage.family == "cipher" and stage.tier < 3:
                assert _solve_cipher(stage.prompt) == stage.answer
                checked += 1
    assert checked > 10


def test_tier_three_cipher_withholds_the_shift():
    found = 0
    for seed in range(1, 60):
        for stage in generate(Rng(seed)):
            if stage.family == "cipher" and stage.tier == 3:
                assert "unknown number of places" in stage.prompt
                assert _solve_cipher(stage.prompt) is None
                found += 1
    assert found > 0


def test_order_answer_is_one_of_the_named_runners():
    for seed in range(1, 30):
        for stage in generate(Rng(seed)):
            if stage.family == "order":
                assert stage.answer in stage.prompt
                assert " " not in stage.answer


def test_public_stage_drops_the_secrets():
    stage = generate(Rng(11))[0]
    public = stage.public()
    assert not hasattr(public, "tier")
    assert not hasattr(public, "answer")


def test_normalise_forgives_wrapping_only():
    assert normalise("  Iron. ") == "iron"
    assert normalise("42") == "42"
    assert normalise("IRON") == "iron"
    assert normalise("iron ore") != "iron"
