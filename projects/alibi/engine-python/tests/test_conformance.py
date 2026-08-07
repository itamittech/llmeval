"""Vectors: seed in, digest out, byte-stable forever (until the rules change)."""

from alibi_engine import conformance


def test_vectors_replay_identically():
    generated = conformance.generate(seeds=(1, 2, 3), max_turns=40)
    assert conformance.check(generated) == []


def test_digest_covers_the_corpus():
    v1 = conformance.run_vector(1)
    v2 = conformance.run_vector(1)
    assert v1["digest"] == v2["digest"]
    assert v1["digest"] != conformance.run_vector(2)["digest"]


def test_engine_identity_is_excluded_from_digest():
    event = {"seq": 0, "turn": 0, "type": "game_started",
             "payload": {"seed": 1, "engine": {"language": "python", "version": "x"}}}
    stripped = conformance.for_digest(event)
    assert "engine" not in stripped["payload"]
    assert "engine" in event["payload"]  # original untouched
