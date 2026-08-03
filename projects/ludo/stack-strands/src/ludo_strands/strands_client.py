"""The Strands binding — the only file in this stack that imports Strands.

Everything else talks to :class:`~ludo_strands.model.ModelClient`. Keeping the
framework behind one small adapter is what makes the comparison legible: when
LangGraph and Spring AI are built, the diff that matters is *this file* and the
turn loop, not the whole harness.

It is also what makes the scripted-model conformance in the harness contract
possible at all — see model.py.
"""

from __future__ import annotations

import time
from typing import Any

from strands import Agent
from strands.models import BedrockModel
from strands.models.anthropic import AnthropicModel

from .budget import Usage
from .model import Reply

#: Bedrock spells the same model with a provider prefix; the direct API does not.
#: Both come from shared/models.yaml already spelled correctly for their route,
#: so nothing here rewrites an id — a stack that "helpfully" normalised one
#: would silently break the ADR-0005 control.


def build_model(access: str, provider: str, model: str,
                inference: dict[str, Any]) -> Any:
    """Construct the Strands model object for one seat.

    ``inference`` arrives already narrowed to this provider by
    :meth:`Profile.inference_for`, because the families genuinely differ: the
    Claude 5 models reject ``temperature``/``top_p`` and take ``effort``, while
    Nova and DeepSeek do the opposite.

    **Two traps, both silent.** Strands takes its config as keyword arguments —
    passing ``model_config={...}`` is accepted, warns, and is then *ignored*, so
    every pinned setting would quietly revert to a default and the parity claim
    would be false with nothing to see. And the two providers do not share a
    config surface even within this one framework: ``BedrockConfig`` has
    ``temperature``/``top_p`` as first-class keys, while ``AnthropicConfig`` has
    neither and takes a ``params`` passthrough instead. ``test_strands_client``
    asserts the settings actually arrive.
    """
    if access == "bedrock":
        config: dict[str, Any] = {"model_id": model}
        if "max_output_tokens" in inference:
            config["max_tokens"] = inference["max_output_tokens"]
        for key in ("temperature", "top_p"):
            if key in inference:
                config[key] = inference[key]
        return BedrockModel(**config)

    if access == "direct":
        if provider != "anthropic":
            raise NotImplementedError(
                f"no direct-route binding for provider {provider!r} yet; "
                f"seat is configured but unimplemented"
            )
        config = {"model_id": model}
        if "max_output_tokens" in inference:
            config["max_tokens"] = inference["max_output_tokens"]

        # Claude 5 controls depth with `effort` and adaptive thinking; sampling
        # parameters are rejected outright. Neither has a first-class key in
        # AnthropicConfig, so they ride the raw passthrough.
        params: dict[str, Any] = {}
        if "effort" in inference:
            params["output_config"] = {"effort": inference["effort"]}
        if "thinking" in inference:
            thinking = {"type": inference["thinking"]}
            if "thinking_display" in inference:
                thinking["display"] = inference["thinking_display"]
            params["thinking"] = thinking
        if params:
            config["params"] = params

        return AnthropicModel(**config)

    raise ValueError(f"unknown access route {access!r}")


class StrandsModel:
    """A :class:`ModelClient` backed by a Strands ``Agent``.

    One agent per seat, rebuilt per call with the system prompt it was given.
    Strands keeps conversation state on the ``Agent``; this harness deliberately
    does not use that — context is assembled by the harness so that all three
    stacks assemble it the same way, and whatever each framework does implicitly
    stays out of the comparison.
    """

    def __init__(self, access: str, provider: str, model: str,
                 inference: dict[str, Any]) -> None:
        self.access = access
        self.provider = provider
        self.model = model
        self._inference = inference
        self._model = build_model(access, provider, model, inference)

    def complete(self, system: str, user: str, purpose: str) -> Reply:
        agent = Agent(model=self._model, system_prompt=system)

        started = time.perf_counter()
        result = agent(user)
        latency_ms = int((time.perf_counter() - started) * 1000)

        usage = result.metrics.accumulated_usage
        return Reply(
            text=str(result),
            usage=Usage(
                input=usage.get("inputTokens", 0),
                output=usage.get("outputTokens", 0),
                cache_read=usage.get("cacheReadInputTokens", 0),
                cache_write=usage.get("cacheWriteInputTokens", 0),
            ),
            latency_ms=latency_ms,
        )
