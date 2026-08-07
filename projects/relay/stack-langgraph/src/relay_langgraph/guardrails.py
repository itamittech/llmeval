"""Structural guardrails on RELAY's one free-text channel.

ADR-0004, third game, same stance: block out-of-fiction attacks, let cunning
through. What counts as cunning here is specific and worth naming, because a
careless rule would kill the game — **a note that lies about a stage's
difficulty, or talks a rival into burning the shared pool, is the intended
play.** Only a note trying to break the frame is blocked.

Three rules, all structural rather than semantic:

1. **Instruction injection** — a note addressing the reader as a model rather
   than as a rival.
2. **Forged state** — a note claiming engine authority: that the quota is
   larger than it is, that a stage was cleared, that the engine says anything.
3. **Claimed tier knowledge** — RELAY's own rule, and the one no other game
   needs. Nobody knows a stage's tier, so a note asserting one is either a lie
   (fine, in-fiction) or a leak (not). Blocking the *claim* is the wrong call,
   so this rule only fires when a note claims to have been *told* — which is a
   claim about the system, not about the race.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

INJECTION = re.compile(
    r"ignore (all |the )?(previous|prior|above) (instructions|prompt)"
    r"|disregard your (instructions|system prompt|rules)"
    r"|you are (now|actually) (a|an) \w+"
    r"|system prompt:"
    r"|<\s*/?\s*(system|instructions)\s*>",
    re.I,
)

FORGED_STATE = re.compile(
    r"\bthe engine (says|confirms|ruled|has|awarded)"
    r"|\bofficial(ly)? (ruling|result)"
    r"|\byour quota (is|has been) (increased|restored|unlimited)"
    r"|\b(referee|engine) (grants|gives) you\b",
    re.I,
)

LEAKED_TIER = re.compile(
    r"\bi (was|have been) (told|shown|given) (the|its|this) tier"
    r"|\bthe (engine|referee|system) (told|showed) me (the|its) tier"
    r"|\btrack[_ ]key\b",
    re.I,
)


@dataclass(frozen=True)
class Violation:
    rule: str
    reason: str


def check(note: str) -> Violation | None:
    if INJECTION.search(note):
        return Violation("instruction_injection",
                         "note addresses the reader as a model, not as a rival")
    if FORGED_STATE.search(note):
        return Violation("forged_state",
                         "note claims engine authority it cannot have")
    if LEAKED_TIER.search(note):
        return Violation("claimed_seal_access",
                         "note claims to have been told a stage's tier")
    return None
