from __future__ import annotations

from pathlib import Path

import pytest

from ludo_eval import transcript

GAMES = Path(__file__).resolve().parents[1].parent / "games"

FIXTURES = sorted(GAMES.glob("*.jsonl"))


@pytest.fixture(scope="session", params=[p.name for p in FIXTURES])
def any_game(request):
    path = GAMES / request.param
    events = transcript.load(path)
    return path, events, transcript.fold(events)


@pytest.fixture(scope="session")
def sample_game():
    """The engine's random-bot game — the one committed game that FINISHED."""
    path = GAMES / "sample-seed7.jsonl"
    events = transcript.load(path)
    return path, events, transcript.fold(events)


@pytest.fixture(scope="session")
def langgraph_game():
    path = GAMES / "scripted-langgraph-seed7.jsonl"
    events = transcript.load(path)
    return path, events, transcript.fold(events)
