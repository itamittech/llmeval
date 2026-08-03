"""Per-agent memory.

Private, persistent across turns, and **deliberately unreliable**: it records
what an agent believes, including things it was successfully lied to about. A
harness that reconciled memory against the board would destroy the phenomenon
the project exists to study.

Implemented as an explicit subsystem rather than left to whatever the framework
does implicitly — that is the only way the three stacks can be compared on it
fairly, and it is one of the capability-matrix rows most likely to separate
them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: The kinds the event schema allows.
KINDS = ("opponent_model", "commitment", "strategy", "observation")

#: What an unclassified note becomes. Never guessed at: inventing a
#: `commitment` would be fabricating a fact about the game.
DEFAULT_KIND = "observation"


@dataclass(frozen=True)
class Note:
    kind: str
    text: str
    turn: int
    about: str | None = None


@dataclass
class Memory:
    """One agent's private notes."""

    color: str
    notes: list[Note] = field(default_factory=list)
    #: Facts folded in from compaction, kept separate so they are never dropped.
    durable: list[str] = field(default_factory=list)

    def write(self, text: str, turn: int, kind: str | None = None,
              about: str | None = None) -> Note:
        note = Note(kind if kind in KINDS else DEFAULT_KIND, text.strip(), turn, about)
        self.notes.append(note)
        return note

    def render(self, limit: int = 40) -> str:
        """The `{{memory}}` variable: what this agent believes, most recent last.

        Rendered here rather than in a template because the prompt language has
        no loops — by design.
        """
        lines = [f"- (durable) {fact}" for fact in self.durable]
        for note in self.notes[-limit:]:
            about = f" [{note.about}]" if note.about else ""
            lines.append(f"- turn {note.turn} ({note.kind}){about}: {note.text}")
        return "\n".join(lines) if lines else "(nothing yet)"

    def absorb(self, summary: str) -> None:
        """Fold a compaction summary in as a durable fact."""
        summary = summary.strip()
        if summary:
            self.durable.append(summary)
