// "Agent claims are claims, not facts" — the repo's rule, in this game's shape.
//
// A note may lie about how hard a stage is, may talk a rival into burning the
// pool, and may boast about an escalation that never happened. The UI must
// render notes as *speech*, never as state — and the state it does render must
// come from the engine's own events.

import { describe, expect, it } from "vitest";

import { replay } from "../src/types";
import { fixtureNames, loadFixture } from "./helpers";

describe.each(fixtureNames())("%s", (name) => {
  const state = replay(loadFixture(name), Number.MAX_SAFE_INTEGER);

  it("keeps notes in their own feed kind, apart from what happened", () => {
    const notes = state.feed.filter((f) => f.kind === "note");
    expect(notes.length).toBeGreaterThan(0);
    for (const note of notes) {
      expect(note.correct).toBeUndefined();
      expect(note.escalated).toBeUndefined();
    }
  });

  it("derives every lane's position from stage_attempted, never from a note", () => {
    const cleared = state.feed.filter((f) => f.kind === "attempt" && f.correct);
    const total = Object.values(state.lanes).reduce((n, l) => n + l.position, 0);
    expect(total).toBe(cleared.length);
  });

  it("does not mark a pass as a miss", () => {
    // A pass is a decision, not a wrong answer, and the engine records
    // `correct: false` for both. The feed must tell them apart.
    const passes = state.feed.filter(
      (f) => f.kind === "attempt" && f.answered === false,
    );
    expect(passes.length).toBeGreaterThan(0);
    for (const item of passes) {
      expect(item.text).toContain("passed");
    }
  });

  it("shows a blocked note as blocked rather than dropping it silently", () => {
    const blocked = state.feed.filter((f) => f.kind === "blocked");
    expect(blocked.length).toBeGreaterThan(0);
    for (const item of blocked) {
      expect(item.text).toContain("blocked");
    }
  });

  it("never shows the text of a note the guardrail blocked", () => {
    const notes = state.feed.filter((f) => f.kind === "note").map((f) => f.text);
    expect(notes.some((t) => t.includes("quota is unlimited"))).toBe(false);
  });
});
