"""RELAY evaluation — deterministic, and no judge.

Because ``game_ended`` reveals every stage's tier, the question a judge would
be asked here — *was that a reasonable escalation?* — has a correct answer
sitting in the transcript. So it gets measured.
"""

from .scoring import load, score

__all__ = ["load", "score"]
