"""Eval command line.

    python -m alibi_eval score <transcript.jsonl>...
    python -m alibi_eval compare <a.jsonl> <b.jsonl> [<c.jsonl>...]

`score` writes `<file>.eval.json` beside each transcript, validated against
the shared result schema first. `compare` checks the cross-stack claim
mechanically: same seed, same scripted decisions, identical engine-event
spines — then prints what actually differed, which is the framework.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from . import scoring

REPO_ROOT = Path(__file__).resolve().parents[5]
SCHEMA_PATH = REPO_ROOT / "shared" / "schemas" / "alibi-eval-result.schema.json"


def _resolve(name: str) -> Path:
    """Accept paths relative to the caller's intent: as given, or repo-rooted —
    because `uv run --directory` moves the working directory here."""
    path = Path(name)
    if path.exists():
        return path
    rooted = REPO_ROOT / name
    if rooted.exists():
        return rooted
    raise FileNotFoundError(name)


def cmd_score(args: argparse.Namespace) -> int:
    validator = Draft202012Validator(
        json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    failures = 0
    for name in args.transcripts:
        path = _resolve(name)
        result = scoring.score(path)
        problems = [e.message for e in validator.iter_errors(result)]
        if problems:
            for p in problems:
                print(f"{path}: result does not satisfy the schema: {p}", file=sys.stderr)
            failures += 1
            continue
        out = path.with_suffix(path.suffix + ".eval.json")
        out.write_text(json.dumps(result, indent=2) + "\n",
                       encoding="utf-8", newline="\n")
        flag = "" if result["checks"]["standings_match"] else "  [STANDINGS MISMATCH]"
        top = result["detectives"][0]
        print(f"{out.name}: {result['game']['reason']} in "
              f"{result['game']['turns_played']} turns; rank 1 {top['player']}"
              f" (brier {top['beliefs']['mean_brier']}){flag}")
        if not result["checks"]["standings_match"]:
            failures += 1
    return 1 if failures else 0


def cmd_compare(args: argparse.Namespace) -> int:
    spines = {}
    results = {}
    for name in args.transcripts:
        path = _resolve(name)
        events = scoring.read_transcript(path)
        spines[path.name] = scoring.engine_skeleton(events)
        results[path.name] = scoring.score(path)

    names = list(spines)
    reference = spines[names[0]]
    diverged = [n for n in names[1:] if spines[n] != reference]
    if diverged:
        print("engine spines DIVERGE — these games did not tell the same story:")
        for n in diverged:
            print(f"  {n}")
        return 1

    print(f"engine spines agree across {len(names)} transcript(s) "
          f"({len(reference)} events) — what differs below is the framework:\n")
    header = f"{'':38}" + "".join(f"{n.split('-')[1]:>12}" for n in names)
    print(header)
    rows = [
        ("llm_call events", lambda r: sum(d["tokens"]["calls"] for d in r["detectives"])),
        ("tokens sent (est.)", lambda r: sum(d["tokens"]["input"] + d["tokens"]["output"]
                                             for d in r["detectives"])),
        ("memory writes", lambda r: sum(d["memory_writes"] for d in r["detectives"])),
    ]
    for label, fn in rows:
        print(f"{label:38}" + "".join(f"{fn(results[n]):>12}" for n in names))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="alibi_eval")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("score", help="score transcripts; write .eval.json beside each")
    p.add_argument("transcripts", nargs="+")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("compare", help="cross-stack spine check + framework diff")
    p.add_argument("transcripts", nargs="+")
    p.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
