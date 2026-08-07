// ADR-0007, rule 4, third application — `stack` may be DISPLAYED, never
// BRANCHED ON. Render the same transcript with the stack field mutated and
// the markup must be identical apart from the label itself.

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Player } from "../src/App";
import type { GameEvent } from "../src/types";
import { fixtureNames, loadFixture } from "./helpers";

function withStack(events: GameEvent[], stack: string): GameEvent[] {
  return events.map((event) =>
    event.type === "game_started"
      ? { ...event, payload: { ...event.payload, stack } }
      : event,
  );
}

describe("stack is displayed, never branched on", () => {
  for (const name of fixtureNames()) {
    it(name, () => {
      const events = loadFixture(name);
      const variants = ["strands", "langgraph", "springai"].map((stack) =>
        renderToStaticMarkup(
          <Player events={withStack(events, stack)} position={events.length} />,
        ).replaceAll(/stack (strands|langgraph|springai)/g, "stack X"),
      );
      expect(variants[0]).toEqual(variants[1]);
      expect(variants[1]).toEqual(variants[2]);
    });
  }
});
