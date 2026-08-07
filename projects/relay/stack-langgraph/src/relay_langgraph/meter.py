"""Token accounting through the framework's callback system.

Same instrument both earlier LangGraph stacks used, same reason: the handler is
passed once per invocation and propagated by the framework to every model call
underneath, so every invocation lands in ``on_llm_end`` without the harness
carrying metering logic. Per-call usage rides ``AIMessage.usage_metadata`` —
per-call by construction, no accumulated totals, no ordering trap.

RELAY adds ``actor``: an anchor call is charged to the lane that escalated,
because that lane spent the quota, but it names the anchor's model. Without
that split the transcript would say a small local model produced an answer only
the frontier one could.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


class BudgetExceeded(RuntimeError):
    """Raised once the ceiling is spent; the engine records a pass."""


class Meter(BaseCallbackHandler):
    """One ``llm_call`` event per model invocation, and the spend that gates them."""

    def __init__(self, sink: Any, lanes: dict[str, dict[str, str]],
                 anchor: dict[str, str], max_tokens_per_game: int,
                 measure_latency: bool = False) -> None:
        super().__init__()
        self._sink = sink
        self._lanes = lanes
        self._anchor = anchor
        self.max_tokens = max_tokens_per_game
        #: Off by default so scripted transcripts stay byte-reproducible.
        self.measure_latency = measure_latency
        self.spent = 0
        self.per_lane: dict[str, int] = {}
        self.calls = 0
        #: Stamped by the harness as the race advances.
        self.turn = 0
        self.purpose = "attempt"
        self.color = "red"
        self.actor = "runner"
        self._started: dict[UUID, float] = {}

    @property
    def exhausted(self) -> bool:
        return self.spent >= self.max_tokens

    def on_chat_model_start(self, serialized: dict, messages: Any, *,
                            run_id: UUID, **kwargs: Any) -> None:
        if self.measure_latency:
            self._started[run_id] = perf_counter()

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        usage: dict = {}
        for generations in response.generations:
            for generation in generations:
                message = getattr(generation, "message", None)
                if message is not None and getattr(message, "usage_metadata", None):
                    usage = message.usage_metadata
        details = usage.get("input_token_details") or {}
        tokens = {
            "input": usage.get("input_tokens", 0),
            "output": usage.get("output_tokens", 0),
            "cache_read": details.get("cache_read", 0),
            "cache_write": details.get("cache_creation", 0),
        }
        total = sum(tokens.values())
        self.spent += total
        self.per_lane[self.color] = self.per_lane.get(self.color, 0) + total
        self.calls += 1

        started = self._started.pop(run_id, None)
        seat = self._anchor if self.actor == "anchor" else self._lanes[self.color]
        self._sink.emit("llm_call", {
            "player": self.color,
            "actor": self.actor,
            "model": seat["model"],
            "access": seat["access"],
            "purpose": self.purpose,
            "tokens": tokens,
            # A failed call still emits — zeros and all.
            "latency_ms": 0 if started is None else int((perf_counter() - started) * 1000),
        }, turn=self.turn)
