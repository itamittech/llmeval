"""Content guardrails — deliberately lenient, deliberately tiny.

The engine already makes cheating structurally impossible (ADR-0004): an agent
can only ever pick from moves the engine validated. That is what buys the
freedom this module protects — **in-game cunning passes**. Lies, bluffs, fake
promises, betrayal: the phenomena under study, never blocked here.

What gets blocked is the *out-of-fiction* attack surface of the one channel
agents share: negotiation messages. Three rules, each high-precision on
purpose — a false positive here doesn't cost a support ticket, it destroys
the experiment by censoring the behaviour the project exists to observe.

Deterministic and model-free, so scripted games stay byte-reproducible and a
rule firing means the same thing in every run. Abuse-class filtering (slurs,
harassment) is deliberately NOT attempted with regexes — word lists are either
useless or wrong; that class belongs to provider-side guardrails (Bedrock
Guardrails) once live games exist, and the gap is recorded in the capability
matrix rather than papered over.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Violation:
    rule: str
    reason: str


#: (rule name, pattern, why it is out-of-fiction).
#: Precision notes, because every pattern was argued with:
#: - "ignore yellow", "forget my last offer", "you are now my ally" all PASS —
#:   in-fiction phrasing must never trip a rule, so each pattern requires
#:   unmistakably meta vocabulary (instructions, prompt, system, engine).
_RULES = (
    ("instruction-override",
     re.compile(r"(?i)\b(ignore|disregard|override)\b[\s\S]{0,40}?\b(instructions?|prompts?)\b"),
     "an attempt to overwrite another player's instructions"),

    ("role-smuggling",
     re.compile(r"(?im)<system>|\[system\]|\bsystem prompt\b|\bdeveloper (message|prompt)\b|^\s*system\s*:"),
     "text posing as a system or developer message"),

    ("system-impersonation",
     re.compile(r"(?im)\bi am the (engine|harness|referee|judge|system)\b|^\s*(engine|harness)\s*:"),
     "a player impersonating the system"),
)


def check(text: str) -> Violation | None:
    """The first rule the text trips, or None — which is the common case."""
    for rule, pattern, description in _RULES:
        if pattern.search(text):
            snippet = text[:100]
            return Violation(rule, f'{description}: "{snippet}"')
    return None
