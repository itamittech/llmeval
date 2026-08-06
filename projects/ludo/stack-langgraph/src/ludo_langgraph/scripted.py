"""A scripted model at the framework's own extension point.

Harness-contract §8: the fake goes through ``BaseChatModel`` — the same seam
``ChatAnthropic`` implements — never a parallel client bolted on beside the
framework. Everything downstream (``create_agent``, the table graph, tool
binding, callbacks, usage metadata) runs exactly as it would live; only
``_generate`` is scripted.

Two deliberate differences from the fakes langchain-core ships:

- **No cycling.** ``FakeMessagesListChatModel`` wraps back to the start when
  the script runs out, which silently masks a harness calling the model more
  often than its author believed. Running past the end here raises instead.
- **Usage is attached.** Each reply carries ``usage_metadata`` (a chars//4
  estimate, same arithmetic as the other stacks' fakes), so token metering is
  testable offline — a metering bug that only appears live is a metering bug
  found too late.

A script entry is either a plain string (the reply text) or
``{"tool": {...args...}}``, which becomes a ``pass_floor`` tool call — the
floor-passing action of ADR-0009 in the form the framework itself uses.
"""

from __future__ import annotations

from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.utils.function_calling import convert_to_openai_tool


class ScriptExhausted(RuntimeError):
    """The harness asked for more replies than the script holds."""


class ScriptedChatModel(BaseChatModel):
    """Replays a committed script through the ``BaseChatModel`` seam."""

    script: list[Any]
    cursor: int = 0
    #: What ``llm_call.model`` records for this player — a scripted run must
    #: say "scripted", never a seat's real model id, or the transcript lies.
    model_label: str = "scripted"

    @property
    def _llm_type(self) -> str:
        return "ludo-scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> Runnable:
        """The same conversion every real provider binding performs.

        The base class raises ``NotImplementedError`` — tool support is the
        provider's job, so the scripted provider does what ``ChatAnthropic``
        does: convert and bind. ``_generate`` then receives the tools like a
        real backend would (and, like a script must, ignores them).
        """
        return self.bind(tools=[convert_to_openai_tool(t) for t in tools], **kwargs)

    def _generate(self, messages: list[BaseMessage],
                  stop: list[str] | None = None,
                  run_manager: CallbackManagerForLLMRun | None = None,
                  **kwargs: Any) -> ChatResult:
        if self.cursor >= len(self.script):
            raise ScriptExhausted(
                f"script exhausted after {len(self.script)} replies "
                f"(deliberately no cycling — see module docstring)")
        entry = self.script[self.cursor]
        self.cursor += 1

        if isinstance(entry, dict):
            reply = AIMessage(
                content="",
                tool_calls=[{
                    "name": "pass_floor",
                    "args": dict(entry["tool"]),
                    "id": f"script-{self.cursor}",
                }],
            )
            reply_chars = len(str(entry["tool"]))
        else:
            reply = AIMessage(content=str(entry))
            reply_chars = len(str(entry))

        prompt_chars = sum(len(m.text or "") for m in messages)
        reply.usage_metadata = {
            "input_tokens": max(1, prompt_chars // 4),
            "output_tokens": max(1, reply_chars // 4),
            "total_tokens": max(1, prompt_chars // 4) + max(1, reply_chars // 4),
        }
        return ChatResult(generations=[ChatGeneration(message=reply)])
