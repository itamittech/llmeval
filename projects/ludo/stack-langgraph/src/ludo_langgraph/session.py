"""Opt-in session persistence: both state holders become durable, and that's it.

The three stacks now give three different answers to "what survives the
process?", and this is the shortest one:

- **Strands** persisted everything through one ``FileSessionManager`` — but on
  the framework's sync schedule, so the harness needs an explicit final
  ``persist()`` or the last writes are lost.
- **Spring AI** persisted the conversation through its JDBC repository
  (write-through, nothing to flush) — but beliefs never touch the framework,
  so the harness saves ``beliefs.json`` itself.
- **LangGraph** already keeps *both* halves in framework stores — the
  conversation in the checkpointer, beliefs in the ``Store``. Persistence is
  therefore just swapping the in-memory implementations for the sqlite ones
  over a session file. The checkpointer writes at every super-step; ``put``
  writes immediately. **No save call exists in this stack**, because there is
  nothing left outside the framework to save.

Constructing a harness over a directory that already holds a session is the
restore: threads resume from the checkpointer, beliefs read back from the
store. Off by default — games are independent experiments unless someone
deliberately decides otherwise (open question 18), the same stance as the
other two stacks.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.sqlite import SqliteStore


def open_session(session_dir: Path):
    """The two framework state holders, durable over one session file."""
    session_dir = Path(session_dir)
    session_dir.mkdir(parents=True, exist_ok=True)
    # One file, one connection, shared serially by both components — the game
    # is single-threaded by construction (the engine drives one turn at a time).
    # Autocommit (isolation_level=None) because the two components disagree
    # about transactions: the checkpointer relies on implicit ones, the store
    # issues its own explicit BEGIN — and an implicit transaction left open by
    # one makes the other's BEGIN an error.
    conn = sqlite3.connect(str(session_dir / "session.db"),
                           check_same_thread=False, isolation_level=None)
    saver = SqliteSaver(conn)
    store = SqliteStore(conn)
    store.setup()
    return saver, store, conn
