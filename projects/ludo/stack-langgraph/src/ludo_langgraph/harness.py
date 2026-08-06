"""The turn loop: the engine's agent hooks, bound to LangGraph.

The engine drives the game and calls three hooks per turn
(``negotiate`` → ``choose``+ → ``reflect``); this module answers them:

    negotiate  a fresh :class:`~ludo_langgraph.table.Table` graph per turn —
               ADR-0009's floor-passing protocol drawn as nodes and edges,
               with ``pass_floor`` a real framework tool run by ``ToolNode``.
    choose     one invocation of the player's ``create_agent`` on its own
               thread (a retry render on attempt 2, same thread — the model
               sees its own rejected answer). The reply names a move; the
               engine validates it — never this module (ADR-0004).
    reflect    one invocation on the same thread; parsed notes land in the
               framework's ``Store`` and emit ``memory_write``.

Decide and reflect share one persistent conversation per agent — held by the
**checkpointer** under ``thread_id=color``, not by any object here. When it
outgrows the game's ``max_context_tokens`` budget, the framework's
summarisation middleware compacts it *inside* the next invocation
(:class:`~ludo_langgraph.players.Compactor` — harness-contract §5); the
harness never checks, because the framework owns the moment.

Token accounting and the budget ceiling live in :class:`~ludo_langgraph.meter.Meter`,
carried by the framework's callback propagation to every model call made
anywhere underneath an invoke — including the summariser's.

Context is rendered fresh into each prompt (board, standings, legal moves,
recent events, memory) because the prompt language has no logic — the code
renders it and passes one variable, per shared/prompts/README.md.
"""

from __future__ import annotations

import json
import re
from collections import deque
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from ludo_engine.board import COLORS, HOME
from ludo_engine.deciders import StateView, TurnContext, TurnEnd, TurnStart
from ludo_engine.events import EventSink, TeeSink
from ludo_engine.game import Game, GameConfig, Outcome
from ludo_engine.moves import Move

from .config import Profile, seating
from .memory import render_memory, write_note
from .meter import BudgetExceeded, Meter
from .players import build_player
from .prompts import PromptSet
from .table import Table

_JSON = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict:
    """The first JSON object in a model reply, fenced or bare.

    Raises ``ValueError`` when there is none — in ``choose`` that costs the
    attempt (the engine's defined meaning for a broken decider), never the run.
    """
    try:
        return json.loads(text)
    except ValueError:
        pass
    match = _JSON.search(text)
    if not match:
        raise ValueError(f"no JSON object in reply: {text[:80]!r}")
    return json.loads(match.group())


# -- context renders ------------------------------------------------------
# The "code renders it" half of the no-template-logic rule. Byte-identical to
# the other two stacks' renders: {{board}} must not depend on the framework.


def _position(p: int) -> str:
    if p == -1:
        return "base"
    if p == HOME:
        return "home"
    if 51 <= p < HOME:
        return f"column+{p - 50}"
    return str(p)


def render_board(view: StateView) -> str:
    return "\n".join(
        f"- {color}: " + ", ".join(_position(p) for p in view.tokens(color))
        for color in COLORS
    )


def render_standings(view: StateView) -> str:
    order = sorted(COLORS, key=lambda c: (view.tokens_home(c), view.progress(c)),
                   reverse=True)
    return "\n".join(
        f"- {c}: {view.tokens_home(c)} home, progress {view.progress(c)}"
        for c in order
    )


def render_moves(moves: list[Move]) -> str:
    return "\n".join(
        f"- token {m.token}: {_position(m.frm)} -> {_position(m.to)}"
        f' (reply {{"token": {m.token}, "to": {m.to}}})'
        for m in moves
    )


def render_events(events: tuple[dict, ...]) -> str:
    return "\n".join(
        f"- {e['type']}: {json.dumps(e['payload'], separators=(',', ':'))}"
        for e in events
    ) or "(none)"


class _EventWindow(EventSink):
    """A rolling window over the merged stream — the ``{{recent_events}}`` variable."""

    def __init__(self, limit: int = 30) -> None:
        super().__init__()
        self.lines: deque[str] = deque(maxlen=limit)

    def _write(self, event: dict) -> None:
        payload = json.dumps(event["payload"], separators=(",", ":"))
        self.lines.append(f"- [turn {event['turn']}] {event['type']}: {payload[:160]}")

    def render(self) -> str:
        return "\n".join(self.lines) if self.lines else "(none yet)"


