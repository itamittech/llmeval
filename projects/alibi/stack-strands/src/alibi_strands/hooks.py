"""The game's Strands hooks: token accounting and the budget ceiling.

Same two lessons LUDO's hooks recorded, still honoured here:

- per-call usage rides the assistant *message*, not the accumulated totals —
  the loop updates those only after the hook fires;
- the ceiling stops *calls*, not the game: once spent, ``BeforeModelCallEvent``
  cancels, phases raise, and the engine records passes — a normal transcript.

ALIBI needs no tool-capture hooks: the archivist tool's observable record is
the engine's own ``archive_searched`` event, emitted where the search budget
is spent. The table note travels inside the suggestion JSON, so its guardrail
gate lives in the harness parse, not at a tool boundary — one of the shape
differences between the two games worth noticing.
"""

from __future__ import annotations

from typing import Any

from strands.hooks import AfterModelCallEvent, BeforeModelCallEvent, HookRegistry


class BudgetExceeded(RuntimeError):
    """Raised by a phase once the ceiling is spent; the engine records a pass."""


class GameHooks:
    """Metering and budget for one game. One instance, shared by all four agents."""

    def __init__(self, sink: Any, seats: dict[str, dict[str, str]],
                 max_tokens_per_game: int) -> None:
        self._sink = sink
        self._seats = seats
        self.max_tokens = max_tokens_per_game
        self.spent = 0
        self.per_agent: dict[str, int] = {}
        self.calls = 0
        #: Set by the harness as phases advance; stamped onto emitted events.
        self.turn = 0
        self.purpose = "suggest"

    @property
    def exhausted(self) -> bool:
        return self.spent >= self.max_tokens

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeModelCallEvent, self._before_model)
        registry.add_callback(AfterModelCallEvent, self._after_model)

    def _before_model(self, event: BeforeModelCallEvent) -> None:
        if self.exhausted:
            event.cancel = "per-game token ceiling reached"

    def _after_model(self, event: AfterModelCallEvent) -> None:
        color = event.agent.name

        meta: dict = {}
        if event.stop_response is not None:
            meta = event.stop_response.message.get("metadata") or {}
        usage = meta.get("usage") or {}
        tokens = {
            "input": usage.get("inputTokens", 0),
            "output": usage.get("outputTokens", 0),
            "cache_read": usage.get("cacheReadInputTokens", 0),
            "cache_write": usage.get("cacheWriteInputTokens", 0),
        }
        total = sum(tokens.values())
        self.spent += total
        self.per_agent[color] = self.per_agent.get(color, 0) + total
        self.calls += 1

        seat = self._seats[color]
        self._sink.emit("llm_call", {
            "player": color,
            "model": seat["model"],
            "access": seat["access"],
            "purpose": self.purpose,
            "tokens": tokens,
            # A failed call still emits — zeros and all. A model call that
            # happened but is absent from the transcript would be a lie.
            "latency_ms": (meta.get("metrics") or {}).get("latencyMs", 0),
        }, turn=self.turn)
