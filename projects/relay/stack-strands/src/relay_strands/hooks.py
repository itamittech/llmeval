"""Token accounting and the budget ceiling, on Strands' lifecycle hooks.

The two lessons both earlier games recorded, still honoured:

- per-call usage rides the assistant *message*, not the accumulated totals —
  the loop updates those only after the hook fires;
- the ceiling stops *calls*, not the race: once spent, ``BeforeModelCallEvent``
  cancels, the turn raises, and the engine records a pass.

RELAY adds one field the other two games had no use for. ``actor`` distinguishes
a runner call from an anchor call, because the whole project is about what the
second costs relative to the first — and both land on the *escalating lane's*
colour, since that is the lane that spent the quota.
"""

from __future__ import annotations

from typing import Any

from strands.hooks import AfterModelCallEvent, BeforeModelCallEvent, HookRegistry


class BudgetExceeded(RuntimeError):
    """Raised by a turn once the ceiling is spent; the engine records a pass."""


class GameHooks:
    """Metering and budget for one race. One instance, shared by every agent."""

    def __init__(self, sink: Any, lanes: dict[str, dict[str, str]],
                 anchor: dict[str, str], max_tokens_per_game: int) -> None:
        self._sink = sink
        self._lanes = lanes
        self._anchor = anchor
        self.max_tokens = max_tokens_per_game
        self.spent = 0
        self.per_lane: dict[str, int] = {}
        self.calls = 0
        #: Set by the harness as the race advances; stamped onto emitted events.
        self.turn = 0
        self.purpose = "attempt"
        #: Which lane's budget the current call belongs to, and which tier ran
        #: it. The anchor agent has no colour of its own — cost lands on whoever
        #: escalated.
        self.color = "red"
        self.actor = "runner"

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
        self.per_lane[self.color] = self.per_lane.get(self.color, 0) + total
        self.calls += 1

        seat = self._anchor if self.actor == "anchor" else self._lanes[self.color]
        self._sink.emit("llm_call", {
            "player": self.color,
            "actor": self.actor,
            "model": seat["model"],
            "access": seat["access"],
            "purpose": self.purpose,
            "tokens": tokens,
            # A failed call still emits — zeros and all. A model call that
            # happened but is absent from the transcript would be a lie.
            "latency_ms": (meta.get("metrics") or {}).get("latencyMs", 0),
        }, turn=self.turn)
