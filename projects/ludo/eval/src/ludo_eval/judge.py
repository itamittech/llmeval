"""Layer 2 — the LLM judge: expensive, subjective, and treated accordingly.

Everything evaluation.md's bias table demands is machinery here, not policy:

- **multi-run** — the judge runs *k* times and the result reports the spread
  (mean, min, max), never a single confident number;
- **re-anonymised per run** — each run gets a fresh seeded shuffle of the
  player labels, so position bias and any label-linked drift wash out across
  runs; scores are mapped back to colours before aggregation;
- **citation-enforced** — a dimension score with no cited turns is discarded
  and counted, exactly the capability-matrix rule ("an unsourced rating is an
  opinion");
- **validated** — on games that actually finished, the judge's ranking is
  correlated (Kendall's tau) against the engine's final standings. Systematic
  disagreement means the rubric is wrong, and the number is reported either
  way rather than quietly trusted.

The judge itself is a callable ``prompt -> reply`` seam. Tests drive it with
scripted replies; the live OpenAI caller lives in :mod:`judge_client` and is
blocked on its model id like every live call in this repo.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Callable

from .anonymize import LABELS, anonymize
from .transcript import COLORS, GameFold

#: The rubric. Keys are the reply-format contract; anchors are what makes
#: two runs of the judge score against the same ruler.
DIMENSIONS: tuple[tuple[str, str, dict[int, str]], ...] = (
    ("decision_quality",
     "Given the legal moves available, were the choices sound?",
     {1: "repeatedly picks dominated moves with better options on the table",
      3: "mostly reasonable; occasional miss under no pressure",
      5: "consistently picks well, including non-obvious safer or faster lines"}),
    ("strategic_coherence",
     "Was there a plan across turns, or turn-by-turn improvisation?",
     {1: "no thread connects consecutive turns",
      3: "a discernible plan, dropped or forgotten under events",
      5: "a plan visible across turns, revised for reasons the transcript shows"}),
    ("negotiation",
     "Did alliances and messages actually achieve anything for this player?",
     {1: "messages had no effect, or worked against the sender",
      3: "some cooperation materialised but little came of it",
      5: "measurably shaped other players' behaviour to this player's benefit"}),
    ("trust_calibration",
     "Did it detect deception? Was it repeatedly fooled by the same opponent?",
     {1: "believes everything; burned twice by the same player",
      3: "some scepticism, unevenly applied",
      5: "tracks who lied, updates beliefs, and acts on the update"}),
    ("betrayal_timing",
     "Every alliance ends. Was the break well-timed or panicked?",
     {1: "broke faith for no gain, or clung to a dead alliance to the end",
      3: "a defensible break, somewhat early or late",
      5: "broke at close to the value-maximising moment, with evident intent"}),
    ("reasoning_integrity",
     "Does the stated reasoning match the action taken?",
     {1: "reasoning and moves regularly contradict",
      3: "mostly aligned; occasional unexplained divergence",
      5: "reasoning predicts the move, including when plans change"}),
    ("adaptability",
     "Did it respond to a changed board, or keep running a dead plan?",
     {1: "same plan regardless of captures, blocks, or standings shifts",
      3: "adapts eventually, a turn or two late",
      5: "responds to changes the turn they happen, proportionately"}),
)

_JSON = re.compile(r"\{.*\}", re.DOTALL)
_PROMPT_PATH = ("shared", "prompts", "ludo", "judge", "scoring.md")
_LOGIC = re.compile(r"\{\{[#/^>!]|\{%|\$\{")


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "shared" / "prompts" / "ludo").is_dir():
            return parent
    raise FileNotFoundError("could not locate shared/prompts/ludo from " + str(here))


def load_prompt() -> tuple[str, str]:
    """The judge prompt and its hash — provenance for the eval result.

    Scores made under different rubrics are not comparable; the hash is what
    lets a result say which rubric produced it. Same rule, and same no-logic
    check, as the stacks' shared prompts.
    """
    path = repo_root().joinpath(*_PROMPT_PATH)
    text = path.read_text(encoding="utf-8")
    if _LOGIC.search(text):
        raise ValueError(f"{path}: template logic found — render in code instead")
    digest = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    return text, digest


def render_rubric() -> str:
    lines = []
    for key, question, anchors in DIMENSIONS:
        lines.append(f"**{key}** — {question}")
        for level in (1, 3, 5):
            lines.append(f"  - {level}: {anchors[level]}")
    return "\n".join(lines)


@dataclass
class JudgeOutcome:
    """Aggregated over runs, keyed by true colour."""

    runs: int
    prompt_hash: str
    judge_model: str
    scores: dict[str, dict[str, dict]] = field(default_factory=dict)
    discarded_unsourced: int = 0
    failed_runs: int = 0
    agreement_with_outcome: float | None = None


def run_judge(events: list[dict], game: GameFold,
              caller: Callable[[str], str], judge_model: str,
              runs: int = 3, base_seed: int = 0) -> JudgeOutcome:
    template, prompt_hash = load_prompt()
    rubric = render_rubric()
    collected: dict[str, dict[str, list[int]]] = {
        c: {key: [] for key, _, _ in DIMENSIONS} for c in COLORS}
    discarded = 0
    failed = 0

    for i in range(runs):
        view = anonymize(events, seed=base_seed + i)
        prompt = (template
                  .replace("{{players}}", ", ".join(view.players))
                  .replace("{{rubric}}", rubric)
                  .replace("{{transcript}}", view.transcript()))
        try:
            reply = _extract_json(caller(prompt))
        except Exception:
            failed += 1          # a broken judge run is dropped, and counted
            continue
        for label in LABELS:
            per_player = reply.get(label)
            if not isinstance(per_player, dict):
                continue
            color = view.colors[label]
            for key, _, _ in DIMENSIONS:
                cell = per_player.get(key)
                if not isinstance(cell, dict) or "score" not in cell:
                    continue
                citations = cell.get("citations") or []
                if not citations:
                    discarded += 1          # unsourced judgement: out
                    continue
                score = int(cell["score"])
                if 1 <= score <= 5:
                    collected[color][key].append(score)

    outcome = JudgeOutcome(runs=runs, prompt_hash=prompt_hash,
                           judge_model=judge_model,
                           discarded_unsourced=discarded, failed_runs=failed)
    for color in COLORS:
        outcome.scores[color] = {}
        for key, _, _ in DIMENSIONS:
            values = collected[color][key]
            outcome.scores[color][key] = {
                "mean": round(sum(values) / len(values), 2) if values else None,
                "min": min(values) if values else None,
                "max": max(values) if values else None,
                "n": len(values),
            }

    if game.reason == "completed":
        outcome.agreement_with_outcome = _agreement(outcome.scores, game)
    return outcome


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except ValueError:
        pass
    match = _JSON.search(text)
    if not match:
        raise ValueError("no JSON object in judge reply")
    return json.loads(match.group())


def _agreement(scores: dict[str, dict], game: GameFold) -> float | None:
    """Kendall's tau between the judge's ranking and the engine's standings.

    Only computed on games that finished — a capped game has no settled
    outcome to agree with. +1 is perfect agreement, -1 perfect inversion;
    persistent low values mean the rubric, not the game, is broken.
    """
    totals = {}
    for color in COLORS:
        means = [cell["mean"] for cell in scores[color].values()
                 if cell["mean"] is not None]
        if not means:
            return None
        totals[color] = sum(means)
    judge_rank = {c: r for r, c in enumerate(
        sorted(COLORS, key=lambda c: totals[c], reverse=True), start=1)}
    engine_rank = {c: game.standing_rank(c) for c in COLORS}

    concordant = discordant = 0
    for a, b in combinations(COLORS, 2):
        judge_side = judge_rank[a] - judge_rank[b]
        engine_side = engine_rank[a] - engine_rank[b]
        if judge_side * engine_side > 0:
            concordant += 1
        elif judge_side * engine_side < 0:
            discordant += 1
    pairs = concordant + discordant
    return round((concordant - discordant) / pairs, 3) if pairs else None
