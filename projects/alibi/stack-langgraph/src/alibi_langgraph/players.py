"""The four detective agents: ``create_agent`` + the archivist tool, one thread each.

One compiled agent per colour. The conversation is not a field anywhere — it
lives in the checkpointer under ``thread_id=color``, LangGraph's grain: state
belongs to the runtime, and code holds none of it.

The archivist is a **real framework tool**: the model emits a
``consult_archivist`` tool call, the framework's tool executor runs it, and the
answer re-enters the loop as a tool message — drawn as visible graph steps, so
a consultation is two metered model invocations in the transcript, never a
hidden round-trip (the exact opposite grain from Spring AI's internal
execution, as LUDO's matrix recorded).

No Compactor middleware, deliberately: the ALIBI contract (§8) does not
require compaction, and this stack does not volunteer it — the thread grows,
and what that costs is the comparison's business to measure, not this module's
to hide. The BudgetGate rides every agent, same as LUDO's.
"""

from __future__ import annotations

from typing import Any, Callable

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.tools import tool

from .meter import Meter


def make_archivist_tool(current_budget: Callable[[], Any]):
    """The consultation tool, closed over the harness's per-turn search budget.

    Scripted tier: the body is the engine's metered baseline retriever — no
    archivist model call, per contract §2. The docstring below is the tool
    description the model reads; tool schemas are framework territory.
    """

    @tool
    def consult_archivist(query: str) -> str:
        """Ask the hotel archivist to search the case archive. Returns the most
        relevant documents, each tagged with its citable [doc-id]. Quota per
        turn is limited; an exhausted quota returns nothing."""
        budget = current_budget()
        if budget is None:
            return "The archivist is unavailable outside your own deliberation."
        results = budget.search(str(query))
        if not results:
            return "The archive has nothing on that."
        return "\n".join(f"[{d.id}] ({d.kind}) {d.text}" for d in results)

    return consult_archivist


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


def build_detective(color: str, model: Any, system_prompt: str, meter: Meter,
                    store: Any, checkpointer: Any, archivist_tool: Any) -> Any:
    """One seat's agent. ``name=color`` keeps transcripts and traces addressable."""
    return create_agent(
        model=model,
        tools=[archivist_tool],
        system_prompt=system_prompt,
        middleware=[BudgetGate(meter)],
        checkpointer=checkpointer,
        store=store,
        name=color,
    )
