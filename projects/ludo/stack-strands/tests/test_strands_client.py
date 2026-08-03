"""The Strands binding.

No network: constructing a model object needs no credentials, and that is
enough to catch the failure that actually matters — pinned inference settings
silently not arriving.
"""

import warnings

import pytest

from ludo_strands import config
from ludo_strands.strands_client import build_model


@pytest.fixture(scope="module")
def profile():
    return config.load("dev")


def test_bedrock_seat_receives_its_settings(profile):
    seat = profile.seat(1)
    inference = profile.inference_for(seat.provider)
    built = build_model(seat.access, seat.provider, seat.model, inference).get_config()

    assert built["model_id"] == seat.model
    assert built["model_id"].startswith("anthropic."), "Bedrock keeps its prefix"
    assert built["max_tokens"] == inference["max_output_tokens"]


def test_direct_seat_receives_effort_and_thinking(profile):
    # Claude 5 rejects temperature/top_p and controls depth with `effort`, so
    # those ride AnthropicConfig's raw `params` passthrough.
    seat = profile.seat(3)
    inference = profile.inference_for(seat.provider)
    built = build_model(seat.access, seat.provider, seat.model, inference).get_config()

    assert built["model_id"] == seat.model
    assert "." not in built["model_id"], "the direct route takes the bare id"
    assert built["max_tokens"] == inference["max_output_tokens"]

    params = built["params"]
    assert params["output_config"] == {"effort": inference["effort"]}
    assert params["thinking"] == {
        "type": inference["thinking"],
        "display": inference["thinking_display"],
    }


def test_settings_are_not_silently_dropped(profile):
    """The bug this file exists for.

    Strands takes config as keyword arguments. Passing ``model_config={...}``
    is accepted, warns, and is then ignored — every pinned setting reverts to a
    default, the parity claim becomes false, and nothing fails. Assert the
    settings arrive rather than trusting that they did.
    """
    seat = profile.seat(1)
    inference = profile.inference_for(seat.provider)

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        built = build_model(seat.access, seat.provider, seat.model, inference)

    assert built.get_config().get("max_tokens") is not None


def test_the_control_pair_is_the_same_model_on_two_routes(profile):
    # ADR-0005, checked at the point it actually reaches the SDK: the ids differ
    # only by Bedrock's provider prefix.
    bedrock, direct = profile.seat(1), profile.seat(3)
    assert bedrock.access == "bedrock" and direct.access == "direct"
    assert bedrock.model.split(".", 1)[-1] == direct.model


def test_an_unimplemented_route_says_so(profile):
    with pytest.raises(NotImplementedError, match="deepseek"):
        build_model("direct", "deepseek", "some-model", {})


def test_an_unknown_route_is_rejected():
    with pytest.raises(ValueError, match="unknown access route"):
        build_model("carrier-pigeon", "anthropic", "m", {})
