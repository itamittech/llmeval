"""Agent beliefs on LangGraph's ``Store`` — the framework's own memory shelf.

Of the three frameworks, LangGraph is the only one with a *dedicated*
cross-conversation memory primitive: ``BaseStore``, a namespaced key-value
store designed to outlive any single thread. Strands put beliefs in
``AgentState``; Spring AI had nowhere to put them at all and hand-rolled a
class. Here the namespace ``("beliefs", color)`` is one agent's private shelf,
and per ADR-0008 the framework holds it.

The contract's rules hold regardless of mechanism: notes reach the model only
through ``{{memory}}``, every write emits ``memory_write`` (from the harness,
which knows the turn), and memory is deliberately unreliable — it records
what an agent believes, including what it was lied to about, and nothing here
reconciles it against the board.

One sharp edge, learned from the source and worth the comment it gets below:
``Store.search`` defaults to ``limit=10``. A memory read that forgets the
limit silently caps an agent at its ten oldest beliefs — no error, just a
player who stops learning.
"""

from __future__ import annotations

from typing import Any

from langgraph.store.base import BaseStore

#: The kinds the event schema allows.
KINDS = ("opponent_model", "commitment", "strategy", "observation")

#: What an unclassified note becomes. Never guessed at: inventing a
#: `commitment` would be fabricating a fact about the game.
DEFAULT_KIND = "observation"

#: Far above anything a game produces; the point is to never hit the
#: default limit=10 (see module docstring).
_ALL = 1000


def _items(store: BaseStore, color: str, prefix: str) -> list[Any]:
    items = store.search(("beliefs", color), limit=_ALL)
    return sorted((i for i in items if i.key.startswith(prefix)), key=lambda i: i.key)


def write_note(store: BaseStore, color: str, text: str, turn: int,
               kind: str | None = None, about: str | None = None) -> dict:
    """Append one belief to the agent's shelf."""
    note = {
        "kind": kind if kind in KINDS else DEFAULT_KIND,
        "text": str(text).strip(),
        "turn": turn,
        "about": about,
    }
    n = len(_items(store, color, "note-"))
    store.put(("beliefs", color), f"note-{n:06d}", note)
    return note


def absorb(store: BaseStore, color: str, summary: str) -> None:
    """Fold a compaction summary in as a durable fact.

    Durable facts are keyed apart from notes so the recency limit in
    :func:`render_memory` can never drop them — that is what "memory survives
    compaction" means.
    """
    summary = str(summary).strip()
    if summary:
        n = len(_items(store, color, "durable-"))
        # Store values are dicts by API contract, so the fact rides one key.
        store.put(("beliefs", color), f"durable-{n:06d}", {"text": summary})


def render_memory(store: BaseStore, color: str, limit: int = 40) -> str:
    """The ``{{memory}}`` variable: what this agent believes, most recent last.

    Rendered here rather than in a template because the prompt language has no
    loops — by design. Byte-identical to the other two stacks' renders.
    """
    lines = [f"- (durable) {i.value['text']}" for i in _items(store, color, "durable-")]
    notes = [i.value for i in _items(store, color, "note-")]
    for note in notes[-limit:]:
        about = f" [{note['about']}]" if note.get("about") else ""
        lines.append(f"- turn {note['turn']} ({note['kind']}){about}: {note['text']}")
    return "\n".join(lines) if lines else "(nothing yet)"
