"""The notebook on LangGraph's ``Store`` — the framework's own memory shelf.

Same primitive both earlier games used, same sharp edge honoured:
``Store.search`` defaults to ``limit=10``, so every read here passes an explicit
limit. A runner whose eleventh note silently vanished would be a runner that
stops learning what it is bad at, which in this game is the only thing worth
learning.

The namespace ``("notebook", color)`` is one lane's private shelf.
"""

from __future__ import annotations

from langgraph.store.base import BaseStore

#: The kinds the event schema allows for this game.
KINDS = ("self", "rival", "plan", "observation")

DEFAULT_KIND = "observation"

#: Far above anything a race produces; the point is to never hit limit=10.
_ALL = 1000


def _notes(store: BaseStore, color: str) -> list:
    items = store.search(("notebook", color), limit=_ALL)
    return sorted(items, key=lambda i: i.key)


def write_note(store: BaseStore, color: str, text: str, turn: int,
               kind: str | None = None, about: str | None = None) -> dict:
    note = {
        "kind": kind if kind in KINDS else DEFAULT_KIND,
        "text": str(text).strip(),
        "turn": turn,
        "about": about,
    }
    n = len(_notes(store, color))
    store.put(("notebook", color), f"note-{n:06d}", note)
    return note


def render_memory(store: BaseStore, color: str, limit: int = 20) -> str:
    """The ``{{memory}}`` variable — byte-identical rendering to the other stacks."""
    notes = [i.value for i in _notes(store, color)]
    lines = []
    for note in notes[-limit:]:
        about = f" [{note['about']}]" if note.get("about") else ""
        lines.append(f"- turn {note['turn']} ({note['kind']}){about}: {note['text']}")
    return "\n".join(lines) if lines else "(nothing yet)"
