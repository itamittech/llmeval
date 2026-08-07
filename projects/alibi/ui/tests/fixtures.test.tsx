// ADR-0007 rule 1: every committed fixture renders, at the end and mid-scrub,
// with zero UI source changes. The reveal rule is the ALIBI-specific bite:
// the solution and the red herrings must NOT appear before game_ended.

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Player } from "../src/App";
import { gameEnded } from "../src/types";
import { fixtureNames, loadEval, loadFixture } from "./helpers";

describe("every committed fixture renders", () => {
  for (const name of fixtureNames()) {
    it(`${name} at full length`, () => {
      const events = loadFixture(name);
      const markup = renderToStaticMarkup(
        <Player events={events} position={events.length} evaluation={loadEval(name)} />,
      );
      expect(markup).toContain("The case");
      expect(markup).toContain("The investigation");
      expect(markup).toContain("The archive");
    });

    it(`${name} mid-scrub`, () => {
      const events = loadFixture(name);
      const markup = renderToStaticMarkup(
        <Player events={events} position={Math.floor(events.length / 2)} />,
      );
      expect(markup).toContain("The case");
    });
  }
});

describe("the solution stays sealed until game_ended", () => {
  for (const name of fixtureNames()) {
    it(name, () => {
      const events = loadFixture(name);
      const ended = gameEnded(events);
      if (!ended) return; // an unfinished transcript never reveals — trivially safe
      const before = renderToStaticMarkup(
        <Player events={events} position={ended.seq} />,
      );
      expect(before).not.toContain("The truth:");
      expect(before).not.toContain("red herring");

      const after = renderToStaticMarkup(
        <Player events={events} position={events.length} />,
      );
      expect(after).toContain("The truth:");
      const herrings: string[] = ended.payload.red_herrings ?? [];
      for (const id of herrings) {
        expect(after).toContain(id);
      }
    });
  }
});

describe("the eval panel renders when a result is committed", () => {
  for (const name of fixtureNames()) {
    const result = loadEval(name);
    if (!result) continue;
    it(name, () => {
      const events = loadFixture(name);
      const markup = renderToStaticMarkup(
        <Player events={events} position={events.length} evaluation={result} />,
      );
      expect(markup).toContain("Scored");
      expect(markup).toContain("brier");
    });
  }
});
