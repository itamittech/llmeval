# alibi-ui

The ALIBI transcript player: React + Vite, static, offline — it consumes the
committed fixtures in [`../games/`](../games/) and their `.eval.json` results,
and nothing else ([ADR-0003](../../../docs/decisions/adr-0003-shared-event-stream.md)).

ADR-0007's rules, third application, enforced by the same three test shapes as
LUDO's suite:

- **every fixture renders** with zero source changes — adding a stack means
  committing its transcript, nothing more;
- **`stack` is displayed, never branched on** — mutate the field, markup
  identical minus the label;
- **claims render as claims** — table notes, reasoning, notebook lines all
  carry the `.claim` style, the visual half of "agent claims are not facts".

Plus the rule only ALIBI needs: **the solution and the red herrings stay
sealed** until the transcript's own `game_ended` — scrub the timeline and the
mystery replays honestly, then the archive panel marks which documents lied.

## Run it

```bash
npm ci --prefix projects/alibi/ui
```

```bash
npm test --prefix projects/alibi/ui
```

```bash
npm run dev --prefix projects/alibi/ui
```
