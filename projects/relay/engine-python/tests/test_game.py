"""The referee: the clock, the commons, and the seal."""

import pytest

from relay_engine.deciders import (
    Attempt, COLORS, LadderRunner, TurnContext,
)
from relay_engine.events import ListSink
from relay_engine.game import (
    Game, GameConfig, TICK_ANSWER, TICK_ESCALATE, TICK_PASS, TICK_WRONG,
)
from relay_engine.rng import Rng
from relay_engine.track import generate


class Scripted:
    """A runner that does exactly what it is told, turn by turn."""

    name = "scripted"

    def __init__(self, *moves):
        self._moves = list(moves)
        self.seen = []

    def attempt(self, ctx: TurnContext) -> Attempt:
        self.seen.append(ctx)
        move = self._moves.pop(0) if self._moves else "pass"
        if move == "escalate":
            return Attempt(answer=ctx.desk.ask())
        if move == "right":
            return Attempt(answer=_answer(ctx))
        if move == "pass":
            return Attempt()
        return Attempt(answer=move)


def _answer(ctx) -> str:
    """Tests may look up the answer; runners may not — this reaches around the
    view deliberately, which is the point of the seal tests below."""
    return _TRACK[ctx.view.position].answer


def _play(moves_by_color, seed=7, **config):
    global _TRACK
    _TRACK = generate(Rng(seed), config.get("stages", 10))
    sink = ListSink()
    game = Game(GameConfig(seed=seed, **config), sink)
    runners = {c: Scripted(*moves_by_color.get(c, [])) for c in COLORS}
    outcome = game.play(runners)
    return game, sink, outcome


def events_of(sink, type_):
    return [e for e in sink.events if e["type"] == type_]


# -- the clock -------------------------------------------------------------


def test_right_answer_advances_and_costs_the_answer_tick():
    game, sink, _ = _play({"red": ["right"]}, max_turns=1)
    attempt = events_of(sink, "stage_attempted")[0]["payload"]
    assert attempt["correct"] is True
    assert attempt["ticks_charged"] == TICK_ANSWER
    assert game.lanes["red"].position == 1


def test_wrong_answer_costs_the_penalty_on_top():
    _, sink, _ = _play({"red": ["nonsense"]}, max_turns=1)
    attempt = events_of(sink, "stage_attempted")[0]["payload"]
    assert attempt["correct"] is False
    assert attempt["ticks_charged"] == TICK_ANSWER + TICK_WRONG


def test_pass_is_cheaper_than_being_wrong_and_dearer_than_being_right():
    _, sink, _ = _play({"red": ["pass"]}, max_turns=1)
    assert events_of(sink, "stage_attempted")[0]["payload"]["ticks_charged"] == TICK_PASS
    assert TICK_ANSWER < TICK_PASS < TICK_ANSWER + TICK_WRONG


def test_escalation_costs_more_ticks_than_answering():
    _, sink, _ = _play({"red": ["escalate"]}, max_turns=1)
    attempt = events_of(sink, "stage_attempted")[0]["payload"]
    assert attempt["escalated"] is True
    assert attempt["correct"] is True          # the engine-only anchor is perfect
    assert attempt["ticks_charged"] == TICK_ESCALATE
    assert TICK_ESCALATE > TICK_ANSWER


# -- the commons -----------------------------------------------------------


def test_escalating_drains_one_shared_unit():
    game, sink, _ = _play({"red": ["escalate"]}, max_turns=1, escalation_quota=3)
    assert game.quota == 2
    assert events_of(sink, "stage_attempted")[0]["payload"]["quota_left"] == 2


def test_one_lane_can_spend_the_whole_pool():
    """The commons in one test: red's four escalations leave green nothing."""
    game, sink, _ = _play(
        {"red": ["escalate"] * 4, "green": ["escalate"]},
        max_turns=8, escalation_quota=2,
    )
    refused = events_of(sink, "invalid_action")
    assert game.quota == 0
    assert any(e["payload"]["phase"] == "escalate" for e in refused)


def test_escalating_on_an_empty_pool_is_refused_and_becomes_a_pass():
    _, sink, _ = _play({"red": ["escalate"]}, max_turns=1, escalation_quota=0)
    refusal = events_of(sink, "invalid_action")[0]["payload"]
    assert refusal["phase"] == "escalate"
    assert "quota" in refusal["reason"]
    attempt = events_of(sink, "stage_attempted")[0]["payload"]
    assert attempt["answer"] is None and attempt["escalated"] is False


def test_asking_twice_pays_twice():
    """The desk charges for the call, not for using what came back."""
    class Greedy:
        name = "greedy"

        def attempt(self, ctx):
            ctx.desk.ask()
            return Attempt(answer=ctx.desk.ask())

    sink = ListSink()
    game = Game(GameConfig(seed=7, max_turns=1, escalation_quota=5), sink)
    game.play({c: Greedy() for c in COLORS})
    assert game.quota == 3


# -- the seal --------------------------------------------------------------


