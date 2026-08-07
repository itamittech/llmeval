"""The four detective agents, their notebooks, and the archivist tool.

One Strands ``Agent`` per colour, alive for the whole game. The notebook lives
in ``agent.state`` (ADR-0008: where memory lives is the framework's business);
notes reach the model only through ``{{memory}}``, every accepted note emits
``memory_write``, and kinds come from the event schema.

**The archivist is a real framework tool** — the agent-as-tool architecture is
this project's deliverable, so the consultation goes model → toolUse →
framework tool executor → answer → model, never a harness shortcut. On the
scripted tier the tool's body is the engine's baseline retriever through the
turn's metered ``SearchBudget`` (no archivist model call, per contract §2); a
live archivist agent slots into the same body later without the tool's shape
changing.

The conversation window is pinned small on purpose. Every phase prompt is
self-contained — hand, eliminations, table, notebook all rendered in — so
carried history is redundancy, and LUDO's token numbers showed what carrying
it costs. What must persist, persists in the notebook.
"""

from __future__ import annotations

from typing import Any, Callable

from strands import Agent, tool
from strands.agent.conversation_manager import SlidingWindowConversationManager

#: Pinned explicitly: a framework default could drift, and an unpinned knob
#: here would be a silent parity break.
WINDOW_SIZE = 12

#: The kinds the event schema allows.
KINDS = ("deduction", "suspicion", "plan", "observation")

#: What an unclassified note becomes. Never guessed upward: inventing a
#: `deduction` would fabricate certainty the detective never claimed.
DEFAULT_KIND = "observation"

#: Contract §4: at most this many notes accepted per reflect.
MAX_NOTES_PER_REFLECT = 3


def make_archivist_tool(current_budget: Callable[[], Any]):
    """The consultation tool, closed over the harness's per-turn search budget.

    The docstring below is the tool description the model reads — the same
    boundary ADR-0009 noted for the swarm's handoff tool: authored prompts stay
    shared and identical; tool schemas are each framework's territory.
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


def build_detective(color: str, model: Any, system_prompt: str, hooks: list,
                    archivist_tool: Any) -> Agent:
    """One seat's agent. ``name=color`` keeps event attribution by badge."""
    return Agent(
        model=model,
        system_prompt=system_prompt,
        name=color,
        agent_id=color,
        state={"notes": []},
        tools=[archivist_tool],
        callback_handler=None,  # no console streaming; the transcript is the record
        hooks=list(hooks),
        conversation_manager=SlidingWindowConversationManager(window_size=WINDOW_SIZE),
    )


def write_note(agent: Agent, text: str, turn: int,
               kind: str | None = None, about: str | None = None) -> dict:
    """Append one belief. ``AgentState`` deep-copies on get, so read-modify-set."""
    note = {
        "kind": kind if kind in KINDS else DEFAULT_KIND,
        "text": str(text).strip(),
        "turn": turn,
        "about": about,
    }
    notes = agent.state.get("notes") or []
    notes.append(note)
    agent.state.set("notes", notes)
    return note


def render_memory(agent: Agent, limit: int = 40) -> str:
    """The ``{{memory}}`` variable: what this detective believes, recent last.

    Rendered here rather than in a template because the prompt language has no
    loops — by design. Unreliable by design too: red-herring damage included.
    """
    notes = agent.state.get("notes") or []
    lines = []
    for note in notes[-limit:]:
        about = f" [{note['about']}]" if note.get("about") else ""
        lines.append(f"- turn {note['turn']} ({note['kind']}){about}: {note['text']}")
    return "\n".join(lines) if lines else "(nothing yet)"
