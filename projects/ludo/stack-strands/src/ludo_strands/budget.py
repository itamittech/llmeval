"""Token accounting and the per-game ceiling.

Every model call is recorded, per agent and per purpose, because the
Bedrock-vs-direct comparison, the cost analysis and the latency comparison all
read the same `llm_call` events. A harness that batched them would destroy all
three at once.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class BudgetExceeded(RuntimeError):
    """The per-game token ceiling was reached. The game stops and says so."""


@dataclass(frozen=True)
class Usage:
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0

    @property
    def total(self) -> int:
        return self.input + self.output + self.cache_read + self.cache_write

    def as_payload(self) -> dict[str, int]:
        return {
            "input": self.input,
            "output": self.output,
            "cache_read": self.cache_read,
            "cache_write": self.cache_write,
        }


@dataclass
class Budget:
    """Whole-game ceiling, plus a per-agent breakdown for the record."""

    max_tokens_per_game: int
    spent: int = 0
    per_agent: dict[str, int] = field(default_factory=dict)
    calls: int = 0

    def record(self, color: str, usage: Usage) -> None:
        self.spent += usage.total
        self.per_agent[color] = self.per_agent.get(color, 0) + usage.total
        self.calls += 1

    @property
    def remaining(self) -> int:
        return max(0, self.max_tokens_per_game - self.spent)

    def check(self) -> None:
        """Raise once the ceiling is reached.

        Checked between calls rather than mid-call: a request already in flight
        has been paid for either way, and stopping halfway would leave the
        transcript describing a turn that never resolved.
        """
        if self.spent >= self.max_tokens_per_game:
            raise BudgetExceeded(
                f"spent {self.spent} of {self.max_tokens_per_game} tokens"
            )
