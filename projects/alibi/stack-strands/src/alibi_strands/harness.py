"""The ALIBI harness on Strands — four detective agents over the engine's seams.

Where LUDO's harness orchestrated a swarm, this one wires four independent
single-agent loops: the engine drives the phases, each phase renders one shared
template, the agent answers (consulting the archivist tool mid-thought if it
chooses), and the harness parses the JSON and hands the engine exactly what the
model said — never a repair, never an invention. The engine's validation and
retry machinery is the arbiter (contract §2).

Privacy is inherited from the engine's per-detective views: everything rendered
into a prompt comes from *this* detective's view, so what must not leak is
never in scope to leak.
"""

from __future__ import annotations

import importlib.metadata
import json
from typing import Any

from alibi_engine.case import ALL_ELEMENTS, COLORS, DIMENSIONS, ELEMENTS
from alibi_engine.deciders import Belief, Suggestion, Triple
from alibi_engine.game import Game, GameConfig

from . import config as config_mod
from . import guardrails
from .hooks import BudgetExceeded, GameHooks
from .players import (
    MAX_NOTES_PER_REFLECT, build_detective, make_archivist_tool, render_memory,
    write_note,
)
from .prompts import PromptSet

#: How many table entries the {{table}} variable carries — the full public log
#: lives in the transcript; the prompt gets the recent story.
TABLE_LIMIT = 12


def parse_object(text: str) -> dict:
    """The single JSON object a phase prompt demands. Garbage raises — the
    engine's invalid_action/retry machinery is the arbiter, not harness repair."""
    value = _parse(text, "{", "}")
    if not isinstance(value, dict):
        raise ValueError("reply is not a JSON object")
    return value


def parse_array(text: str) -> list:
    value = _parse(text, "[", "]")
    if not isinstance(value, list):
        raise ValueError("reply is not a JSON array")
    return value


def _parse(text: str, open_ch: str, close_ch: str):
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start < 0 or end <= start:
            raise ValueError(f"no JSON {open_ch}...{close_ch} in reply")
        return json.loads(text[start:end + 1])


