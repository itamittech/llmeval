"""The optional per-turn hooks an agent harness plugs into.

`choose` runs once per ROLL; `negotiate` and `reflect` run once per TURN. A six
or a capture earns another roll, so the difference is real — an agent that
negotiated on every extra roll would get a free multiplier on influence and
cost. See docs/projects/ludo/harness-contract.md.
"""

import pytest

from ludo_engine.board import BASE, COLORS
from ludo_engine.deciders import FirstLegal, Negotiator, RandomBot, Reflector
from ludo_engine.events import ListSink
from ludo_engine.game import Game, GameConfig

from test_game import ScriptedDice


class Recorder(FirstLegal):
    """A decider that also implements both optional hooks."""

    name = "recorder"

    def __init__(self):
        self.negotiated = []
        self.reflected = []
        self.chose = 0

    def negotiate(self, start):
        self.negotiated.append((start.turn, start.color))

    def choose(self, ctx):
        self.chose += 1
        return super().choose(ctx)

    def reflect(self, end):
        self.reflected.append(end)


def play(deciders, seed=7, max_turns=40, dice=None):
    game = Game(GameConfig(seed=seed, max_turns=max_turns), ListSink())
    if dice is not None:
        game.dice = dice
    return game, game.play(deciders)


def test_a_plain_decider_needs_neither_hook():
    # RandomBot has no negotiate/reflect. The engine must not require them —
    # this is what keeps bot games (and turn_order.py) runnable.
    _, outcome = play({c: RandomBot(seed=i) for i, c in enumerate(COLORS)})
    assert outcome.turns_played > 0


def test_protocols_detect_the_hooks_structurally():
    assert isinstance(Recorder(), Negotiator)
    assert isinstance(Recorder(), Reflector)
    assert not isinstance(RandomBot(seed=1), Negotiator)
    assert not isinstance(RandomBot(seed=1), Reflector)


def test_negotiate_and_reflect_fire_once_per_turn():
    red = Recorder()
    deciders = {c: RandomBot(seed=i) for i, c in enumerate(COLORS)}
    deciders["red"] = red

    play(deciders)

    assert red.negotiated, "the hook ran at all"
    assert len(red.negotiated) == len(red.reflected)
    assert all(color == "red" for _, color in red.negotiated)
    # Each turn number seen exactly once, in order.
    turns = [t for t, _ in red.negotiated]
    assert turns == sorted(set(turns))


def test_extra_rolls_multiply_choose_but_not_negotiate():
    """The rule this whole design exists for."""
    red = Recorder()
    deciders = {c: FirstLegal() for c in COLORS}
    deciders["red"] = red

    # Red rolls 6 (leave base), 6 (move), 6 -> three sixes cancels the turn.
    # Everyone else rolls 1s and stays in base with no legal move.
    game, _ = play(deciders, max_turns=1, dice=ScriptedDice([6, 6, 6], tail=1))

    assert red.chose == 2, "two rolls produced two move choices"
    assert len(red.negotiated) == 1, "negotiation is once per TURN, not per roll"
    assert len(red.reflected) == 1


def test_reflect_receives_the_turn_reason_and_its_events():
    red = Recorder()
    deciders = {c: FirstLegal() for c in COLORS}
    deciders["red"] = red

    play(deciders, max_turns=1, dice=ScriptedDice([6, 6, 6], tail=1))

    end = red.reflected[0]
    assert end.reason == "three_sixes"
    kinds = [e["type"] for e in end.events]
    assert kinds[0] == "turn_started"
    assert kinds[-1] == "turn_ended"
    assert kinds.count("dice_rolled") == 3


def test_reflect_sees_the_board_after_the_turn_resolved():
    red = Recorder()
    deciders = {c: FirstLegal() for c in COLORS}
    deciders["red"] = red

    # A single 6 puts one token on the start square and ends the turn there
    # (the extra roll is a 1, which has no legal move for a token at 0... it
    # does: 0 -> 1). Use 6 then 1 to move on.
    play(deciders, max_turns=1, dice=ScriptedDice([6, 1], tail=1))

    end = red.reflected[0]
    assert end.color == "red"
    assert end.state.tokens("red").count(BASE) == 3, "one token left the base"


def test_a_failing_hook_is_not_swallowed():
    """Unlike `choose`, whose failure means a forfeit — a defined outcome.

    A provider error mid-negotiation has no in-game meaning, so it belongs to
    the harness that made the call. Hiding it here would produce a transcript
    that lies about what happened.
    """

    class Broken(FirstLegal):
        name = "broken"

        def negotiate(self, start):
            raise RuntimeError("provider exploded")

    deciders = {c: FirstLegal() for c in COLORS}
    deciders["red"] = Broken()

    with pytest.raises(RuntimeError, match="provider exploded"):
        play(deciders)


def test_a_failing_choose_still_only_forfeits():
    """The contrast: `choose` failures are absorbed, because forfeit is real."""

    class Broken(FirstLegal):
        name = "broken-choose"

        def choose(self, ctx):
            raise RuntimeError("provider exploded")

    deciders = {c: FirstLegal() for c in COLORS}
    deciders["red"] = Broken()

    # Red must roll a 6, or it has no legal move and `choose` never runs.
    _, outcome = play(deciders, max_turns=1, dice=ScriptedDice([6], tail=1))

    assert outcome.turns_played == 1, "the game continued rather than crashing"
    red = next(s for s in outcome.standings if s["player"] == "red")
    assert red["turns_forfeited"] == 1
