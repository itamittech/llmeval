// Claims are claims: everything an agent merely said — notes, reasoning,
// notebook lines — renders inside the .claim style, the visual contract that
// nothing downstream treats it as fact.

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Player } from "../src/App";
import { eventsOfType } from "../src/types";
import { fixtureNames, loadFixture } from "./helpers";

describe("agent speech renders as claim, never as fact", () => {
  for (const name of fixtureNames()) {
    it(name, () => {
      const events = loadFixture(name);
      const notes = eventsOfType(events, "suggestion_made")
        .map((e) => e.payload.note)
        .filter((note): note is string => typeof note === "string");
      if (notes.length === 0) return;
      const markup = renderToStaticMarkup(
        <Player events={events} position={events.length} />,
      );
      for (const note of notes) {
        const index = markup.indexOf(note);
        expect(index).toBeGreaterThan(-1);
        const before = markup.slice(Math.max(0, index - 200), index);
        expect(before).toContain("claim");
      }
    });
  }
});
