"""Content guardrails — lenient by design (ADR-0004), same line as LUDO's.

In-fiction cunning passes: bluff suggestions, lying table notes, misdirection.
Blocked are the three out-of-fiction attacks the harness contract names:

    injection   — prompting the archivist, a rival, or the harness to break role
    authority   — claiming the engine or the case file as a source
    forgery     — citing an archive document id that does not exist

A note citing a REAL document is in-fiction argument and passes — possibly a
misleading one, which is the game. Only invented evidence is an attack on the
system rather than on the players.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

INJECTION = re.compile(
    r"ignore (all |your |previous |the )?(instructions?|prompts?)"
    r"|disregard (your|the) (instructions?|system prompt)"
    r"|you are now\b"
    r"|system prompt",
    re.IGNORECASE,
)

AUTHORITY = re.compile(
    r"the engine (confirms|says|revealed|shows)"
    r"|the case file (confirms|shows|proves|names)"
    r"|the referee (confirms|says)",
    re.IGNORECASE,
)

CITATION = re.compile(r"\[?(doc-\d{3})\]?")


@dataclass(frozen=True)
class Violation:
    rule: str
    reason: str


def check(text: str, valid_doc_ids: frozenset[str] = frozenset()) -> Violation | None:
    """Return the violation, or None when the text is merely cunning."""
    if INJECTION.search(text):
        return Violation("injection", "instructions aimed at the system, not the players")
    if AUTHORITY.search(text):
        return Violation("authority", "claims the engine or case file as a source")
    for cited in CITATION.findall(text):
        if cited not in valid_doc_ids:
            return Violation("forgery", f"cites {cited}, which does not exist in the archive")
    return None
