// The seal rule, tested at the layer that could break it.
//
// The engine keeps tiers out of a runner's reach by type. The UI has the whole
// transcript, `game_ended` included, so nothing stops it rendering a tier on
// turn one except a decision — and a decision that is not tested is a decision
// that will be undone by a refactor.

import { describe, expect, it } from "vitest";

import { replay } from "../src/types";
import { fixtureNames, loadFixture } from "./helpers";

describe.each(fixtureNames())("%s", (name) => {
  const events = loadFixture(name);
  const endedAt = events.find((e) => e.type === "game_ended")!.seq;

  it("hides the track key at every point before the finish", () => {
    for (let seq = 0; seq < endedAt; seq += 1) {
      const state = replay(events, seq);
      expect(state.trackKey, `leaked at seq ${seq}`).toBeUndefined();
      expect(state.standings, `leaked standings at seq ${seq}`).toBeUndefined();
    }
  });

  it("opens it at the finish and not before", () => {
    expect(replay(events, endedAt - 1).trackKey).toBeUndefined();
    const opened = replay(events, endedAt);
    expect(opened.trackKey).toBeDefined();
    expect(opened.trackKey!.length).toBeGreaterThan(0);
    for (const entry of opened.trackKey!) {
      expect(entry.tier).toBeGreaterThanOrEqual(1);
      expect(entry.tier).toBeLessThanOrEqual(3);
    }
  });

  it("never carries a tier on a stage the player view holds", () => {
    const state = replay(events, endedAt);
    for (const stage of state.stages) {
      expect(Object.keys(stage).sort()).toEqual(["family", "id", "prompt"]);
    }
  });
});
