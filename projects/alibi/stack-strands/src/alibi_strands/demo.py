"""One scripted case, end to end — free, offline, deterministic.

    uv run --directory projects/alibi/stack-strands python -m alibi_strands.demo out.jsonl

The whole stack runs — engine phases, agent loop, the archivist as a real
framework tool, hooks metering every call — with the "models" replaying the
committed script below. Same seed, same script, same bytes: the transcript is
the committed fixture ``projects/alibi/games/scripted-strands-seed7.jsonl``
(ADR-0007's rule, third game running).

The script tells the project's own moral as a five-turn story. On turn 1 red
searches the archive and is fed BOTH red herrings for seed 7 — the hatch
"bolted", the cloakroom "locked" — bluffs a suggestion with its own terrace,
and files a belief that is wrong in all three dimensions. On turn 5 red
cross-checks the witness (doc-009: Asha Nair left before ten), watches the
alibi collapse, and accuses correctly: photographer / service-hatch /
cloakroom. The table is facts; the archive is claims.
"""

from __future__ import annotations

import sys

from alibi_engine.case import COLORS
from alibi_engine.events import JsonlSink

from . import config, prompts
from .harness import AlibiHarness
from .scripted import ScriptedModel

#: A consultation costs two entries: the tool call, then the post-tool text.
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
            {c: ScriptedModel(list(SCRIPTS[c])) for c in COLORS},
            JsonlSink(f), seed=SEED,
        )
        outcome = harness.play()

    print(f"{out_path}: {outcome.reason} after {outcome.turns_played} turns, "
          f"{harness.hooks.calls} model calls, {harness.hooks.spent} scripted tokens")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m alibi_strands.demo <out.jsonl>")
    main(sys.argv[1])
