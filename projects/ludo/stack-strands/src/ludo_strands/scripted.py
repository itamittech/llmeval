"""A scripted model, implemented through Strands' own ``Model`` interface.

The harness contract (§8) requires every stack to accept an injected model that
replays committed responses — **through the framework's own extension point**,
never a parallel client bolted on beside it (ADR-0008). For Strands that means
subclassing :class:`strands.models.Model`: the same streaming surface a real
provider binding implements. The entire agent loop — tools, hooks, metrics,
the swarm — runs exactly as it would live, with only the network call replaced.

A scripted reply is plain text or a floor pass:

    "just text"                                   -> an end_turn text message
    {"text": "..."}                               -> the same, explicit
    {"handoff": {"to": "blue", "message": "...",
                 "note": "optional table note"}}  -> a handoff_to_agent tool call

A handoff consumes TWO script entries: the tool call, then the text the model
produces after seeing the tool result — the event loop always asks again.
Scripts are explicit about that on purpose: they are committed artifacts, and
hiding the mechanical second call in here would make them lie about how many
model invocations a phase costs.
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

    @property
    def calls(self) -> int:
        """How many replies have been consumed — an assertion surface for tests."""
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

        yield {"messageStart": {"role": "assistant"}}

        if "handoff" in reply:
            handoff = reply["handoff"]
            tool_input: dict[str, Any] = {
                "agent_name": handoff["to"],
                "message": handoff["message"],
            }
            if handoff.get("note"):
                tool_input["context"] = {"table_note": handoff["note"]}
            yield {"contentBlockStart": {"start": {"toolUse": {
                "toolUseId": f"script-{self._cursor}", "name": "handoff_to_agent",
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

        # Deterministic pretend-usage — chars/4, the same heuristic Strands
        # itself falls back to — so token accounting and the budget ceiling are
        # exercisable offline. All zeros would let a broken meter pass unseen.
        input_chars = 0
        for message in messages or []:
            for block in message.get("content", []):
                if "text" in block:
                    input_chars += len(block["text"])
        usage = {
            "inputTokens": max(1, input_chars // 4),
            "outputTokens": max(1, len(out_text) // 4),
        }
        usage["totalTokens"] = usage["inputTokens"] + usage["outputTokens"]
        yield {"metadata": {"usage": usage, "metrics": {"latencyMs": 0}}}
