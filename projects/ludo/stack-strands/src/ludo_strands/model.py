"""The model boundary — and the seam the harness contract requires.

Everything above this module talks to :class:`ModelClient`. Two implementations
exist: one that calls a provider, and one that replays a committed script and
never touches the network.

BEING REPLACED per ADR-0008 (docs/decisions/adr-0008-framework-native-harness.md):
the *requirement* — an injectable scripted model, so all three stacks can be
compared on the same script — survives, but contract §8 now demands it go
through the framework's own extension point. For Strands that means a custom
``Model`` implementation, not this parallel Protocol beside the framework.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from .budget import Usage


@dataclass(frozen=True)
class Reply:
    text: str
    usage: Usage
    #: Wall-clock, milliseconds. None for scripted replies — there was no call
    #: to time, and inventing a number would put fiction in the transcript.
    latency_ms: int | None = None


class ModelClient(Protocol):
    """What the harness needs from a model. Deliberately tiny."""

    #: Model id as the transcript should record it.
    model: str
    #: "bedrock" or "direct" — the field ADR-0005's whole comparison rests on.
    access: str

    def complete(self, system: str, user: str, purpose: str) -> Reply: ...


class ScriptedModel:
    """Replays canned replies in order. No network, no keys, no cost.

    Used by the harness tests and by cross-stack conformance. Running out of
    script is an error rather than a silent fallback: a stack that quietly
    invented a reply would produce a transcript nobody could reproduce.
    """

    def __init__(self, replies: list[str], *, model: str = "scripted",
                 access: str = "direct", tokens_per_reply: int = 100) -> None:
        self._replies = list(replies)
        self._index = 0
        self.model = model
        self.access = access
        self._tokens = tokens_per_reply
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, purpose: str) -> Reply:
        self.calls.append((purpose, user))
        if self._index >= len(self._replies):
            raise IndexError(
                f"scripted model exhausted after {self._index} replies "
                f"(asked for {purpose})"
            )
        text = self._replies[self._index]
        self._index += 1
        # Deterministic, so a scripted run has stable token counts across stacks.
        return Reply(text, Usage(input=self._tokens, output=self._tokens // 2))


def parse_json_reply(text: str) -> dict[str, Any]:
    """Pull the JSON object out of a model reply.

    Models wrap JSON in prose or fences more often than not, and the prompts ask
    for a bare object. Tolerating the wrapper is not the same as tolerating
    nonsense: anything that does not contain a parseable object raises, and the
    caller treats that as a failed turn rather than guessing what was meant.
    """
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else None

    if candidate is None:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError(f"no JSON object in reply: {text[:120]!r}")
        candidate = text[start:end + 1]

    return json.loads(candidate)
