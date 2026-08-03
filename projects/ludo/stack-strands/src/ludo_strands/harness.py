"""The turn loop: the engine's agent hooks, bound to Strands.

The engine drives the game and calls three hooks per turn
(``negotiate`` → ``choose``+ → ``reflect``); this module answers them:

    negotiate  a fresh ``Swarm`` per turn — the floor-passing table of
               ADR-0009. Directed messages are handoffs, table notes ride the
               handoff context, the pass cap is ``max_handoffs``. Per-agent
               briefings are seeded into each agent's history *before* the
               swarm is constructed: Swarm snapshots state at construction and
               resets each activation to that snapshot, which turns the reset
               semantics into the briefing delivery mechanism.
    choose     one direct agent call (a retry render on attempt 2). The reply
               names a move; the engine validates it — never this module
               (ADR-0004).
    reflect    one direct agent call; parsed notes land in ``AgentState`` and
               emit ``memory_write``.

Token accounting, the budget ceiling, and message capture live in
:mod:`ludo_strands.hooks`, fired by the framework, not called from here.

Context is rendered fresh into each prompt (board, standings, legal moves,
recent events, memory) because the prompt language has no logic — the code
renders it and passes one variable, per shared/prompts/README.md.
"""

from __future__ import annotations

import json
import re
from collections import deque
from typing import Any

from ludo_engine.board import COLORS, HOME
from ludo_engine.deciders import StateView, TurnContext, TurnEnd, TurnStart
from ludo_engine.events import EventSink, TeeSink
from ludo_engine.game import Game, GameConfig, Outcome
from ludo_engine.moves import Move
from strands.multiagent import Swarm

from .config import Profile, seating
from .hooks import BudgetExceeded, GameHooks
from .players import build_player, render_memory, write_note
from .prompts import PromptSet

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
# The "code renders it" half of the no-template-logic rule.


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
    """The engine-facing face of one seat. Thin on purpose: the engine's

    ``isinstance`` checks see negotiate/choose/reflect, and everything they do
    is the harness's job.
    """

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
                 max_turns: int | None = None) -> None:
        self.prompts = prompts
        self.budgets = profile.budgets
        self._last_reply: dict[str, str] = {}

        seat_by_color = seating(profile, COLORS, game_index)
        # The label names what actually answers — a scripted run must say
        # "scripted", never the seat's real model id, or the transcript lies.
        labels = {
            color: str(models[color].get_config().get("model_id")
                       or seat.model or "unknown")
            for color, seat in seat_by_color.items()
        }

        #: One tee: engine events and agent events share one sequence, which is
        #: what makes the transcript a single ordered record (ADR-0003).
        self._window = _EventWindow()
        self.sink = TeeSink(sink, self._window)

        self.hooks = GameHooks(
            self.sink,
            {c: {"model": labels[c], "access": seat_by_color[c].access} for c in COLORS},
            self.budgets.max_tokens_per_game,
        )

        system = {
            color: prompts.system_prompt(
                color=color,
                max_floor_passes=self.budgets.max_floor_passes,
                max_message_chars=self.budgets.max_message_chars,
            )
            for color in COLORS
        }
        self.players = {
            color: build_player(color, models[color], system[color], [self.hooks])
            for color in COLORS
        }
        self.deciders = {
            color: _Decider(self, color, f"strands:{labels[color]}")
            for color in COLORS
        }

        self.game = Game(
            GameConfig(
                seed=seed,
                max_turns=max_turns or self.budgets.max_turns,
                stack="strands",
                players={
                    color: {
                        "agent": f"strands:{labels[color]}",
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

    # -- negotiate --------------------------------------------------------

    def negotiate(self, start: TurnStart) -> None:
        self.hooks.turn = start.turn
        self.hooks.purpose = "negotiate"
        if self.hooks.exhausted:
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
        for color, agent in self.players.items():
            text = briefing.render(
                color=color,
                inbox=self.hooks.drain_inbox(color),
                memory=render_memory(agent),
            )
            # Seeded BEFORE the swarm exists: construction snapshots this, and
            # every activation resets to it — the reset is the delivery.
            agent.messages = [
                {"role": "user", "content": [{"text": text}]},
                {"role": "assistant", "content": [{"text": "Noted."}]},
            ]

        task = self.prompts.turn["negotiate"].render(
            turn=start.turn,
            active=start.color,
            board=render_board(start.state),
            standings=render_standings(start.state),
        )
        table = Swarm(
            nodes=[self.players[c] for c in COLORS],
            entry_point=self.players[start.color],
            max_handoffs=self.budgets.max_floor_passes,
            max_iterations=self.budgets.max_floor_passes + 1,
        )
        table(task)

    # -- choose -----------------------------------------------------------

    def choose(self, ctx: TurnContext) -> Move:
        self.hooks.turn = ctx.turn
        self.hooks.purpose = "move"
        if self.hooks.exhausted:
            # The engine records this as a forfeit — the defined in-game
            # outcome — and the game runs on to its cap without model calls.
            raise BudgetExceeded("per-game token ceiling reached")

        agent = self.players[ctx.color]
        if ctx.attempt == 1:
            agent.messages = []
            prompt = self.prompts.turn["decide"].render(
                turn=ctx.turn, color=ctx.color, die=ctx.die,
                board=render_board(ctx.state),
                legal_moves=render_moves(ctx.legal_moves),
                recent_events=self._window.render(),
                memory=render_memory(agent),
            )
        else:
            # Same conversation, so the model sees its own rejected answer.
            prompt = self.prompts.turn["retry"].render(
                reason="not a legal move for this roll",
                rejected=self._last_reply.get(ctx.color, "(no parseable reply)"),
                legal_moves=render_moves(ctx.legal_moves),
            )

        reply = str(agent(prompt))
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
        self.hooks.turn = end.turn
        self.hooks.purpose = "reflect"
        if self.hooks.exhausted:
            return

        agent = self.players[end.color]
        try:
            agent.messages = []
            prompt = self.prompts.turn["reflect"].render(
                turn=end.turn, color=end.color,
                turn_summary=render_events(end.events),
                memory=render_memory(agent),
            )
            notes = extract_json(str(agent(prompt))).get("notes") or []
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
            note = write_note(agent, text, end.turn, raw.get("kind"), about)
            self.sink.emit("memory_write", {
                "player": end.color, "kind": note["kind"],
                "about": note["about"], "text": note["text"],
            }, turn=end.turn)
