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


def test_the_digest_matches_every_stack_and_language(prompt_set):
    # The parity claim, mechanically: three independent loaders (two Python
    # copies, one Java port) hashed shared/prompts and RECORDED the result in
    # their fixtures' game_started (this very test originally went looking
    # for that record, found none, and became open question 19 — answered).
    import json
    root = prompts.repo_root()
    for fixture in ("scripted-strands-seed7.jsonl",
                    "scripted-langgraph-seed7.jsonl",
                    "scripted-springai-seed7.jsonl"):
        first = json.loads(
            (root / "projects" / "ludo" / "games" / fixture)
            .read_text(encoding="utf-8").splitlines()[0])
        assert first["payload"]["prompt_set"]["hash"] == prompt_set.digest, fixture


def test_seat_rotation_cycles_in_four_games():
    profile = config.load("dev")
    colors = ("red", "green", "yellow", "blue")
    game0 = config.seating(profile, colors, 0)
    game1 = config.seating(profile, colors, 1)
    assert game0["red"].seat == 1
    assert game1["red"].seat == 2
    assert config.seating(profile, colors, 4) == game0    # full rotation
