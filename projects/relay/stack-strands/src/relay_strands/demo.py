"""A full scripted race — offline, free, byte-reproducible.

    python -m relay_strands.demo out.jsonl

Regenerates the committed fixture exactly. That is the contract §9 deliverable:
the UI and the eval are built against it, and three stacks replaying the same
seed are what makes the comparison mean anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

from relay_engine.deciders import COLORS
from relay_engine.events import JsonlSink

from . import config as config_mod, policies, prompts as prompts_mod
from .harness import RelayHarness
from .scripted import PolicyModel

SEED = 7
#: Short enough to read end to end, long enough that the pool runs dry and the
#: lanes have to live with what the spendthrift left them.
MAX_TURNS = 24


def build(sink, seed: int = SEED, max_turns: int = MAX_TURNS) -> RelayHarness:
    profile = config_mod.load("dev")
    models = {
        color: PolicyModel(policies.RUNNERS[color], model_id=f"scripted-{color}")
        for color in COLORS
    }
    anchor = PolicyModel(policies.anchor, model_id="scripted-anchor")
    return RelayHarness(
        profile=profile,
        prompts=prompts_mod.load(),
        anchor_prompt=prompts_mod.load_anchor(),
        models=models,
        anchor_model=anchor,
        sink=sink,
        seed=seed,
        max_turns=max_turns,
    )


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    out = Path(argv[0]) if argv else Path("relay-strands.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8", newline="\n") as fh:
        sink = JsonlSink(fh)
        harness = build(sink)
        outcome = harness.play()

    print(f"wrote {out}")
    print(f"reason={outcome.reason} turns={outcome.turns_played} "
          f"quota_left={harness.game.quota} calls={harness.hooks.calls}")
    for row in outcome.standings:
        print(f"  {row['rank']}. {row['player']:<7} stages={row['stages_cleared']:>2} "
              f"ticks={row['ticks']:>3} escalations={row['escalations']} "
              f"correct={row['correct']} wrong={row['wrong']} passes={row['passes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
