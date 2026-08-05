// The geometry constants mirror engine-python's board.py by hand. This test
// is what makes that safe: every move in every committed transcript records
// both the colour-relative position AND the absolute square the engine
// computed — so our toSquare() is checked against the engine's on thousands
// of real values, not trusted.

import { describe, expect, it } from "vitest";

import { HOME_CELL, HOME_COLUMN, PATH, tokenCell, toSquare } from "../src/geometry";
import type { Color } from "../src/types";
import { fixtureNames, loadFixture } from "./helpers";

describe("toSquare matches the engine on every recorded move", () => {
  for (const name of fixtureNames()) {
    it(name, () => {
      let checked = 0;
      for (const event of loadFixture(name)) {
        if (event.type !== "move_made") continue;
        const p = event.payload;
        expect(toSquare(p.player as Color, p.from as number)).toBe(p.from_square);
        expect(toSquare(p.player as Color, p.to as number)).toBe(p.to_square);
        checked += 1;
      }
      expect(checked).toBeGreaterThan(0);
    });
  }
});

describe("the grid itself", () => {
  it("has 52 distinct circuit cells", () => {
    expect(new Set(PATH.map(([r, c]) => `${r},${c}`)).size).toBe(52);
  });

  it("walks each home column into that colour's centre cell", () => {
    for (const color of ["red", "green", "yellow", "blue"] as Color[]) {
      const [lastRow, lastCol] = HOME_COLUMN[color][4];
      const [homeRow, homeCol] = HOME_CELL[color];
      expect(Math.abs(lastRow - homeRow) + Math.abs(lastCol - homeCol)).toBe(1);
    }
  });

  it("maps every position a token can occupy", () => {
    for (const color of ["red", "green", "yellow", "blue"] as Color[]) {
      for (let pos = -1; pos <= 56; pos++) {
        expect(tokenCell(color, pos, 0)).toBeDefined();
      }
    }
  });
});
