"""The eval CLI — free by default, like everything scripted in this repo.

    uv run --directory projects/ludo/eval python -m ludo_eval score <game.jsonl> [--json out.json]
    uv run --directory projects/ludo/eval python -m ludo_eval compare <a.jsonl> <b.jsonl> ...

``score`` runs layer 1 (deterministic, no model calls) and prints the
summary; ``--json`` writes the schema-validated result. The judge does not
run from here yet — its model id is TBD, and when it lands it will be an
explicit, priced flag, never a default.

``compare`` answers the repo's real question for a set of transcripts of the
same matchup: which stack ran the game best — events, calls, tokens,
overhead — with play quality deliberately out of frame.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import report, transcript


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ludo_eval")
    sub = parser.add_subparsers(dest="command", required=True)

    score = sub.add_parser("score", help="deterministic scoring of one transcript")
    score.add_argument("transcript")
    score.add_argument("--json", dest="out", help="write the validated result here")

    compare = sub.add_parser("compare", help="the same matchup across stacks")
    compare.add_argument("transcripts", nargs="+")

    conf = sub.add_parser(
        "conformance",
        help="harness-contract §8: normalise and diff event sequences across stacks")
    conf.add_argument("transcripts", nargs="+")

    args = parser.parse_args(argv)

    if args.command == "conformance":
        from . import conformance
        named = []
        for path in args.transcripts:
            events = transcript.load(path)
            game = transcript.fold(events)
            named.append((game.stack or Path(path).stem, events))
        print(conformance.render(conformance.compare(named)))
        return 0

    if args.command == "score":
        events = transcript.load(args.transcript)
        game = transcript.fold(events)
        result = report.build_result(args.transcript, events, game)
        print(report.summary(result))
        if args.out:
            Path(args.out).write_text(json.dumps(result, indent=2) + "\n",
                                      encoding="utf-8")
            print(f"\n  result -> {args.out}")
        return 0

    results = []
    for path in args.transcripts:
        events = transcript.load(path)
        game = transcript.fold(events)
        results.append(report.build_result(path, events, game))
    print(report.compare(results))
    return 0
