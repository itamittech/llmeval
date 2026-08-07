"""The committed fixture regenerates byte-identically (ADR-0007's rule)."""

from pathlib import Path

from alibi_langgraph import demo

FIXTURE = (Path(__file__).resolve().parents[2]
           / "games" / "scripted-langgraph-seed7.jsonl")


def test_demo_regenerates_the_committed_fixture(tmp_path):
    out = tmp_path / "out.jsonl"
    demo.main(str(out))
    assert FIXTURE.exists(), "fixture missing — run the demo and commit its output"
    assert out.read_bytes() == FIXTURE.read_bytes()