class AlibiHarness:
    """One game: engine, four agents, one archivist tool, one event stream."""

    def __init__(self, profile: config_mod.Profile, prompts: PromptSet,
                 models: dict[str, Any], sink: Any, seed: int,
                 max_turns: int | None = None, game_index: int = 0) -> None:
        self.profile = profile
        self.prompts = prompts
        self.sink = sink

        seats = config_mod.seating(profile, COLORS, game_index)
        seat_meta = {
            color: {
                "model": models[color].get_config().get("model_id", seat.model),
                "access": seat.access,
            }
            for color, seat in seats.items()
        }
        self.hooks = GameHooks(sink, seat_meta, profile.budgets.max_tokens_per_game)

        #: The active deliberation's metered SearchBudget; None outside one.
        self._budget = None
        archivist_tool = make_archivist_tool(lambda: self._budget)

        system = {
            color: prompts.system_prompt(
                color=color,
                max_searches_per_turn=profile.budgets.max_searches_per_turn,
                max_note_chars=profile.budgets.max_note_chars,
            )
            for color in COLORS
        }
        self.agents = {
            color: build_detective(color, models[color], system[color],
                                   [self.hooks], archivist_tool)
            for color in COLORS
        }

        self.game = Game(GameConfig(
            seed=seed,
            max_turns=max_turns or profile.budgets.max_turns,
            max_searches_per_turn=profile.budgets.max_searches_per_turn,
            stack="strands",
            players={
                color: {"seat": seat.seat, "model": seat_meta[color]["model"],
                        "access": seat.access}
                for color, seat in seats.items()
            },
            profile=profile.name,
            prompt_set=prompts.provenance(),
            framework={"name": "strands",
                       "version": importlib.metadata.version("strands-agents")},
            # Scripted tier: the tool's body is the engine's baseline retriever;
            # no archivist model is called, and the transcript says so. A live
            # archivist replaces this block with model/access when it exists.
            archivist={"agent": "baseline-retriever",
                       "retrieval_profile": profile.archivist.retrieval_profile},
        ), sink)
        self._doc_ids = frozenset(d.id for d in self.game.archive.documents)

    # -- public -----------------------------------------------------------

    def play(self):
        detectives = {color: _Detective(self, color) for color in COLORS}
        return self.game.play(detectives)

    # -- shared helpers ---------------------------------------------------

    def ask(self, color: str, phase: str, game_turn: int, /, **variables: Any) -> str:
        """Render the phase template, invoke the agent, return its final text.

        The three positionals are positional-ONLY (the ``/``): templates
        declare variables named ``color`` and ``turn``, and those must be free
        to travel through ``**variables`` without colliding with parameters.
        """
        self.hooks.turn = game_turn
        self.hooks.purpose = phase
        prompt = self.prompts.turn[phase].render(**variables)
        result = self.agents[color](prompt)
        return str(result)

    def maybe_reasoning(self, color: str, turn: int, data: dict) -> None:
        """An optional "reasoning" key in any phase JSON becomes the event —
        private to the detective, visible to spectators and the judge."""
        text = data.get("reasoning")
        if isinstance(text, str) and text.strip():
            self.sink.emit("agent_reasoning", {"player": color, "text": text.strip()},
                           turn=turn)

    def gate_note(self, color: str, turn: int, note: str) -> str | None:
        """Contract §5 and §6 on the one free-text channel: truncate visibly,
        block out-of-fiction attacks, let cunning through."""
        note = note[: self.profile.budgets.max_note_chars]
        violation = guardrails.check(note, self._doc_ids)
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

    def render_table(self, view) -> str:
        lines = []
        for r in view.suggestions()[-TABLE_LIMIT:]:
            refuted = f"refuted by {r.refuter}" if r.refuter else "NOBODY could refute"
            note = f' — note: "{r.note}"' if r.note else ""
            lines.append(f"- turn {r.turn}: {r.player} suggested "
                         f"{r.who} / {r.how} / {r.where} ({refuted}){note}")
        return "\n".join(lines) if lines else "(no suggestions yet)"

    def render_candidates(self, view) -> str:
        known = set(view.known_not_solution())
        parts = []
        for dim in DIMENSIONS:
            open_ = [e for e in ELEMENTS[dim] if e not in known]
            parts.append(f"{dim}: {', '.join(open_)}")
        return " | ".join(parts)

    def render_turn_summary(self, color: str, events: tuple[dict, ...]) -> str:
        lines = []
        for event in events:
            kind, p = event["type"], event["payload"]
            if kind == "suggestion_made":
                lines.append(f"you suggested {p['who']} / {p['how']} / {p['where']}")
            elif kind == "refutation_made":
                if p["refuter"] is None:
                    lines.append("NOBODY could refute your suggestion")
                else:
                    lines.append(f"{p['refuter']} privately showed you: {p['element']}")
            elif kind == "archive_searched":
                lines.append(f'you searched "{p["query"]}" -> '
                             f'{", ".join(p["results"]) or "nothing"}')
            elif kind == "accusation_made":
                verdict = "CORRECT" if p["correct"] else "wrong — you are out"
                lines.append(f"you accused {p['who']} / {p['how']} / {p['where']}: {verdict}")
            elif kind == "invalid_action":
                lines.append(f"invalid {p['phase']}: {p['reason']}")
        return "\n".join(f"- {line}" for line in lines) if lines else "- (a quiet turn)"


