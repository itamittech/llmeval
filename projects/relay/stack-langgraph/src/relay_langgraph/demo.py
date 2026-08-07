"""A full scripted race — offline, free, byte-reproducible.

    python -m relay_langgraph.demo out.jsonl

Same seed and same policies as the Strands stack, which is the whole point: the
engine spine must come out identical, event for event, or the two harnesses are
not comparable and every number below them is noise.
"""

from __future__ import annotations

import sys
from pathlib import Path

from relay_engine.deciders import COLORS
from relay_engine.events import JsonlSink

from . import config as config_mod, policies, prompts as prompts_mod
from .harness import RelayHarness
from .scripted import PolicyChatModel

SEED = 7
MAX_TURNS = 24


def build(sink, seed: int = SEED, max_turns: int = MAX_TURNS) -> RelayHarness:
    profile = config_mod.load("dev")
    models = {
        color: PolicyChatModel(decide=policies.RUNNERS[color],
                               model_label=f"scripted-{color}", seen=[], seen_rendered=[])
        for color in COLORS
    }
    anchor = PolicyChatModel(decide=policies.anchor, model_label="scripted-anchor",
                             seen=[], seen_rendered=[])
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
    out = Path(argv[0]) if argv else Path("relay-langgraph.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8", newline="\n") as fh:
        harness = build(JsonlSink(fh))
        outcome = harness.play()

    print(f"wrote {out}")
    print(f"reason={outcome.reason} turns={outcome.turns_played} "
          f"quota_left={harness.game.quota} calls={harness.meter.calls}")
    for row in outcome.standings:
        print(f"  {row['rank']}. {row['player']:<7} stages={row['stages_cleared']:>2} "
              f"ticks={row['ticks']:>3} escalations={row['escalations']} "
              f"correct={row['correct']} wrong={row['wrong']} passes={row['passes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
