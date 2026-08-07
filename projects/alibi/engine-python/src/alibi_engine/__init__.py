"""ALIBI deduction engine — deterministic, LLM-free, event-emitting.

Public surface, in reading order:

    case        the elements, the cast, and the deal
    archive     generated testimony + the baseline retriever
    deciders    the Detective protocol, views, and the bots
    game        the referee: turn loop, refutation, accusation, standings
    events      the shared event stream (ADR-0003)
    conformance cross-engine vectors (ADR-0002)
    rng         the portable randomness both engines share
"""

from .case import ALL_ELEMENTS, COLORS, DIMENSIONS, ELEMENTS, Case, deal
from .deciders import (
    Belief, Detective, DetectiveView, EliminationBot, RandomSleuth,
    ShowContext, Suggestion, Triple, TurnContext, TurnEnd,
)
from .events import EventSink, JsonlSink, ListSink, TeeSink
from .game import Game, GameConfig, Outcome

__all__ = [
    "ALL_ELEMENTS", "COLORS", "DIMENSIONS", "ELEMENTS", "Case", "deal",
    "Belief", "Detective", "DetectiveView", "EliminationBot", "RandomSleuth",
    "ShowContext", "Suggestion", "Triple", "TurnContext", "TurnEnd",
    "EventSink", "JsonlSink", "ListSink", "TeeSink",
    "Game", "GameConfig", "Outcome",
]
