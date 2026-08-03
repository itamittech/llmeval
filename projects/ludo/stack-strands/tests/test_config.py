"""models.yaml is where the experiment's controls live. These pin them."""

import pytest

from ludo_strands import config


def test_loads_both_profiles():
    for name in ("dev", "headline"):
        profile = config.load(name)
        assert len(profile.seats) == 4
        assert profile.budgets.max_turns > 0


def test_unknown_profile_is_an_error():
    with pytest.raises(KeyError, match="nope"):
        config.load("nope")


def test_two_seats_per_route():
    # The brief's shape: two Bedrock, two direct.
    profile = config.load("dev")
    routes = [s.access for s in profile.seats]
    assert routes.count("bedrock") == 2
    assert routes.count("direct") == 2


def test_one_model_sits_on_both_routes():
    # ADR-0005's control. Without it, a Bedrock-vs-direct difference cannot be
    # told apart from a model difference.
    for name in ("dev", "headline"):
        profile = config.load(name)
        bedrock = {s.provider for s in profile.seats if s.access == "bedrock"}
        direct = {s.provider for s in profile.seats if s.access == "direct"}
        assert len(bedrock & direct) == 1, f"{name}: {bedrock} vs {direct}"


def test_the_judge_never_plays():
    for name in ("dev", "headline"):
        profile = config.load(name)
        assert profile.judge.provider not in {s.provider for s in profile.seats}


def test_inference_is_per_provider_not_global():
    # The Claude 5 models reject temperature/top_p; Nova and DeepSeek require
    # them. A single global setting would 400 on half the seats.
    profile = config.load("dev")
    anthropic = profile.inference_for("anthropic")
    amazon = profile.inference_for("amazon")

    assert "temperature" not in anthropic, "Claude 5 rejects sampling params"
    assert "effort" in anthropic
    assert "temperature" in amazon
    assert "effort" not in amazon
    # The one setting everybody honours.
    assert anthropic["max_output_tokens"] == amazon["max_output_tokens"]


def test_seat_rotation_gives_every_seat_every_colour():
    # ADR-0006: a full rotation is four games, so a run supporting a claim about
    # models should be a multiple of four.
    profile = config.load("dev")
    colors = ("red", "green", "yellow", "blue")

    seen: dict[int, set[str]] = {s.seat: set() for s in profile.seats}
    for game in range(4):
        mapping = config.seating(profile, colors, game)
        assert len(mapping) == 4
        assert len({s.seat for s in mapping.values()}) == 4, "no seat played twice"
        for color, seat in mapping.items():
            seen[seat.seat].add(color)

    for seat, colours in seen.items():
        assert colours == set(colors), f"seat {seat} only played {colours}"


def test_unpinned_seats_are_reported_rather_than_guessed():
    profile = config.load("dev")
    unpinned = {s.provider for s in profile.unpinned()}
    # Nova and DeepSeek ids are still TBD; the Anthropic pair is pinned.
    assert "anthropic" not in unpinned
