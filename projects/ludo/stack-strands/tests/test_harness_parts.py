"""Memory, budgets, and the model seam."""

import pytest

from ludo_strands.budget import Budget, BudgetExceeded, Usage
from ludo_strands.memory import Memory
from ludo_strands.model import ScriptedModel, parse_json_reply


# -- memory --------------------------------------------------------------


def test_memory_keeps_what_it_was_told_even_when_false():
    # The point of the whole project: an agent's memory records what it
    # BELIEVES. A harness that reconciled this against the board would delete
    # the phenomenon under study.
    m = Memory("red")
    m.write("green promised not to capture me", turn=3, kind="commitment")
    assert "green promised" in m.render()


def test_an_unclassified_note_becomes_an_observation():
    # Never guessed at: inventing a `commitment` would fabricate a fact.
    m = Memory("red")
    note = m.write("blue is ahead", turn=1)
    assert note.kind == "observation"
    assert m.write("x", turn=1, kind="not_a_kind").kind == "observation"


def test_compaction_summaries_survive_as_durable_facts():
    m = Memory("red")
    for i in range(60):
        m.write(f"note {i}", turn=i)
    m.absorb("blue betrayed me on turn 12")

    rendered = m.render(limit=5)
    assert "blue betrayed me on turn 12" in rendered, "durable facts are never trimmed"
    assert "note 59" in rendered
    assert "note 3" not in rendered, "old notes fall out of the window"


def test_empty_memory_renders_something_a_model_can_read():
    assert Memory("red").render() == "(nothing yet)"


# -- budget --------------------------------------------------------------


def test_budget_tracks_per_agent_and_total():
    b = Budget(max_tokens_per_game=1000)
    b.record("red", Usage(input=100, output=50))
    b.record("green", Usage(input=10, output=5))

    assert b.spent == 165
    assert b.per_agent == {"red": 150, "green": 15}
    assert b.calls == 2
    assert b.remaining == 835


def test_budget_stops_the_game_when_the_ceiling_is_reached():
    b = Budget(max_tokens_per_game=100)
    b.check()
    b.record("red", Usage(input=80, output=40))
    with pytest.raises(BudgetExceeded, match="120 of 100"):
        b.check()


def test_usage_payload_matches_the_event_schema():
    assert set(Usage(1, 2, 3, 4).as_payload()) == {
        "input", "output", "cache_read", "cache_write",
    }


# -- the model seam ------------------------------------------------------


def test_scripted_model_replays_in_order_and_costs_nothing():
    model = ScriptedModel(['{"a": 1}', '{"b": 2}'])
    assert model.complete("sys", "one", "decide").text == '{"a": 1}'
    assert model.complete("sys", "two", "reflect").text == '{"b": 2}'
    assert [purpose for purpose, _ in model.calls] == ["decide", "reflect"]


def test_running_out_of_script_is_an_error():
    # A stack that quietly invented a reply would produce a transcript nobody
    # could reproduce — which is exactly what scripted conformance is for.
    model = ScriptedModel(['{"a": 1}'])
    model.complete("sys", "one", "decide")
    with pytest.raises(IndexError, match="exhausted"):
        model.complete("sys", "two", "decide")


def test_scripted_replies_carry_no_invented_latency():
    reply = ScriptedModel(["{}"]).complete("s", "u", "decide")
    assert reply.latency_ms is None, "there was no call to time"
    assert reply.usage.total > 0


@pytest.mark.parametrize("raw", [
    '{"token": 1, "to": 6}',
    'Sure! Here you go:\n{"token": 1, "to": 6}',
    '```json\n{"token": 1, "to": 6}\n```',
    'reasoning first...\n```\n{"token": 1, "to": 6}\n```\nthanks',
])
def test_json_is_recovered_from_the_wrappers_models_actually_produce(raw):
    assert parse_json_reply(raw) == {"token": 1, "to": 6}


@pytest.mark.parametrize("raw", ["no json here", "", "{unclosed"])
def test_unparseable_replies_raise_rather_than_guess(raw):
    with pytest.raises((ValueError, Exception)):
        parse_json_reply(raw)
