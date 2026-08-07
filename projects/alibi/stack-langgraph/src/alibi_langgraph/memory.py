"""The notebook on LangGraph's ``Store`` — the framework's own memory shelf.

Same primitive the LUDO stack used for beliefs, same sharp edge honoured:
``Store.search`` defaults to ``limit=10``, so every read here passes an
explicit limit — a notebook that silently forgets its eleventh note is a
detective that stops learning.

The namespace ``("notebook", color)`` is one detective's private shelf. Notes
reach the model only through ``{{memory}}``, every accepted note emits
``memory_write`` (from the harness, which knows the turn), and the notebook is
deliberately unreliable — red-herring damage included, never corrected.
"""

from __future__ import annotations

from langgraph.store.base import BaseStore

#: The kinds the event schema allows.
KINDS = ("deduction", "suspicion", "plan", "observation")

#: What an unclassified note becomes — never guessed upward.
DEFAULT_KIND = "observation"

#: Far above anything a game produces; the point is to never hit limit=10.
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


def render_memory(store: BaseStore, color: str, limit: int = 40) -> str:
    """The ``{{memory}}`` variable — byte-identical rendering to the other stacks."""
    notes = [i.value for i in _notes(store, color)]
    lines = []
    for note in notes[-limit:]:
        about = f" [{note['about']}]" if note.get("about") else ""
        lines.append(f"- turn {note['turn']} ({note['kind']}){about}: {note['text']}")
    return "\n".join(lines) if lines else "(nothing yet)"
