"""The ALIBI harness on LangGraph — four ``create_agent`` loops over the engine.

Structurally the twin of the Strands harness: the engine drives the phases,
each phase renders one shared template, the agent answers (consulting the
archivist tool mid-thought), and the harness hands the engine exactly what the
model said. What differs is pure grain: conversations live in the checkpointer
under ``thread_id=color``, notebooks on the framework ``Store``, metering in a
callback the framework propagates to every call underneath an invoke.
"""

from __future__ import annotations

import importlib.metadata
import json
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from alibi_engine.case import ALL_ELEMENTS, COLORS, DIMENSIONS, ELEMENTS
from alibi_engine.deciders import Belief, Suggestion, Triple
from alibi_engine.game import Game, GameConfig

from . import config as config_mod
from . import guardrails
from . import memory as notebook
from .meter import BudgetExceeded, Meter
from .players import build_detective, make_archivist_tool
from .prompts import PromptSet

TABLE_LIMIT = 12
MAX_NOTES_PER_REFLECT = 3


def parse_object(text: str) -> dict:
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
        self.meter = Meter(sink, seat_meta, profile.budgets.max_tokens_per_game)

        self.store = InMemoryStore()
        self.checkpointer = InMemorySaver()
        self._budget = None
        archivist_tool = make_archivist_tool(lambda: self._budget)

        self.agents = {
            color: build_detective(
                color, models[color],
                prompts.system_prompt(
                    color=color,
                    max_searches_per_turn=profile.budgets.max_searches_per_turn,
                    max_note_chars=profile.budgets.max_note_chars,
                ),
                self.meter, self.store, self.checkpointer, archivist_tool,
            )
            for color in COLORS
        }

        self.game = Game(GameConfig(
            seed=seed,
            max_turns=max_turns or profile.budgets.max_turns,
            max_searches_per_turn=profile.budgets.max_searches_per_turn,
            stack="langgraph",
            players={
                color: {"seat": seat.seat, "model": seat_meta[color]["model"],
                        "access": seat.access}
                for color, seat in seats.items()
            },
            profile=profile.name,
            prompt_set=prompts.provenance(),
            framework={"name": "langgraph",
                       "version": importlib.metadata.version("langgraph")},
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
        """Render, invoke on the colour's thread, return the final text.

        Positional-only parameters (the ``/``): templates declare variables
        named ``color`` and ``turn``, which travel through ``**variables``.
        """
        self.meter.turn = game_turn
        self.meter.purpose = phase
        self.meter.color = color
        prompt = self.prompts.turn[phase].render(**variables)
        state = self.agents[color].invoke(
            {"messages": [HumanMessage(prompt)]},
            {"configurable": {"thread_id": color}, "callbacks": [self.meter]},
        )
        return state["messages"][-1].text or ""

    def maybe_reasoning(self, color: str, turn: int, data: dict) -> None:
        text = data.get("reasoning")
        if isinstance(text, str) and text.strip():
            self.sink.emit("agent_reasoning", {"player": color, "text": text.strip()},
                           turn=turn)

    def gate_note(self, color: str, turn: int, note: str) -> str | None:
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
    """The engine-facing adapter for one colour."""

    name = "llm-detective"

    def __init__(self, harness: AlibiHarness, color: str) -> None:
        self.h = harness
        self.color = color

    def suggest(self, ctx) -> Suggestion | None:
        if self.h.meter.exhausted:
            return None
        self.h._budget = ctx.archive
        try:
            reply = self.h.ask(
                self.color, "suggest", ctx.turn,
                turn=ctx.turn, color=self.color,
                hand=", ".join(ctx.view.my_hand()),
                eliminated=", ".join(ctx.view.known_not_solution()) or "(none)",
                table=self.h.render_table(ctx.view),
                memory=notebook.render_memory(self.h.store, self.color),
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
        if self.h.meter.exhausted:
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
        if self.h.meter.exhausted:
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
            reply = self.h.ask(self.color, "accuse", ctx.turn,
                               outcome=outcome,
                               memory=notebook.render_memory(self.h.store, self.color))
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
        if self.h.meter.exhausted:
            raise BudgetExceeded("ceiling spent — no belief to declare")
        reply = self.h.ask(self.color, "conclude", ctx.turn,
                           candidates=self.h.render_candidates(ctx.view),
                           memory=notebook.render_memory(self.h.store, self.color))
        data = parse_object(reply)
        self.h.maybe_reasoning(self.color, ctx.turn, data)
        confidence = data.get("confidence") or {}
        return Belief(
            who=str(data.get("who")), how=str(data.get("how")),
            where=str(data.get("where")),
            confidence={dim: float(confidence.get(dim, 0)) for dim in DIMENSIONS},
        )

    def reflect(self, end) -> None:
        if self.h.meter.exhausted:
            return
        reply = self.h.ask(
            self.color, "reflect", end.turn,
            turn=end.turn,
            turn_summary=self.h.render_turn_summary(self.color, end.events),
            memory=notebook.render_memory(self.h.store, self.color),
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
            note = notebook.write_note(self.h.store, self.color, raw["text"],
                                       end.turn, kind=raw.get("kind"), about=about)
            self.h.sink.emit("memory_write", {
                "player": self.color,
                "kind": note["kind"],
                "about": note["about"],
                "text": note["text"],
            }, turn=end.turn)
