"""A scripted model at the framework's own extension point.

Contract §9: the fake goes through ``BaseChatModel`` — the seam
``ChatAnthropic`` implements — never a parallel client. Everything downstream
(``create_agent``, tool binding, callbacks, usage metadata) runs exactly as it
would live; only ``_generate`` is scripted.

Same two deliberate differences from langchain's shipped fakes as the LUDO
stack recorded: no cycling (running out raises), and usage attached (chars//4)
so metering is testable offline.

A script entry is a plain string (the reply text) or ``{"consult": "query"}``,
which becomes a ``consult_archivist`` tool call — a consultation therefore
costs two entries, the call and the post-tool reply, visibly.
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
    #: What ``llm_call.model`` records — a scripted run must say "scripted".
    model_label: str = "scripted"
    #: Every prompt text this model was sent — the privacy tests' evidence.
    seen: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "alibi-scripted"

    def get_config(self) -> dict[str, Any]:
        """The same shape the Strands scripted model exposes, so the harness
        reads a model label the same way in both Python stacks."""
        return {"model_id": self.model_label}

    def bind_tools(self, tools: Any, **kwargs: Any) -> Runnable:
        """What a real provider binding does: convert and bind."""
        return self.bind(tools=[convert_to_openai_tool(t) for t in tools], **kwargs)

    def _generate(self, messages: list[BaseMessage],
                  stop: list[str] | None = None,
                  run_manager: CallbackManagerForLLMRun | None = None,
                  **kwargs: Any) -> ChatResult:
        if self.cursor >= len(self.script):
            raise ScriptExhausted(
                f"script exhausted after {len(self.script)} replies "
                f"(deliberately no cycling)")
        entry = self.script[self.cursor]
        self.cursor += 1

        for m in messages:
            if m.text:
                self.seen.append(m.text)

        if isinstance(entry, dict):
            reply = AIMessage(
                content="",
                tool_calls=[{
                    "name": "consult_archivist",
                    "args": {"query": str(entry["consult"])},
                    "id": f"script-{self.cursor}",
                }],
            )
            reply_chars = len(str(entry["consult"]))
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
