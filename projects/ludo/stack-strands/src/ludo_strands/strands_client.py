"""Provider model construction — one seat's settings, pinned and verified.

Per ADR-0008 the framework is the implementation, not a dependency to hide, so
Strands is imported wherever a primitive is used (players, hooks, harness,
scripted). What stays in this module is the one genuinely provider-specific
job: turning a `shared/models.yaml` seat into a configured Strands model
object without any pinned setting silently reverting to a default.
"""

from __future__ import annotations

from typing import Any

from strands.models import BedrockModel
from strands.models.anthropic import AnthropicModel

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
