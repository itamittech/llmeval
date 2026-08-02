"""Vectors that the Java engine must reproduce exactly (ADR-0002)."""

import json
from pathlib import Path

from ludo_engine import conformance

VECTORS_PATH = Path(__file__).resolve().parents[4] / "shared" / "conformance" / "vectors.json"


def test_a_vector_is_reproducible():
    assert conformance.run_vector(3) == conformance.run_vector(3)


def test_different_seeds_produce_different_digests():
    assert conformance.run_vector(1)["digest"] != conformance.run_vector(2)["digest"]


def test_generated_vectors_check_out():
    assert conformance.check(conformance.generate(seeds=(1, 2, 3))) == []


def test_a_rule_change_would_be_caught():
    """Sanity-check the check: a tampered digest must fail."""
    vectors = conformance.generate(seeds=(1,))
    vectors["vectors"][0]["digest"] = "0" * 64
    assert conformance.check(vectors)


def test_committed_vectors_still_hold():
    """Fails if the engine's behaviour drifted without vectors being regenerated."""
    assert VECTORS_PATH.exists(), (
        f"{VECTORS_PATH} missing — run: python -m ludo_engine.cli conformance --generate"
    )
    stored = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
    assert conformance.check(stored) == []
