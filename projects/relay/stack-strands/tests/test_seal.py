"""The seal, tested where it could actually break: the bytes sent to a model.

The engine enforces the seal by type — `PublicStage` has no tier and no answer.
That protects the engine. It does not protect a harness that renders something
it should not, so these tests read what each scripted model was *actually sent*
and look for what must never be there.
"""

import pytest
from relay_engine.events import ListSink

from relay_strands import demo, policies


@pytest.fixture(scope="module")
def race():
    sink = ListSink()
    harness = demo.build(sink)
    harness.play()
    # seen_rendered, not seen: a runner's own past answers come back to it as
    # conversation history, which is how conversations work and proves nothing.
    # What must never carry an answer is what the HARNESS composed.
    runner_prompts = [text for color in harness.agents
                      for text in harness.agents[color].model.seen_rendered]
    anchor_prompts = list(harness.anchor.model.seen_rendered)
    return harness, sink, runner_prompts, anchor_prompts


def track_key(sink):
    for event in sink.events:
        if event["type"] == "game_ended":
            return event["payload"]["track_key"]
    raise AssertionError("no game_ended")


def test_no_prompt_ever_names_a_tier(race):
    _, _, runner_prompts, anchor_prompts = race
    for text in runner_prompts + anchor_prompts:
        lowered = text.lower()
        assert "tier 1" not in lowered
        assert "tier 2" not in lowered
        assert "tier 3" not in lowered


def test_no_cipher_answer_reaches_a_runner(race):
    """Cipher plaintexts are the clean probe: unlike an ordering puzzle's names,
    the answer never appears in its own prompt, so finding one anywhere in a
    runner's context would mean the harness leaked it."""
    harness, sink, runner_prompts, _ = race
    ciphers = {s.answer for s in harness.game.track if s.family == "cipher"}
    assert ciphers, "seed 7 has no cipher stages — pick another seed for this test"

    blob = "\n".join(runner_prompts).lower()
    for answer in ciphers:
        # Escalated stages are answered by the anchor, and the runner commits
        # that answer — so it may appear AFTER the fact in a transcript, but
        # never in a prompt: nothing the harness renders carries an answer.
        assert answer not in blob, f"the plaintext {answer!r} reached a runner"


def test_the_anchor_gets_a_stage_and_nothing_else(race):
    """Contract §3: the anchor is a model call, not an agent with a situation.
    No race state, no history, no notes, no memory of the last escalation."""
    _, _, _, anchor_prompts = race
    assert anchor_prompts
    for text in anchor_prompts:
        assert "Shared pool" not in text
        assert "Your notes" not in text
        assert "How you have done so far" not in text


def test_the_anchor_carries_nothing_between_calls(race):
    """Two escalations in a row must be independent — otherwise one lane's
    stage would be visible in the next lane's anchor call."""
    harness, _, _, _ = race
    assert harness.anchor.messages == [] or len(harness.anchor.messages) <= 2


def test_the_scripted_policies_read_only_the_prompt(race):
    """The fixture is evidence about the seal only if the policies that made it
    could not cheat. They take one argument: the rendered prompt."""
    import inspect

    for policy in list(policies.RUNNERS.values()) + [policies.anchor]:
        params = list(inspect.signature(policy).parameters)
        assert params == ["prompt"], f"{policy.__name__} takes more than the prompt"


def test_the_view_handed_to_a_runner_has_no_answer_field(race):
    harness, _, _, _ = race
    stage = harness.game.track[0]
    public = stage.public()
    assert not hasattr(public, "tier")
    assert not hasattr(public, "answer")
    assert stage.tier in (1, 2, 3)  # the engine still has it
