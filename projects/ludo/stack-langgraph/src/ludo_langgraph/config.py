"""Reading ``shared/models.yaml``.

Seats, routes, budgets and inference settings all come from that file. Nothing
here decides anything — a stack that picked its own temperature, or its own
turn cap, would be a stack the comparison cannot use.
"""

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
    #: Floor passes per negotiation phase (ADR-0009) — maps to the swarm
    #: orchestrator's handoff cap.
    max_floor_passes: int
    max_message_chars: int
    #: Per-agent conversation budget (harness-contract §5) — over it, the
    #: oldest exchanges are summarised into memory and dropped.
    max_context_tokens: int
    max_tokens_per_game: int


@dataclass(frozen=True)
class Profile:
    name: str
    seats: tuple[Seat, ...]
    judge: Seat
    budgets: Budgets
    #: Per-provider inference settings. Not uniform across families: the Claude
    #: 5 models reject temperature/top_p and take `effort` instead, while Nova
    #: and DeepSeek do the opposite. See the capability matrix.
    inference: dict[str, Any]

    def seat(self, number: int) -> Seat:
        for s in self.seats:
            if s.seat == number:
                return s
        raise KeyError(f"no seat {number} in profile {self.name}")

    def unpinned(self) -> tuple[Seat, ...]:
        """Seats whose model id is still TBD — they cannot be played live."""
        return tuple(s for s in self.seats if not s.pinned)

    def inference_for(self, provider: str) -> dict[str, Any]:
        settings = {k: v for k, v in self.inference.items() if not isinstance(v, dict)}
        settings.update(self.inference.get(provider, {}))
        return settings


def load(name: str = "dev", path: Path | None = None) -> Profile:
    path = path or (repo_root() / "shared" / "models.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    if name not in raw["profiles"]:
        raise KeyError(f"no profile {name!r}; have {sorted(raw['profiles'])}")
    spec = raw["profiles"][name]

    seats = tuple(
        Seat(s["seat"], s["access"], s["provider"], s.get("model"))
        for s in sorted(spec["seats"], key=lambda s: s["seat"])
    )
    judge = Seat(0, spec["judge"]["access"], spec["judge"]["provider"],
                 spec["judge"].get("model"))

    b = spec["budgets"]
    return Profile(
        name=name,
        seats=seats,
        judge=judge,
        budgets=Budgets(b["max_turns"], b["max_floor_passes"],
                        b["max_message_chars"], b["max_context_tokens"],
                        b["max_tokens_per_game"]),
        inference=raw.get("inference", {}),
    )


def seating(profile: Profile, colors: tuple[str, ...], game_index: int = 0
            ) -> dict[str, Seat]:
    """Assign seats to colours for one game, rotating with ``game_index``.

    Turn order is an advantage in principle, and a fixed mapping would bake any
    colour-linked effect permanently into the model comparison. Rotating costs
    nothing now and is unfixable later — ADR-0006.

    A full rotation is four games, so any run supporting a claim about models
    should be a multiple of four.
    """
    n = len(colors)
    return {
        colors[i]: profile.seats[(i + game_index) % n]
        for i in range(n)
    }
