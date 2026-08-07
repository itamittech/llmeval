"""The RELAY harness on LangGraph — four runner agents, one shared anchor.

Deliberately the same shape as the Strands harness, because the point is what
differs *below* it. The engine drives, one template renders per turn, three
lines come back, and the engine performs escalation.

Where this stack differs, and it is not much:

- the conversation lives in a checkpointer thread named after the lane, not in
  a sliding window the harness configured;
- the notebook lives in the framework ``Store``, not in agent state;
- the budget gate is middleware that jumps past the model, not a hook that
  cancels the call;
- the anchor is a bare ``BaseChatModel`` invocation rather than a second agent.

Four rows in the matrix, and none of them changes a single event in the
transcript. That equivalence is the third game's contribution to the comparison.
"""

from __future__ import annotations

import importlib.metadata
import re
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from relay_engine.deciders import Attempt, COLORS
from relay_engine.game import Game, GameConfig
from relay_engine.track import PublicStage

from . import config as config_mod
from . import guardrails
from .memory import render_memory, write_note
from .meter import BudgetExceeded, Meter
from .players import ask_anchor, build_runner
from .prompts import PromptSet, Template

NOTES_LIMIT = 8
MAX_NOTES_PER_REFLECT = 2

# The reply grammar is shared prose, so the parser is shared logic — copied
# rather than imported, because the two Python stacks never share a venv.
SPACE = r"[^\S\n]*"
DECISION = re.compile(rf"^{SPACE}DECISION:{SPACE}(answer|escalate|pass){SPACE}$", re.I | re.M)
ANSWER = re.compile(rf"^{SPACE}ANSWER:{SPACE}(.*)$", re.I | re.M)
NOTE = re.compile(rf"^{SPACE}NOTE:{SPACE}(.*)$", re.I | re.M)


def parse_decision(text: str) -> tuple[str, str | None, str | None]:
    r"""Read the three lines. ``[^\S\n]*`` rather than ``\s*`` — the latter
    crosses newlines, so an empty ANSWER: line swallows the NOTE: beneath it and
    submits a runner's table talk as its answer."""
    match = DECISION.search(text)
    if not match:
        raise ValueError("no DECISION line in reply")
    answer_match = ANSWER.search(text)
    answer = (answer_match.group(1).strip() if answer_match else None) or None
    note_match = NOTE.search(text)
    note = (note_match.group(1).strip() if note_match else None) or None
    return match.group(1).lower(), answer, note


def _framework_version() -> str:
    try:
        return importlib.metadata.version("langgraph")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        return "unknown"


