"""The game's Strands hooks: token accounting, the budget ceiling, table capture.

ADR-0008's mapping made concrete. One :class:`GameHooks` instance is shared by
all four agents; the framework fires it at its own lifecycle points, so
metering, enforcement, and message capture happen without the turn loop
carrying any of that logic itself:

    AfterModelCallEvent  -> one ``llm_call`` event per model invocation
    BeforeModelCallEvent -> cancel the call once the per-game ceiling is spent
    AfterToolCallEvent   -> a floor pass becomes ``message_sent`` events

The ceiling stops *calls*, not the game. Once spent, the harness skips
negotiation and reflection outright and ``choose`` raises — which the engine
records as a forfeit, a defined in-game outcome — so the game runs to its turn
cap through instant forfeits and ends with a normal, schema-valid transcript.
``BeforeModelCallEvent.cancel`` backstops the same rule mid-phase, where a
swarm conversation could otherwise cross the line between harness checks.
"""

from __future__ import annotations

from typing import Any

from strands.hooks import (
    AfterModelCallEvent, AfterToolCallEvent, BeforeModelCallEvent,
    BeforeToolCallEvent, HookRegistry,
)

from . import guardrails


class BudgetExceeded(RuntimeError):
    """Raised by ``choose`` once the ceiling is spent; the engine forfeits."""


class GameHooks:
    """Metering, budget, and table capture for one game."""

    def __init__(self, sink: Any, seats: dict[str, dict[str, str]],
                 max_tokens_per_game: int, max_message_chars: int) -> None:
        #: seats: color -> {"model": ..., "access": ...} for llm_call payloads.
        self._sink = sink
        self._seats = seats
        self.max_tokens = max_tokens_per_game
        self.max_message_chars = max_message_chars
        self.spent = 0
        self.per_agent: dict[str, int] = {}
        self.calls = 0
        #: Set by the harness as phases advance; stamped onto emitted events.
        self.turn = 0
        self.purpose = "negotiate"
        #: Directed messages and table notes awaiting each colour's briefing.
        self._inbox: dict[str, list[str]] = {}

    @property
    def exhausted(self) -> bool:
        return self.spent >= self.max_tokens

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeModelCallEvent, self._before_model)
        registry.add_callback(AfterModelCallEvent, self._after_model)
        registry.add_callback(BeforeToolCallEvent, self._before_tool)
        registry.add_callback(AfterToolCallEvent, self._after_tool)

    # -- model calls ------------------------------------------------------

    def _before_model(self, event: BeforeModelCallEvent) -> None:
        if self.exhausted:
            event.cancel = "per-game token ceiling reached"

    def _after_model(self, event: AfterModelCallEvent) -> None:
        color = event.agent.name

        # Per-call usage rides on the message itself — the event loop attaches
        # it before firing this hook, precisely so hooks need not diff the
        # accumulated totals (which are only updated *after* the hook runs).
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

    # -- floor passes -----------------------------------------------------

    def _before_tool(self, event: BeforeToolCallEvent) -> None:
        """The guardrail gate — the one place agent-to-agent text can be stopped.

        Fires before the handoff executes, so a blocked message is never
        delivered, never reaches an inbox, and never becomes ``message_sent``.
        Cancelling puts the reason into the tool result: the model reads why
        and may rephrase — a blocked message costs the attempt, not the floor.

        Two different failures, deliberately treated differently:
        - over-length is budget enforcement (contract §2's cap), cancelled
          silently — not an attack, so no ``guardrail_triggered``;
        - a content rule is an out-of-fiction attack, cancelled AND recorded,
          because the schema reserves that event for exactly this.
        """
        if event.tool_use.get("name") != "handoff_to_agent":
            return
        params = event.tool_use.get("input") or {}
        note = (params.get("context") or {}).get("table_note")
        for text in filter(None, [str(params.get("message", "")), note and str(note)]):
            if len(text) > self.max_message_chars:
                event.cancel_tool = (
                    f"message not delivered: over the {self.max_message_chars}"
                    f"-character limit — say it shorter"
                )
                return
            violation = guardrails.check(text)
            if violation:
                event.cancel_tool = f"message not delivered: {violation.reason}"
                self._sink.emit("guardrail_triggered", {
                    "player": event.agent.name,
                    "rule": violation.rule,
                    "action": "blocked",
                    "source": "harness",
                    "detail": violation.reason,
                }, turn=self.turn)
                return

    def _after_tool(self, event: AfterToolCallEvent) -> None:
        if event.tool_use.get("name") != "handoff_to_agent":
            return
        if event.cancel_message is not None:
            # Cancelled by the gate above: nothing was delivered, so nothing
            # is recorded — a message_sent for an undelivered message would lie.
            return
        params = event.tool_use.get("input") or {}
        speaker = event.agent.name
        to = params.get("agent_name")
        if to not in self._seats:
            # The model addressed a player that does not exist; the tool
            # already told it so. Nothing was delivered, nothing is recorded.
            return

        text = str(params.get("message", ""))
        self._sink.emit("message_sent",
                        {"player": speaker, "to": to, "text": text},
                        turn=self.turn)
        self._inbox.setdefault(to, []).append(f'from {speaker}: "{text}"')

        note = (params.get("context") or {}).get("table_note")
        if note:
            note = str(note)
            self._sink.emit("message_sent",
                            {"player": speaker, "to": None, "text": note},
                            turn=self.turn)
            for color in self._seats:
                if color != speaker:
                    self._inbox.setdefault(color, []).append(
                        f'(table) from {speaker}: "{note}"')

    def drain_inbox(self, color: str) -> str:
        """The ``{{inbox}}`` variable — consumed into a briefing, then gone.

        What an agent wants to keep past its briefing, it writes to memory at
        reflect. The transcript remains the durable record either way.
        """
        lines = self._inbox.pop(color, [])
        return "\n".join(f"- {line}" for line in lines) if lines else "(none)"
