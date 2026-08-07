"""Vectors: the committed proof that two engines agree."""

import json
from pathlib import Path

from relay_engine import conformance

VECTORS = Path(__file__).resolve().parents[4] / "shared" / "conformance" / "relay-vectors.json"


def test_vectors_are_committed():
    assert VECTORS.exists(), "run: python -m relay_engine.cli conformance --generate"


def test_python_engine_matches_its_own_vectors():
    assert conformance.check(json.loads(VECTORS.read_text(encoding="utf-8"))) == []


def test_a_vector_is_reproducible():
    assert conformance.run_vector(7) == conformance.run_vector(7)


def test_the_digest_covers_the_stage_prompts():
    """The whole point: the track rides in the transcript, so a generator that
    renders one character differently fails every vector."""
    from relay_engine.deciders import COLORS, LadderRunner
    from relay_engine.events import ListSink
    from relay_engine.game import Game, GameConfig

    sink = ListSink()
    Game(GameConfig(seed=7, max_turns=80), sink).play({c: LadderRunner() for c in COLORS})
    events = sink.events
    baseline = conformance.digest(events)

    tampered = [dict(e) for e in events]
    for event in tampered:
        if event["type"] == "track_generated":
            stages = [dict(s) for s in event["payload"]["stages"]]
            stages[0]["prompt"] = stages[0]["prompt"] + " "
            event["payload"] = {"stages": stages}
    assert conformance.digest(tampered) != baseline


def test_engine_language_is_excluded_from_the_digest():
    a = {"seq": 0, "turn": 0, "type": "game_started",
         "payload": {"seed": 1, "engine": {"language": "python", "version": "0.1.0"}}}
    b = {"seq": 0, "turn": 0, "type": "game_started",
         "payload": {"seed": 1, "engine": {"language": "java", "version": "0.1.0"}}}
    assert conformance.digest([a]) == conformance.digest([b])
