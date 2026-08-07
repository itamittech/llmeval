"""A scripted model through Strands' own ``Model`` interface.

Same requirement as LUDO's (harness contract §9): the injected fake goes
through the framework's extension point, so the whole agent loop — the
archivist tool included — runs exactly as it would live.

A scripted reply is plain text or an archivist consultation:

    "just text"                          -> an end_turn text message
    {"text": "..."}                      -> the same, explicit
    {"consult": "vault key"}             -> a consult_archivist tool call

A consultation consumes TWO script entries: the tool call, then the text the
model produces after reading the archivist's answer — the agent loop always
asks again. Scripts are explicit about that on purpose: hiding the mechanical
second call would make committed scripts lie about what a phase costs.
"""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator

from strands.models import Model


class ScriptExhausted(RuntimeError):
    """The script ran out of replies — the run asked for more than it committed."""


class ScriptedModel(Model):
    """Replays a fixed list of replies. Deterministic, free, offline."""

    def __init__(self, replies: list[Any], model_id: str = "scripted") -> None:
        self._replies = list(replies)
        self._cursor = 0
        self._config: dict[str, Any] = {"model_id": model_id}
        #: Every prompt text this model was sent — the privacy tests' evidence.
        self.seen: list[str] = []

    @property
    def calls(self) -> int:
        return self._cursor

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self._config

    async def structured_output(
        self, output_model: Any, prompt: Any, system_prompt: Any = None, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        raise NotImplementedError("scripted games do not use structured output")
        yield  # pragma: no cover — makes this an async generator, per the ABC

    async def stream(
        self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        if self._cursor >= len(self._replies):
            raise ScriptExhausted(
                f"reply {self._cursor + 1} requested, only {len(self._replies)} scripted"
            )
        reply = self._replies[self._cursor]
        self._cursor += 1
        if isinstance(reply, str):
            reply = {"text": reply}

        input_chars = 0
        for message in messages or []:
            for block in message.get("content", []):
                if "text" in block:
                    text = block["text"]
                    input_chars += len(text)
                    self.seen.append(text)
        if system_prompt:
            self.seen.append(str(system_prompt))

        yield {"messageStart": {"role": "assistant"}}

        if "consult" in reply:
            tool_input = {"query": reply["consult"]}
            yield {"contentBlockStart": {"start": {"toolUse": {
                "toolUseId": f"script-{self._cursor}", "name": "consult_archivist",
            }}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(tool_input)}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
            out_text = json.dumps(tool_input)
        else:
            yield {"contentBlockDelta": {"delta": {"text": reply["text"]}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
            out_text = reply["text"]

        # Deterministic pretend-usage — chars/4 — so token accounting and the
        # budget ceiling are exercisable offline. Zeros would hide a broken meter.
        usage = {
            "inputTokens": max(1, input_chars // 4),
            "outputTokens": max(1, len(out_text) // 4),
        }
        usage["totalTokens"] = usage["inputTokens"] + usage["outputTokens"]
        yield {"metadata": {"usage": usage, "metrics": {"latencyMs": 0}}}
