// Board geometry: the engine's coordinate system, mapped onto a 15×15 grid.
//
// The constants mirror engine-python's board.py and are NOT trusted on faith:
// tests/geometry.test.ts checks toSquare() against every from_square/to_square
// the committed fixtures record, so a drift between this file and the engine
// fails CI rather than drawing tokens on the wrong cells.

import type { Color } from "./types";

export const BASE = -1;
export const LAST_CIRCUIT = 50;
export const HOME = 56;
export const CIRCUIT_SIZE = 52;

export const START_SQUARE: Record<Color, number> = {
  red: 0,
  green: 13,
  yellow: 26,
  blue: 39,
};

export const SAFE_SQUARES = new Set([0, 8, 13, 21, 26, 34, 39, 47]);

export function toSquare(color: Color, position: number): number | null {
  if (position < 0 || position > LAST_CIRCUIT) return null;
  return (START_SQUARE[color] + position) % CIRCUIT_SIZE;
}

export type Cell = [row: number, col: number];

// The 52 circuit squares, absolute square -> grid cell, clockwise from red's
// start. Each colour's start lands 13 later: red (6,1), green (1,8),
// yellow (8,13), blue (13,6) — the cell just outside each base.
export const PATH: Cell[] = [
  [6, 1], [6, 2], [6, 3], [6, 4], [6, 5],
  [5, 6], [4, 6], [3, 6], [2, 6], [1, 6], [0, 6],
  [0, 7],
  [0, 8], [1, 8], [2, 8], [3, 8], [4, 8], [5, 8],
  [6, 9], [6, 10], [6, 11], [6, 12], [6, 13], [6, 14],
  [7, 14],
  [8, 14], [8, 13], [8, 12], [8, 11], [8, 10], [8, 9],
  [9, 8], [10, 8], [11, 8], [12, 8], [13, 8], [14, 8],
  [14, 7],
  [14, 6], [13, 6], [12, 6], [11, 6], [10, 6], [9, 6],
  [8, 5], [8, 4], [8, 3], [8, 2], [8, 1], [8, 0],
  [7, 0],
  [6, 0],
];

// Home columns: colour-relative positions 51..55, walking in toward the centre.
export const HOME_COLUMN: Record<Color, Cell[]> = {
  red: [[7, 1], [7, 2], [7, 3], [7, 4], [7, 5]],
  green: [[1, 7], [2, 7], [3, 7], [4, 7], [5, 7]],
  yellow: [[7, 13], [7, 12], [7, 11], [7, 10], [7, 9]],
  blue: [[13, 7], [12, 7], [11, 7], [10, 7], [9, 7]],
};

// The centre cell each colour's home column empties into (position 56).
export const HOME_CELL: Record<Color, Cell> = {
  red: [7, 6],
  green: [6, 7],
  yellow: [7, 8],
  blue: [8, 7],
};

// Four resting slots inside each base quadrant, one per token index.
export const BASE_SLOTS: Record<Color, Cell[]> = {
  red: [[1.5, 1.5], [1.5, 3.5], [3.5, 1.5], [3.5, 3.5]],
  green: [[1.5, 10.5], [1.5, 12.5], [3.5, 10.5], [3.5, 12.5]],
  yellow: [[10.5, 10.5], [10.5, 12.5], [12.5, 10.5], [12.5, 12.5]],
  blue: [[10.5, 1.5], [10.5, 3.5], [12.5, 1.5], [12.5, 3.5]],
};

/** Grid cell for one token, given its colour-relative position. */
export function tokenCell(color: Color, position: number, token: number): Cell {
  if (position === BASE) return BASE_SLOTS[color][token];
  if (position === HOME) return HOME_CELL[color];
  if (position > LAST_CIRCUIT) return HOME_COLUMN[color][position - 51];
  return PATH[toSquare(color, position) as number];
}
