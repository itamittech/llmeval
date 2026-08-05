// ADR-0007, rule 4 — the test the whole ADR exists for. The `stack` field may
// be DISPLAYED, never BRANCHED ON. Enforced the way the ADR specifies: render
// the same transcript twice with game_started.stack mutated, and assert the
// markup is identical apart from the label itself. A UI that styled, laid out,
// or behaved differently per stack fails here, loudly, before it fails subtly.

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

      const asStrands = renderToStaticMarkup(
        <Player events={withStack(events, "strands")} position={events.length} />,
      );
      const asLanggraph = renderToStaticMarkup(
        <Player events={withStack(events, "langgraph")} position={events.length} />,
      );

      // The labels themselves must differ — proving the field IS displayed…
      expect(asStrands).toContain("stack: strands");
      expect(asLanggraph).toContain("stack: langgraph");

      // …and once each is normalised away, nothing else may.
      expect(asLanggraph.replace("stack: langgraph", "stack: strands")).toBe(asStrands);
    });
  }
});
