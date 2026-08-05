// The projector: fold the event stream into a view of the game.
//
// The transcript is the only input (ADR-0003). The UI holds no game logic of
// its own except this replay — and one genuinely subtle rule: the engine
// CANCELS a turn on three consecutive sixes, restoring its snapshot silently.
// The transcript still records the moves that were then reverted, so a naive
// fold would leave phantom token positions. The projector keeps a per-turn
// undo journal and rolls it back when `turn_ended` says `three_sixes`.
//
// Agent claims are claims (CLAUDE.md): messages and memory notes are carried
// verbatim as what a player SAID, never folded into board state.

import { COLORS, type Color, type GameEvent, type PlayerMeta } from "./types";

export interface TokenTotals {
  input: number;
  output: number;
  cacheRead: number;
  cacheWrite: number;
  calls: number;
}

export interface FeedItem {
  seq: number;
  turn: number;
  player: Color;
  kind: string;
  text: string;
  extra?: string;
}

export interface GameView {
  stack: string;
  seed: number | null;
  maxTurns: number | null;
  profile: string | null;
  players: PlayerMeta[];
  turn: number;
  currentPlayer: Color | null;
  lastRoll: { player: Color; value: number } | null;
  tokens: Record<Color, number[]>;
  stats: Record<Color, { made: number; suffered: number; forfeits: number }>;
  spend: Record<Color, TokenTotals>;
  finished: Color[];
  feed: FeedItem[];
  gameEnded: Record<string, unknown> | null;
  eventsApplied: number;
}

const emptyTotals = (): TokenTotals =>
  ({ input: 0, output: 0, cacheRead: 0, cacheWrite: 0, calls: 0 });

function emptyView(): GameView {
  return {
    stack: "none",
    seed: null,
    maxTurns: null,
    profile: null,
    players: [],
    turn: 0,
    currentPlayer: null,
    lastRoll: null,
    tokens: Object.fromEntries(COLORS.map((c) => [c, [-1, -1, -1, -1]])) as GameView["tokens"],
    stats: Object.fromEntries(
      COLORS.map((c) => [c, { made: 0, suffered: 0, forfeits: 0 }]),
    ) as GameView["stats"],
    spend: Object.fromEntries(COLORS.map((c) => [c, emptyTotals()])) as GameView["spend"],
    finished: [],
    feed: [],
    gameEnded: null,
    eventsApplied: 0,
  };
}

type Undo = () => void;

/** Replay events[0..count) into a view. Pure: same input, same view. */
export function project(events: GameEvent[], count: number = events.length): GameView {
  const view = emptyView();
  // Everything this turn did, so three_sixes can take it all back.
  let turnUndo: Undo[] = [];

  const feed = (e: GameEvent, kind: string, text: string, extra?: string) =>
    view.feed.push({ seq: e.seq, turn: e.turn, player: e.payload.player as Color, kind, text, extra });

  for (const event of events.slice(0, count)) {
    const p = event.payload;
    switch (event.type) {
      case "game_started": {
        view.stack = (p.stack as string) ?? "none";
        view.seed = (p.seed as number) ?? null;
        view.maxTurns = (p.max_turns as number) ?? null;
        view.profile = (p.profile as string) ?? null;
        view.players = (p.players as PlayerMeta[]) ?? [];
        break;
      }
      case "turn_started": {
        view.turn = event.turn;
        view.currentPlayer = p.player as Color;
        turnUndo = [];
        break;
      }
      case "dice_rolled": {
        view.lastRoll = { player: p.player as Color, value: p.value as number };
        break;
      }
      case "move_made": {
        const color = p.player as Color;
        const token = p.token as number;
        const from = p.from as number;
        view.tokens[color][token] = p.to as number;
        turnUndo.push(() => { view.tokens[color][token] = from; });
        break;
      }
      case "token_captured": {
        const captor = p.captor as Color;
        const victim = p.victim as Color;
        const victimToken = p.victim_token as number;
        const was = view.tokens[victim][victimToken];
        view.tokens[victim][victimToken] = -1;
        view.stats[captor].made += 1;
        view.stats[victim].suffered += 1;
        turnUndo.push(() => {
          view.tokens[victim][victimToken] = was;
          view.stats[captor].made -= 1;
          view.stats[victim].suffered -= 1;
        });
        break;
      }
      case "illegal_move_rejected": {
        feed(event, "rejected", String(p.reason ?? ""), `attempt ${p.attempt ?? "?"}`);
        break;
      }
      case "turn_ended": {
        const reason = p.reason as string;
        if (reason === "three_sixes") {
          // The engine restored its snapshot; restore ours, newest first.
          for (const undo of turnUndo.reverse()) undo();
        }
        if (reason === "illegal_move") {
          view.stats[p.player as Color].forfeits += 1;
        }
        turnUndo = [];
        break;
      }
      case "player_finished": {
        view.finished.push(p.player as Color);
        break;
      }
      case "game_ended": {
        view.gameEnded = p;
        view.currentPlayer = null;
        break;
      }
      case "llm_call": {
        const spend = view.spend[p.player as Color];
        const tokens = (p.tokens ?? {}) as Record<string, number>;
        spend.input += tokens.input ?? 0;
        spend.output += tokens.output ?? 0;
        spend.cacheRead += tokens.cache_read ?? 0;
        spend.cacheWrite += tokens.cache_write ?? 0;
        spend.calls += 1;
        break;
      }
      case "message_sent": {
        const to = p.to as Color | null;
        feed(event, to === null ? "table note" : "message", String(p.text ?? ""),
          to === null ? "to everyone" : `to ${to}`);
        break;
      }
      case "agent_reasoning": {
        feed(event, "reasoning", String(p.text ?? ""));
        break;
      }
      case "memory_write": {
        feed(event, "memory", String(p.text ?? ""),
          `${p.kind}${p.about ? ` · about ${p.about}` : ""}`);
        break;
      }
      case "context_compacted": {
        feed(event, "compaction", String(p.summary ?? ""),
          `${p.tokens_before} → ${p.tokens_after} tokens`);
        break;
      }
      case "guardrail_triggered": {
        feed(event, "guardrail", String(p.detail ?? p.rule ?? ""), String(p.action ?? ""));
        break;
      }
    }
    view.eventsApplied += 1;
  }
  return view;
}

export function tokensHome(view: GameView, color: Color): number {
  return view.tokens[color].filter((pos) => pos === 56).length;
}

export function progress(view: GameView, color: Color): number {
  return view.tokens[color].reduce((sum, pos) => sum + (pos === -1 ? 0 : pos + 1), 0);
}

/** Live standings, same ordering rule as the engine: finishers first in
 *  finishing order, the rest by tokens home then progress, ties stable. */
export function standings(view: GameView): Color[] {
  const rest = COLORS.filter((c) => !view.finished.includes(c));
  const keyed = rest.map((c, i) => ({ c, i, home: tokensHome(view, c), prog: progress(view, c) }));
  keyed.sort((a, b) => b.home - a.home || b.prog - a.prog || a.i - b.i);
  return [...view.finished, ...keyed.map((k) => k.c)];
}
