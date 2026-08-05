// ADR-0007, rules 1 and 2: the UI renders EVERY committed transcript, and the
// engine-only fixture — zero agent events — is a first-class citizen. A UI
// that renders it correctly cannot be depending on any agent event existing,
// which is the strongest stack-independence guarantee available before a
// second stack exists.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Player } from "../src/App";
import { fixtureNames, loadFixture } from "./helpers";

describe("every committed transcript renders end to end", () => {
  for (const name of fixtureNames()) {
    it(name, () => {
      const events = loadFixture(name);
      const { container, unmount } = render(<Player events={events} position={events.length} />);
      expect(container.querySelector("svg")).not.toBeNull();
      expect(screen.getByText(/game over/)).toBeTruthy();
      unmount();
    });
  }
});

describe("the zero-agent-event fixture", () => {
  it("renders with the agent panels honestly empty", () => {
    const events = loadFixture("sample-seed7.jsonl");
    expect(events.some((e) => e.type.startsWith("agent") || e.type === "llm_call")).toBe(false);

    render(<Player events={events} position={events.length} />);
    expect(screen.getByText(/engine-only game/)).toBeTruthy();
    expect(screen.getByText(/No agent events/)).toBeTruthy();
  });
});
