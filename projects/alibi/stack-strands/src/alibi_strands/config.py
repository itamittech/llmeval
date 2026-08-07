"""Reading ``shared/models.yaml`` — seats from the shared profiles, budgets and
the archivist from the ``alibi`` section. Nothing here decides anything."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .prompts import repo_root


@dataclass(frozen=True)
class Seat:
    seat: int
    access: str          # bedrock | direct
    provider: str
    model: str

    @property
    def pinned(self) -> bool:
        return self.model not in (None, "", "TBD")


@dataclass(frozen=True)
class Budgets:
    max_turns: int
    max_searches_per_turn: int
    max_note_chars: int
    #: Hard per-game ceiling across all seats AND the archivist (contract §5).
    max_tokens_per_game: int


@dataclass(frozen=True)
class Archivist:
    provider: str
    access: str
    model: str
    retrieval_profile: str


@dataclass(frozen=True)
class Profile:
    name: str
    seats: tuple[Seat, ...]
    budgets: Budgets
    archivist: Archivist
    inference: dict[str, Any]

    def inference_for(self, provider: str) -> dict[str, Any]:
        settings = {k: v for k, v in self.inference.items() if not isinstance(v, dict)}
        settings.update(self.inference.get(provider, {}))
        return settings


def load(name: str = "dev", path: Path | None = None) -> Profile:
    path = path or (repo_root() / "shared" / "models.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    if name not in raw["profiles"]:
        raise KeyError(f"no profile {name!r}; have {sorted(raw['profiles'])}")
    seats = tuple(
        Seat(s["seat"], s["access"], s["provider"], s.get("model"))
        for s in sorted(raw["profiles"][name]["seats"], key=lambda s: s["seat"])
    )

    alibi = raw["alibi"]
    b = alibi["budgets"][name]
    a = alibi["archivist"]
    return Profile(
        name=name,
        seats=seats,
        budgets=Budgets(b["max_turns"], b["max_searches_per_turn"],
                        b["max_note_chars"], b["max_tokens_per_game"]),
        archivist=Archivist(a["provider"], a["access"], a["model"],
                            a["retrieval_profile"]),
        inference=raw.get("inference", {}),
    )


def seating(profile: Profile, colors: tuple[str, ...], game_index: int = 0
            ) -> dict[str, Seat]:
    """Seat -> colour for one game, rotating with ``game_index`` (ADR-0006)."""
    n = len(colors)
    return {
        colors[i]: profile.seats[(i + game_index) % n]
        for i in range(n)
    }