# -- the harness ----------------------------------------------------------


class _Decider:
    """The engine-facing face of one seat. Thin on purpose."""

    def __init__(self, harness: "LudoHarness", color: str, label: str) -> None:
        self._harness = harness
        self._color = color
        self.name = label

    def negotiate(self, start: TurnStart) -> None:
        self._harness.negotiate(start)

    def choose(self, ctx: TurnContext) -> Move:
        return self._harness.choose(ctx)

    def reflect(self, end: TurnEnd) -> None:
        self._harness.reflect(end)


class LudoHarness:
    """One game: four agents, one shared event stream, one budget."""

    def __init__(self, profile: Profile, prompts: PromptSet,
                 models: dict[str, Any], sink: EventSink,
                 seed: int = 1, game_index: int = 0,
                 max_turns: int | None = None,
                 session_dir: Path | None = None) -> None:
        self.prompts = prompts
        self.budgets = profile.budgets
        self._last_reply: dict[str, str] = {}
        self._inboxes: dict[str, list[str]] = {}

        seat_by_color = seating(profile, COLORS, game_index)
        # The label names what actually answers — a scripted run must say
        # "scripted", never the seat's real model id, or the transcript lies.
        labels = {
            color: str(getattr(models[color], "model_label", "")
                       or getattr(models[color], "model", "")
                       or seat.model or "unknown")
            for color, seat in seat_by_color.items()
        }

        #: One tee: engine events and agent events share one sequence, which is
        #: what makes the transcript a single ordered record (ADR-0003).
        self._window = _EventWindow()
        self.sink = TeeSink(sink, self._window)

        self.meter = Meter(
            self.sink,
            {c: {"model": labels[c], "access": seat_by_color[c].access} for c in COLORS},
            self.budgets.max_tokens_per_game,
        )

        self._systems = {
            color: prompts.system_prompt(
                color=color,
                max_floor_passes=self.budgets.max_floor_passes,
                max_message_chars=self.budgets.max_message_chars,
            )
            for color in COLORS
        }
        #: The framework's two state holders — conversations in the
        #: checkpointer (one thread per colour), beliefs in the store (one
        #: namespace per colour). With a session directory, both become
        #: durable — see :mod:`ludo_langgraph.session`.
        self.checkpointer, self.store, self._session = _open_state(session_dir)
        self._models = models
        self.players = {
            color: build_player(color, models[color], self._systems[color],
                                self.meter, self.store, self.checkpointer,
                                self.sink, self.budgets.max_context_tokens)
            for color in COLORS
        }
        self.deciders = {
            color: _Decider(self, color, f"langgraph:{labels[color]}")
            for color in COLORS
        }

        self.game = Game(
            GameConfig(
                seed=seed,
                max_turns=max_turns or self.budgets.max_turns,
                stack="langgraph",
                players={
                    color: {
                        "agent": f"langgraph:{labels[color]}",
                        "seat": seat_by_color[color].seat,
                        "model": labels[color],
                        "access": seat_by_color[color].access,
                    }
                    for color in COLORS
                },
            ),
            self.sink,
        )

    def play(self) -> Outcome:
        return self.game.play(self.deciders)

    def conversation(self, color: str) -> list:
        """The framework-held decide/reflect thread — a test window."""
        agent = self.players[color]
        state = agent.get_state({"configurable": {"thread_id": color}})
        return list(state.values.get("messages", []))

    def _thread(self, color: str) -> dict:
        return {"configurable": {"thread_id": color}, "callbacks": [self.meter]}

    def _drain_inbox(self, color: str) -> str:
        """The ``{{inbox}}`` variable — consumed into a briefing, then gone."""
        lines = self._inboxes.pop(color, [])
        return "\n".join(f"- {line}" for line in lines) if lines else "(none)"

    # -- negotiate --------------------------------------------------------

    def negotiate(self, start: TurnStart) -> None:
        self.meter.turn = start.turn
        self.meter.purpose = "negotiate"
        if self.meter.exhausted:
            return
        try:
            self._run_table(start)
        except Exception:
            # A provider failing mid-conversation has no in-game meaning
            # (harness-contract §2.1), so it must not escape an engine hook.
            # Whatever was said before the failure is already in the
            # transcript; the turn simply goes on to the roll.
            pass

    def _run_table(self, start: TurnStart) -> None:
        briefing = self.prompts.turn["briefing"]
        briefings = {
            color: briefing.render(
                color=color,
                inbox=self._drain_inbox(color),
                memory=render_memory(self.store, color),
            )
            for color in COLORS
        }
        task = self.prompts.turn["negotiate"].render(
            turn=start.turn,
            active=start.color,
            board=render_board(start.state),
            standings=render_standings(start.state),
        )
        # The table is ephemeral by design (ADR-0009): a fresh graph over the
        # players' MODELS — never their threads. Nothing said here enters the
        # decide/reflect conversations; the transcript is the durable record.
        table = Table(COLORS, self._models, self._systems, briefings, task,
                      self.meter, self.sink, self._inboxes,
                      self.budgets.max_floor_passes,
                      self.budgets.max_message_chars)
        table.run(start.color, callbacks=[self.meter])

    # -- choose -----------------------------------------------------------

    def choose(self, ctx: TurnContext) -> Move:
        self.meter.turn = ctx.turn
        self.meter.color = ctx.color
        if self.meter.exhausted:
            # The engine records this as a forfeit — the defined in-game
            # outcome — and the game runs on to its cap without model calls.
            raise BudgetExceeded("per-game token ceiling reached")

        self.meter.purpose = "move"
        if ctx.attempt == 1:
            prompt = self.prompts.turn["decide"].render(
                turn=ctx.turn, color=ctx.color, die=ctx.die,
                board=render_board(ctx.state),
                legal_moves=render_moves(ctx.legal_moves),
                recent_events=self._window.render(),
                memory=render_memory(self.store, ctx.color),
            )
        else:
            # Same conversation, so the model sees its own rejected answer.
            prompt = self.prompts.turn["retry"].render(
                reason="not a legal move for this roll",
                rejected=self._last_reply.get(ctx.color, "(no parseable reply)"),
                legal_moves=render_moves(ctx.legal_moves),
            )

        state = self.players[ctx.color].invoke(
            {"messages": [HumanMessage(prompt)]}, self._thread(ctx.color))
        reply = state["messages"][-1].text or ""
        self._last_reply[ctx.color] = reply.strip()

        data = extract_json(reply)
        reasoning = str(data.get("reasoning", "")).strip()
        if reasoning:
            self.sink.emit("agent_reasoning",
                           {"player": ctx.color, "text": reasoning}, turn=ctx.turn)

        token, to = int(data["token"]), int(data["to"])
        for move in ctx.legal_moves:
            if move.token == token and move.to == to:
                return move

        # Not legal. Return it anyway: rejecting is the ENGINE's job, and the
        # rejection event plus the retry render is the whole §6 failure path.
        frm = ctx.state.tokens(ctx.color)[token] if 0 <= token <= 3 else -1
        return Move(token, frm, to)

    # -- reflect ----------------------------------------------------------

    def reflect(self, end: TurnEnd) -> None:
        self.meter.turn = end.turn
        self.meter.color = end.color
        self.meter.purpose = "reflect"
        if self.meter.exhausted:
            return

        try:
            prompt = self.prompts.turn["reflect"].render(
                turn=end.turn, color=end.color,
                turn_summary=render_events(end.events),
                memory=render_memory(self.store, end.color),
            )
            state = self.players[end.color].invoke(
                {"messages": [HumanMessage(prompt)]}, self._thread(end.color))
            notes = extract_json(state["messages"][-1].text or "").get("notes") or []
        except Exception:
            # Best-effort by contract: a failed reflection loses a note,
            # never the game — and it must not escape an engine hook.
            return

        for raw in notes:
            if not isinstance(raw, dict):
                continue
            text = str(raw.get("text", "")).strip()
            if not text:
                continue
            about = raw.get("about") if raw.get("about") in COLORS else None
            note = write_note(self.store, end.color, text, end.turn,
                              raw.get("kind"), about)
            self.sink.emit("memory_write", {
                "player": end.color, "kind": note["kind"],
                "about": note["about"], "text": note["text"],
            }, turn=end.turn)


def _open_state(session_dir: Path | None):
    """The two framework state holders, in-memory by default, durable opt-in."""
    if session_dir is None:
        return InMemorySaver(), InMemoryStore(), None
    from .session import open_session
    return open_session(session_dir)
