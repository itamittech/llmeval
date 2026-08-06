"""The four player agents: ``create_agent`` + middleware, one thread each.

One compiled agent per colour, built with the framework's own agent factory.
The conversation is not a field anywhere — it lives in the **checkpointer**,
keyed by ``thread_id=color``: invoking the same agent on the same thread *is*
the persistent decide/reflect conversation, growing turn over turn. That is
LangGraph's grain — state belongs to the runtime, and code holds none of it.

Two pieces of middleware ride every player, both at the framework's documented
extension point:

- :class:`BudgetGate` — the mid-phase backstop for the per-game token ceiling,
  using the same ``jump_to`` mechanism as the framework's own
  ``ModelCallLimitMiddleware``. The harness checks the ceiling between calls;
  the gate enforces it inside the framework's loop, where harness code isn't
  running.
- :class:`Compactor` — harness-contract §5 on the framework's
  ``SummarizationMiddleware``. The subclass adds observation, not behaviour:
  the summary must reach the transcript (``context_compacted``) and durable
  memory, and the summariser's own model call must be metered as
  ``purpose: "compact"`` — §4's rule that memory the transcript cannot see
  does not exist.
"""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, SummarizationMiddleware, hook_config
from langchain_core.messages import AnyMessage, RemoveMessage

from . import memory as beliefs
from .meter import Meter

#: How many recent messages always survive a compaction. Pinned explicitly:
#: the same value as the other two stacks, and a framework default here would
#: be a silent parity break.
PRESERVE_RECENT_MESSAGES = 4

#: The framework formats ``{messages}`` into this and asks the model for the
#: summary. Game-flavoured replacement for the framework's coding-assistant
#: default; the placeholder is the constant's documented contract.
SUMMARY_PROMPT = (
    "Summarise this earlier part of your game so far in at most three "
    "sentences, first person, keeping any deals and suspicions.\n\n"
    "<messages>\n{messages}\n</messages>"
)


def parity_token_counter(system_chars: int):
    """The same chars//4 estimate the Spring AI stack uses, plus the system layer.

    The framework would happily count with a model-aware tokenizer; the game
    counts the way the *budget* is defined, identically in every stack.
    """
    def count(messages: list[AnyMessage]) -> int:
        return system_chars // 4 + sum(len(m.text or "") for m in messages) // 4
    return count


class BudgetGate(AgentMiddleware):
    """Once the ceiling is spent, jump past the model — the call never happens."""

    def __init__(self, meter: Meter) -> None:
        super().__init__()
        self._meter = meter

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        if self._meter.exhausted:
            return {"jump_to": "end"}
        return None


class Compactor(SummarizationMiddleware):
    """The framework's summariser, taught to leave a paper trail.

    Configuration does most of the §5 work: the trigger is the *game's*
    context budget (never the provider's window), the counter is the parity
    estimate, four recent messages always survive, and the model handed in is
    the agent's own — a cheaper summariser would make this stack's games
    cheaper for reasons invisible to the comparison.

    The two overrides observe at documented extension points:

    - ``_create_summary`` flips the meter to ``purpose: "compact"`` for the
      duration of the framework's own summary call — which, unlike Strands'
      manager, runs through the model properly and therefore through the
      callback system: the summariser *cannot* dodge metering here.
    - ``before_model`` lets the framework decide and rewrite, then reads the
      decision: fold the summary into durable memory, emit
      ``context_compacted`` with the before/after counts.
    """

    def __init__(self, model: Any, color: str, meter: Meter, store: Any,
                 sink: Any, max_context_tokens: int, system_chars: int) -> None:
        counter = parity_token_counter(system_chars)
        super().__init__(
            model=model,
            trigger=("tokens", max_context_tokens),
            keep=("messages", PRESERVE_RECENT_MESSAGES),
            token_counter=counter,
            summary_prompt=SUMMARY_PROMPT,
        )
        self._color = color
        self._meter = meter
        self._store = store
        self._sink = sink
        self._counter = counter
        self._last_summary: str | None = None

    def _create_summary(self, messages_to_summarize: list[AnyMessage]) -> str:
        before = self._meter.purpose
        self._meter.purpose = "compact"
        try:
            summary = super()._create_summary(messages_to_summarize)
        finally:
            self._meter.purpose = before
        self._last_summary = summary.strip()
        return summary

    def before_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        tokens_before = self._counter(state["messages"])
        result = super().before_model(state, runtime)
        if result is None:
            return None

        kept = [m for m in result["messages"] if not isinstance(m, RemoveMessage)]
        summary = self._last_summary or ""
        if summary:
            beliefs.absorb(self._store, self._color, summary)
        self._sink.emit("context_compacted", {
            "player": self._color,
            "tokens_before": tokens_before,
            "tokens_after": self._counter(kept),
            "summary": summary,
        }, turn=self._meter.turn)
        return result


def build_player(color: str, model: Any, system_prompt: str, meter: Meter,
                 store: Any, checkpointer: Any, sink: Any,
                 max_context_tokens: int) -> Any:
    """One seat's agent. ``name=color`` keeps transcripts and traces addressable."""
    return create_agent(
        model=model,
        tools=[],
        system_prompt=system_prompt,
        middleware=[
            BudgetGate(meter),
            Compactor(model, color, meter, store, sink,
                      max_context_tokens, len(system_prompt)),
        ],
        checkpointer=checkpointer,
        store=store,
        name=color,
    )
