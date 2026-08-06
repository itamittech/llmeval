"""Token accounting through the framework's callback system.

ADR-0008's mapping for LangGraph: where Strands fired lifecycle hooks and
Spring AI attached usage to the response object, LangChain's instrument is the
**callback handler** — passed once per invocation and propagated by the
framework to every model call made underneath, however deep. That propagation
is the point: the summarisation middleware's model call, a table-graph node's
call, a retry — all of them land in ``on_chat_model_end`` without the turn
loop carrying any metering logic.

One :class:`Meter` is shared by the whole game. The harness stamps ``turn``,
``purpose`` and ``color`` as phases advance (the same discipline as the
Strands stack's hooks object); the framework supplies the usage, riding on
``AIMessage.usage_metadata``.

The ceiling stops *calls*, not the game: once spent, the harness skips
negotiation and reflection, ``choose`` raises — the engine records a forfeit,
a defined in-game outcome — and the game runs to its cap with a schema-valid
transcript. Mid-phase, the :class:`~ludo_langgraph.players.BudgetGate`
middleware backstops the same rule inside the framework's own loop.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


class BudgetExceeded(RuntimeError):
    """Raised by ``choose`` once the ceiling is spent; the engine forfeits."""


class Meter(BaseCallbackHandler):
    """One ``llm_call`` event per model invocation, and the spend that gates them."""

    def __init__(self, sink: Any, seats: dict[str, dict[str, str]],
                 max_tokens_per_game: int, measure_latency: bool = False) -> None:
        super().__init__()
        self._sink = sink
        self._seats = seats
        self.max_tokens = max_tokens_per_game
        #: Off by default so scripted transcripts stay byte-reproducible —
        #: a wall-clock milliseconds field is the one thing that would make
        #: two identical runs differ. Live harnesses turn it on.
        self.measure_latency = measure_latency
        self.spent = 0
        self.per_agent: dict[str, int] = {}
        self.calls = 0
        #: Stamped by the harness as phases advance.
        self.turn = 0
        self.purpose = "negotiate"
        self.color = "red"
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
        self.per_agent[self.color] = self.per_agent.get(self.color, 0) + total
        self.calls += 1

        started = self._started.pop(run_id, None)
        seat = self._seats[self.color]
        self._sink.emit("llm_call", {
            "player": self.color,
            "model": seat["model"],
            "access": seat["access"],
            "purpose": self.purpose,
            "tokens": tokens,
            # A failed call still emits — zeros and all. A model call that
            # happened but is absent from the transcript would be a lie.
            "latency_ms": 0 if started is None else int((perf_counter() - started) * 1000),
        }, turn=self.turn)
