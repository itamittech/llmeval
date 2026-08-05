// Mirrors shared/schemas/event.schema.json — the UI's ONLY input (ADR-0003).
// Types cover the fields the player reads; unknown payload fields pass through
// untouched, so a schema addition does not break old builds.

export type Color = "red" | "green" | "yellow" | "blue";

export const COLORS: readonly Color[] = ["red", "green", "yellow", "blue"];

export interface GameEvent {
  seq: number;
  turn: number;
  type: string;
  payload: Record<string, unknown> & { player?: Color };
}

export interface PlayerMeta {
  color: Color;
  agent?: string;
  seat?: number;
  model?: string;
  access?: string;
}

export function parseTranscript(jsonl: string): GameEvent[] {
  return jsonl
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .map((line) => JSON.parse(line) as GameEvent);
}
