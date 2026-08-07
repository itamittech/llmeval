"""The four runner agents, and the anchor.

One compiled ``create_agent`` per lane. The conversation is not a field
anywhere — it lives in the checkpointer under ``thread_id=color``, LangGraph's
grain: state belongs to the runtime, and code holds none of it.

**No tools, and no graph.** LUDO drew its negotiation protocol as a
``StateGraph`` because there was a protocol to draw. RELAY has none: runners
never address each other, and escalation is a model swap the engine performs.
So the framework's headline primitive has nothing to do here, and this stack is
four ordinary agent loops. Recording that is the point — *which* framework
differences you meet is decided by your protocol, and RELAY's protocol asks for
almost nothing.

## The anchor, and what LangChain does not have

LangChain *does* ship a fallback primitive: ``Runnable.with_fallbacks``. It is
not this. `with_fallbacks` triggers on an **exception** — the primary model
errored, try the next — and RELAY's escalation is a deliberate choice made
while the primary is working perfectly. Wiring a policy decision through an
error handler would mean raising on purpose to route a call, which is a lie in
the shape of a design pattern.

So the anchor is a second model invoked directly through the framework's own
``BaseChatModel`` interface, with the meter's callback attached. **Adapter**,
and the same answer Strands gave for a different reason: the frameworks have
fallbacks for failure, and nobody has one for judgement.
"""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.messages import HumanMessage

from .meter import Meter


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


def build_runner(color: str, model: Any, system_prompt: str, meter: Meter,
                 store: Any, checkpointer: Any) -> Any:
    """One lane's agent. ``name=color`` keeps transcripts and traces addressable."""
    return create_agent(
        model=model,
        tools=[],
        system_prompt=system_prompt,
        middleware=[BudgetGate(meter)],
        checkpointer=checkpointer,
        store=store,
        name=color,
    )


def ask_anchor(model: Any, prompt: str, meter: Meter) -> str:
    """One stateless call to the shared frontier model.

    No agent, no thread, no checkpointer — deliberately. The contract says the
    anchor is a model call, and here that is literally what it is: the
    ``BaseChatModel`` seam, invoked once, with the meter's callback attached so
    the call is still counted. Two escalations in a row cannot see each other,
    because there is no state for them to see each other through.
    """
    reply = model.invoke([HumanMessage(content=prompt)], config={"callbacks": [meter]})
    return str(reply.content).strip()
