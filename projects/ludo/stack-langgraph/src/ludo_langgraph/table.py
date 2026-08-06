"""The floor-passing table of ADR-0009, drawn as a graph.

LangGraph's core primitive is not an agent — it is the **graph**: you draw
your control flow as nodes and edges, and the framework runs it. So where
Strands handed the table to a prebuilt ``Swarm`` and Spring AI wrote a while
loop, this stack *draws the protocol*:

    START → brief → speak → (tool call?) → tools ──delivered──→ brief (next holder)
                      ↑                      │        └─cap──→ END
                      └──────not delivered───┘
                    (plain text? → END: the floor lapses)

``langgraph-swarm`` was evaluated first and rejected on evidence — its
``SwarmState`` is one shared ``messages`` channel, so every activation reads
the full history: every directed message, every other player's words. Built
for cooperating specialists serving one conversation; LUDO's players are
adversaries whose directed messages are private *by rule* (the contract's
MUST NOT). The package itself is ~200 lines over ``StateGraph`` — proof the
primitive carries the protocol; only the state shape had to change. Recorded
in the capability matrix.

Privacy, in this shape: ``brief`` REPLACES the message channel with the next
holder's private context (their briefing, the shared task, and only the one
message addressed to them) — the same wipe-and-seed the framework's own
summarisation performs, ``RemoveMessage(REMOVE_ALL_MESSAGES)``. Nothing an
agent said survives into another agent's view except what ``pass_floor``
delivered.

The pass itself is a real framework tool, executed by the framework's
``ToolNode``; its result updates graph state through ``Command`` — the same
mechanism ``langgraph-swarm``'s handoff uses. **The guardrail gate is the tool
body** (as in the Spring AI stack): a blocked message never delivers, never
reaches an inbox, and the model reads why in the tool result — a blocked
message costs the attempt, not the floor, and the not-delivered edge routes
the speaker back to try again or give up.

The runaway bound is the framework's own ``recursion_limit`` — a stuck model
retrying forever hits it and the phase is abandoned (harness-contract §2.1:
a provider failure has no in-game meaning; the turn goes on).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from langchain_core.messages import (
    AIMessage, AnyMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages
from langgraph.prebuilt import InjectedState, ToolNode, tools_condition
from langgraph.types import Command
from typing_extensions import TypedDict

from . import guardrails
from .meter import Meter


class TableState(TypedDict):
    """What one table run remembers between floor holdings."""

    messages: Annotated[list[AnyMessage], add_messages]
    holder: str
    passes: int
    delivered: bool
    last_message: str


class Table:
    """One negotiation phase. Built fresh per turn, like the Strands swarm."""

    def __init__(self, colors: tuple[str, ...], models: dict[str, Any],
                 systems: dict[str, str], briefings: dict[str, str], task: str,
                 meter: Meter, sink: Any, inboxes: dict[str, list[str]],
                 max_floor_passes: int, max_message_chars: int) -> None:
        self._colors = colors
        self._models = models
        self._systems = systems
        self._briefings = briefings
        self._task = task
        self._meter = meter
        self._sink = sink
        self._inboxes = inboxes
        self._max_passes = max_floor_passes
        self._max_chars = max_message_chars
        self._pass_floor = self._make_pass_floor()
        self._graph = self._draw()

    # -- the protocol, as nodes -------------------------------------------

    def _brief(self, state: TableState) -> dict:
        """Seat the next holder: wipe the channel, seed their private context."""
        context = self._briefings[state["holder"]] + "\n\n" + self._task
        if state.get("last_message"):
            context += ("\n\nMessage addressed to you this conversation: "
                        + state["last_message"])
        return {
            "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), HumanMessage(context)],
            "delivered": False,
        }

    def _speak(self, state: TableState, config: RunnableConfig) -> dict:
        """One model call for the floor holder — the framework parses the reply."""
        holder = state["holder"]
        if self._meter.exhausted:
            # The mid-phase backstop: the ceiling stops calls, never the game.
            return {"messages": [AIMessage(content="")]}
        self._meter.color = holder
        reply = (self._models[holder]
                 .bind_tools([self._pass_floor])
                 .invoke([SystemMessage(self._systems[holder]), *state["messages"]],
                         config))
        return {"messages": [reply]}

    def _route_after_tools(self, state: TableState) -> Literal["brief", "speak", "__end__"]:
        if not state["delivered"]:
            return "speak"          # the model reads why and may rephrase
        if state["passes"] >= self._max_passes:
            return END              # cap reached: the table closes
        return "brief"              # the floor moves to state["holder"]

    def _draw(self) -> Any:
        builder = StateGraph(TableState)
        builder.add_node("brief", self._brief)
        builder.add_node("speak", self._speak)
        builder.add_node("tools", ToolNode([self._pass_floor]))
        builder.add_edge(START, "brief")
        builder.add_edge("brief", "speak")
        builder.add_conditional_edges("speak", tools_condition,
                                      {"tools": "tools", END: END})
        builder.add_conditional_edges("tools", self._route_after_tools,
                                      {"brief": "brief", "speak": "speak", END: END})
        return builder.compile()

    # -- the action -------------------------------------------------------

    def _make_pass_floor(self) -> Any:
        table = self

        @tool("pass_floor")
        def pass_floor(to: str, message: str,
                       state: Annotated[dict, InjectedState],
                       tool_call_id: Annotated[str, InjectedToolCallId],
                       note: str | None = None) -> Command | str:
            """Send one message to one named player (red, green, yellow or blue)
            and pass them the floor. Optionally include a public table note
            every player will see. This is the only way to speak; reply without
            calling it to end the conversation."""
            return table._deliver(state, tool_call_id, to, message, note)

        return pass_floor

    def _deliver(self, state: dict, tool_call_id: str, to: str,
                 message: str, note: str | None) -> Command | str:
        """The delivery decision — cap, validation, guardrail, fan-out.

        Everything the model gets back is the truth about what was delivered.
        """
        speaker = state["holder"]
        if state["passes"] >= self._max_passes:
            return "the table is closed: the floor-pass cap was reached"
        if to not in self._colors or to == speaker or not str(message).strip():
            return "not delivered: name one other player and give the message"

        message = str(message)
        texts = [message] + ([str(note)] if note else [])
        for text in texts:
            if len(text) > self._max_chars:
                # Over-length is budget enforcement, not an attack: cancelled
                # silently, no guardrail_triggered.
                return (f"message not delivered: over the {self._max_chars}"
                        f"-character limit — say it shorter")
            violation = guardrails.check(text)
            if violation:
                self._sink.emit("guardrail_triggered", {
                    "player": speaker,
                    "rule": violation.rule,
                    "action": "blocked",
                    "source": "harness",
                    "detail": violation.reason,
                }, turn=self._meter.turn)
                return f"message not delivered: {violation.reason}"

        self._sink.emit("message_sent",
                        {"player": speaker, "to": to, "text": message},
                        turn=self._meter.turn)
        self._inboxes.setdefault(to, []).append(f'from {speaker}: "{message}"')
        if note:
            note = str(note)
            self._sink.emit("message_sent",
                            {"player": speaker, "to": None, "text": note},
                            turn=self._meter.turn)
            for color in self._colors:
                if color != speaker:
                    self._inboxes.setdefault(color, []).append(
                        f'(table) from {speaker}: "{note}"')

        return Command(update={
            "messages": [ToolMessage(f"delivered to {to}",
                                     tool_call_id=tool_call_id)],
            "delivered": True,
            "holder": to,
            "passes": state["passes"] + 1,
            "last_message": message,
        })

    # -- running one phase ------------------------------------------------

    def run(self, opener: str, callbacks: list) -> None:
        self._graph.invoke(
            {"messages": [], "holder": opener, "passes": 0,
             "delivered": False, "last_message": ""},
            config={
                "callbacks": callbacks,
                # The framework's own runaway bound: generous enough for a full
                # table (each pass is ~4 graph steps), hit only by a model
                # stuck in a retry loop.
                "recursion_limit": 6 * (self._max_passes + 2),
            },
        )
