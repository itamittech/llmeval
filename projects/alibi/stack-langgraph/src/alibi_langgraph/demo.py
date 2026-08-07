"""One scripted case, end to end — free, offline, deterministic.

    uv run --directory projects/alibi/stack-langgraph python -m alibi_langgraph.demo out.jsonl

**The same seed and the same story as the Strands fixture, deliberately.**
Three stacks playing identical scripted decisions produce transcripts whose
engine-event skeletons must agree — that is the cross-stack conformance the
eval mechanises. What differs between the fixtures is exactly what differs
between the frameworks: message shapes, call granularity, token estimates.

Consultation entries are ``{"consult": "query"}``; a consultation costs two
script entries, the tool call and the post-tool reply.
"""

from __future__ import annotations

import sys

from alibi_engine.case import COLORS
from alibi_engine.events import JsonlSink

from . import config, prompts
from .harness import AlibiHarness
from .scripted import ScriptedChatModel

SCRIPTS: dict[str, list] = {
    "red": [
        # -- turn 1: seduced by the archive --
        {"consult": "photographer cloakroom service hatch"},
        '{"action": "suggest", "who": "magician", "how": "service-hatch", '
        '"where": "terrace", "note": "The service hatch keeps coming up in the logs.", '
        '"reasoning": "Bluff my own terrace, probe the magician, and watch who twitches '
        'at the hatch."}',
        '{"action": "wait"}',
        '{"who": "heiress", "how": "duplicate-key", "where": "vault-room", '
        '"confidence": {"who": 0.25, "how": 0.3, "where": 0.2}}',
        '[{"kind": "observation", "about": "photographer", "text": "Asha Nair puts the '
        'photographer on the main stage all night. Check Nair before trusting it."}, '
        '{"kind": "plan", "text": "Hatch and cloakroom both conveniently ruled out. '
        'Verify those witnesses too."}]',
        # -- turn 5: the cross-check --
        {"consult": "security guard Asha Nair"},
        '{"action": "pass", "reasoning": "Nair left before ten. Her photographer alibi '
        'is secondhand, and the other two convenient exonerations smell the same."}',
        '{"action": "accuse", "who": "photographer", "how": "service-hatch", '
        '"where": "cloakroom", "reasoning": "Strike the lying witnesses and the case '
        'reads plainly: no alibi, a hatch that was never bolted, a cloakroom that was '
        'never watched."}',
        '[{"kind": "deduction", "about": "photographer", "text": "Nair was in the car '
        'park by ten. The photographer never had an alibi."}]',
    ],
    "green": [
        '{"show": "magician"}',
        '{"action": "pass", "reasoning": "Watch the table before spending questions."}',
        '{"action": "wait"}',
        '{"who": "photographer", "how": "sleight-of-hand", "where": "terrace", '
        '"confidence": {"who": 0.2, "how": 0.2, "where": 0.125}}',
        '[]',
    ],
    "yellow": [
        '{"action": "pass"}',
        '{"action": "wait"}',
        '{"who": "photographer", "how": "service-hatch", "where": "kitchen", '
        '"confidence": {"who": 0.2, "how": 0.25, "where": 0.14}}',
        '[{"kind": "suspicion", "about": "red", "text": "Red pushed the hatch in an '
        'open note. Either a lead or a plant."}]',
    ],
    "blue": [
        '{"action": "pass"}',
        '{"action": "wait"}',
        '{"who": "chef", "how": "duplicate-key", "where": "cloakroom", '
        '"confidence": {"who": 0.2, "how": 0.25, "where": 0.14}}',
        '[]',
    ],
}

SEED = 7


def main(out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        harness = AlibiHarness(
            config.load("dev"), prompts.load(),
            {c: ScriptedChatModel(script=list(SCRIPTS[c]), seen=[]) for c in COLORS},
            JsonlSink(f), seed=SEED,
        )
        outcome = harness.play()

    print(f"{out_path}: {outcome.reason} after {outcome.turns_played} turns, "
          f"{harness.meter.calls} model calls, {harness.meter.spent} scripted tokens")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m alibi_langgraph.demo <out.jsonl>")
    main(sys.argv[1])
