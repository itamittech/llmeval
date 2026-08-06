"""Layer 1 against every committed game.

The strongest assertion is inside ``fold`` itself: it raises unless its
replayed positions, captures and forfeits agree with ``game_ended.standings``
— the engine's own account. Every fixture passing through the ``any_game``
fixture IS that check, across two engines' output, four games, one finished
and three capped, with a three-sixes reversal in the mix.
"""

from __future__ import annotations

import pytest

from ludo_eval import scoring, transcript


def test_every_committed_game_folds_and_verifies(any_game):
    path, events, game = any_game
    assert game.turns_played > 0
    assert set(game.players) == set(transcript.COLORS)


def test_a_shuffled_transcript_is_rejected(langgraph_game):
    path, events, _ = langgraph_game
    broken = [dict(e) for e in events]
    broken[3]["seq"] = 99
    with pytest.raises(ValueError, match="contiguous"):
        # load() guards files; folding a hand-broken list re-checks nothing,
        # so recheck through load's guard by round-tripping is overkill —
        # the seq guard lives in load, exercise it directly.
        _reload(broken)


def _reload(events):
    import json
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "broken.jsonl"
        p.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
        return transcript.load(p)


def test_the_finished_game_scores_sanely(sample_game):
    path, events, game = sample_game
    scores = scoring.score(game, events)
    winner = min(transcript.COLORS, key=lambda c: scores[c]["rank"])
    assert scores[winner]["position"]["tokens_home"] == 4
    assert scores[winner]["position"]["score"] == 400 + scores[winner]["position"]["progress"]
    # A bot game has no agent layer: nothing spent, nothing said.
    assert all(s["efficiency"]["llm_calls"] == 0 for s in scores.values())
    assert all(s["efficiency"]["progress_per_1k_tokens"] is None for s in scores.values())
    # Someone was reset by three sixes in this game — and the engine agreed
    # with our fold anyway, which is what pins the apply-on-commit semantics.
    assert sum(s["play"]["three_sixes"] for s in scores.values()) == 1


def test_the_scripted_story_is_counted(langgraph_game):
    path, events, game = langgraph_game
    scores = scoring.score(game, events)
    red = scores["red"]
    assert red["negotiation"]["messages_sent"] == 1     # the directed pass to blue
    assert red["negotiation"]["table_notes"] == 1       # "I want a quiet table"
    assert scores["blue"]["negotiation"]["messages_sent"] == 1
    assert red["seat"] == 1                             # game 0: no rotation yet
    total = sum(s["efficiency"]["tokens_in"] + s["efficiency"]["tokens_out"]
                for s in scores.values())
    assert total > 0
    assert all(s["efficiency"]["reasoning_chars"] >= 0 for s in scores.values())
