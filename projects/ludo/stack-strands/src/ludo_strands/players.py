"""The four player agents, and their memory on ``AgentState``.

One Strands ``Agent`` per colour, alive for the whole game. Memory lives in
``agent.state`` — the framework's own key-value store — per ADR-0008: *where*
memory lives is the framework's business; what the contract fixes is observable
behaviour. Notes reach the model only through ``{{memory}}``, every write emits
``memory_write``, and kinds come from the event schema.

Memory is **deliberately unreliable**: it records what an agent believes,
including things it was successfully lied to about. Nothing here reconciles it
against the board.
"""

from __future__ import annotations

from typing import Any

from strands import Agent
from strands.agent.conversation_manager import SummarizingConversationManager

#: How much of the conversation one compaction summarises, and how many recent
#: messages always survive one. Pinned explicitly: framework defaults could
#: drift, and an unpinned knob here would be a silent parity break.
SUMMARY_RATIO = 0.5
PRESERVE_RECENT_MESSAGES = 4

#: The kinds the event schema allows.
KINDS = ("opponent_model", "commitment", "strategy", "observation")

#: What an unclassified note becomes. Never guessed at: inventing a
#: `commitment` would be fabricating a fact about the game.
DEFAULT_KIND = "observation"


def build_player(color: str, model: Any, system_prompt: str, hooks: list) -> Agent:
    """One seat's agent.

    ``name=color`` is load-bearing: the agent's name becomes its Swarm node id,
    which is what makes ``handoff_to_agent(agent_name="blue")`` addressable by
    colour — the floor-passing protocol of ADR-0009 rides on it.

    **Each agent is its own summariser.** The conversation manager's default
    path calls ``model.stream()`` directly, bypassing the agent pipeline — no
    lifecycle hooks, so no ``llm_call``, no budget gate (a capability-matrix
    finding). Passing the agent as its own ``summarization_agent`` routes the
    summary through a full invocation instead: the agent's own model and
    settings (harness-contract §5), metered and budget-gated like every other
    call, and the summary is written from the player's own perspective.
    """
    manager = SummarizingConversationManager(
        summary_ratio=SUMMARY_RATIO,
        preserve_recent_messages=PRESERVE_RECENT_MESSAGES,
    )
    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        name=color,
        state={"notes": [], "durable": []},
        callback_handler=None,  # no console streaming; the transcript is the record
        hooks=list(hooks),
        conversation_manager=manager,
    )
    # After construction, because the agent must exist to be its own summariser.
    manager.summarization_agent = agent
    return agent


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
    """The ``{{memory}}`` variable: what this agent believes, most recent last.

    Rendered here rather than in a template because the prompt language has no
    loops — by design.
    """
    durable = agent.state.get("durable") or []
    notes = agent.state.get("notes") or []
    lines = [f"- (durable) {fact}" for fact in durable]
    for note in notes[-limit:]:
        about = f" [{note['about']}]" if note.get("about") else ""
        lines.append(f"- turn {note['turn']} ({note['kind']}){about}: {note['text']}")
    return "\n".join(lines) if lines else "(nothing yet)"


def absorb(agent: Agent, summary: str) -> None:
    """Fold a compaction summary in as a durable fact.

    Kept separate from notes so the recency limit in :func:`render_memory`
    can never drop it — that is what "memory survives compaction" means.
    """
    summary = str(summary).strip()
    if summary:
        durable = agent.state.get("durable") or []
        durable.append(summary)
        agent.state.set("durable", durable)
