"""RELAY — the deterministic race engine.

Standard library only. No LLM SDK, no network, no clock: the same seed and the
same decisions replay a race exactly, which is what makes the conformance
vectors (ADR-0002) and the offline UI and eval possible at all.
"""

from .game import Game, GameConfig, Outcome
from .track import Stage, PublicStage

__all__ = ["Game", "GameConfig", "Outcome", "Stage", "PublicStage"]
