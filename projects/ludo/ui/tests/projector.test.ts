// The projector against the engine's own answers. The strongest check is the
// last one: replay a whole recorded game and compare the projected standings
// with what the engine wrote into game_ended — home counts, progress, capture
// stats, all of it. If the fold drifts from the rules, this is what fires.

import { describe, expect, it } from "vitest";

import { progress, project, standings, tokensHome } from "../src/projector";
import type { GameEvent } from "../src/types";
import { fixtureNames, loadFixture } from "./helpers";

const ev = (seq: number, turn: number, type: string, payload: Record<string, unknown>): GameEvent =>
  ({ seq, turn, type, payload: payload as GameEvent["payload"] });

describe("folding the stream", () => {
  it("moves tokens and returns capture victims to base", () => {
    const view = project([
      ev(0, 1, "turn_started", { player: "red" }),
      ev(1, 1, "move_made", { player: "red", token: 0, from: -1, to: 0 }),
      ev(2, 1, "move_made", { player: "red", token: 0, from: 0, to: 13 }),
      ev(3, 1, "token_captured", { captor: "red", captor_token: 0, victim: "green", victim_token: 2, square: 13 }),
    ]);
    expect(view.tokens.red[0]).toBe(13);
    expect(view.tokens.green[2]).toBe(-1);
    expect(view.stats.red.made).toBe(1);
    expect(view.stats.green.suffered).toBe(1);
  });

  it("three sixes revert the whole turn, captures included", () => {
    const before = [
      ev(0, 1, "turn_started", { player: "green" }),
      ev(1, 1, "move_made", { player: "green", token: 1, from: -1, to: 0 }),
    ];
    const cancelled = [
      ...before,
      ev(2, 2, "turn_started", { player: "red" }),
      ev(3, 2, "move_made", { player: "red", token: 0, from: -1, to: 0 }),
      ev(4, 2, "move_made", { player: "red", token: 0, from: 0, to: 13 }),
      ev(5, 2, "token_captured", { captor: "red", captor_token: 0, victim: "green", victim_token: 1, square: 13 }),
      ev(6, 2, "turn_ended", { player: "red", reason: "three_sixes" }),
    ];
    const view = project(cancelled);
    // Exactly as if red's turn had never happened:
    expect(view.tokens.red[0]).toBe(-1);
    expect(view.tokens.green[1]).toBe(0);      // the captured token is BACK
    expect(view.stats.red.made).toBe(0);
    expect(view.stats.green.suffered).toBe(0);
  });

  it("counts a forfeit only on an illegal_move turn end", () => {
    const view = project([
      ev(0, 1, "turn_started", { player: "red" }),
      ev(1, 1, "turn_ended", { player: "red", reason: "illegal_move" }),
      ev(2, 2, "turn_started", { player: "green" }),
      ev(3, 2, "turn_ended", { player: "green", reason: "no_legal_move" }),
    ]);
    expect(view.stats.red.forfeits).toBe(1);
    expect(view.stats.green.forfeits).toBe(0);
  });
});

describe("a full replay agrees with the engine's game_ended", () => {
  for (const name of fixtureNames()) {
    it(name, () => {
      const events = loadFixture(name);
      const view = project(events);
      const ended = view.gameEnded as { standings: Array<Record<string, unknown>> };
      expect(ended).not.toBeNull();

      for (const row of ended.standings) {
        const color = row.player as "red";
        expect(tokensHome(view, color)).toBe(row.tokens_home);
        expect(progress(view, color)).toBe(row.progress);
        expect(view.stats[color].made).toBe(row.captures_made);
        expect(view.stats[color].suffered).toBe(row.captures_suffered);
        expect(view.stats[color].forfeits).toBe(row.turns_forfeited);
      }
      // And the ordering rule reproduces the engine's ranking exactly.
      expect(standings(view)).toEqual(ended.standings.map((row) => row.player));
    });
  }
});