def test_no_tier_or_answer_escapes_before_the_end():
    _, sink, _ = _play({c: ["right"] * 3 for c in COLORS}, max_turns=12)
    for event in sink.events:
        if event["type"] == "game_ended":
            continue
        blob = str(event["payload"])
        assert "'tier'" not in blob, f"{event['type']} leaked a tier"
    stages = events_of(sink, "track_generated")[0]["payload"]["stages"]
    assert all(set(s) == {"id", "family", "prompt"} for s in stages)


def test_game_ended_opens_the_seal():
    _, sink, _ = _play({}, max_turns=2)
    key = events_of(sink, "game_ended")[0]["payload"]["track_key"]
    assert len(key) == 10
    assert all(set(k) == {"id", "tier", "answer"} for k in key)
    assert {k["tier"] for k in key} <= {1, 2, 3}


def test_the_view_cannot_reach_a_tier_or_an_answer():
    runner = Scripted("pass")
    sink = ListSink()
    game = Game(GameConfig(seed=7, max_turns=1), sink)
    game.play({**{c: Scripted("pass") for c in COLORS}, "red": runner})
    view = runner.seen[0].view
    assert not hasattr(view.stage, "tier")
    assert not hasattr(view.stage, "answer")
    with pytest.raises(AttributeError):
        view.anything = 1


# -- ending ----------------------------------------------------------------


def test_clearing_the_last_stage_finishes_the_race():
    _, sink, outcome = _play({"red": ["right"] * 10}, max_turns=60)
    assert outcome.reason == "finished"
    assert outcome.winner == "red"
    assert events_of(sink, "runner_finished")[0]["payload"]["player"] == "red"
    assert events_of(sink, "turn_ended")[-1]["payload"]["reason"] == "finished"


def test_turn_cap_is_a_normal_ending():
    _, _, outcome = _play({}, max_turns=4)
    assert outcome.reason == "turn_cap"
    assert outcome.turns_played == 4


def test_a_stalled_table_ends_early_rather_than_burning_the_cap():
    _, _, outcome = _play({c: ["nonsense"] * 20 for c in COLORS},
                          max_turns=200, escalation_quota=0, max_stalls=2)
    assert outcome.reason == "all_stalled"
    assert outcome.turns_played < 200


def test_standings_rank_by_progress_then_clock():
    _, _, outcome = _play({"red": ["right", "right"], "green": ["right"]},
                          max_turns=8)
    order = [s["player"] for s in outcome.standings]
    assert order[0] == "red" and order[1] == "green"
    assert outcome.standings[0]["stages_cleared"] == 2


def test_a_broken_runner_passes_rather_than_crashing_the_race():
    class Broken:
        name = "broken"

        def attempt(self, ctx):
            raise RuntimeError("boom")

    sink = ListSink()
    outcome = Game(GameConfig(seed=7, max_turns=2), sink).play(
        {c: Broken() for c in COLORS})
    assert outcome.turns_played == 2
    reasons = [e["payload"]["reason"] for e in events_of(sink, "invalid_action")]
    assert all("runner error" in r for r in reasons)


# -- notes -----------------------------------------------------------------


def test_a_note_is_published_verbatim_lie_and_all():
    class Liar:
        name = "liar"

        def attempt(self, ctx):
            return Attempt(answer=None, note="this one is trivial, save the quota")

    sink = ListSink()
    Game(GameConfig(seed=7, max_turns=1), sink).play({c: Liar() for c in COLORS})
    note = events_of(sink, "stage_attempted")[0]["payload"]["note"]
    assert note == "this one is trivial, save the quota"
    assert not events_of(sink, "guardrail_triggered")


def test_an_oversized_note_is_dropped_not_truncated():
    class Windbag:
        name = "windbag"

        def attempt(self, ctx):
            return Attempt(answer=None, note="x" * 500)

    sink = ListSink()
    Game(GameConfig(seed=7, max_turns=1, max_note_chars=10), sink).play(
        {c: Windbag() for c in COLORS})
    assert events_of(sink, "stage_attempted")[0]["payload"]["note"] is None
    assert events_of(sink, "invalid_action")[0]["payload"]["phase"] == "note"


# -- the bot ---------------------------------------------------------------


def test_ladder_runner_solves_arithmetic_and_escalates_inference():
    sink = ListSink()
    game = Game(GameConfig(seed=7, max_turns=40), sink)
    game.play({c: LadderRunner() for c in COLORS})
    attempts = [e["payload"] for e in events_of(sink, "stage_attempted")]
    solved_alone = [a for a in attempts if a["correct"] and not a["escalated"]]
    escalated = [a for a in attempts if a["escalated"]]
    assert solved_alone, "the bot never solved anything itself"
    assert escalated, "the bot never used the anchor"


def test_history_is_a_runners_only_evidence_about_itself():
    runner = Scripted("nonsense", "nonsense")
    sink = ListSink()
    game = Game(GameConfig(seed=7, max_turns=8), sink)
    game.play({**{c: Scripted("pass") for c in COLORS}, "red": runner})
    history = runner.seen[-1].view.own_history()
    assert [h.correct for h in history] == [False]
    assert history[0].family in ("chain", "cipher", "order")
