"""The loader: strict rendering, stable digest, the archivist pair."""

import pytest

from alibi_strands import prompts


def test_loads_and_digests_deterministically():
    a = prompts.load()
    b = prompts.load()
    assert a.digest == b.digest
    assert a.digest.startswith("sha256:")
    assert a.version == 1
    assert set(a.turn) == {"suggest", "show", "accuse", "conclude", "reflect"}


def test_system_prompt_renders_once_per_game():
    ps = prompts.load()
    text = ps.system_prompt(color="red", max_searches_per_turn=2, max_note_chars=240)
    assert "red badge" in text
    assert "{{" not in text


def test_render_is_strict_both_ways():
    ps = prompts.load()
    with pytest.raises(KeyError):
        ps.turn["show"].render(suggester="red", suggestion="a / b / c")  # missing options
    with pytest.raises(KeyError):
        ps.turn["show"].render(suggester="red", suggestion="a / b / c",
                               options="x", bogus="y")


def test_archivist_pair_loads_with_fixed_contract():
    pair = prompts.load_archivist()
    assert set(pair) == {"system", "answer"}
    assert pair["system"].variables == ()
    assert set(pair["answer"].variables) == {"query", "documents"}
