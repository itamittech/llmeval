"""The four runner agents, their notebooks, and the anchor.

One Strands ``Agent`` per lane, alive for the whole race. The notebook lives in
``agent.state`` (ADR-0008: where memory lives is the framework's business);
notes reach the model only through ``{{memory}}``, and every accepted note emits
``memory_write``.

**No tools.** RELAY's anchor is a model swap, not a consultation, so nothing
here registers a tool — which is exactly what makes this stack's call counts
boring, and boring here is the finding.

## The anchor, and what Strands does not have

Escalation needs one call to a *different* model, with no memory and no tools.
Strands has no fallback, router, or model-swap primitive: `Agent` binds one
model at construction, and there is no equivalent of a chain of alternates.

So the anchor is a second `Agent` over the anchor model, with its message list
cleared before every call — a one-shot invocation of a stateless agent. That is
an **Adapter**, not a Native: the framework's extension point (constructing an
agent over a chosen model) does the work, and the harness supplies the
statelessness the contract requires.

Worth naming the temptation resisted: calling `model.stream()` directly would
skip the agent loop, and with it the lifecycle hooks — so the anchor's tokens
would vanish from the meter in the one project where measuring them is the
point. The same shape as the Strands summariser trap LUDO recorded.
"""

from __future__ import annotations

from typing import Any

from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager

#: Pinned explicitly: a framework default could drift, and an unpinned knob
#: here would be a silent parity break.
WINDOW_SIZE = 12

#: The kinds the event schema allows for this game. `self` is the one that
#: matters — a runner learning what it is bad at.
KINDS = ("self", "rival", "plan", "observation")

#: What an unclassified note becomes.
DEFAULT_KIND = "observation"

#: Contract: at most this many notes accepted per reflect.
MAX_NOTES_PER_REFLECT = 2


def build_runner(color: str, model: Any, system_prompt: str, hooks: list) -> Agent:
    """One lane's agent. ``name=color`` keeps event attribution by lane."""
    return Agent(
        model=model,
        system_prompt=system_prompt,
        name=color,
        agent_id=color,
        state={"notes": []},
        callback_handler=None,  # no console streaming; the transcript is the record
        hooks=list(hooks),
        conversation_manager=SlidingWindowConversationManager(window_size=WINDOW_SIZE),
    )


def build_anchor(model: Any, hooks: list) -> Agent:
    """The shared frontier model, as close to "just a model" as Strands allows.

    No system prompt, no tools, no state — and :func:`ask_anchor` wipes its
    messages before each call, so it carries nothing between escalations. Two
    runners escalating in a row must get two independent answers, or the race
    would leak one lane's stage into another's.
    """
    return Agent(
        model=model,
        name="anchor",
        agent_id="anchor",
        callback_handler=None,
        hooks=list(hooks),
    )


def ask_anchor(anchor: Agent, prompt: str) -> str:
    anchor.messages = []  # statelessness the framework will not enforce for us
    return str(anchor(prompt)).strip()


def write_note(agent: Agent, text: str, turn: int,
               kind: str | None = None, about: str | None = None) -> dict:
    """Append one note. ``AgentState`` deep-copies on get, so read-modify-set."""
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


def render_memory(agent: Agent, limit: int = 20) -> str:
    """The ``{{memory}}`` variable: what this runner believes about itself.

    Rendered here rather than in a template because the prompt language has no
    loops — by design.
    """
    notes = agent.state.get("notes") or []
    lines = []
    for note in notes[-limit:]:
        about = f" [{note['about']}]" if note.get("about") else ""
        lines.append(f"- turn {note['turn']} ({note['kind']}){about}: {note['text']}")
    return "\n".join(lines) if lines else "(nothing yet)"
