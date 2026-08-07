"""The committed fixture must be exactly what the demo produces.

ADR-0007's rule, third game: the UI and the eval are built against this file,
so a fixture that has drifted from its generator is a test suite proving things
about a race nobody can reproduce.
"""

from pathlib import Path

from relay_strands import demo

FIXTURE = Path(__file__).resolve().parents[2] / "games" / "scripted-strands-seed7.jsonl"


def test_the_fixture_is_committed():
    assert FIXTURE.exists(), (
        "run: python -m relay_strands.demo ../games/scripted-strands-seed7.jsonl")


def test_the_demo_regenerates_it_byte_for_byte(tmp_path):
    out = tmp_path / "regenerated.jsonl"
    demo.main([str(out)])
    assert out.read_bytes() == FIXTURE.read_bytes()
