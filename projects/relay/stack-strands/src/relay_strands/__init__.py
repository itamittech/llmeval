"""RELAY on Strands — four runner agents and one shared anchor model.

The simplest harness in this repo: no orchestration, no tools, one decision per
turn. What is left is the thing the project measures.
"""

from .harness import RelayHarness

__all__ = ["RelayHarness"]
