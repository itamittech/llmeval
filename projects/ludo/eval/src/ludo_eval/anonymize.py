"""The judge's view of a game: four anonymous players and a transcript.

Anonymisation is the load-bearing bias mitigation (evaluation.md): the judge
must not know which model sat where, which route served it, which framework
ran it — or who won. This module builds that view:

- **Relabelled.** Colours become ``Player A``–``Player D``, assignment
  shuffled by a seeded RNG *per judging run* — which serves two mitigations
  at once: identity leakage (labels carry nothing) and position bias (who
  gets presented first changes run to run).
- **Free text included.** Players *talk about* colours — "ally against
  yellow?" — so relabelling only structured fields would leak the mapping
  through every message. Colour words inside text fields are replaced too.
  (A model that says "the crimson one" defeats this; a known, documented
  limit of textual anonymisation, not a bug to paper over.)
- **Stripped.** ``llm_call`` events (model ids, access routes) and the
  identifying half of ``game_started`` never reach the view.
- **Outcome-blind.** ``game_ended`` is withheld — the judge scores decisions
  against the information available at the time, not against the final
  table. ``player_finished`` stays: a player going out mid-game is a fact
  the remaining players saw and reacted to.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from random import Random

from .transcript import COLORS

LABELS = ("Player A", "Player B", "Player C", "Player D")

#: Fields whose values are colours and must be relabelled structurally.
_COLOR_FIELDS = ("player", "to", "about", "captor", "victim", "active")

#: Fields carrying agent-authored text, where colour words hide.
_TEXT_FIELDS = ("text", "summary", "reason")

#: Event types the judge never sees.
_WITHHELD = {"llm_call", "game_ended"}


@dataclass(frozen=True)
class JudgeView:
    """One run's anonymised game."""

    labels: dict[str, str]        # colour -> "Player C"
    colors: dict[str, str]        # "Player C" -> colour (for mapping scores back)
    players: tuple[str, ...]      # labels in presentation order
    lines: tuple[str, ...]

    def transcript(self) -> str:
        return "\n".join(self.lines)


def anonymize(events: list[dict], seed: int) -> JudgeView:
    order = list(COLORS)
    Random(seed).shuffle(order)
    labels = {color: LABELS[i] for i, color in enumerate(order)}
    pattern = re.compile(r"\b(" + "|".join(COLORS) + r")\b", re.IGNORECASE)

    def relabel_text(text: str) -> str:
        return pattern.sub(lambda m: labels[m.group(1).lower()], text)

    lines: list[str] = []
    for event in events:
        type_, payload = event["type"], event["payload"]
        if type_ in _WITHHELD:
            continue
        if type_ == "game_started":
            lines.append(f"- [turn 0] game_started: "
                         + json.dumps({"ruleset": payload.get("ruleset"),
                                       "max_turns": payload.get("max_turns")},
                                      separators=(",", ":")))
            continue

        clean = dict(payload)
        for f in _COLOR_FIELDS:
            if isinstance(clean.get(f), str) and clean[f].lower() in labels:
                clean[f] = labels[clean[f].lower()]
        for f in _TEXT_FIELDS:
            if isinstance(clean.get(f), str):
                clean[f] = relabel_text(clean[f])
        lines.append(f"- [turn {event['turn']}] {type_}: "
                     + json.dumps(clean, separators=(",", ":")))

    return JudgeView(
        labels=labels,
        colors={label: color for color, label in labels.items()},
        players=tuple(LABELS),
        lines=tuple(lines),
    )
