from ludo_engine.board import BASE, COLORS, HOME
from ludo_engine.deciders import FirstLegal, RandomBot
from ludo_engine.events import ListSink
from ludo_engine.game import Game, GameConfig
from ludo_engine.moves import Move


class ScriptedDice:
    """Deterministic dice for rules that are hard to reach by luck."""

    def __init__(self, script, tail=1):
        self._script = list(script)
        self._tail = tail
        self.rolls = 0

    def roll(self):
        self.rolls += 1
        return self._script.pop(0) if self._script else self._tail


def build(seed=1, max_turns=400, dice=None):
    sink = ListSink()
    game = Game(GameConfig(seed=seed, max_turns=max_turns), sink)
    if dice is not None:
        game.dice = dice
    return game, sink


def types(sink):
    return [e["type"] for e in sink.events]


def test_a_game_terminates_and_produces_full_standings():
    game, sink = build()
    outcome = game.play({c: FirstLegal() for c in COLORS})

    assert outcome.reason in ("completed", "turn_cap")
    assert len(outcome.standings) == 4
    assert [s["rank"] for s in outcome.standings] == [1, 2, 3, 4]
    assert types(sink)[0] == "game_started"
    assert types(sink)[-1] == "game_ended"


def test_seq_numbers_are_contiguous():
    game, sink = build(seed=5)
    game.play({c: RandomBot(seed=c_i) for c_i, c in enumerate(COLORS)})
    assert [e["seq"] for e in sink.events] == list(range(len(sink.events)))


def test_same_seed_replays_identically():
    def run():
        game, sink = build(seed=77)
        game.play({c: RandomBot(seed=i) for i, c in enumerate(COLORS)})
        return sink.events

    assert run() == run()


def test_turn_cap_is_a_normal_outcome():
    game, sink = build(seed=3, max_turns=5)
    outcome = game.play({c: FirstLegal() for c in COLORS})

    assert outcome.reason == "turn_cap"
    assert outcome.turns_played == 5
    assert sink.events[-1]["payload"]["reason"] == "turn_cap"


def test_a_six_grants_an_extra_roll():
    game, sink = build(dice=ScriptedDice([6, 3]))
    game.play({c: FirstLegal() for c in COLORS})

    granted = [e for e in sink.events if e["type"] == "extra_roll_granted"]
    assert granted and granted[0]["payload"] == {"player": "red", "reason": "six"}


def test_three_consecutive_sixes_cancel_the_whole_turn():
    game, sink = build(dice=ScriptedDice([6, 6, 6]), max_turns=1)
    game.play({c: FirstLegal() for c in COLORS})

    assert game.state.tokens["red"] == [BASE] * 4, "movement must be reverted"
    ended = [e for e in sink.events if e["type"] == "turn_ended"]
    assert ended[0]["payload"] == {"player": "red", "reason": "three_sixes"}
    # Bad luck is not agent failure, so it is not counted as a forfeit.
    assert game.state.stats["red"].turns_forfeited == 0


def test_three_sixes_also_reverts_a_capture():
    game, sink = build(dice=ScriptedDice([6, 6, 6]), max_turns=1)
    # Green sits on red's path at absolute square 5; red would capture en route.
    game.state.tokens["red"] = [3, BASE, BASE, BASE]
    game.state.tokens["green"] = [44, BASE, BASE, BASE]

    game.play({c: FirstLegal() for c in COLORS})

    assert game.state.tokens["green"][0] == 44, "captured token must be restored"
    assert game.state.stats["red"].captures_made == 0


def test_no_legal_move_ends_the_turn_without_penalty():
    game, sink = build(dice=ScriptedDice([2]), max_turns=1)
    game.play({c: FirstLegal() for c in COLORS})

    ended = [e for e in sink.events if e["type"] == "turn_ended"]
    assert ended[0]["payload"] == {"player": "red", "reason": "no_legal_move"}
    assert game.state.stats["red"].turns_forfeited == 0


def test_an_illegal_move_is_rejected_twice_then_forfeits():
    """The engine rejects rather than corrects — ADR-0004's structural guardrail."""

    class Cheater:
        name = "cheater"

        def choose(self, ctx):
            return Move(0, 0, 99)

    game, sink = build(dice=ScriptedDice([6]), max_turns=1)
    game.play({**{c: FirstLegal() for c in COLORS}, "red": Cheater()})

    rejected = [e for e in sink.events if e["type"] == "illegal_move_rejected"]
    assert [e["payload"]["attempt"] for e in rejected] == [1, 2]
    assert sink.events[-2]["payload"] == {"player": "red", "reason": "illegal_move"}
    assert game.state.stats["red"].turns_forfeited == 1
    assert game.state.tokens["red"] == [BASE] * 4


def test_a_crashing_agent_forfeits_rather_than_killing_the_game():
    class Broken:
        name = "broken"

        def choose(self, ctx):
            raise RuntimeError("boom")

    game, sink = build(dice=ScriptedDice([6]), max_turns=1)
    outcome = game.play({**{c: FirstLegal() for c in COLORS}, "red": Broken()})

    assert outcome.reason == "turn_cap"
    reasons = [e["payload"]["reason"] for e in sink.events
               if e["type"] == "illegal_move_rejected"]
    assert reasons == ["decider error: RuntimeError"] * 2


def test_finishing_is_announced_and_removes_the_player_from_the_rotation():
    game, sink = build(dice=ScriptedDice([1]), max_turns=8)
    game.state.tokens["red"] = [55, HOME, HOME, HOME]

    game.play({c: FirstLegal() for c in COLORS})

    finished = [e for e in sink.events if e["type"] == "player_finished"]
    assert finished[0]["payload"] == {"player": "red", "rank": 1}
    later_turns = [e for e in sink.events
                   if e["type"] == "turn_started" and e["seq"] > finished[0]["seq"]]
    assert all(e["payload"]["player"] != "red" for e in later_turns)


def test_capture_grants_an_extra_roll():
    game, sink = build(dice=ScriptedDice([2, 3]), max_turns=1)
    game.state.tokens["red"] = [3, BASE, BASE, BASE]
    game.state.tokens["green"] = [44, BASE, BASE, BASE]

    game.play({c: FirstLegal() for c in COLORS})

    granted = [e for e in sink.events if e["type"] == "extra_roll_granted"]
    assert granted[0]["payload"] == {"player": "red", "reason": "capture"}
    assert [e["type"] for e in sink.events].count("token_captured") == 1
