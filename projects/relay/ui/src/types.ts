// The event contract, as TypeScript. Mirrors shared/schemas/relay-event.schema.json
// and nothing else (ADR-0003) — the UI never imports from an engine or a stack.

export type Color = "red" | "green" | "yellow" | "blue";

export interface GameEvent {
  seq: number;
  turn: number;
  type: string;
  payload: Record<string, unknown>;
}

export interface PublicStage {
  id: string;
  family: string;
  prompt: string;
}

export interface StageKey {
  id: string;
  tier: number;
  answer: string;
}

export interface Standing {
  player: Color;
  rank: number;
  stages_cleared: number;
  ticks: number;
  finished: boolean;
  escalations?: number;
  correct?: number;
  wrong?: number;
  passes?: number;
}

export interface LaneScore {
  player: Color;
  stages_cleared: number;
  ticks: number;
  solo_accuracy: number | null;
  escalations: number;
  escalation_precision: number | null;
  escalation_recall: number | null;
  escalation_fit: number | null;
  tokens: number;
  calls: number;
}

export interface EvalResult {
  stack: string;
  seed: number;
  reason: string;
  turns_played: number;
  commons: { quota: number; spent: number; exhausted: boolean };
  lanes: LaneScore[];
  self_check: { ok: boolean; detail: string };
}

export function parseTranscript(text: string): GameEvent[] {
  return text
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .map((line) => JSON.parse(line) as GameEvent);
}

/**
 * The state of a race at one point in the transcript.
 *
 * `trackKey` is `undefined` until `game_ended` has been played. That is the
 * seal, and it is enforced here rather than in a component: a view that only
 * receives the key after the finish cannot leak it before, however it is
 * rendered.
 */
export interface RaceState {
  seed: number;
  stack: string;
  stages: PublicStage[];
  quota: number;
  quotaStart: number;
  maxTurns: number;
  turn: number;
  lanes: Record<Color, LaneState>;
  feed: FeedItem[];
  trackKey?: StageKey[];
  standings?: Standing[];
  reason?: string;
}

export interface LaneState {
  color: Color;
  position: number;
  ticks: number;
  escalations: number;
  finished: boolean;
  model?: string;
  access?: string;
}

export interface FeedItem {
  seq: number;
  turn: number;
  kind: "attempt" | "note" | "blocked" | "finish" | "invalid" | "memory";
  player: Color;
  text: string;
  escalated?: boolean;
  correct?: boolean;
  /** False when the runner passed. A pass is not a wrong answer. */
  answered?: boolean;
}

export const COLORS: Color[] = ["red", "green", "yellow", "blue"];

export function replay(events: GameEvent[], upTo: number): RaceState {
  const started = events.find((e) => e.type === "game_started");
  const track = events.find((e) => e.type === "track_generated");
  const startPayload = (started?.payload ?? {}) as Record<string, any>;

  const lanes = {} as Record<Color, LaneState>;
  for (const color of COLORS) {
    lanes[color] = {
      color,
      position: 0,
      ticks: 0,
      escalations: 0,
      finished: false,
    };
  }
  for (const player of (startPayload.players ?? []) as Record<string, any>[]) {
    const lane = lanes[player.color as Color];
    if (lane) {
      lane.model = player.model;
      lane.access = player.access;
    }
  }

  const state: RaceState = {
    seed: startPayload.seed ?? 0,
    stack: startPayload.stack ?? "none",
    stages: ((track?.payload?.stages ?? []) as PublicStage[]) ?? [],
    quota: startPayload.escalation_quota ?? 0,
    quotaStart: startPayload.escalation_quota ?? 0,
    maxTurns: startPayload.max_turns ?? 0,
    turn: 0,
    lanes,
    feed: [],
  };

  for (const event of events) {
    if (event.seq > upTo) break;
    const p = event.payload as Record<string, any>;
    state.turn = event.turn;

    switch (event.type) {
      case "stage_attempted": {
        const lane = state.lanes[p.player as Color];
        lane.ticks = p.ticks_total;
        lane.escalations += p.escalated ? 1 : 0;
        if (p.correct) lane.position += 1;
        state.quota = p.quota_left;
        state.feed.push({
          seq: event.seq,
          turn: event.turn,
          kind: "attempt",
          player: p.player,
          escalated: p.escalated,
          correct: p.correct,
          answered: p.answer !== null,
          text:
            p.answer === null
              ? `passed on ${p.stage}`
              : `${p.escalated ? "the anchor answered" : "answered"} ${p.stage}: “${p.answer}”`,
        });
        if (p.note) {
          state.feed.push({
            seq: event.seq,
            turn: event.turn,
            kind: "note",
            player: p.player,
            text: p.note,
          });
        }
        break;
      }
      case "runner_finished":
        state.lanes[p.player as Color].finished = true;
        state.feed.push({
          seq: event.seq,
          turn: event.turn,
          kind: "finish",
          player: p.player,
          text: `finished the track on ${p.ticks} ticks`,
        });
        break;
      case "guardrail_triggered":
        state.feed.push({
          seq: event.seq,
          turn: event.turn,
          kind: "blocked",
          player: p.player,
          text: `note blocked — ${p.rule}: ${p.detail}`,
        });
        break;
      case "invalid_action":
        state.feed.push({
          seq: event.seq,
          turn: event.turn,
          kind: "invalid",
          player: p.player,
          text: `invalid ${p.phase}: ${p.reason}`,
        });
        break;
      case "memory_write":
        state.feed.push({
          seq: event.seq,
          turn: event.turn,
          kind: "memory",
          player: p.player,
          text: p.text,
        });
        break;
      case "game_ended":
        state.trackKey = p.track_key as StageKey[];
        state.standings = p.standings as Standing[];
        state.reason = p.reason;
        break;
      default:
        break;
    }
  }

  return state;
}
