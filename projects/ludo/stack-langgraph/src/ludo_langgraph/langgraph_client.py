"""Provider model construction — one seat's settings, pinned and verified.

The same job, and the same discipline, as the Strands stack's
``strands_client.py`` and the Spring AI stack's ``LiveModels``: turn a
`shared/models.yaml` seat into a configured model object without any pinned
setting silently reverting to a framework default. An unpinned parameter is a
parity break that never announces itself; the test reads every setting back.

One genuine difference worth the matrix line: LangChain's Anthropic binding
exposes the Claude 5 depth controls **first-class** — ``reasoning_effort`` is
a typed field and ``thinking`` a documented dict — where Strands needed a raw
``params`` passthrough and Spring AI's options surface had no knob at all.

Bedrock seats need ``langchain-aws`` (a separate package, not a LangChain
core install), which arrives with live play — the same staging as the Spring
AI stack's provider starters. Until then the route raises loudly rather than
quietly constructing something unpinned.
"""

from __future__ import annotations

from typing import Any

from langchain_anthropic import ChatAnthropic


def build_model(access: str, provider: str, model: str,
                inference: dict[str, Any]) -> Any:
    """Construct the LangChain chat model for one seat.

    ``inference`` arrives already narrowed to this provider by
    :meth:`Profile.inference_for`, because the families genuinely differ: the
    Claude 5 models reject ``temperature``/``top_p`` and take ``effort``, while
    Nova and DeepSeek do the opposite.
    """
    if access == "bedrock":
        raise NotImplementedError(
            "Bedrock seats need langchain-aws, which arrives with live play; "
            "seat is configured but unimplemented")

    if access == "direct":
        if provider != "anthropic":
            raise NotImplementedError(
                f"no direct-route binding for provider {provider!r} yet; "
                f"seat is configured but unimplemented")

        config: dict[str, Any] = {"model": model}
        if "max_output_tokens" in inference:
            config["max_tokens"] = inference["max_output_tokens"]
        if "effort" in inference:
            config["reasoning_effort"] = inference["effort"]
        if "thinking" in inference:
            thinking = {"type": inference["thinking"]}
            if "thinking_display" in inference:
                thinking["display"] = inference["thinking_display"]
            config["thinking"] = thinking
        # Transport retries stay at the framework's default (max_retries=2) —
        # contract §6: what the SDK does to get ONE answer out is framework
        # behaviour under test, recorded in the matrix, never tuned per stack.
        return ChatAnthropic(**config)

    raise ValueError(f"unknown access route {access!r}")
