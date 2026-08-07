"""A scripted model at the framework's own extension point.

Contract §9: the fake goes through ``BaseChatModel`` — the seam
``ChatAnthropic`` implements — never a parallel client. Everything downstream
(the agent loop, callbacks, usage metadata) runs exactly as it would live; only
``_generate`` is scripted.

RELAY's version computes its reply from the prompt rather than replaying a
list, for the same reason the Strands one does: a hand-typed list encodes
knowledge of the track that the runner is not allowed to have. See
``policies.py``.
"""

from __future__ import annotations

from typing import Any, Callable

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class PolicyChatModel(BaseChatModel):
    """Replies computed from the latest human message, through the real seam."""

    decide: Callable[[str], str]
    #: What ``llm_call.model`` records — a scripted run must say "scripted".
    model_label: str = "scripted"
    #: Everything this model was sent, and (separately) only what the harness
    #: rendered. The seal tests need the distinction: a runner's own past answer
    #: comes back as conversation history and proves nothing.
    seen: list[str] = []
    seen_rendered: list[str] = []
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "relay-scripted"

    def get_config(self) -> dict[str, Any]:
        """The same shape the Strands scripted model exposes, so the harness
        reads a model label the same way in both Python stacks."""
        return {"model_id": self.model_label}

    def _generate(self, messages: list[BaseMessage],
                  stop: list[str] | None = None,
                  run_manager: CallbackManagerForLLMRun | None = None,
                  **kwargs: Any) -> ChatResult:
        self.calls += 1
        latest = ""
        for m in messages:
            if not m.text:
                continue
            self.seen.append(m.text)
            if m.type in ("human", "system"):
                self.seen_rendered.append(m.text)
            if m.type == "human":
                latest = m.text

        text = self.decide(latest)
        reply = AIMessage(content=text)

        prompt_chars = sum(len(m.text or "") for m in messages)
        reply.usage_metadata = {
            "input_tokens": max(1, prompt_chars // 4),
            "output_tokens": max(1, len(text) // 4),
            "total_tokens": max(1, prompt_chars // 4) + max(1, len(text) // 4),
        }
        return ChatResult(generations=[ChatGeneration(message=reply)])
