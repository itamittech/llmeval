"""The turn loop, end to end, against scripted models.

No network, no keys, fully deterministic: dice come from the engine's seeded
RNG and every model reply is committed here. The scripted model goes through
Strands' own ``Model`` interface (harness contract §8), so the whole loop —
the swarm, the hooks, the metrics — runs exactly as it would live.
"""

from __future__ import annotations

import pytest
from ludo_engine.board import COLORS
from ludo_engine.deciders import StateView, TurnContext, TurnEnd, TurnStart
from ludo_engine.events import ListSink
from ludo_engine.moves import Move
from ludo_engine.state import GameState
from strands import Agent

from ludo_strands import config, prompts
from ludo_strands.harness import LudoHarness
from ludo_strands.hooks import BudgetExceeded
from ludo_strands.scripted import ScriptedModel

SCHEMA_EVENT_TYPES = {
    "game_started", "turn_started", "dice_rolled", "move_made", "token_captured",
    "token_home", "extra_roll_granted", "illegal_move_rejected", "turn_ended",
    "player_finished", "game_ended",
    "agent_reasoning", "message_sent", "memory_write", "context_compacted",
    "llm_call", "guardrail_triggered",
}


@pytest.fixture(scope="module")
def prompt_set():
    return prompts.load()


@pytest.fixture(scope="module")
def profile():
    return config.load("dev")


def build(profile, prompt_set, scripts, **kwargs):
    sink = ListSink()
    models = {c: ScriptedModel(scripts.get(c, [])) for c in COLORS}
    harness = LudoHarness(profile, prompt_set, models, sink, **kwargs)
    return harness, sink


def of_type(sink, type_):
    return [e for e in sink.events if e["type"] == type_]


def test_scripted_model_is_a_real_strands_model():
    # The §8 seam: a bare Agent runs on it with no special casing at all.
    model = ScriptedModel(["hello from the script"])
    result = Agent(model=model, callback_handler=None)("hi")
    assert str(result).strip() == "hello from the script"
    assert model.calls == 1


def test_choose_picks_the_scripted_move(profile, prompt_set):
    harness, sink = build(profile, prompt_set, {
        "red": ['{"token": 0, "to": 0, "reasoning": "only way out of base"}'],
    })
    ctx = TurnContext(StateView(GameState()), "red", 6, [Move(0, -1, 0)], turn=1)

    move = harness.deciders["red"].choose(ctx)

    assert move == Move(0, -1, 0)
    reasoning = of_type(sink, "agent_reasoning")
    assert [e["payload"]["text"] for e in reasoning] == ["only way out of base"]
    calls = of_type(sink, "llm_call")
    assert len(calls) == 1
    payload = calls[0]["payload"]
    assert payload["player"] == "red"
    assert payload["purpose"] == "move"
    assert payload["model"] == "scripted"  # never the seat's real id on a scripted run
    assert payload["tokens"]["input"] > 0 and payload["tokens"]["output"] > 0


def test_the_retry_prompt_carries_the_rejected_reply(profile, prompt_set):
    harness, sink = build(profile, prompt_set, {
        "red": ['{"token": 0, "to": 9, "reasoning": "confused"}',
                '{"token": 0, "to": 0}'],
    })
    view = StateView(GameState())
    legal = [Move(0, -1, 0)]

    first = harness.deciders["red"].choose(TurnContext(view, "red", 6, legal, 1))
    assert first not in legal  # returned as-is; REJECTING is the engine's job

    second = harness.deciders["red"].choose(TurnContext(view, "red", 6, legal, 1, attempt=2))
    assert second == Move(0, -1, 0)

    # Attempt 2 continued the same conversation and rendered turn/retry.md,
    # whose {{rejected}} variable is the model's own first answer.
    messages = harness.players["red"].messages
    assert len(messages) == 4
    retry_prompt = messages[2]["content"][0]["text"]
    assert '"to": 9' in retry_prompt
    assert len(of_type(sink, "llm_call")) == 2


def test_an_unparseable_reply_costs_the_attempt(profile, prompt_set):
    harness, _ = build(profile, prompt_set, {"red": ["I refuse to answer in JSON."]})
    ctx = TurnContext(StateView(GameState()), "red", 6, [Move(0, -1, 0)], turn=1)
    # The engine catches this and records illegal_move_rejected — the defined
    # in-game meaning of a broken decider. The harness does not mask it.
    with pytest.raises(ValueError):
        harness.deciders["red"].choose(ctx)


