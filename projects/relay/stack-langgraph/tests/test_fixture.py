"""The committed fixture must be exactly what the demo produces."""

from pathlib import Path

from relay_langgraph import demo

FIXTURE = Path(__file__).resolve().parents[2] / "games" / "scripted-langgraph-seed7.jsonl"


def test_the_fixture_is_committed():
    assert FIXTURE.exists(), (
        "run: python -m relay_langgraph.demo ../games/scripted-langgraph-seed7.jsonl")


def test_the_demo_regenerates_it_byte_for_byte(tmp_path):
    out = tmp_path / "regenerated.jsonl"
    demo.main([str(out)])
    assert out.read_bytes() == FIXTURE.read_bytes()
