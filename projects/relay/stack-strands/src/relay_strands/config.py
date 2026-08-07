"""Reading ``shared/models.yaml`` — RELAY's own lanes, budgets and anchor.

The first game in this repo that does *not* read the four shared seats. Its
runners are small models on local hardware, so a lane carries a quantisation
knob a hosted API has no equivalent for, and ``access`` has a third value.
Nothing here decides anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .prompts import repo_root


@dataclass(frozen=True)
class Lane:
    lane: int
    access: str          # local | bedrock | direct
    provider: str
    model: str
    quantisation: str | None = None

    @property
    def pinned(self) -> bool:
        return self.model not in (None, "", "TBD")


@dataclass(frozen=True)
class Anchor:
    provider: str
    access: str
    model: str


@dataclass(frozen=True)
class Budgets:
    max_turns: int
    escalation_quota: int
    max_note_chars: int
    #: Hard per-game ceiling across every lane AND the anchor (contract §6).
    max_tokens_per_game: int


@dataclass(frozen=True)
class Profile:
    name: str
    lanes: tuple[Lane, ...]
    budgets: Budgets
    anchor: Anchor
    inference: dict[str, Any]

    def inference_for(self, provider: str) -> dict[str, Any]:
        settings = {k: v for k, v in self.inference.items() if not isinstance(v, dict)}
        settings.update(self.inference.get(provider, {}))
        return settings


def load(name: str = "dev", path: Path | None = None) -> Profile:
    path = path or (repo_root() / "shared" / "models.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    relay = raw["relay"]
    if name not in relay["budgets"]:
        raise KeyError(f"no profile {name!r}; have {sorted(relay['budgets'])}")

    lanes = tuple(
        Lane(lane["lane"], lane["access"], lane["provider"], lane.get("model"),
             lane.get("quantisation"))
        for lane in sorted(relay["lanes"], key=lambda lane: lane["lane"])
    )
    b = relay["budgets"][name]
    a = relay["anchor"]
    return Profile(
        name=name,
        lanes=lanes,
        budgets=Budgets(b["max_turns"], b["escalation_quota"], b["max_note_chars"],
                        b["max_tokens_per_game"]),
        anchor=Anchor(a["provider"], a["access"], a["model"]),
        inference=raw.get("inference", {}),
    )


def lane_assignment(profile: Profile, colors: tuple[str, ...], game_index: int = 0
                    ) -> dict[str, Lane]:
    """Lane -> colour for one race, rotating with ``game_index`` (ADR-0006).

    Turn order is an advantage here in a way it never was in LUDO: the runner
    who moves first reaches the shared pool first. Rotating is not decoration.
    """
    n = len(colors)
    return {colors[i]: profile.lanes[(i + game_index) % n] for i in range(n)}
