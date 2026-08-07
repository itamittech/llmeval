"""A scripted model through Strands' own ``Model`` interface.

Same requirement as both earlier games (harness contract §9): the injected fake
goes through the framework's extension point, so the whole agent loop runs
exactly as it would live.

Simpler than ALIBI's, and the reason is the project's central design choice:
RELAY has **no tool**. Escalation is a model swap performed by the engine, not
a consultation the model requests, so a scripted reply is always plain text and
a phase always costs exactly one call. When the ALIBI stacks disagreed about
what "one call" meant, it was tool execution doing it — remove the tool and the
disagreement has nowhere to live.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Callable

from strands.models import Model


class ScriptExhausted(RuntimeError):
    """The script ran out of replies — the run asked for more than it committed."""


class PolicyModel(Model):
    """A scripted model whose reply is *computed* from the prompt it was sent.

    RELAY's scripted tier cannot use a hand-typed reply list the way the earlier
    games did, and the reason is the seal. A fixed list is written by a human
    who looked at the track — so the moment a generator changes, the list is
    wrong in a way that looks like a model getting worse. Worse, a list written
    from the answers would encode knowledge the runner is not allowed to have.

    A policy reads only what a runner reads: the rendered prompt. It stands in
    for a small model with a personality — one that is good at arithmetic and
    hopeless at ordering puzzles, say — and it stays honest, because it has no
    access to anything the real model would not have.
    """

    def __init__(self, decide: Callable[[str], str], model_id: str = "scripted") -> None:
        self._decide = decide
        self._config: dict[str, Any] = {"model_id": model_id}
        self._calls = 0
        #: Everything this model was sent, including its own replies coming back
        #: as conversation history.
        self.seen: list[str] = []
        #: Only what the HARNESS rendered. The seal tests need this distinction:
        #: a runner's own past answer legitimately reappears in its context, so
        #: searching `seen` for an answer finds the model's own words and proves
        #: nothing. What must never carry an answer is what the harness composed.
        self.seen_rendered: list[str] = []

    @property
    def calls(self) -> int:
        return self._calls

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self._config

    async def structured_output(
        self, output_model: Any, prompt: Any, system_prompt: Any = None, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        raise NotImplementedError("scripted races do not use structured output")
        yield  # pragma: no cover — makes this an async generator, per the ABC

    async def stream(
        self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        self._calls += 1
        latest = ""
        input_chars = 0
        for message in messages or []:
            for block in message.get("content", []):
                if "text" in block:
                    input_chars += len(block["text"])
                    self.seen.append(block["text"])
                    if message.get("role") == "user":
                        latest = block["text"]
                        self.seen_rendered.append(block["text"])
        if system_prompt:
            self.seen.append(str(system_prompt))
            self.seen_rendered.append(str(system_prompt))

        text = self._decide(latest)

        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockDelta": {"delta": {"text": text}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        usage = {
            "inputTokens": max(1, input_chars // 4),
            "outputTokens": max(1, len(text) // 4),
        }
        usage["totalTokens"] = usage["inputTokens"] + usage["outputTokens"]
        yield {"metadata": {"usage": usage, "metrics": {"latencyMs": 0}}}


class ScriptedModel(Model):
    """Replays a fixed list of text replies. Deterministic, free, offline."""

    def __init__(self, replies: list[str], model_id: str = "scripted") -> None:
        self._replies = list(replies)
        self._cursor = 0
        self._config: dict[str, Any] = {"model_id": model_id}
        #: Every prompt text this model was sent — the seal tests' evidence.
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
        raise NotImplementedError("scripted races do not use structured output")
        yield  # pragma: no cover — makes this an async generator, per the ABC

    async def stream(
        self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kwargs: Any
    ) -> AsyncGenerator[dict[str, Any], None]:
        if self._cursor >= len(self._replies):
            raise ScriptExhausted(
                f"reply {self._cursor + 1} requested, only {len(self._replies)} scripted"
            )
        text = self._replies[self._cursor]
        self._cursor += 1

        input_chars = 0
        for message in messages or []:
            for block in message.get("content", []):
                if "text" in block:
                    input_chars += len(block["text"])
                    self.seen.append(block["text"])
        if system_prompt:
            self.seen.append(str(system_prompt))

        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockDelta": {"delta": {"text": text}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}

        # Deterministic pretend-usage — chars/4 — so token accounting and the
        # budget ceiling are exercisable offline. Zeros would hide a broken meter.
        usage = {
            "inputTokens": max(1, input_chars // 4),
            "outputTokens": max(1, len(text) // 4),
        }
        usage["totalTokens"] = usage["inputTokens"] + usage["outputTokens"]
        yield {"metadata": {"usage": usage, "metrics": {"latencyMs": 0}}}
