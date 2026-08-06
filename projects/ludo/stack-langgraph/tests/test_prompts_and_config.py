"""The shared contracts, loaded by this stack's own copy of the loaders."""

from __future__ import annotations

import pytest

from ludo_langgraph import config, prompts


@pytest.fixture(scope="module")
def prompt_set():
    return prompts.load()


def test_prompts_load_with_parity_invariants(prompt_set):
    assert prompt_set.digest.startswith("sha256:")
    assert set(prompt_set.turn) == {"negotiate", "briefing", "decide", "retry", "reflect"}
    once = prompt_set.system_prompt(color="red", max_floor_passes=3,
                                    max_message_chars=240)
    assert "red" in once
    assert "{{" not in once
    with pytest.raises(KeyError):
        prompt_set.turn["decide"].render(turn=1)          # missing variables
    with pytest.raises(KeyError):
        prompt_set.turn["retry"].render(reason="r", rejected="x",
                                        legal_moves="m", extra="smuggled")


def test_the_digest_is_deterministic(prompt_set):
    # Two loads, one hash. (A cross-stack equality test wants the digest
    # RECORDED somewhere — and no stack currently emits prompt provenance
    # into game_started, a gap logged in docs/open-questions.md when this
    # stack's build surfaced it.)
    assert prompts.load().digest == prompt_set.digest


def test_seat_rotation_cycles_in_four_games():
    profile = config.load("dev")
    colors = ("red", "green", "yellow", "blue")
    game0 = config.seating(profile, colors, 0)
    game1 = config.seating(profile, colors, 1)
    assert game0["red"].seat == 1
    assert game1["red"].seat == 2
    assert config.seating(profile, colors, 4) == game0    # full rotation
