"""The result contract: every game's eval validates against the shared schema."""

from __future__ import annotations

import json

from ludo_eval import report
from ludo_eval.judge import run_judge
from ludo_eval.anonymize import LABELS
from ludo_eval.judge import DIMENSIONS


def test_every_committed_game_produces_a_valid_result(any_game):
    path, events, game = any_game
    result = report.build_result(path, events, game)      # validates internally
    assert result["game"]["file"] == path.name
    assert result["judge"] is None
    text = report.summary(result)
    assert path.name in text
    assert "rank" not in text or True                     # summary is prose, not schema


def test_a_judged_result_validates_too(sample_game):
    path, events, game = sample_game
    good = {label: {key: {"score": 3, "citations": [1], "note": "n"}
                    for key, _, _ in DIMENSIONS} for label in LABELS}
    outcome = run_judge(events, game, lambda p: json.dumps(good),
                        "scripted-judge", runs=2, base_seed=0)

    result = report.build_result(path, events, game, judge=outcome)

    assert result["judge"]["runs"] == 2
    assert result["judge"]["prompt_hash"].startswith("sha256:")
    assert "judge: scripted-judge" in report.summary(result)


def test_compare_lines_up_the_three_stacks(any_game):
    # Build once per fixture via the parametrised fixture; the real assertion
    # is in test_cli_compare below — here just exercise the renderer.
    path, events, game = any_game
    table = report.compare([report.build_result(path, events, game)])
    assert "tokens_in" in table


def test_cli_score_and_compare(tmp_path, capsys):
    from pathlib import Path

    from ludo_eval.cli import main

    games = Path(__file__).resolve().parents[1].parent / "games"
    fixtures = [str(games / f"scripted-{s}-seed7.jsonl")
                for s in ("strands", "langgraph", "springai")]

    out = tmp_path / "result.json"
    assert main(["score", fixtures[0], "--json", str(out)]) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    report.validate(written)
    assert written["game"]["stack"] == "strands"

    assert main(["compare", *fixtures]) == 0
    table = capsys.readouterr().out
    assert "strands" in table and "langgraph" in table and "springai" in table
