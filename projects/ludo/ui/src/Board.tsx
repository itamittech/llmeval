// The board, as SVG: a 15×15 grid, drawn purely from the projected view.

import type { ReactNode } from "react";

import { BASE_SLOTS, HOME_CELL, HOME_COLUMN, PATH, SAFE_SQUARES, START_SQUARE, tokenCell } from "./geometry";
import type { GameView } from "./projector";
import { COLORS, type Color } from "./types";

const CELL = 30;
const SIZE = CELL * 15;

const FILL: Record<Color, string> = {
  red: "#d64545",
  green: "#3f9c5a",
  yellow: "#d6a534",
  blue: "#3f6fbf",
};
const LIGHT: Record<Color, string> = {
  red: "#f6dada",
  green: "#d9ecdf",
  yellow: "#f6ecd0",
  blue: "#dbe4f4",
};

const BASE_RECT: Record<Color, [number, number]> = {
  red: [0, 0],
  green: [0, 9],
  yellow: [9, 9],
  blue: [9, 0],
};

function rect(row: number, col: number, fill: string, key: string, stroke = "#b9b2a6") {
  return (
    <rect key={key} x={col * CELL} y={row * CELL} width={CELL} height={CELL}
      fill={fill} stroke={stroke} strokeWidth={1} />
  );
}

export function Board({ view }: { view: GameView }) {
  const cells: ReactNode[] = [];

  // Base quadrants, 6×6 each, with four resting slots.
  for (const color of COLORS) {
    const [r, c] = BASE_RECT[color];
    cells.push(
      <rect key={`base-${color}`} x={c * CELL} y={r * CELL} width={6 * CELL} height={6 * CELL}
        fill={LIGHT[color]} stroke={FILL[color]} strokeWidth={2} />,
    );
    for (const [sr, sc] of BASE_SLOTS[color]) {
      cells.push(
        <circle key={`slot-${color}-${sr}-${sc}`} cx={(sc + 0.5) * CELL} cy={(sr + 0.5) * CELL}
          r={CELL * 0.42} fill="#fff" stroke={FILL[color]} />,
      );
    }
  }

  // The 52 shared circuit squares; colour each start, star each safe square.
  PATH.forEach(([r, c], square) => {
    const startOf = COLORS.find((col) => START_SQUARE[col] === square);
    cells.push(rect(r, c, startOf ? LIGHT[startOf] : "#faf7f0", `sq-${square}`));
    if (SAFE_SQUARES.has(square)) {
      cells.push(
        <text key={`safe-${square}`} x={(c + 0.5) * CELL} y={(r + 0.72) * CELL}
          textAnchor="middle" fontSize={CELL * 0.55} fill="#c4bbaa">★</text>,
      );
    }
  });

  // Home columns and the centre.
  for (const color of COLORS) {
    HOME_COLUMN[color].forEach(([r, c], i) =>
      cells.push(rect(r, c, LIGHT[color], `hc-${color}-${i}`, FILL[color])),
    );
    const [hr, hc] = HOME_CELL[color];
    cells.push(rect(hr, hc, FILL[color], `home-${color}`));
  }

  // Tokens: group by cell so stacked tokens fan out instead of hiding.
  const byCell = new Map<string, { color: Color; token: number }[]>();
  for (const color of COLORS) {
    view.tokens[color].forEach((pos, token) => {
      const [r, c] = tokenCell(color, pos, token);
      const key = `${r},${c}`;
      byCell.set(key, [...(byCell.get(key) ?? []), { color, token }]);
    });
  }
  const tokens: ReactNode[] = [];
  for (const [key, here] of byCell) {
    const [r, c] = key.split(",").map(Number);
    here.forEach(({ color, token }, i) => {
      const offset = here.length === 1 ? 0 : (i - (here.length - 1) / 2) * CELL * 0.28;
      tokens.push(
        <g key={`tok-${color}-${token}`}>
          <circle cx={(c + 0.5) * CELL + offset} cy={(r + 0.5) * CELL - Math.abs(offset) * 0.2}
            r={CELL * 0.34} fill={FILL[color]} stroke="#3a3630" strokeWidth={1.5} />
          <text x={(c + 0.5) * CELL + offset} y={(r + 0.62) * CELL - Math.abs(offset) * 0.2}
            textAnchor="middle" fontSize={CELL * 0.34} fill="#fff">{token}</text>
        </g>,
      );
    });
  }

  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} width={SIZE} height={SIZE} role="img"
      aria-label="Ludo board">
      <rect x={0} y={0} width={SIZE} height={SIZE} fill="#f3efe6" />
      {cells}
      {tokens}
    </svg>
  );
}
