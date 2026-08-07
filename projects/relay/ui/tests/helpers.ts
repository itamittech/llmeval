// Test helpers: every committed race, loaded from projects/relay/games/.
// ADR-0007 rule 1, fourth application — the suite renders every one of them,
// offline, no keys. Adding a stack means dropping its transcript in that
// directory; these tests pick it up automatically, and the UI source must not
// need to change.

import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { parseTranscript, type EvalResult, type GameEvent } from "../src/types";

// vitest runs with cwd = projects/relay/ui, so the fixture set is one up.
const GAMES_DIR = join(process.cwd(), "..", "games");

export function fixtureNames(): string[] {
  return readdirSync(GAMES_DIR).filter((name) => name.endsWith(".jsonl")).sort();
}

export function loadFixture(name: string): GameEvent[] {
  return parseTranscript(readFileSync(join(GAMES_DIR, name), "utf-8"));
}

export function loadEval(name: string): EvalResult | undefined {
  try {
    return JSON.parse(
      readFileSync(join(GAMES_DIR, `${name}.eval.json`), "utf-8"),
    ) as EvalResult;
  } catch {
    return undefined;
  }
}
