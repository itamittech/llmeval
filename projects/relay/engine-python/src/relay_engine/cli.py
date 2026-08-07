"""Engine command line.

    python -m relay_engine.cli play --seed 7 --out race.jsonl
    python -m relay_engine.cli bench --games 500
    python -m relay_engine.cli sweep
    python -m relay_engine.cli validate race.jsonl
    python -m relay_engine.cli conformance --check
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from . import conformance
from .deciders import COLORS, LadderRunner, ProfileRunner
from .events import JsonlSink, ListSink, TeeSink
from .game import Game, GameConfig
from .rng import Rng
from .track import generate as generate_track

REPO_ROOT = Path(__file__).resolve().parents[5]
SCHEMA_PATH = REPO_ROOT / "shared" / "schemas" / "relay-event.schema.json"
VECTORS_PATH = REPO_ROOT / "shared" / "conformance" / "relay-vectors.json"

#: Bench profiles: percent chance of solving a tier alone. Named for what they
#: represent — a small local model is good at mechanical work and falls off a
#: cliff on inference, which is the shape the whole game assumes.
SKILLS = {
    "weak":   {1: 70, 2: 35, 3: 10},
    "middle": {1: 90, 2: 60, 3: 25},
    "strong": {1: 98, 2: 85, 3: 55},
}


def cmd_play(args: argparse.Namespace) -> int:
    collector = ListSink()
    config = GameConfig(seed=args.seed, max_turns=args.max_turns, stack="none")
    runners = _bots(args.seed, args.bots, config)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8", newline="\n") as fh:
            outcome = Game(config, TeeSink(collector, JsonlSink(fh))).play(runners)
        print(f"wrote {out} ({len(collector.events)} events)")
    else:
        outcome = Game(config, collector).play(runners)

    print(f"seed={args.seed} reason={outcome.reason} turns={outcome.turns_played}")
    for s in outcome.standings:
        mark = "FINISHED" if s["finished"] else ""
        print(f"  {s['rank']}. {s['player']:<7} stages={s['stages_cleared']:>2} "
              f"ticks={s['ticks']:>3} escalations={s['escalations']:>2} "
              f"correct={s['correct']} wrong={s['wrong']} {mark}")
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    """Pace statistics for one skill/insight combination — open question 25."""
    stats = _bench(args.games, SKILLS[args.skill], args.insight, args.max_turns)
    print(f"games={args.games} skill={args.skill} insight={args.insight}% "
          f"cap={args.max_turns}")
    print(f"finished={stats['finished']} ({stats['finished'] / args.games:.0%})  "
          f"stalled={stats['stalled']}")
    print(f"turns    min={stats['min']} median={stats['median']:.0f} "
          f"p90={stats['p90']} p99={stats['p99']} max={stats['max']}")
    print(f"quota    spent={stats['quota']:.1f}/{GameConfig().escalation_quota} avg   "
          f"wasted={stats['wasted']:.0%} of escalations were on tier-1 stages")
    return 0


def cmd_sweep(args: argparse.Namespace) -> int:
    """Open question 25, asked properly.

    Four runners of equal skill and *unequal insight* race each other, so the
    only difference between the lanes is how well each senses a stage it cannot
    do. The insight-to-lane assignment rotates per seed for the reason
    ADR-0006 rotates seats: otherwise turn order would be measured instead.

    If the win share comes out flat, the escalation decision does not matter
    and RELAY's central mechanic is decoration.
    """
    if len(args.insights) != len(COLORS):
        print(f"--insights needs exactly {len(COLORS)} values, one per lane",
              file=sys.stderr)
        return 2

    quota = args.quota if args.quota is not None else GameConfig().escalation_quota
    print(f"{args.games} games per row, cap {args.max_turns}, quota {quota}\n")
    header = "".join(f"insight {i:>3}%  " for i in args.insights)
    print(f"{'skill':<8}{header}")

    for name, skill in SKILLS.items():
        wins = {i: 0 for i in args.insights}
        ticks = {i: 0 for i in args.insights}
        stages = {i: 0 for i in args.insights}

        for seed in range(1, args.games + 1):
            config = GameConfig(seed=seed, max_turns=args.max_turns, stack="none",
                                escalation_quota=quota)
            game = Game(config, ListSink())
            lane_insight = {COLORS[(i + seed) % len(COLORS)]: args.insights[i]
                            for i in range(len(COLORS))}
            outcome = game.play({
                c: ProfileRunner(seed * 100 + i, game.track, skill, lane_insight[c])
                for i, c in enumerate(COLORS)
            })
            for standing in outcome.standings:
                level = lane_insight[standing["player"]]
                ticks[level] += standing["ticks"]
                stages[level] += standing["stages_cleared"]
            wins[lane_insight[outcome.standings[0]["player"]]] += 1

        cells = "".join(
            f"{wins[i] / args.games:>6.0%} {stages[i] / args.games:>4.1f}s  "
            for i in args.insights
        )
        print(f"{name:<8}{cells}")

    print("\nCell: share of races won, and average stages cleared.")
    print("Flat rows would mean the escalation decision is decoration.")
    return 0


def _bench(games: int, skill: dict, insight: int, max_turns: int) -> dict:
    turns, finished, stalled = [], 0, 0
    quota_spent, wasted, escalations = 0, 0, 0

    for seed in range(1, games + 1):
        config = GameConfig(seed=seed, max_turns=max_turns, stack="none")
        game = Game(config, ListSink())
        track = game.track
        outcome = game.play({
            c: ProfileRunner(seed * 100 + i, track, skill, insight)
            for i, c in enumerate(COLORS)
        })
        turns.append(outcome.turns_played)
        finished += outcome.reason == "finished"
        stalled += outcome.reason == "all_stalled"
        quota_spent += config.escalation_quota - game.quota
        for lane in game.lanes.values():
            for record in lane.history:
                if record.escalated:
                    escalations += 1
                    wasted += track[
                        [s.id for s in track].index(record.stage)
                    ].tier == 1

    ordered = sorted(turns)
    pct = lambda p: ordered[min(len(ordered) - 1, int(len(ordered) * p))]  # noqa: E731
    return {
        "min": min(turns), "median": statistics.median(turns),
        "p90": pct(0.90), "p99": pct(0.99), "max": max(turns),
        "finished": finished, "stalled": stalled,
        "quota": quota_spent / games,
        "wasted": (wasted / escalations) if escalations else 0.0,
    }


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
        events = [json.loads(line) for line in
                  Path(path).read_text(encoding="utf-8").splitlines() if line]
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


def cmd_track(args: argparse.Namespace) -> int:
    """Print a seed's track with its sealed answers — for reading the
    generators, never for playing."""
    for stage in generate_track(Rng(args.seed)):
        print(f"{stage.id}  tier {stage.tier}  {stage.family:<7} -> {stage.answer}")
        print(f"    {stage.prompt}")
    return 0


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
    VECTORS_PATH.write_text(json.dumps(vectors, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
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


def _bots(seed: int, kind: str, config: GameConfig) -> dict:
    if kind == "profile":
        track = generate_track(Rng(seed), config.stages)
        return {c: ProfileRunner(seed * 100 + i, track, SKILLS["middle"], 70)
                for i, c in enumerate(COLORS)}
    return {c: LadderRunner() for c in COLORS}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="relay_engine.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("play", help="race one bot game")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--max-turns", type=int, default=60)
    p.add_argument("--bots", choices=("ladder", "profile"), default="ladder")
    p.add_argument("--out", help="write the transcript here as JSONL")
    p.set_defaults(func=cmd_play)

    p = sub.add_parser("bench", help="pace statistics for one runner profile")
    p.add_argument("--games", type=int, default=200)
    p.add_argument("--max-turns", type=int, default=120)
    p.add_argument("--skill", choices=tuple(SKILLS), default="middle")
    p.add_argument("--insight", type=int, default=70)
    p.set_defaults(func=cmd_bench)

    p = sub.add_parser("sweep", help="do sharper runners win? — open question 25")
    p.add_argument("--games", type=int, default=200)
    p.add_argument("--max-turns", type=int, default=120)
    p.add_argument("--insights", type=int, nargs="+", default=[0, 33, 66, 100],
                   help="one insight percentage per lane; assignment rotates per seed")
    p.add_argument("--quota", type=int, help="override the shared pool, to size it from data")
    p.set_defaults(func=cmd_sweep)

    p = sub.add_parser("track", help="print a seed's track, answers included")
    p.add_argument("--seed", type=int, default=1)
    p.set_defaults(func=cmd_track)

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
