"""Every event a bot game emits must validate against the shared schema.

The UI and the eval consume only this contract (ADR-0003), so an engine that
emits something the schema forbids has broken both without either noticing.
"""

import json
from pathlib import Path

import pytest

from relay_engine.deciders import COLORS, LadderRunner, ProfileRunner
from relay_engine.events import ListSink
from relay_engine.game import Game, GameConfig
from relay_engine.rng import Rng
from relay_engine.track import generate

SCHEMA = Path(__file__).resolve().parents[4] / "shared" / "schemas" / "relay-event.schema.json"

jsonschema = pytest.importorskip("jsonschema")


@pytest.fixture(scope="module")
def validator():
    return jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))


def _events(seed: int, bots: str = "ladder") -> list[dict]:
    sink = ListSink()
    config = GameConfig(seed=seed, max_turns=80)
    if bots == "profile":
        track = generate(Rng(seed))
        runners = {c: ProfileRunner(seed * 100 + i, track, {1: 90, 2: 60, 3: 25}, 70)
                   for i, c in enumerate(COLORS)}
    else:
        runners = {c: LadderRunner() for c in COLORS}
    Game(config, sink).play(runners)
    return sink.events


@pytest.mark.parametrize("seed", [1, 7, 13])
def test_bot_games_validate(validator, seed):
    for event in _events(seed):
        errors = list(validator.iter_errors(event))
        assert not errors, f"{event['type']}: {errors[0].message}"


def test_profile_bot_games_validate(validator):
    for event in _events(5, "profile"):
        assert not list(validator.iter_errors(event))


def test_sequence_numbers_are_contiguous():
    events = _events(7)
    assert [e["seq"] for e in events] == list(range(len(events)))


def test_transcript_is_self_contained():
    """A reader with the file and nothing else can replay the race: the track
    is in it, and the answers arrive at the end."""
    events = _events(7)
    types = {e["type"] for e in events}
    assert {"game_started", "track_generated", "game_ended"} <= types
