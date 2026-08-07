"""The RELAY harness on Strands — four runner agents and one shared anchor.

The simplest harness in this repo, and deliberately so. RELAY is one decision
per turn, there is no orchestration and no tool, so what is left is the thing
the project actually wants to measure: a model deciding whether it can do
something, and a second model being paid for when it can't.

Two structural properties a reader should see enforced here rather than trusted:

- **The seal.** Nothing rendered into a prompt has ever held a tier or an
  answer. The engine hands out ``PublicStage``; there is no field to leak.
- **Escalation is the engine's.** The harness never calls the anchor directly.
  It passes ``anchor=`` into ``GameConfig`` and the engine calls it through the
  desk, having charged the shared quota first. So the harness cannot escalate
  without paying, and cannot pay without escalating.
"""

from __future__ import annotations

import importlib.metadata
import re
from typing import Any

from relay_engine.deciders import Attempt, COLORS
from relay_engine.game import Game, GameConfig
from relay_engine.track import PublicStage

from . import config as config_mod
from . import guardrails
from .hooks import BudgetExceeded, GameHooks
from .players import (
    MAX_NOTES_PER_REFLECT, ask_anchor, build_anchor, build_runner, render_memory,
    write_note,
)
from .prompts import PromptSet, Template

#: How many public notes the {{notes}} variable carries. The full record lives
#: in the transcript; the prompt gets the recent talk.
NOTES_LIMIT = 8

#: The two-or-three line reply the attempt template demands.
#:
#: `[^\S\n]*` rather than `\s*`, and the difference is a bug this repo shipped
#: for about ten minutes: `\s*` crosses newlines, so an empty `ANSWER:` line
#: swallowed the `NOTE:` line beneath it and submitted a runner's table talk as
#: its answer. Escalating with a note would have been an automatic miss.
SPACE = r"[^\S\n]*"
DECISION = re.compile(rf"^{SPACE}DECISION:{SPACE}(answer|escalate|pass){SPACE}$", re.I | re.M)
ANSWER = re.compile(rf"^{SPACE}ANSWER:{SPACE}(.*)$", re.I | re.M)
NOTE = re.compile(rf"^{SPACE}NOTE:{SPACE}(.*)$", re.I | re.M)


def parse_decision(text: str) -> tuple[str, str | None, str | None]:
    """Read the three lines. A reply the runner mangled is *not* repaired here —
    the engine's invalid/retry machinery is the arbiter, so an unparseable
    decision raises and the engine asks again."""
    match = DECISION.search(text)
    if not match:
        raise ValueError("no DECISION line in reply")
    decision = match.group(1).lower()

    answer_match = ANSWER.search(text)
    answer = answer_match.group(1).strip() if answer_match else None
    answer = answer or None

    note_match = NOTE.search(text)
    note = note_match.group(1).strip() if note_match else None
    return decision, answer, note or None