class RelayHarness:
    """One race: engine, four runner agents, one anchor, one event stream."""

    def __init__(self, profile: config_mod.Profile, prompts: PromptSet,
                 anchor_prompt: Template, models: dict[str, Any], anchor_model: Any,
                 sink: Any, seed: int, max_turns: int | None = None,
                 game_index: int = 0, checkpointer: Any = None,
                 store: Any = None) -> None:
        self.profile = profile
        self.prompts = prompts
        self.anchor_prompt = anchor_prompt
        self.sink = sink
        self.anchor_model = anchor_model

        self.checkpointer = checkpointer or InMemorySaver()
        self.store = store or InMemoryStore()

        lanes = config_mod.lane_assignment(profile, COLORS, game_index)
        lane_meta = {
            color: {
                "model": models[color].get_config().get("model_id", lane.model),
                "access": lane.access,
            }
            for color, lane in lanes.items()
        }
        anchor_meta = {
            "model": anchor_model.get_config().get("model_id", profile.anchor.model),
            "access": profile.anchor.access,
        }
        self.meter = Meter(sink, lane_meta, anchor_meta,
                           profile.budgets.max_tokens_per_game)

        system = {
            color: prompts.system_prompt(
                color=color,
                escalation_quota=profile.budgets.escalation_quota,
                max_turns=max_turns or profile.budgets.max_turns,
                max_note_chars=profile.budgets.max_note_chars,
            )
            for color in COLORS
        }
        self.agents = {
            color: build_runner(color, models[color], system[color], self.meter,
                                self.store, self.checkpointer)
            for color in COLORS
        }

        self.game = Game(GameConfig(
            seed=seed,
            max_turns=max_turns or profile.budgets.max_turns,
            escalation_quota=profile.budgets.escalation_quota,
            max_note_chars=profile.budgets.max_note_chars,
            stack="langgraph",
            players={
                color: {"seat": lane.lane, "model": lane_meta[color]["model"],
                        "access": lane.access}
                for color, lane in lanes.items()
            },
            anchor=self.call_anchor,
            profile=profile.name,
            prompt_set=prompts.provenance(),
            framework={"name": "langgraph", "version": _framework_version()},
            anchor_meta=anchor_meta,
        ), sink)

    # -- public -----------------------------------------------------------

    def play(self):
        return self.game.play({color: _Runner(self, color) for color in COLORS})

    # -- the anchor -------------------------------------------------------

    def call_anchor(self, stage: PublicStage) -> str:
        self.meter.actor = "anchor"
        self.meter.purpose = "escalate"
        try:
            reply = ask_anchor(self.anchor_model,
                               self.anchor_prompt.render(stage=stage.prompt),
                               self.meter)
        finally:
            self.meter.actor = "runner"
        return reply.strip().splitlines()[0].strip() if reply.strip() else ""

    # -- shared helpers ---------------------------------------------------

    def ask(self, color: str, phase: str, turn: int, /, **variables: Any) -> str:
        self.meter.turn = turn
        self.meter.color = color
        self.meter.purpose = phase
        self.meter.actor = "runner"
        prompt = self.prompts.turn[phase].render(**variables)
        result = self.agents[color].invoke(
            {"messages": [HumanMessage(content=prompt)]},
            config={"configurable": {"thread_id": color}, "callbacks": [self.meter]},
        )
        messages = result.get("messages") or []
        return str(messages[-1].content) if messages else ""

    def gate_note(self, color: str, turn: int, note: str) -> str | None:
        note = note[: self.profile.budgets.max_note_chars]
        violation = guardrails.check(note)
        if violation:
            self.sink.emit("guardrail_triggered", {
                "player": color, "rule": violation.rule, "action": "blocked",
                "source": "harness", "detail": violation.reason,
            }, turn=turn)
            return None
        return note

    def render_lanes(self, view) -> str:
        lines = []
        for lane in view.lanes():
            mark = " (finished)" if lane.finished else ""
            you = " <- you" if lane.color == view.color else ""
            lines.append(f"- {lane.color}: stage {lane.position + 1} of "
                         f"{view.track_length}, {lane.ticks} ticks, "
                         f"{lane.escalations} escalations{mark}{you}")
        return "\n".join(lines)

    def render_notes(self, view) -> str:
        lines = [f'- turn {n.turn}, {n.player}: "{n.text}"'
                 for n in view.notes()[-NOTES_LIMIT:]]
        return "\n".join(lines) if lines else "(nobody has said anything)"

    def render_history(self, view) -> str:
        records = view.own_history()
        if not records:
            return "(this is your first stage)"
        lines = []
        for r in records[-12:]:
            how = "the anchor answered" if r.escalated else "you answered"
            verdict = "cleared" if r.correct else "missed"
            lines.append(f"- turn {r.turn}, a {r.family} stage: {how}, {verdict}")

        by_family: dict[str, list[bool]] = {}
        for r in records:
            if not r.escalated:
                by_family.setdefault(r.family, []).append(r.correct)
        tally = ", ".join(f"{family} {sum(results)}/{len(results)}"
                          for family, results in sorted(by_family.items()))
        if tally:
            lines.append(f"- on your own, unaided: {tally}")
        return "\n".join(lines)

    def render_turn_summary(self, events: tuple[dict, ...]) -> str:
        lines = []
        for event in events:
            kind, p = event["type"], event["payload"]
            if kind == "stage_attempted":
                who = "the anchor" if p["escalated"] else "you"
                verdict = "cleared it" if p["correct"] else "got it wrong"
                lines.append(f"{who} answered {p['stage']} and {verdict} "
                             f"({p['ticks_charged']} ticks, {p['quota_left']} quota left)")
            elif kind == "invalid_action":
                lines.append(f"invalid {p['phase']}: {p['reason']}")
            elif kind == "runner_finished":
                lines.append("you finished the track")
        return "\n".join(f"- {line}" for line in lines) if lines else "- (a quiet turn)"


class _Runner:
    """The engine-facing adapter for one lane."""

    name = "llm-runner"

    def __init__(self, harness: RelayHarness, color: str) -> None:
        self.h = harness
        self.color = color

    def attempt(self, ctx) -> Attempt:
        if self.h.meter.exhausted:
            return Attempt()

        view = ctx.view
        reply = self.h.ask(
            self.color, "attempt", ctx.turn,
            turn=ctx.turn, color=self.color,
            stage=view.stage.prompt,
            lanes=self.h.render_lanes(view),
            quota_left=view.quota_left,
            notes=self.h.render_notes(view),
            history=self.h.render_history(view),
            memory=render_memory(self.h.store, self.color),
        )
        decision, answer, note = parse_decision(reply)
        if note:
            note = self.h.gate_note(self.color, ctx.turn, note)

        if decision == "escalate":
            return Attempt(answer=ctx.desk.ask(), note=note)
        if decision == "pass":
            return Attempt(answer=None, note=note)
        return Attempt(answer=answer, note=note)

    def reflect(self, end) -> None:
        if self.h.meter.exhausted:
            return
        reply = self.h.ask(
            self.color, "reflect", end.turn,
            turn=end.turn,
            turn_summary=self.h.render_turn_summary(end.events),
            memory=render_memory(self.h.store, self.color),
        )
        text = reply.strip()
        if not text:
            return
        for line in text.splitlines()[:MAX_NOTES_PER_REFLECT]:
            line = line.strip().lstrip("-").strip()
            if not line:
                continue
            note = write_note(self.h.store, self.color, line, end.turn, kind="self")
            self.h.sink.emit("memory_write", {
                "player": self.color, "kind": note["kind"],
                "about": note["about"], "text": note["text"],
            }, turn=end.turn)


__all__ = ["RelayHarness", "BudgetExceeded", "parse_decision"]
