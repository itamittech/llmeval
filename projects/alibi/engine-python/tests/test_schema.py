"""Every event the engine emits must satisfy the shared contract."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from alibi_engine.case import COLORS
from alibi_engine.deciders import EliminationBot, RandomSleuth
from alibi_engine.events import ListSink
from alibi_engine.game import Game, GameConfig

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[4] / "shared" / "schemas" / "alibi-event.schema.json")
    .read_text(encoding="utf-8")
)


def _validate_events(events):
    validator = Draft202012Validator(SCHEMA)
    problems = []
    for event in events:
        problems.extend(f"{event['seq']}: {e.message}" for e in validator.iter_errors(event))
    return problems


def test_elimination_game_is_schema_valid():
    sink = ListSink()
    Game(GameConfig(seed=7, max_turns=40), sink).play({c: EliminationBot() for c in COLORS})
    assert _validate_events(sink.events) == []


def test_random_game_is_schema_valid():
    sink = ListSink()
    Game(GameConfig(seed=7, max_turns=10), sink).play(
        {c: RandomSleuth(700 + i) for i, c in enumerate(COLORS)}
    )
    assert _validate_events(sink.events) == []
