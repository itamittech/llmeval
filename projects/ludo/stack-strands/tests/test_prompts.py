"""The prompt set is the parity contract. These are the checks that keep it one."""

import pytest

from ludo_strands import prompts


@pytest.fixture(scope="module")
def loaded():
    return prompts.load()


def test_loads_the_shared_set(loaded):
    assert loaded.version >= 1
    assert loaded.digest.startswith("sha256:")
    assert {t.name for t in loaded.system} == {
        "system/identity.md", "system/rules.md", "system/negotiation.md",
    }
    assert set(loaded.turn) == {"negotiate", "decide", "retry", "reflect"}


def test_system_prompt_is_stable_for_the_whole_game(loaded):
    # The cacheable layer. If this varied per turn, prompt caching would stop
    # working silently and the only symptom would be the bill.
    once = loaded.system_prompt(color="red", max_messages_per_turn=1,
                                max_message_chars=240)
    twice = loaded.system_prompt(color="red", max_messages_per_turn=1,
                                 max_message_chars=240)
    assert once == twice
    assert "{{" not in once, "every variable was substituted"
    assert "red" in once


def test_a_missing_variable_is_an_error_not_a_literal(loaded):
    # The failure this prevents: `{{board}}` reaching a model as literal braces,
    # which produces confident nonsense rather than an error anyone notices.
    with pytest.raises(KeyError, match="board"):
        loaded.turn["decide"].render(turn=1, color="red", die=6,
                                     legal_moves="", recent_events="", memory="")


def test_an_undeclared_variable_is_also_an_error(loaded):
    with pytest.raises(KeyError, match="mood"):
        loaded.turn["retry"].render(reason="x", rejected="y", legal_moves="z",
                                    mood="aggressive")


def test_rendering_substitutes_every_declared_variable(loaded):
    text = loaded.turn["retry"].render(
        reason="not a legal move for this roll",
        rejected="token 2 to 14",
        legal_moves="- token 0 to 6",
    )
    assert "{{" not in text
    assert "not a legal move for this roll" in text


def test_template_logic_is_rejected(tmp_path):
    # Two languages would implement `{{#if}}` differently, and the disagreement
    # would be invisible. Better to refuse to load.
    base = tmp_path / "ludo"
    (base / "system").mkdir(parents=True)
    (base / "system" / "identity.md").write_text("{{#if winning}}push{{/if}}",
                                                 encoding="utf-8")
    (base / "manifest.yaml").write_text(
        "version: 1\nsystem:\n  - file: system/identity.md\n    variables: []\nturn: {}\n",
        encoding="utf-8")

    with pytest.raises(ValueError, match="template logic"):
        prompts.load(base)


def test_declared_and_used_variables_must_agree(tmp_path):
    base = tmp_path / "ludo"
    (base / "system").mkdir(parents=True)
    (base / "system" / "identity.md").write_text("you are {{color}}", encoding="utf-8")
    (base / "manifest.yaml").write_text(
        "version: 1\nsystem:\n  - file: system/identity.md\n    variables: [colour]\nturn: {}\n",
        encoding="utf-8")

    with pytest.raises(ValueError, match="manifest declares"):
        prompts.load(base)


def test_digest_changes_when_a_prompt_changes(tmp_path):
    # Provenance: a transcript must name exactly the prompts that produced it.
    def build(text):
        base = tmp_path / text[:4]
        (base / "system").mkdir(parents=True)
        (base / "system" / "identity.md").write_text(text, encoding="utf-8")
        (base / "manifest.yaml").write_text(
            "version: 1\nsystem:\n  - file: system/identity.md\n    variables: []\nturn: {}\n",
            encoding="utf-8")
        return prompts.load(base).digest

    assert build("aaaa first") != build("bbbb second")


def test_provenance_matches_the_schema_shape(loaded):
    payload = loaded.provenance()
    assert set(payload) == {"version", "hash"}
    assert payload["hash"].startswith("sha256:")
    assert len(payload["hash"].removeprefix("sha256:")) == 64
