"""The judge machinery, driven through scripted callers — no model, no cost.

The callers speak in ``Player A``–``D`` because that is all a judge ever
sees; the tests recover the colour mapping from the run's seed to assert the
scores landed on the right players.
"""

from __future__ import annotations

import json

from ludo_eval.anonymize import LABELS, anonymize
from ludo_eval.judge import DIMENSIONS, run_judge

DIMS = [key for key, _, _ in DIMENSIONS]


def reply(per_label_score, uncited=()):
    """A well-formed judge reply: every player, every dimension, cited."""
    out = {}
    for label in LABELS:
        out[label] = {}
        for dim in DIMS:
            cell = {"score": per_label_score(label, dim), "note": "n"}
            cell["citations"] = [] if (label, dim) in uncited else [1, 2]
            out[label][dim] = cell
    return json.dumps(out)


def test_scores_map_back_to_the_right_colours(langgraph_game):
    path, events, game = langgraph_game
    caller = lambda prompt: reply(lambda label, dim: 5 if label == "Player A" else 3)

    outcome = run_judge(events, game, caller, "scripted-judge", runs=1, base_seed=42)

    player_a_color = anonymize(events, seed=42).colors["Player A"]
    for color, cells in outcome.scores.items():
        expected = 5 if color == player_a_color else 3
        assert all(cell["mean"] == expected for cell in cells.values()), color
    assert outcome.discarded_unsourced == 0
    assert outcome.failed_runs == 0
    assert outcome.prompt_hash.startswith("sha256:")
    assert outcome.agreement_with_outcome is None       # capped game: no outcome


def test_unsourced_scores_are_discarded(langgraph_game):
    path, events, game = langgraph_game
    caller = lambda prompt: reply(lambda label, dim: 4,
                                  uncited={("Player B", "negotiation")})

    outcome = run_judge(events, game, caller, "scripted-judge", runs=1, base_seed=0)

    assert outcome.discarded_unsourced == 1
    player_b_color = anonymize(events, seed=0).colors["Player B"]
    assert outcome.scores[player_b_color]["negotiation"]["n"] == 0
    assert outcome.scores[player_b_color]["negotiation"]["mean"] is None
    assert outcome.scores[player_b_color]["decision_quality"]["n"] == 1


def test_multiple_runs_report_the_spread_not_a_number(langgraph_game):
    path, events, game = langgraph_game
    scores = iter([2, 3, 4])

    def caller(prompt):
        s = next(scores)
        return reply(lambda label, dim: s)

    outcome = run_judge(events, game, caller, "scripted-judge", runs=3, base_seed=7)

    for cells in outcome.scores.values():
        for cell in cells.values():
            assert (cell["mean"], cell["min"], cell["max"], cell["n"]) == (3.0, 2, 4, 3)


def test_a_broken_run_is_dropped_and_counted(langgraph_game):
    path, events, game = langgraph_game
    replies = iter(["no json here at all", reply(lambda label, dim: 3)])
    caller = lambda prompt: next(replies)

    outcome = run_judge(events, game, caller, "scripted-judge", runs=2, base_seed=0)

    assert outcome.failed_runs == 1
    assert all(cell["n"] == 1 for cells in outcome.scores.values()
               for cell in cells.values())


def test_agreement_with_outcome_on_the_finished_game(sample_game):
    path, events, game = sample_game
    ranks = {row["player"]: row["rank"] for row in game.standings}

    def caller(prompt):
        # A judge that perfectly agrees with the engine's final table: score
        # each label by its player's true rank. The test recovers the mapping
        # the same way run_judge does — from the run's seed.
        view = anonymize(events, seed=0)
        return reply(lambda label, dim: 5 - ranks[view.colors[label]])

    outcome = run_judge(events, game, caller, "scripted-judge", runs=1, base_seed=0)

    assert outcome.agreement_with_outcome == 1.0
