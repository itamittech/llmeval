# LUDO Transcript Player

A static React + Vite app that replays recorded game transcripts — **the event stream is its only input** ([ADR-0003](../../../docs/decisions/adr-0003-shared-event-stream.md)). No backend, no API keys, works offline: both committed fixtures are bundled into the build.

Built to completion alongside the first stack, on purpose and by rule — [ADR-0007](../../../docs/decisions/adr-0007-ui-alongside-first-stack.md) explains why the UI exists *before* stacks two and three, and this README explains how its rules are enforced rather than intended.

## Run it

```bash
npm ci --prefix projects/ludo/ui
```

```bash
npm run dev --prefix projects/ludo/ui
```

```bash
npm test --prefix projects/ludo/ui
```

```bash
npm run build --prefix projects/ludo/ui
```

The build in `dist/` is fully static — open it from a file path or any web server.

## The rules this app is held to

All four of [ADR-0007](../../../docs/decisions/adr-0007-ui-alongside-first-stack.md)'s guarantees are tests, not intentions, and they run in CI:

| Rule | Enforced by |
|---|---|
| Every transcript in [`projects/ludo/games/`](../games/) renders, offline | [`tests/fixtures.test.tsx`](tests/fixtures.test.tsx) walks the directory — a new stack's transcript is picked up with **zero UI changes** |
| The zero-agent-event fixture is first-class | the same test asserts the engine-only game renders with the agent panels *honestly empty* |
| `stack` is displayed, **never branched on** | [`tests/stack-independence.test.tsx`](tests/stack-independence.test.tsx) re-renders with `game_started.stack` mutated and diffs the markup — identical apart from the label, or the build fails |
| The replay is faithful to the rules | [`tests/projector.test.ts`](tests/projector.test.ts) replays whole games and compares projected standings, capture counts, and forfeits against the engine's own `game_ended` payload |

One more that ADR-0007 didn't have to ask for: [`tests/geometry.test.ts`](tests/geometry.test.ts) checks the hand-drawn board mapping against **every `from_square`/`to_square` the fixtures record** — the engine has already computed the absolute square for thousands of real moves, so the grid is verified against the engine rather than trusted.

## The eval report

Below the player, the app renders the pipeline's *second* artifact: each bundled game ships with its committed eval result (`games/<name>.eval.json`, produced by [the eval harness](../eval/README.md) and schema-validated before commit). [`src/Eval.tsx`](src/Eval.tsx) is pure like `Player` — parsed result in, markup out — and held to the same rules by [`tests/eval.test.tsx`](tests/eval.test.tsx): every committed result in `games/` must render (the suite grows when a result lands, zero source changes), `stack` is displayed never branched on, and rank is shown verbatim from the result — which the eval harness in turn guarantees is the engine's own standings. No judge has scored a committed game yet, and the panel says so honestly instead of rendering an empty table; judge scores land in the same panel when the judge model id does. An uploaded transcript has no result and shows no panel — run `just score` on it to make one.

## How it works

| Module | Job |
|---|---|
| [`src/types.ts`](src/types.ts) | The event shapes, mirroring [`shared/schemas/event.schema.json`](../../../shared/schemas/event.schema.json) |
| [`src/projector.ts`](src/projector.ts) | Folds events into a view: token positions, stats, spend, the agent feed. Pure — same events, same view |
| [`src/geometry.ts`](src/geometry.ts) | The engine's coordinates on a 15×15 grid: 52 circuit cells, home columns, bases |
| [`src/Board.tsx`](src/Board.tsx) | The board as SVG, drawn from the projected view |
| [`src/Panels.tsx`](src/Panels.tsx) | Standings, per-agent token spend, and the feed |
| [`src/App.tsx`](src/App.tsx) | `Player` (pure: events + position → page) wrapped in loading and playback controls |

**The one genuinely subtle piece** lives in the projector: on three consecutive sixes the engine *cancels the whole turn*, silently restoring its snapshot — but the transcript still records the moves that were then reverted. The projector keeps a per-turn undo journal and rolls it back when `turn_ended` says `three_sixes`, captures included. A naive fold leaves phantom tokens, which is why the full-replay-vs-`game_ended` test exists.

**Claims, not facts.** The feed shows what players *said* — messages, table notes, reasoning, memory. Agents lie deliberately; nothing a player says is ever folded into board state, and the panel says so on screen.

## Deliberately not here yet

Live streaming (watching a game as it runs) is deferred by the [answered UI question](../../../docs/open-questions.md) — transcript replay first. When it comes, it consumes the same events over a socket instead of a file, and nothing in the projector changes.

## Related

- [ADR-0007](../../../docs/decisions/adr-0007-ui-alongside-first-stack.md) — why the UI is built now, and the fixture-set rules
- [ADR-0003](../../../docs/decisions/adr-0003-shared-event-stream.md) — why the event stream is the only integration contract
- [shared/schemas](../../../shared/schemas/README.md) — the events this app consumes
