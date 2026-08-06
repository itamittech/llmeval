"""§8 mechanised — the normaliser, the diff, and the honest report."""

from __future__ import annotations

from pathlib import Path

from ludo_eval import conformance, transcript

GAMES = Path(__file__).resolve().parents[1].parent / "games"


def load_stacks():
    named = []
    for stack in ("strands", "langgraph", "springai"):
        events = transcript.load(GAMES / f"scripted-{stack}-seed7.jsonl")
        named.append((stack, events))
    return named


def test_normalise_strips_exactly_the_volatile_fields():
    events = [
        {"seq": 0, "turn": 0, "type": "game_started",
         "payload": {"seed": 7, "stack": "strands", "ruleset": "baseline"}},
        {"seq": 1, "turn": 1, "type": "llm_call",
         "payload": {"player": "red", "latency_ms": 42, "cost_usd": 0.01,
                     "tokens": {"input": 5}}},
    ]
    out = conformance.normalise(events)
    assert "stack" not in out[0]["payload"]
    assert out[0]["payload"]["seed"] == 7                # everything else survives
    assert "latency_ms" not in out[1]["payload"]
    assert "cost_usd" not in out[1]["payload"]
    assert out[1]["payload"]["tokens"] == {"input": 5}
    assert events[1]["payload"]["latency_ms"] == 42      # the input is untouched


def test_identical_engine_streams_compare_identical():
    events = transcript.load(GAMES / "scripted-langgraph-seed7.jsonl")
    result = conformance.compare([("a", events), ("b", list(events))])
    assert result.engine_identical
    assert result.first_divergence is None


def test_a_planted_divergence_is_named():
    events = transcript.load(GAMES / "scripted-langgraph-seed7.jsonl")
    tampered = [dict(e, payload=dict(e["payload"])) for e in events]
    for event in tampered:
        if event["type"] == "dice_rolled":
            event["payload"]["value"] = 1              # loaded dice
            break
    result = conformance.compare([("real", events), ("tampered", tampered)])
    assert not result.engine_identical
    assert result.first_divergence["tampered"]["payload"]["value"] == 1


def test_python_engine_and_java_engine_games_are_engine_identical():
    # The §8 claim, across LANGUAGES: the langgraph fixture ran on the Python
    # engine, the springai fixture on the Java engine, same seed, and their
    # scripts fed both engines the same decisions. After normalising the
    # by-design fields (stack, framework, engine, players[].agent), the two
    # engine-event sequences must be IDENTICAL — ADR-0002's interchangeability
    # promise, checked on whole harness-driven games instead of vectors.
    named = [(s, e) for s, e in load_stacks() if s in ("langgraph", "springai")]
    result = conformance.compare(named)
    assert result.engine_identical, result.first_divergence


def test_the_three_fixtures_tell_one_story_in_three_rhythms():
    result = conformance.compare(load_stacks())

    # The rhythms differ — that is documented framework territory.
    assert result.agent_profile["strands"] != result.agent_profile["langgraph"]

    # The story must not: same three deliveries in every stack.
    deliveries = {name: [(m[0], m[1]) for m in result.story[name]["messages"]]
                  for name in ("strands", "langgraph", "springai")}
    assert deliveries["strands"] == deliveries["langgraph"] == deliveries["springai"] \
        == [("red", "blue"), ("red", None), ("blue", "red")]

    # And the report renders both facts without crashing.
    text = conformance.render(result)
    assert "rhythm" in text
    assert "AGREE" in text or "DIFFER" in text
