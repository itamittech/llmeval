"""Engine command line.

    python -m alibi_engine.cli play --seed 7 --out case.jsonl
    python -m alibi_engine.cli bench --games 200
    python -m alibi_engine.cli validate case.jsonl
    python -m alibi_engine.cli conformance --check
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from . import conformance
from .case import COLORS
from .deciders import EliminationBot, RandomSleuth
from .events import JsonlSink, ListSink, TeeSink
from .game import Game, GameConfig

REPO_ROOT = Path(__file__).resolve().parents[5]
SCHEMA_PATH = REPO_ROOT / "shared" / "schemas" / "alibi-event.schema.json"
VECTORS_PATH = REPO_ROOT / "shared" / "conformance" / "alibi-vectors.json"


def cmd_play(args: argparse.Namespace) -> int:
    collector = ListSink()
    config = GameConfig(seed=args.seed, max_turns=args.max_turns, stack="none")
    detectives = _bots(args.seed, args.bots)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8", newline="\n") as fh:
            outcome = Game(config, TeeSink(collector, JsonlSink(fh))).play(detectives)
        print(f"wrote {out} ({len(collector.events)} events)")
    else:
        outcome = Game(config, collector).play(detectives)

    print(f"seed={args.seed} reason={outcome.reason} turns={outcome.turns_played}")
    print(f"solution: {outcome.solution['who']} / {outcome.solution['how']} / {outcome.solution['where']}")
    for s in outcome.standings:
        marks = ("SOLVED" if s["solved"] else "out" if s["eliminated"] else "")
        print(f"  {s['rank']}. {s['player']:<7} belief={s['belief_dimensions_correct']}/3 "
              f"suggestions={s['suggestions_made']} searches={s['searches_made']} {marks}")
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    """Deduction-bot games, to size the turn cap from data rather than guesswork
    (open question 21 — the same discipline as LUDO's question 7)."""
    turns, solved = [], 0
    for seed in range(1, args.games + 1):
        config = GameConfig(seed=seed, max_turns=args.max_turns, stack="none")
        outcome = Game(config, ListSink()).play(_bots(seed, args.bots))
        turns.append(outcome.turns_played)
        solved += outcome.reason == "solved"

    ordered = sorted(turns)
    pct = lambda p: ordered[min(len(ordered) - 1, int(len(ordered) * p))]  # noqa: E731
    print(f"games={args.games} cap={args.max_turns} bots={args.bots}")
    print(f"solved={solved} ({solved / args.games:.0%})")
    print(f"turns  min={min(turns)} median={statistics.median(turns):.0f} "
          f"p90={pct(0.90)} p99={pct(0.99)} max={max(turns)}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print("validation needs jsonschema:  uv sync --group dev", file=sys.stderr)
        return 2

    validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    failures = 0

    paths = _expand(args.transcripts)
    if not paths:
        print(f"no transcripts matched {args.transcripts}", file=sys.stderr)
        return 2

    for path in paths:
        events = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]
        for i, event in enumerate(events):
            for err in validator.iter_errors(event):
                print(f"{path}:{i + 1}: {err.message}", file=sys.stderr)
                failures += 1
        if [e["seq"] for e in events] != list(range(len(events))):
            print(f"{path}: seq numbers are not contiguous from 0", file=sys.stderr)
            failures += 1
        print(f"{path}: {len(events)} events")

    if failures:
        print(f"{failures} problem(s)", file=sys.stderr)
    return 1 if failures else 0


def cmd_conformance(args: argparse.Namespace) -> int:
    if args.check:
        if not VECTORS_PATH.exists():
            print(f"no vectors at {VECTORS_PATH}; run with --generate", file=sys.stderr)
            return 2
        failures = conformance.check(json.loads(VECTORS_PATH.read_text(encoding="utf-8")))
        for line in failures:
            print(line, file=sys.stderr)
        print("conformance: FAIL" if failures else "conformance: ok")
        return 1 if failures else 0

    vectors = conformance.generate()
    VECTORS_PATH.parent.mkdir(parents=True, exist_ok=True)
    VECTORS_PATH.write_text(json.dumps(vectors, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {VECTORS_PATH} ({len(vectors['vectors'])} vectors)")
    return 0


def _expand(patterns: list[str]) -> list[Path]:
    """Resolve wildcards ourselves — PowerShell doesn't glob for native
    commands, and a shell that does globs relative to its own cwd."""
    found: list[Path] = []
    for pattern in patterns:
        if any(ch in pattern for ch in "*?["):
            base = Path(pattern).parent
            found.extend(sorted(base.glob(Path(pattern).name)))
        else:
            found.append(Path(pattern))
    return found


def _bots(seed: int, kind: str) -> dict:
    if kind == "random":
        # Distinct per-colour seeds so the four sleuths do not move in lockstep.
        return {c: RandomSleuth(seed * 100 + i) for i, c in enumerate(COLORS)}
    return {c: EliminationBot() for c in COLORS}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="alibi_engine.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("play", help="play one bot game")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--max-turns", type=int, default=40)
    p.add_argument("--bots", choices=("elimination", "random"), default="elimination")
    p.add_argument("--out", help="write the transcript here as JSONL")
    p.set_defaults(func=cmd_play)

    p = sub.add_parser("bench", help="pace statistics for turn-cap sizing")
    p.add_argument("--games", type=int, default=200)
    p.add_argument("--max-turns", type=int, default=200)
    p.add_argument("--bots", choices=("elimination", "random"), default="elimination")
    p.set_defaults(func=cmd_bench)

    p = sub.add_parser("validate", help="validate transcripts against the shared schema")
    p.add_argument("transcripts", nargs="+")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("conformance", help="generate or check cross-engine vectors")
    p.add_argument("--check", action="store_true")
    p.add_argument("--generate", action="store_true")
    p.set_defaults(func=cmd_conformance)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
