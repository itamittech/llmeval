"""The referee: refutation mediation, accusations, privacy, and endings."""

import pytest

from alibi_engine.case import COLORS, DIMENSIONS, ELEMENTS
from alibi_engine.deciders import Belief, EliminationBot, Suggestion, Triple
from alibi_engine.events import ListSink
from alibi_engine.game import Game, GameConfig


class Stub:
    """A puppet detective the tests steer per phase."""

    name = "stub"

    def __init__(self, suggestion=None, accusation=None, show_pick=None):
        self.suggestion = suggestion
        self.accusation = accusation
        self.show_pick = show_pick
        self.show_contexts = []

    def suggest(self, ctx):
        return self.suggestion

    def show(self, ctx):
        self.show_contexts.append(ctx)
        return self.show_pick if self.show_pick is not None else ctx.options[0]

    def accuse(self, ctx):
        return self.accusation

    def conclude(self, ctx):
        first = {d: ELEMENTS[d][0] for d in DIMENSIONS}
        return Belief(first["who"], first["how"], first["where"],
                      {d: 0.5 for d in DIMENSIONS})


def _game(seed=1, **kw):
    sink = ListSink()
    game = Game(GameConfig(seed=seed, **kw), sink)
    return game, sink


def _types(sink):
    return [e["type"] for e in sink.events]


def test_transcript_opens_and_closes_correctly():
    game, sink = _game(max_turns=2)
    game.play({c: Stub() for c in COLORS})
    types = _types(sink)
    assert types[:3] == ["game_started", "case_dealt", "archive_generated"]
    assert types[-1] == "game_ended"
    assert [e["seq"] for e in sink.events] == list(range(len(sink.events)))


def test_refuter_is_first_clockwise_holder():
    game, sink = _game(max_turns=1)
    # Red suggests a triple containing an element that only one other holds.
    element = game.case.hands["yellow"][0]
    dim = next(d for d in DIMENSIONS if element in ELEMENTS[d])
    triple = {d: game.case.solution[d] for d in DIMENSIONS}  # unrefutable base
    triple[dim] = element
    stubs = {c: Stub() for c in COLORS}
    stubs["red"].suggestion = Suggestion(triple["who"], triple["how"], triple["where"])
    game.play(stubs)

    refutation = next(e for e in sink.events if e["type"] == "refutation_made")
    assert refutation["payload"]["refuter"] == "yellow"
    assert refutation["payload"]["element"] == element
    assert refutation["payload"]["chosen_by"] == "detective"


def test_nobody_can_refute_the_solution():
    game, sink = _game(max_turns=1)
    s = game.case.solution
    stubs = {c: Stub() for c in COLORS}
    stubs["red"].suggestion = Suggestion(s["who"], s["how"], s["where"])
    game.play(stubs)

    refutation = next(e for e in sink.events if e["type"] == "refutation_made")
    assert refutation["payload"]["refuter"] is None
    assert refutation["payload"]["element"] is None


def test_invalid_show_falls_back_to_engine_choice():
    game, sink = _game(max_turns=1)
    element = game.case.hands["green"][0]
    dim = next(d for d in DIMENSIONS if element in ELEMENTS[d])
    triple = {d: game.case.solution[d] for d in DIMENSIONS}
    triple[dim] = element
    stubs = {c: Stub() for c in COLORS}
    stubs["red"].suggestion = Suggestion(triple["who"], triple["how"], triple["where"])
    stubs["green"].show_pick = "not-an-element"
    game.play(stubs)

    refutation = next(e for e in sink.events if e["type"] == "refutation_made")
    assert refutation["payload"]["chosen_by"] == "engine"
    assert refutation["payload"]["element"] == element
    assert any(e["type"] == "invalid_action" and e["payload"]["phase"] == "show"
               for e in sink.events)


def test_correct_accusation_wins():
    game, sink = _game()
    s = game.case.solution
    stubs = {c: Stub() for c in COLORS}
    stubs["red"].accusation = Triple(s["who"], s["how"], s["where"])
    outcome = game.play(stubs)

    assert outcome.reason == "solved"
    assert outcome.winner == "red"
    assert outcome.turns_played == 1
    accusation = next(e for e in sink.events if e["type"] == "accusation_made")
    assert accusation["payload"]["correct"] is True
    assert outcome.standings[0]["player"] == "red"
    assert outcome.standings[0]["solved"] is True


