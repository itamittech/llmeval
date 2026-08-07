#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Verify the shared prompt set and model config still hold their invariants.

    uv run scripts/check_prompts.py

`shared/` is what makes the three-stack comparison mean anything. Every rule
below protects a claim this repo makes out loud, and each one fails silently
if left unchecked — no exception, no crash, just a result that quietly isn't
what it says it is.

  1. Templates contain no logic. Python and Java must render them identically,
     and template engines disagree at the edges. (prompts/README.md)
  2. Declared variables match used variables, both ways. A typo in `{{clr}}`
     would otherwise ship an unsubstituted placeholder straight to a model.
  3. No per-colour prompt files. Personas are not hand-coded — whether styles
     emerge from identical prompts is the observation. (agent-design.md)
  4. The rules briefing's numbers match the engine's constants. Two rulebooks
     that disagree look like stupid agents, not like a bad markdown file.
  5. One model sits on both access routes. Break it and every Bedrock-vs-direct
     conclusion becomes uninterpretable. (ADR-0005)
  6. The judge is not a family that played. (evaluation.md)
  7. No secrets in models.yaml. It is public and committed.
  8. The judge prompt (judge/, deliberately outside the manifest — it is the
     eval's, not the stacks') obeys the same template law, with its variables
     checked against the eval's fixed contract instead of a manifest entry.
  9. The ALIBI set (shared/prompts/alibi/) obeys every law above: same template
     rules, its rules-briefing numbers checked against the ALIBI engine, and
     its archivist prompts (outside the manifest, like ludo's judge/) held to a
     fixed variable contract. Its budgets in models.yaml must exist per profile.

Exits non-zero on failure, so it can gate CI.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "shared" / "prompts" / "ludo"
MODELS = ROOT / "shared" / "models.yaml"

# Both engines are standard-library only, so they import without being installed.
sys.path.insert(0, str(ROOT / "projects" / "ludo" / "engine-python" / "src"))
sys.path.insert(0, str(ROOT / "projects" / "alibi" / "engine-python" / "src"))
from ludo_engine.board import (  # noqa: E402
    BASE, COLORS, HOME, HOME_ENTRY, LAST_CIRCUIT, SAFE_SQUARES, START,
    TOKENS_PER_PLAYER,
)
from ludo_engine.game import MOVE_ATTEMPTS, SIX_LIMIT  # noqa: E402
from alibi_engine.archive import SEARCH_K  # noqa: E402
from alibi_engine.case import ALL_ELEMENTS, DIMENSIONS, ELEMENTS  # noqa: E402
from alibi_engine.game import PHASE_ATTEMPTS  # noqa: E402

PROMPTS_ALIBI = ROOT / "shared" / "prompts" / "alibi"

VARIABLE = re.compile(r"\{\{(\w+)\}\}")
# Anything a template engine would treat as control flow.
LOGIC = re.compile(r"\{\{[#/^>!]|\{%|\$\{|\{\{\s*\w+\s*\|")
ENV_VAR = re.compile(r"^[A-Z][A-Z0-9_]*$")
ROW = re.compile(r"^\|\s*(.+?)\s*\|\s*(-?\d+)\s*\|$", re.M)

#: Rules-briefing row label -> the engine constant it must equal.
RULE_NUMBERS = {
    "tokens per player": TOKENS_PER_PLAYER,
    "base position": BASE,
    "start square": START,
    "last shared square": LAST_CIRCUIT,
    "first home-column square": HOME_ENTRY,
    "home": HOME,
    "safe squares on the circuit": len(SAFE_SQUARES),
    "consecutive sixes that cancel a turn": SIX_LIMIT,
    "attempts to name a legal move before forfeiting": MOVE_ATTEMPTS,
}

errors: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


# -- prompts ---------------------------------------------------------------


def entries(manifest: dict) -> list[dict]:
    """Every template the manifest declares, system layer and turn layer."""
    found = list(manifest.get("system", []))
    found.extend(manifest.get("turn", {}).values())
    return found


def check_prompts() -> None:
    manifest = yaml.safe_load((PROMPTS / "manifest.yaml").read_text(encoding="utf-8"))
    declared = entries(manifest)

    listed = {e["file"] for e in declared}
    on_disk = {
        str(p.relative_to(PROMPTS)).replace("\\", "/")
        for p in PROMPTS.rglob("*.md")
        # judge/ is the eval's, not the stacks': single consumer, provenance
        # by content hash in each result rather than by manifest version.
        # Checked by check_judge_prompt below, not exempted.
        if not str(p.relative_to(PROMPTS)).replace("\\", "/").startswith("judge/")
    }
    for orphan in sorted(on_disk - listed):
        fail(f"{orphan} is not in manifest.yaml — no stack would ever load it")
    for missing in sorted(listed - on_disk):
        fail(f"manifest.yaml lists {missing}, which does not exist")

    for entry in declared:
        path = PROMPTS / entry["file"]
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        name = entry["file"]

        if LOGIC.search(text):
            fail(f"{name}: template logic found — Python and Java would diverge; "
                 f"render it in code and pass the result in as one variable")

        used = set(VARIABLE.findall(text))
        want = set(entry.get("variables") or [])
        for extra in sorted(used - want):
            fail(f"{name}: uses {{{{{extra}}}}} but manifest.yaml does not declare it")
        for unused in sorted(want - used):
            fail(f"{name}: manifest.yaml declares '{unused}' but the template never uses it")

    # One agent prompt, not four.
    for path in PROMPTS.rglob("*.md"):
        for color in COLORS:
            if color in path.stem.lower():
                fail(f"{path.name}: per-colour prompt file — the base prompt takes "
                     f"{{{{color}}}} as a variable; personas are not hand-coded")

    check_rule_numbers()
    check_judge_prompt()


#: The eval renders exactly these into the judge prompt — its fixed contract,
#: mirrored in projects/ludo/eval/src/ludo_eval/judge.py.
JUDGE_VARIABLES = {"players", "rubric", "transcript"}


def check_judge_prompt() -> None:
    path = PROMPTS / "judge" / "scoring.md"
    if not path.exists():
        fail("judge/scoring.md is missing — the eval's rubric prompt")
        return
    text = path.read_text(encoding="utf-8")
    if LOGIC.search(text):
        fail("judge/scoring.md: template logic found — same law as every prompt")
    used = set(VARIABLE.findall(text))
    if used != JUDGE_VARIABLES:
        fail(f"judge/scoring.md: uses {sorted(used)}, the eval renders "
             f"{sorted(JUDGE_VARIABLES)} — they must match exactly")


def check_rule_numbers() -> None:
    """The rules briefing is a second rulebook. Keep its numbers honest."""
    path = PROMPTS / "system" / "rules.md"
    if not path.exists():
        fail("system/rules.md is missing")
        return

    table = {m.group(1).strip().lower(): int(m.group(2))
             for m in ROW.finditer(path.read_text(encoding="utf-8"))}

    for label, expected in RULE_NUMBERS.items():
        if label not in table:
            fail(f"system/rules.md: numbers table has no row '{label}'")
        elif table[label] != expected:
            fail(f"system/rules.md: '{label}' says {table[label]}, "
                 f"engine says {expected}")


# -- the ALIBI set ---------------------------------------------------------

#: ALIBI rules-briefing row label -> the engine value it must equal.
ALIBI_RULE_NUMBERS = {
    "suspects": len(ELEMENTS["who"]),
    "methods": len(ELEMENTS["how"]),
    "places": len(ELEMENTS["where"]),
    "exhibits in your hand": (len(ALL_ELEMENTS) - len(DIMENSIONS)) // 4,
    "red herrings in the archive": len(DIMENSIONS),
    "results per archive search": SEARCH_K,
    "attempts per action before the engine decides for you": PHASE_ATTEMPTS,
}

#: The stacks render exactly these into the archivist prompts — a fixed
#: contract, like ludo's judge prompt: one shared instrument, no manifest entry.
ARCHIVIST_VARIABLES = {
    "system.md": set(),
    "answer.md": {"query", "documents"},
}


def check_alibi_prompts() -> None:
    manifest = yaml.safe_load((PROMPTS_ALIBI / "manifest.yaml").read_text(encoding="utf-8"))
    declared = entries(manifest)

    listed = {e["file"] for e in declared}
    on_disk = {
        str(p.relative_to(PROMPTS_ALIBI)).replace("\\", "/")
        for p in PROMPTS_ALIBI.rglob("*.md")
        if not str(p.relative_to(PROMPTS_ALIBI)).replace("\\", "/").startswith("archivist/")
    }
    for orphan in sorted(on_disk - listed):
        fail(f"alibi/{orphan} is not in manifest.yaml — no stack would ever load it")
    for missing in sorted(listed - on_disk):
        fail(f"alibi/manifest.yaml lists {missing}, which does not exist")

    for entry in declared:
        path = PROMPTS_ALIBI / entry["file"]
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        name = f"alibi/{entry['file']}"

        if LOGIC.search(text):
            fail(f"{name}: template logic found — Python and Java would diverge; "
                 f"render it in code and pass the result in as one variable")

        used = set(VARIABLE.findall(text))
        want = set(entry.get("variables") or [])
        for extra in sorted(used - want):
            fail(f"{name}: uses {{{{{extra}}}}} but manifest.yaml does not declare it")
        for unused in sorted(want - used):
            fail(f"{name}: manifest.yaml declares '{unused}' but the template never uses it")

    for path in PROMPTS_ALIBI.rglob("*.md"):
        for color in COLORS:
            if color in path.stem.lower():
                fail(f"alibi/{path.name}: per-colour prompt file — personas are "
                     f"not hand-coded, in either game")

    for filename, expected in ARCHIVIST_VARIABLES.items():
        path = PROMPTS_ALIBI / "archivist" / filename
        if not path.exists():
            fail(f"alibi/archivist/{filename} is missing")
            continue
        text = path.read_text(encoding="utf-8")
        if LOGIC.search(text):
            fail(f"alibi/archivist/{filename}: template logic found — same law as every prompt")
        used = set(VARIABLE.findall(text))
        if used != expected:
            fail(f"alibi/archivist/{filename}: uses {sorted(used)}, the stacks render "
                 f"{sorted(expected)} — they must match exactly")

    rules = PROMPTS_ALIBI / "system" / "rules.md"
    if not rules.exists():
        fail("alibi/system/rules.md is missing")
        return
    table = {m.group(1).strip().lower(): int(m.group(2))
             for m in ROW.finditer(rules.read_text(encoding="utf-8"))}
    for label, expected in ALIBI_RULE_NUMBERS.items():
        if label not in table:
            fail(f"alibi/system/rules.md: numbers table has no row '{label}'")
        elif table[label] != expected:
            fail(f"alibi/system/rules.md: '{label}' says {table[label]}, "
                 f"engine says {expected}")


def check_alibi_models(config: dict) -> None:
    """ALIBI's budgets and archivist ride in models.yaml beside LUDO's profiles."""
    alibi = config.get("alibi")
    if not alibi:
        fail("models.yaml: no 'alibi' section — ALIBI budgets and archivist are unconfigured")
        return

    profiles = set((config.get("profiles") or {}).keys())
    budgets = alibi.get("budgets") or {}
    if set(budgets.keys()) != profiles:
        fail(f"models.yaml: alibi.budgets covers {sorted(budgets)} but profiles are "
             f"{sorted(profiles)} — every profile needs ALIBI budgets")
    for profile, values in budgets.items():
        for field in ("max_turns", "max_searches_per_turn", "max_note_chars",
                      "max_tokens_per_game"):
            if field not in (values or {}):
                fail(f"models.yaml: alibi.budgets.{profile} is missing {field}")

    archivist = alibi.get("archivist") or {}
    for field in ("provider", "access", "model", "retrieval_profile"):
        if field not in archivist:
            fail(f"models.yaml: alibi.archivist is missing {field}")


# -- models ----------------------------------------------------------------


def check_models() -> None:
    config = yaml.safe_load(MODELS.read_text(encoding="utf-8"))

    for provider, names in (config.get("credentials") or {}).items():
        for name in names:
            if not ENV_VAR.match(name):
                fail(f"models.yaml: credentials.{provider} contains '{name}', which is "
                     f"not an environment variable NAME — this file is public")

    profiles = config.get("profiles") or {}
    if not profiles:
        fail("models.yaml: no profiles defined")
        return

    shapes = {}
    for profile, spec in profiles.items():
        seats = spec.get("seats") or []
        if len(seats) != 4:
            fail(f"models.yaml: profile '{profile}' has {len(seats)} seats, needs 4")
            continue

        routes = [s.get("access") for s in seats]
        for route in ("bedrock", "direct"):
            if routes.count(route) != 2:
                fail(f"models.yaml: profile '{profile}' has {routes.count(route)} "
                     f"'{route}' seats, needs 2")

        check_control(profile, seats)
        check_judge(profile, spec, seats)

        for field in ("max_turns", "max_floor_passes", "max_message_chars",
                      "max_context_tokens"):
            if field not in (spec.get("budgets") or {}):
                fail(f"models.yaml: profile '{profile}' is missing budgets.{field} — "
                     f"every stack's harness reads these; the negotiation prompt "
                     f"renders some of them")

        shapes[profile] = [(s.get("seat"), s.get("access"), s.get("provider"))
                           for s in seats]

    # Switching profile must change the models, never the experiment's shape.
    distinct = {tuple(v) for v in shapes.values()}
    if len(distinct) > 1:
        fail("models.yaml: profiles disagree on seat structure — switching profile "
             "would change the experiment, not just the cost")


def check_control(profile: str, seats: list[dict]) -> None:
    """ADR-0005: one model must sit on both routes, or the route is confounded.

    Bedrock spells the same model with a provider prefix (`anthropic.claude-opus-5`
    vs `claude-opus-5`), so compare with it stripped — otherwise a correct control
    pair looks broken.
    """
    by_route: dict[str, set] = {"bedrock": set(), "direct": set()}
    unpinned = False
    for seat in seats:
        model = seat.get("model")
        if model in (None, "TBD"):
            unpinned = True
            model = f"{seat.get('provider')}:*"
        else:
            model = model.split(".", 1)[-1] if "." in model else model
        by_route.setdefault(seat.get("access"), set()).add((seat.get("provider"), model))

    shared = by_route["bedrock"] & by_route["direct"]
    if len(shared) != 1:
        fail(f"models.yaml: profile '{profile}' has {len(shared)} model(s) on both "
             f"routes, needs exactly 1 — without it, Bedrock-vs-direct differences "
             f"cannot be told apart from model differences (ADR-0005)")
    if unpinned:
        notes.append(f"profile '{profile}': model ids are TBD, so the control was "
                     f"checked by provider only")


def check_judge(profile: str, spec: dict, seats: list[dict]) -> None:
    judge = spec.get("judge") or {}
    if not judge:
        fail(f"models.yaml: profile '{profile}' has no judge")
        return
    seated = {s.get("provider") for s in seats}
    if judge.get("provider") in seated:
        fail(f"models.yaml: profile '{profile}' judge provider "
             f"'{judge.get('provider')}' also holds a seat — an LLM judge scoring "
             f"its own family is the first thing a reader will attack "
             f"(evaluation.md)")


# -- main ------------------------------------------------------------------


def main() -> int:
    check_prompts()
    check_alibi_prompts()
    check_models()
    check_alibi_models(yaml.safe_load(MODELS.read_text(encoding="utf-8")))

    for note in notes:
        print(f"note: {note}")

    if errors:
        print(f"\n{len(errors)} problem(s):\n")
        for err in errors:
            print(f"  - {err}")
        return 1

    templates = len(entries(yaml.safe_load(
        (PROMPTS / "manifest.yaml").read_text(encoding="utf-8"))))
    alibi_templates = len(entries(yaml.safe_load(
        (PROMPTS_ALIBI / "manifest.yaml").read_text(encoding="utf-8"))))
    print(f"prompts ok — ludo: {templates} templates, {len(RULE_NUMBERS)} rule numbers; "
          f"alibi: {alibi_templates} templates, {len(ALIBI_RULE_NUMBERS)} rule numbers")
    print("Reminder: this checks invariants, not whether the prompts are any good.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
