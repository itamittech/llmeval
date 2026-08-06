"""The judge's view leaks nothing — the bias table's load-bearing row.

"Leaks nothing" is checked the blunt way: the rendered transcript is searched
for every forbidden token — colours (including inside message text), stack
names, model ids, access routes. One hit anywhere fails.
"""

from __future__ import annotations

import re

from ludo_eval.anonymize import LABELS, anonymize

FORBIDDEN = ("red", "green", "yellow", "blue",
             "strands", "springai", "langgraph",
             "bedrock", "scripted", "anthropic", "claude")


def test_nothing_identifying_survives(any_game):
    path, events, _ = any_game
    view = anonymize(events, seed=0)
    text = view.transcript()
    for token in FORBIDDEN:
        assert re.search(rf"\b{token}\b", text, re.IGNORECASE) is None, token


def test_colour_words_inside_messages_are_relabelled(langgraph_game):
    path, events, _ = langgraph_game
    view = anonymize(events, seed=0)
    text = view.transcript()
    # "ally against yellow?" must have become "ally against Player X?"
    match = re.search(r"ally against (Player [A-D])\?", text)
    assert match
    assert match.group(1) == view.labels["yellow"]


def test_outcome_blind_and_llm_calls_withheld(any_game):
    path, events, _ = any_game
    text = anonymize(events, seed=0).transcript()
    assert "game_ended" not in text
    assert "standings" not in text
    assert "llm_call" not in text


def test_the_shuffle_is_seeded_and_actually_shuffles(langgraph_game):
    path, events, _ = langgraph_game
    assert anonymize(events, seed=3).labels == anonymize(events, seed=3).labels
    mappings = {tuple(sorted(anonymize(events, seed=s).labels.items()))
                for s in range(8)}
    assert len(mappings) > 1          # position bias mitigation: order varies

    view = anonymize(events, seed=3)
    assert sorted(view.labels.values()) == list(LABELS)
    assert all(view.colors[label] == color
               for color, label in view.labels.items())