def test_wrong_accusation_eliminates_but_still_refutes():
    game, sink = _game(max_turns=8)
    wrong = {d: None for d in DIMENSIONS}
    for d in DIMENSIONS:
        wrong[d] = next(e for e in ELEMENTS[d] if e != game.case.solution[d])
    stubs = {c: Stub() for c in COLORS}
    stubs["red"].accusation = Triple(wrong["who"], wrong["how"], wrong["where"])

    # Green later suggests something only red can refute.
    red_only = game.case.hands["red"][0]
    dim = next(d for d in DIMENSIONS if red_only in ELEMENTS[d])
    triple = {d: game.case.solution[d] for d in DIMENSIONS}
    triple[dim] = red_only
    stubs["green"].suggestion = Suggestion(triple["who"], triple["how"], triple["where"])

    game.play(stubs)

    assert any(e["type"] == "detective_eliminated" and e["payload"]["player"] == "red"
               for e in sink.events)
    refutations = [e for e in sink.events if e["type"] == "refutation_made"
                   and e["payload"]["refuter"] == "red"]
    assert refutations, "an eliminated detective must still refute"


def test_all_eliminated_ends_the_game():
    game, sink = _game()
    stubs = {}
    for c in COLORS:
        game_wrong = {d: next(e for e in ELEMENTS[d] if e != game.case.solution[d])
                      for d in DIMENSIONS}
        stubs[c] = Stub(accusation=Triple(game_wrong["who"], game_wrong["how"], game_wrong["where"]))
    outcome = game.play(stubs)
    assert outcome.reason == "all_eliminated"
    assert outcome.turns_played == 4
    assert outcome.winner is None


def test_search_quota_is_enforced_and_visible():
    class Searcher(Stub):
        def suggest(self, ctx):
            for i in range(3):  # one more than the quota of 2
                ctx.archive.search(f"vault key {i}")
            return None

    game, sink = _game(max_turns=1, max_searches_per_turn=2)
    stubs = {c: Stub() for c in COLORS}
    stubs["red"] = Searcher()
    game.play(stubs)

    searches = [e for e in sink.events if e["type"] == "archive_searched"]
    assert len(searches) == 2
    assert searches[0]["payload"]["quota_left"] == 1
    assert searches[1]["payload"]["quota_left"] == 0
    assert any(e["type"] == "invalid_action" and e["payload"]["phase"] == "search"
               for e in sink.events)


def test_turn_cap_reached():
    game, sink = _game(max_turns=3)
    outcome = game.play({c: Stub() for c in COLORS})
    assert outcome.reason == "turn_cap"
    assert outcome.turns_played == 3


def test_views_leak_nothing_private():
    game, _ = _game(max_turns=1)
    view = game._view("red")
    assert set(view.my_hand()) == set(game.case.hands["red"])
    with pytest.raises(AttributeError):
        view.anything = 1
    # The view object simply has no path to other hands or the solution.
    assert not hasattr(view, "solution")
    assert not any("green" in str(v) for v in [view.my_hand()])


def test_elimination_bots_solve_the_case():
    for seed in range(1, 6):
        game, sink = _game(seed=seed, max_turns=60)
        outcome = game.play({c: EliminationBot() for c in COLORS})
        assert outcome.reason == "solved", f"seed {seed} did not converge"
        accusation = next(e for e in sink.events if e["type"] == "accusation_made")
        assert accusation["payload"]["correct"] is True
        beliefs = [e for e in sink.events if e["type"] == "belief_declared"]
        assert beliefs, "bots must declare beliefs"


def test_belief_dimensions_correct_in_standings():
    game, _ = _game(seed=2, max_turns=60)
    outcome = game.play({c: EliminationBot() for c in COLORS})
    for s in outcome.standings:
        assert 0 <= s["belief_dimensions_correct"] <= 3
    # The solver's certainty must show up as a fully correct final belief
    # or a solve on its own turn before concluding.
    assert outcome.standings[0]["solved"]
