"""The live judge caller — a seam today, a client when the id lands.

`shared/models.yaml` seats the judge with OpenAI (`judge: provider: openai`),
deliberately a family that does not play (evaluation.md's self-preference
mitigation), and its model id is still TBD — the same open question blocking
every live call in this repo. Until it lands, constructing the live judge
fails loudly rather than quietly constructing something unpinned; tests drive
:func:`ludo_eval.judge.run_judge` through scripted callers instead, which is
the same offline discipline as the three stacks' scripted models.
"""

from __future__ import annotations

from typing import Callable


def live_judge(model: str | None) -> Callable[[str], str]:
    raise NotImplementedError(
        "the judge model id in shared/models.yaml is TBD (open question: "
        "concrete model IDs); the OpenAI client arrives when it lands")