class RelayHarness:
    """One race: engine, four runner agents, one anchor, one event stream."""

    def __init__(self, profile: config_mod.Profile, prompts: PromptSet,
                 anchor_prompt: Template, models: dict[str, Any], anchor_model: Any,
                 sink: Any, seed: int, max_turns: int | None = None,
                 game_index: int = 0) -> None:
        self.profile = profile
        self.prompts = prompts
        self.anchor_prompt = anchor_prompt
        self.sink = sink

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
        self.hooks = GameHooks(sink, lane_meta, anchor_meta,
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
            color: build_runner(color, models[color], system[color], [self.hooks])
            for color in COLORS
        }
        self.anchor = build_anchor(anchor_model, [self.hooks])

        self.game = Game(GameConfig(
            seed=seed,
            max_turns=max_turns or profile.budgets.max_turns,
            escalation_quota=profile.budgets.escalation_quota,
            max_note_chars=profile.budgets.max_note_chars,
            stack="strands",
            players={
                color: {"seat": lane.lane, "model": lane_meta[color]["model"],
                        "access": lane.access}
                for color, lane in lanes.items()
            },
            anchor=self.call_anchor,
            profile=profile.name,
            prompt_set=prompts.provenance(),
            framework={"name": "strands",
                       "version": importlib.metadata.version("strands-agents")},
            anchor_meta=anchor_meta,
        ), sink)

    # -- public -----------------------------------------------------------

    def play(self):
        return self.game.play({color: _Runner(self, color) for color in COLORS})

    # -- the anchor -------------------------------------------------------

    def call_anchor(self, stage: PublicStage) -> str:
        """What the engine's desk invokes, once the quota has been charged.

        Note what it receives: a ``PublicStage``. The harness cannot see the
        answer either, so an anchor that gets it right earned it.
        """
        self.hooks.actor = "anchor"
        self.hooks.purpose = "escalate"
        try:
            reply = ask_anchor(self.anchor, self.anchor_prompt.render(stage=stage.prompt))
        finally:
            self.hooks.actor = "runner"
        return reply.strip().splitlines()[0].strip() if reply.strip() else ""

    # -- shared helpers ---------------------------------------------------

    def ask(self, color: str, phase: str, turn: int, /, **variables: Any) -> str:
        """Render the phase template, invoke the lane's agent, return its text."""
        self.hooks.turn = turn
        self.hooks.color = color
        self.hooks.purpose = phase
        self.hooks.actor = "runner"
        prompt = self.prompts.turn[phase].render(**variables)
        return str(self.agents[color](prompt))

    def gate_note(self, color: str, turn: int, note: str) -> str | None:
        """Contract §7 on the one free-text channel: block out-of-fiction
        attacks, let every kind of cunning through."""
        note = note[: self.profile.budgets.max_note_chars]
        violation = guardrails.check(note)
        if violation:
            self.sink.emit("guardrail_triggered", {
                "player": color,
                "rule": violation.rule,
                "action": "blocked",
                "source": "harness",
                "detail": violation.reason,
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
        """The evidence a runner has about itself, which is the whole input to
        the only decision it makes."""
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
        tally = ", ".join(
            f"{family} {sum(results)}/{len(results)}"
            for family, results in sorted(by_family.items())
        )
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
    """The engine-facing adapter for one lane. Its name lands in game_started."""

    name = "llm-runner"

    def __init__(self, harness: RelayHarness, color: str) -> None:
        self.h = harness
        self.color = color

    def attempt(self, ctx) -> Attempt:
        if self.h.hooks.exhausted:
            return Attempt()  # ceiling spent: the race plays out in passes

        view = ctx.view
        reply = self.h.ask(
            self.color, "attempt", ctx.turn,
            turn=ctx.turn, color=self.color,
            stage=view.stage.prompt,
            lanes=self.h.render_lanes(view),
            quota_left=view.quota_left,
            notes=self.h.render_notes(view),
            history=self.h.render_history(view),
            memory=render_memory(self.h.agents[self.color]),
        )
        decision, answer, note = parse_decision(reply)

        if note:
            note = self.h.gate_note(self.color, ctx.turn, note)

        if decision == "escalate":
            # The engine charges the pool and calls the anchor. If the pool is
            # empty this comes back None and the turn is a pass — which is the
            # rules working, not an error to paper over.
            return Attempt(answer=ctx.desk.ask(), note=note)
        if decision == "pass":
            return Attempt(answer=None, note=note)
        return Attempt(answer=answer, note=note)

    def reflect(self, end) -> None:
        if self.h.hooks.exhausted:
            return
        agent = self.h.agents[self.color]
        reply = self.h.ask(
            self.color, "reflect", end.turn,
            turn=end.turn,
            turn_summary=self.h.render_turn_summary(end.events),
            memory=render_memory(agent),
        )
        text = reply.strip()
        if not text:
            return
        for line in text.splitlines()[:MAX_NOTES_PER_REFLECT]:
            line = line.strip().lstrip("-").strip()
            if not line:
                continue
            note = write_note(agent, line, end.turn, kind="self")
            self.h.sink.emit("memory_write", {
                "player": self.color,
                "kind": note["kind"],
                "about": note["about"],
                "text": note["text"],
            }, turn=end.turn)


__all__ = ["RelayHarness", "BudgetExceeded", "parse_decision"]
