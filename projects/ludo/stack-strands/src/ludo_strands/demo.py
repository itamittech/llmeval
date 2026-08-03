"""One scripted game, end to end — free, offline, deterministic.

    uv run --directory projects/ludo/stack-strands python -m ludo_strands.demo out.jsonl

This is the whole stack running: the engine drives the turns, negotiation runs
on the Swarm orchestrator, memory lands in agent state, hooks meter every
call — with the one difference that the "model" replays the committed script
below. Same seed, same script, same bytes: the transcript it writes is the
committed UI fixture `projects/ludo/games/scripted-strands-seed7.jsonl`
(ADR-0007 — adding a stack means adding its transcript to the fixture set).

The script tells a tiny story on turn 1 — red proposes an alliance with a
table note, blue accepts — and then plays generic moves whose legality is the
dice's problem. Forfeits are valid outcomes; the transcript stays well-formed
through all of them.
"""

from __future__ import annotations

import sys

from ludo_engine.board import COLORS
from ludo_engine.events import JsonlSink

from . import config, prompts
from .harness import LudoHarness
from .scripted import ScriptedModel

DECIDES = ['{"token": 0, "to": 0, "reasoning": "press on"}'] * 7
REFLECTS = ['{"notes": [{"kind": "strategy", "text": "long game ahead"}]}'] * 2

#: A handoff costs two entries: the tool call, then the post-tool text.
SCRIPTS: dict[str, list] = {
    "red": [
        {"handoff": {"to": "blue", "message": "ally against yellow?",
                     "note": "I want a quiet table"}},
        "(floor passed)",
        "nothing further",
    ] + DECIDES + REFLECTS,
    "blue": [
        {"handoff": {"to": "red", "message": "agreed - yellow first"}},
        "(floor passed)",
        "(quiet)",
    ] + DECIDES + REFLECTS,
    "green": ["(quiet)"] * 2 + DECIDES + REFLECTS,
    "yellow": ["(quiet)"] * 2 + DECIDES + REFLECTS,
}

SEED = 7
MAX_TURNS = 4


def main(out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        harness = LudoHarness(
            config.load("dev"), prompts.load(),
            {c: ScriptedModel(list(SCRIPTS[c])) for c in COLORS},
            JsonlSink(f), seed=SEED, max_turns=MAX_TURNS,
        )
        outcome = harness.play()

    print(f"{out_path}: {outcome.reason} after {outcome.turns_played} turns, "
          f"{harness.hooks.calls} model calls, {harness.hooks.spent} scripted tokens")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m ludo_strands.demo <out.jsonl>")
    main(sys.argv[1])
