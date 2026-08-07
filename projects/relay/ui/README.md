# RELAY transcript player

Watch a race. Four lanes, a shared pool draining, and a difficulty key that stays shut until the finish.

React + Vite, consuming [the shared event schema](../../../shared/schemas/relay-event.schema.json) and nothing else ([ADR-0003](../../../docs/decisions/adr-0003-shared-event-stream.md)). No engine import, no stack import, no keys.

```bash
npm ci --prefix projects/relay/ui
```

```bash
npm test --prefix projects/relay/ui
```

```bash
npm run dev --prefix projects/relay/ui
```

## What it shows

**The commons**, as a meter. One pool, four lanes, and watching it drain is the point — this is the only panel in any of this repo's UIs where one player's move visibly costs the others.

**The track**, one row per lane, a pip per stage. Cleared pips fill in the lane's colour; the current pip is outlined.

**The race feed**, with three things kept apart on purpose: what the engine adjudicated, what a runner *said*, and what the guardrail blocked. A note is rendered as speech, never as state.

**The key**, sealed.

## The seal is a UI rule, and it is tested

The engine keeps tiers away from runners *by type* — `PublicStage` has no such field. That protects the engine. It does nothing for the UI, which holds the whole transcript, `game_ended` included, and could render every tier on turn one.

So `replay(events, upTo)` only populates `trackKey` once `game_ended` has actually been played, and [`tests/seal.test.ts`](tests/seal.test.ts) walks **every sequence number of every committed race** asserting it is absent before then. A viewer who could see the tiers would know something every runner was forbidden to know, and the replay would stop being an honest account of the race.

## ADR-0007's three rules, fourth application

1. The suite walks `projects/relay/games/` and renders whatever is there.
2. Adding a stack's fixture requires **no UI source change** — three stacks' transcripts landed and the suite grew by itself.
3. Everything runs offline against committed files.

39 tests.

## The scoreboard shows two rulers

The eval panel renders each race's committed `.eval.json`, and it shows **precision** and **fit** side by side deliberately:

- *precision* — did that unit go on an objectively hard stage?
- *fit* — did it go on a family this lane is actually bad at?

They come apart, and the winning lane in the committed races scores 0% on the first and 100% on the second. A panel showing only precision would call the winning strategy a mistake.

## Related

- [Evaluation](../../../docs/projects/relay/evaluation.md) · [Game rules](../../../docs/projects/relay/game-rules.md)
- [ADR-0007](../../../docs/decisions/adr-0007-ui-alongside-first-stack.md) — why the UI is built against fixtures