def test_reflect_writes_notes_to_agent_state(profile, prompt_set):
    harness, sink = build(profile, prompt_set, {
        "red": ['{"notes": ['
                '{"kind": "commitment", "about": "blue", "text": "promised not to capture me"},'
                '{"kind": "nonsense", "text": "keep tokens paired"}]}'],
    })
    end = TurnEnd(StateView(GameState()), "red", 3, "moved",
                  ({"type": "dice_rolled", "payload": {"player": "red", "value": 4}},))

    harness.deciders["red"].reflect(end)

    writes = [e["payload"] for e in of_type(sink, "memory_write")]
    assert [(w["kind"], w["about"]) for w in writes] == [
        ("commitment", "blue"),
        ("observation", None),  # unknown kind defaults, never guesses
    ]
    notes = harness.players["red"].state.get("notes")
    assert len(notes) == 2 and notes[0]["text"] == "promised not to capture me"
    assert of_type(sink, "llm_call")[0]["payload"]["purpose"] == "reflect"


def test_the_table_runs_on_the_swarm(profile, prompt_set):
    harness, sink = build(profile, prompt_set, {
        # A handoff costs two entries: the tool call, then the post-tool text.
        "red": [
            {"handoff": {"to": "blue", "message": "ally with me against yellow?",
                         "note": "I want a quiet table"}},
            "(floor passed)",
            "nothing further",  # holds the floor again, says nothing -> phase ends
        ],
        "blue": [
            {"handoff": {"to": "red", "message": "agreed - yellow first"}},
            "(floor passed)",
        ],
    })

    harness.deciders["red"].negotiate(TurnStart(StateView(GameState()), "red", 1))

    sent = [(e["payload"]["player"], e["payload"]["to"], e["payload"]["text"])
            for e in of_type(sink, "message_sent")]
    assert sent == [
        ("red", "blue", "ally with me against yellow?"),
        ("red", None, "I want a quiet table"),   # the table note, public
        ("blue", "red", "agreed - yellow first"),
    ]

    # red opened, blue spoke, red closed: five model calls, all negotiate.
    calls = of_type(sink, "llm_call")
    assert len(calls) == 5
    assert {c["payload"]["purpose"] for c in calls} == {"negotiate"}

    # Directed replies land in the next briefing; the table note reached
    # everyone except its speaker.
    assert 'blue: "agreed - yellow first"' in harness.hooks.drain_inbox("red")
    for color in ("green", "yellow"):
        assert "quiet table" in harness.hooks.drain_inbox(color)


def test_a_spent_budget_stops_calls_and_forfeits(profile, prompt_set):
    harness, sink = build(profile, prompt_set, {"red": ["never used"]})
    harness.hooks.max_tokens = 0  # spent >= ceiling from the first check
    view = StateView(GameState())

    harness.deciders["red"].negotiate(TurnStart(view, "red", 1))
    with pytest.raises(BudgetExceeded):
        harness.deciders["red"].choose(TurnContext(view, "red", 6, [Move(0, -1, 0)], 1))
    harness.deciders["red"].reflect(TurnEnd(view, "red", 1, "moved", ()))

    assert of_type(sink, "llm_call") == []  # not one model call got through


def test_a_full_scripted_game_produces_a_wellformed_transcript(profile, prompt_set):
    # Generous generic scripts: enough entries that no phase starves, generic
    # enough that legality is the dice's problem — forfeits are valid outcomes
    # and the transcript must stay well-formed through all of them.
    script = (["(quiet)"]
              + ['{"token": 0, "to": 0, "reasoning": "press on"}'] * 7
              + ['{"notes": [{"text": "long game"}]}'] * 2)
    harness, sink = build(profile, prompt_set,
                          {c: list(script) for c in COLORS},
                          seed=7, max_turns=4)

    outcome = harness.play()

    events = sink.events
    assert events[0]["type"] == "game_started"
    assert events[-1]["type"] == "game_ended"
    assert [e["seq"] for e in events] == list(range(len(events)))
    assert {e["type"] for e in events} <= SCHEMA_EVENT_TYPES

    started = of_type(sink, "turn_started")
    ended = of_type(sink, "turn_ended")
    assert len(started) == len(ended) == outcome.turns_played == 4

    for call in of_type(sink, "llm_call"):
        payload = call["payload"]
        assert payload["player"] in COLORS
        assert payload["access"] in ("bedrock", "direct")
        assert set(payload["tokens"]) == {"input", "output", "cache_read", "cache_write"}

    meta = events[0]["payload"]
    assert meta["stack"] == "strands"
    assert {p["color"] for p in meta["players"]} == set(COLORS)
    assert all(p["model"] == "scripted" for p in meta["players"])
