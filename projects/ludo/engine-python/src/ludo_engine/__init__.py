"""Deterministic LUDO rules engine.

Pure standard library, no LLM dependencies — see docs/architecture/repository-layout.md.
Shared by both Python stacks (Strands and LangGraph) so that the agent framework
is the only variable between them (ADR-0002).
"""

from .board import COLORS, HOME, BASE, Color, to_square
from .deciders import Decider, FirstLegal, RandomBot, TurnContext
from .dice import Dice
from .events import EventSink, JsonlSink, ListSink, TeeSink
from .game import ENGINE_VERSION, Game, GameConfig, Outcome
from .moves import Move, apply_move, legal_moves
from .state import GameState, standings

__version__ = ENGINE_VERSION

__all__ = [
    "BASE", "COLORS", "HOME", "Color", "to_square",
    "Decider", "FirstLegal", "RandomBot", "TurnContext",
    "Dice",
    "EventSink", "JsonlSink", "ListSink", "TeeSink",
    "ENGINE_VERSION", "Game", "GameConfig", "Outcome",
    "Move", "apply_move", "legal_moves",
    "GameState", "standings",
]