class _Detective:
    """The engine-facing adapter for one colour. Its name lands in game_started."""

    name = "llm-detective"

    def __init__(self, harness: AlibiHarness, color: str) -> None:
        self.h = harness
        self.color = color

    # -- phases -----------------------------------------------------------

    def suggest(self, ctx) -> Suggestion | None:
        if self.h.hooks.exhausted:
            return None  # ceiling spent: the game plays out in passes
        self.h._budget = ctx.archive
        try:
            agent = self.h.agents[self.color]
            reply = self.h.ask(
                self.color, "suggest", ctx.turn,
                turn=ctx.turn, color=self.color,
                hand=", ".join(ctx.view.my_hand()),
                eliminated=", ".join(ctx.view.known_not_solution()) or "(none)",
                table=self.h.render_table(ctx.view),
                memory=render_memory(agent),
            )
        finally:
            self.h._budget = None

        data = parse_object(reply)
        self.h.maybe_reasoning(self.color, ctx.turn, data)
        if data.get("action") == "pass":
            return None
        if data.get("action") != "suggest":
            raise ValueError(f"unknown action {data.get('action')!r}")
        note = data.get("note")
        if isinstance(note, str) and note.strip():
            note = self.h.gate_note(self.color, ctx.turn, note.strip())
        else:
            note = None
        return Suggestion(str(data.get("who")), str(data.get("how")),
                          str(data.get("where")), note)

    def show(self, ctx) -> str:
        if self.h.hooks.exhausted:
            raise BudgetExceeded("ceiling spent — the engine chooses")
        s = ctx.suggestion
        reply = self.h.ask(
            self.color, "show", ctx.turn,
            suggester=ctx.suggester,
            suggestion=f"{s.who} / {s.how} / {s.where}",
            options=", ".join(ctx.options),
        )
        data = parse_object(reply)
        self.h.maybe_reasoning(self.color, ctx.turn, data)
        return str(data.get("show"))

    def accuse(self, ctx) -> Triple | None:
        if self.h.hooks.exhausted:
            return None
        if ctx.refutation is not None:
            refuter, element = ctx.refutation
            outcome = (f"The {refuter} detective privately showed you: {element}. "
                       f"That element is certainly NOT part of the truth.")
        elif ctx.no_refutation is not None:
            s = ctx.no_refutation
            outcome = (f"NOBODY could refute your suggestion "
                       f"({s.who} / {s.how} / {s.where}). If you hold none of "
                       f"those three yourself, that suggestion IS the answer.")
        else:
            outcome = "You made no suggestion this turn."

        self.h._budget = ctx.archive
        try:
            agent = self.h.agents[self.color]
            reply = self.h.ask(self.color, "accuse", ctx.turn,
                               outcome=outcome, memory=render_memory(agent))
        finally:
            self.h._budget = None

        data = parse_object(reply)
        self.h.maybe_reasoning(self.color, ctx.turn, data)
        if data.get("action") == "accuse":
            return Triple(str(data.get("who")), str(data.get("how")),
                          str(data.get("where")))
        if data.get("action") == "wait":
            return None
        raise ValueError(f"unknown action {data.get('action')!r}")

    def conclude(self, ctx) -> Belief:
        if self.h.hooks.exhausted:
            raise BudgetExceeded("ceiling spent — no belief to declare")
        agent = self.h.agents[self.color]
        reply = self.h.ask(self.color, "conclude", ctx.turn,
                           candidates=self.h.render_candidates(ctx.view),
                           memory=render_memory(agent))
        data = parse_object(reply)
        self.h.maybe_reasoning(self.color, ctx.turn, data)
        confidence = data.get("confidence") or {}
        return Belief(
            who=str(data.get("who")), how=str(data.get("how")),
            where=str(data.get("where")),
            confidence={dim: float(confidence.get(dim, 0)) for dim in DIMENSIONS},
        )

    def reflect(self, end) -> None:
        if self.h.hooks.exhausted:
            return
        agent = self.h.agents[self.color]
        reply = self.h.ask(
            self.color, "reflect", end.turn,
            turn=end.turn,
            turn_summary=self.h.render_turn_summary(self.color, end.events),
            memory=render_memory(agent),
        )
        try:
            notes = parse_array(reply)
        except ValueError:
            return  # a reflect that says nothing loses only its own notes
        for raw in notes[:MAX_NOTES_PER_REFLECT]:
            if not isinstance(raw, dict) or not str(raw.get("text", "")).strip():
                continue
            about = raw.get("about")
            if about not in ALL_ELEMENTS and about not in COLORS:
                about = None
            note = write_note(agent, raw["text"], end.turn,
                              kind=raw.get("kind"), about=about)
            self.h.sink.emit("memory_write", {
                "player": self.color,
                "kind": note["kind"],
                "about": note["about"],
                "text": note["text"],
            }, turn=end.turn)
