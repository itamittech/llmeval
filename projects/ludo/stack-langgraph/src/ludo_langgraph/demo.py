"""One scripted game, end to end — free, offline, deterministic.

    uv run --directory projects/ludo/stack-langgraph python -m ludo_langgraph.demo out.jsonl

This is the whole stack running: the engine drives the turns, negotiation runs
on the table graph, memory lands in the framework's Store, the callback meter
counts every call — with the one difference that the "model" replays the
committed script below. Same seed, same script, same bytes: the transcript it
writes is the committed UI fixture
`projects/ludo/games/scripted-langgraph-seed7.jsonl` (ADR-0007 — adding a
stack means adding its transcript to the fixture set).

The script tells the same tiny story as the other stacks' fixtures — red
proposes an alliance with a table note, blue accepts — then plays generic
moves whose legality is the dice's problem. The rhythm differs from both:
this graph gives a speaker ONE call per successful pass (the floor moves on
the tool result), so a pass costs one entry, and a closing remark costs one.
"""

from __future__ import annotations

import sys

from ludo_engine.board import COLORS
from ludo_engine.events import JsonlSink

from . import config, prompts
from .harness import LudoHarness
from .scripted import ScriptedChatModel

DECIDES = ['{"token": 0, "to": 0, "reasoning": "press on"}'] * 7
REFLECTS = ['{"notes": [{"kind": "strategy", "text": "long game ahead"}]}'] * 2

#: One entry per floor holding: a pass is a tool entry, a lapse is text.
SCRIPTS: dict[str, list] = {
    "red": [
        {"tool": {"to": "blue", "message": "ally against yellow?",
                  "note": "I want a quiet table"}},
        "nothing further",
    ] + DECIDES + REFLECTS,
    "blue": [
        {"tool": {"to": "red", "message": "agreed - yellow first"}},
        "(quiet)",
    ] + DECIDES + REFLECTS,
    "green": ["(quiet)"] + DECIDES + REFLECTS,
    "yellow": ["(quiet)"] + DECIDES + REFLECTS,
}

SEED = 7
MAX_TURNS = 4


def main(out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        harness = LudoHarness(
            config.load("dev"), prompts.load(),
            {c: ScriptedChatModel(script=list(SCRIPTS[c])) for c in COLORS},
            JsonlSink(f), seed=SEED, max_turns=MAX_TURNS,
        )
        outcome = harness.play()

    print(f"{out_path}: {outcome.reason} after {outcome.turns_played} turns, "
          f"{harness.meter.calls} model calls, {harness.meter.spent} scripted tokens")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m ludo_langgraph.demo <out.jsonl>")
    main(sys.argv[1])
