"""Every emitted event must satisfy the shared contract in shared/schemas/."""

import json
from pathlib import Path

import pytest

from ludo_engine.board import COLORS
from ludo_engine.deciders import RandomBot
from ludo_engine.events import ListSink
from ludo_engine.game import Game, GameConfig

jsonschema = pytest.importorskip("jsonschema")

SCHEMA_PATH = Path(__file__).resolve().parents[4] / "shared" / "schemas" / "event.schema.json"


@pytest.fixture(scope="module")
def validator():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


@pytest.fixture(scope="module")
def events():
    sink = ListSink()
    Game(GameConfig(seed=11, max_turns=300), sink).play(
        {c: RandomBot(seed=i) for i, c in enumerate(COLORS)}
    )
    return sink.events


def test_the_schema_itself_is_valid(validator):
    assert validator is not None


def test_every_event_validates(validator, events):
    errors = [
        f"seq {event['seq']} ({event['type']}): {err.message}"
        for event in events
        for err in validator.iter_errors(event)
    ]
    assert not errors, "\n".join(errors[:20])


def test_a_full_game_exercises_most_engine_event_types(events):
    seen = {e["type"] for e in events}
    expected = {
        "game_started", "turn_started", "dice_rolled", "move_made",
        "token_captured", "extra_roll_granted", "turn_ended", "game_ended",
    }
    assert expected <= seen, f"never emitted: {expected - seen}"


def test_engine_events_carry_no_timestamp(events):
    """Transcripts from the same seed must diff cleanly."""
    assert not any("ts" in e for e in events)


def test_no_agent_events_in_an_engine_only_run(events):
    agent_only = {"agent_reasoning", "message_sent", "memory_write",
                  "context_compacted", "llm_call", "guardrail_triggered"}
    assert not agent_only & {e["type"] for e in events}
