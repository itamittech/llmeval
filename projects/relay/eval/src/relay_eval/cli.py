"""The eval command line.

    python -m relay_eval score  projects/relay/games/scripted-strands-seed7.jsonl
    python -m relay_eval compare projects/relay/games/*.jsonl

Consumes transcripts only. Free, offline, no keys — and no judge, because the
answers to the questions a judge would be asked are in the transcript.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import scoring


def cmd_score(args: argparse.Namespace) -> int:
    for path in _expand(args.transcripts):
        result = scoring.score(scoring.load(path))
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            _print_race(path, result)
        if args.write:
            out = Path(str(path) + ".eval.json")
            out.write_text(json.dumps(result, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
            print(f"wrote {out}")
        if not result["self_check"]["ok"]:
            print(f"SELF-CHECK FAILED: {result['self_check']['detail']}", file=sys.stderr)
            return 1
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Prove the stacks played the same race, then compare what differed.

    That order matters. Two stacks that disagree about the race are not
    comparable at all, and a comparison that skipped the check would report the
    disagreement as a framework difference.
    """
    paths = _expand(args.transcripts)
    if len(paths) < 2:
        print("compare needs at least two transcripts", file=sys.stderr)
        return 2

    results = [(path, scoring.score(scoring.load(path))) for path in paths]

    spine = {path: _spine(scoring.load(path)) for path, _ in results}
    reference = spine[paths[0]]
    mismatched = [str(p) for p in paths[1:] if spine[p] != reference]
    if mismatched:
        print("ENGINE SPINES DIFFER — these transcripts are not comparable:",
              file=sys.stderr)
        for name in mismatched:
            print(f"  {name}", file=sys.stderr)
        return 1
    print(f"engine spine identical across {len(paths)} transcripts "
          f"({len(reference)} engine events each)\n")

    print(f"{'':<22}" + "".join(f"{r['stack']:>14}" for _, r in results))
    for label, get in (
        ("llm_call events", lambda r: sum(l["calls"] for l in r["lanes"])),
        ("  of which anchor", lambda r: sum(l["anchor_calls"] for l in r["lanes"])),
        ("tokens sent", lambda r: sum(l["tokens"] for l in r["lanes"])),
        ("quota spent", lambda r: r["commons"]["spent"]),
        ("guardrails fired", lambda r: r["guardrails_triggered"]),
    ):
        print(f"{label:<22}" + "".join(f"{get(r):>14,}" for _, r in results))

    print("\nEscalation judgement, scored against the tier nobody was shown:")
    print(f"{'lane':<8}{'cleared':>9}{'ticks':>7}{'solo acc':>10}"
          f"{'precision':>11}{'recall':>9}{'fit':>6}")
    for lane in results[0][1]["lanes"]:
        print(f"{lane['player']:<8}{lane['stages_cleared']:>9}{lane['ticks']:>7}"
              f"{_pct(lane['solo_accuracy']):>10}"
              f"{_pct(lane['escalation_precision']):>11}"
              f"{_pct(lane['escalation_recall']):>9}"
              f"{_pct(lane['escalation_fit']):>6}")
    print("\nprecision = spent on an objectively hard stage;  "
          "fit = spent on a family THIS lane is bad at.")
    print("They come apart, and the winner is the lane with the better fit.")
    return 0


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.0%}"


def _print_race(path: Path, result: dict) -> None:
    print(f"{path}  seed={result['seed']} stack={result['stack']} "
          f"reason={result['reason']} turns={result['turns_played']}")
    commons = result["commons"]
    print(f"  commons: {commons['spent']}/{commons['quota']} spent"
          f"{' (exhausted)' if commons['exhausted'] else ''}")
    print(f"  {'lane':<8}{'cleared':>9}{'ticks':>7}{'esc':>5}"
          f"{'solo acc':>10}{'precision':>11}{'recall':>9}{'fit':>6}{'share':>8}")
    for lane in result["lanes"]:
        print(f"  {lane['player']:<8}{lane['stages_cleared']:>9}{lane['ticks']:>7}"
              f"{lane['escalations']:>5}{_pct(lane['solo_accuracy']):>10}"
              f"{_pct(lane['escalation_precision']):>11}"
              f"{_pct(lane['escalation_recall']):>9}{_pct(lane['escalation_fit']):>6}"
              f"{_pct(commons['share'][lane['player']]):>8}")
    check = result["self_check"]
    print(f"  self-check: {'ok' if check['ok'] else 'FAILED'} — {check['detail']}")


def _spine(events: list[dict]) -> list[str]:
    """Engine events only, with the stack's own metadata dropped."""
    engine = {"game_started", "track_generated", "turn_started", "stage_attempted",
              "runner_finished", "invalid_action", "turn_ended", "game_ended"}
    out = []
    for event in events:
        if event["type"] not in engine:
            continue
        payload = dict(event["payload"])
        if event["type"] == "game_started":
            for stack_key in ("stack", "framework", "players", "anchor", "engine",
                              "profile", "prompt_set", "host"):
                payload.pop(stack_key, None)
        out.append(json.dumps({"turn": event["turn"], "type": event["type"],
                               "payload": payload}, sort_keys=True))
    return out


def _expand(patterns: list[str]) -> list[Path]:
    """Resolve wildcards ourselves — PowerShell does not glob for native commands."""
    found: list[Path] = []
    for pattern in patterns:
        if any(ch in pattern for ch in "*?["):
            base = Path(pattern).parent
            found.extend(sorted(p for p in base.glob(Path(pattern).name)
                                if p.suffix == ".jsonl"))
        else:
            found.append(Path(pattern))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="relay_eval")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("score", help="score one or more races")
    p.add_argument("transcripts", nargs="+")
    p.add_argument("--json", action="store_true")
    p.add_argument("--write", action="store_true",
                   help="write <transcript>.eval.json beside each input")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("compare", help="prove the stacks played one race, then compare")
    p.add_argument("transcripts", nargs="+")
    p.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
