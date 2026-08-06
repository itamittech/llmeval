// The eval panel, held to the same rules as the transcript player:
//
// - every committed eval result in projects/ludo/games/ must render — the
//   suite grows when a result is added, with no source change here;
// - `stack` is displayed, never branched on;
// - rank comes from the result verbatim (which the eval harness guarantees is
//   the engine's own standings, never reordered by scoring).

import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { EvalPanel, parseEvalResult } from "../src/Eval";

const GAMES = join(process.cwd(), "..", "games");
const RESULTS = readdirSync(GAMES).filter((f) => f.endsWith(".eval.json"));

describe("every committed eval result renders", () => {
  it("found committed results to test against", () => {
    expect(RESULTS.length).toBeGreaterThanOrEqual(4);
  });

  for (const file of RESULTS) {
    it(`renders ${file}`, () => {
      const result = parseEvalResult(readFileSync(join(GAMES, file), "utf-8"));
      const html = renderToStaticMarkup(<EvalPanel result={result} />);

      // The report names its game and its stack — displayed, not branched on.
      expect(html).toContain(result.game.file);
      expect(html).toContain(String(result.game.turns_played));

      // All four players appear, in rank order.
      const order = ["red", "green", "yellow", "blue"].sort(
        (a, b) => result.players[a].rank - result.players[b].rank);
      let last = -1;
      for (const color of order) {
        const at = html.indexOf(`<td>${color}</td>`);
        expect(at, color).toBeGreaterThan(last);
        last = at;
      }

      // No judge has run on any committed game yet: the panel must say so
      // honestly rather than render an empty table.
      if (result.judge === null) {
        expect(html).toContain("No judge has scored this game");
      }
    });
  }
});

describe("the panel never invents data", () => {
  it("shows the engine's rank, not a recomputed one", () => {
    const result = parseEvalResult(
      readFileSync(join(GAMES, "sample-seed7.eval.json"), "utf-8"));
    const html = renderToStaticMarkup(<EvalPanel result={result} />);
    const winner = Object.entries(result.players)
      .find(([, p]) => p.rank === 1)![0];
    // The rank-1 row is the first player row in the table.
    const firstRow = html.indexOf("<td>1</td>");
    expect(html.indexOf(`<td>${winner}</td>`)).toBeGreaterThan(firstRow);
    expect(html.indexOf(`<td>${winner}</td>`)).toBeLessThan(firstRow + 200);
  });
});
