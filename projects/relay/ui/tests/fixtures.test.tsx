// ADR-0007's three rules, fourth application.
//
//  1. the suite walks projects/relay/games and renders every transcript there;
//  2. adding a stack's fixture must not require a UI source change;
//  3. everything runs offline, against committed files, with no keys.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "../src/App";
import { COLORS, replay } from "../src/types";
import { fixtureNames, loadEval, loadFixture } from "./helpers";

describe("the committed race set", () => {
  it("has one transcript per stack", () => {
    const names = fixtureNames();
    expect(names.length).toBeGreaterThanOrEqual(3);
    for (const stack of ["strands", "langgraph", "springai"]) {
      expect(names.some((n) => n.includes(stack)), `no ${stack} race`).toBe(true);
    }
  });

  it("renders the player without being told which stacks exist", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "RELAY" })).toBeDefined();
    expect(screen.getByLabelText("the track")).toBeDefined();
    expect(screen.getByLabelText("shared quota")).toBeDefined();
  });
});

describe.each(fixtureNames())("%s", (name) => {
  const events = loadFixture(name);

  it("replays to a complete race", () => {
    const state = replay(events, Number.MAX_SAFE_INTEGER);
    expect(state.stages.length).toBeGreaterThan(0);
    expect(state.standings).toHaveLength(4);
    expect(state.reason).toBeDefined();
  });

  it("tracks the commons draining to the level the transcript records", () => {
    const state = replay(events, Number.MAX_SAFE_INTEGER);
    const spent = COLORS.reduce((n, c) => n + state.lanes[c].escalations, 0);
    expect(state.quotaStart - state.quota).toBe(spent);
  });

  it("agrees with the engine about who cleared what", () => {
    const state = replay(events, Number.MAX_SAFE_INTEGER);
    for (const standing of state.standings!) {
      expect(state.lanes[standing.player].position).toBe(standing.stages_cleared);
      expect(state.lanes[standing.player].ticks).toBe(standing.ticks);
    }
  });

  it("has a committed eval result whose self-check passed", () => {
    const result = loadEval(name);
    expect(result, `no ${name}.eval.json`).toBeDefined();
    expect(result!.self_check.ok).toBe(true);
  });
});

describe("stack independence", () => {
  it("shows the same shape of race whichever stack produced it", () => {
    const shapes = fixtureNames().map((name) => {
      const state = replay(loadFixture(name), Number.MAX_SAFE_INTEGER);
      return JSON.stringify({
        stages: state.stages.map((s) => s.id),
        standings: state.standings,
        key: state.trackKey,
      });
    });
    expect(new Set(shapes).size).toBe(1);
  });
});
