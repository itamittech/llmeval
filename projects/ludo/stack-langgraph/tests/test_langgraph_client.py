"""Live provider settings, pinned and read back — before any live call exists.

The same discipline as the other two stacks, for the same reason: an unpinned
sampling parameter is a parity break that never announces itself. No key is
needed and no request is made; the test reads the constructed object's fields.
"""

from __future__ import annotations

import pytest

from ludo_langgraph import config
from ludo_langgraph.langgraph_client import build_model


def test_direct_anthropic_settings_arrive(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-never-used")
    profile = config.load("dev")
    control = profile.seat(3)                      # ADR-0005: anthropic, direct
    model = build_model(control.access, control.provider, control.model,
                        profile.inference_for("anthropic"))

    assert model.model == control.model
    assert model.max_tokens == 2000                # models.yaml max_output_tokens
    assert model.reasoning_effort == "medium"      # first-class here; a raw
    assert model.thinking == {"type": "adaptive",  # passthrough in Strands,
                              "display": "summarized"}  # absent in Spring AI
    assert model.max_retries == 2                  # the framework default, recorded


def test_unbuilt_routes_fail_loudly():
    with pytest.raises(NotImplementedError):
        build_model("bedrock", "anthropic", "some-model", {})
    with pytest.raises(NotImplementedError):
        build_model("direct", "deepseek", "some-model", {})
    with pytest.raises(ValueError):
        build_model("carrier-pigeon", "anthropic", "some-model", {})
