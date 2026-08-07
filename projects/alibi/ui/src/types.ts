// The event vocabulary this player understands — a projection of
// shared/schemas/alibi-event.schema.json, which is the only contract the UI
// has with anything (ADR-0003). Agent claims are claims: nothing here treats
// a note, a document, or a notebook line as true.

export type Color = "red" | "green" | "yellow" | "blue";

export interface GameEvent {
  seq: number;
  turn: number;
  type: string;
  payload: Record<string, any>;
}

export interface EvalResult {
  game: Record<string, any>;
  detectives: Array<Record<string, any>>;
  checks: { standings_match: boolean };
}

export function parseTranscript(raw: string): GameEvent[] {
  const events = raw
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .map((line) => JSON.parse(line) as GameEvent);
  events.forEach((event, index) => {
    if (event.seq !== index) {
      throw new Error(`seq ${event.seq} at line ${index + 1}: transcript is not contiguous`);
    }
  });
  return events;
}

export function eventsOfType(events: GameEvent[], type: string): GameEvent[] {
  return events.filter((event) => event.type === type);
}

export function gameStarted(events: GameEvent[]): GameEvent {
  const first = events[0];
  if (!first || first.type !== "game_started") {
    throw new Error("transcript does not open with game_started");
  }
  return first;
}

export function gameEnded(events: GameEvent[]): GameEvent | undefined {
  return events.find((event) => event.type === "game_ended");
}
