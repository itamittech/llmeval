# Shared Schemas

The integration contract between the three stack implementations, the UI, and the evaluation harness ([ADR-0003](../../docs/decisions/adr-0003-shared-event-stream.md)).

| File | Purpose |
|---|---|
| [`event.schema.json`](event.schema.json) | One LUDO transcript event. JSON Schema 2020-12. (Predates project two, so the filename carries no project prefix — kept, because renaming a published contract breaks its consumers.) |
| [`alibi-event.schema.json`](alibi-event.schema.json) | One ALIBI transcript event. Same discipline, second game: deduction events (`suggestion_made`, `refutation_made`, `belief_declared`…) replace board events, and the element enums are normative — they mirror [game-rules.md](../../docs/projects/alibi/game-rules.md), and renaming one regenerates conformance vectors. |
| [`eval-result.schema.json`](eval-result.schema.json) | One LUDO game's evaluation: deterministic scores always, judge scores when a judge ran. Produced by [`projects/ludo/eval`](../../projects/ludo/eval/README.md), which validates every result against this before emitting it. |

## Transcript format

A game is a **JSON Lines** file — one event object per line, ordered by `seq`:

```jsonl
{"seq":0,"turn":0,"type":"game_started","payload":{...}}
{"seq":1,"turn":1,"type":"turn_started","payload":{"player":"red"}}
{"seq":2,"turn":1,"type":"dice_rolled","payload":{"player":"red","value":6,"roll_index":0}}
```

JSONL rather than a single JSON array so transcripts can be streamed as a game plays, appended to without a rewrite, and read line-by-line without loading the whole file.

## Who emits what

**LUDO engine events** — `game_started`, `turn_started`, `dice_rolled`, `move_made`, `token_captured`, `token_home`, `extra_roll_granted`, `illegal_move_rejected`, `turn_ended`, `player_finished`, `game_ended`.

**ALIBI engine events** — `game_started`, `case_dealt`, `archive_generated`, `turn_started`, `archive_searched`, `suggestion_made`, `refutation_made`, `accusation_made`, `detective_eliminated`, `belief_declared`, `invalid_action`, `turn_ended`, `game_ended`. The archive rides *in* the transcript (`archive_generated`), which is what keeps ALIBI transcripts self-contained for the UI and eval; which documents were red herrings is revealed only in `game_ended`.

Emitted by each project's `engine-python` and `engine-java`. Deterministic: same seed plus same decisions produces a byte-identical sequence.

**Agent events** (both games) — `agent_reasoning`, `memory_write`, `context_compacted`, `llm_call`, `guardrail_triggered`; LUDO adds `message_sent` (ALIBI v1 has no free message channel — its only table talk is the `note` riding on `suggestion_made`, per answered question 22).

Emitted by the stack implementations. Non-deterministic by nature.

The split matters: an engine-only run (bots, no models) produces a valid transcript containing no agent events at all. That's what makes fast, free rule testing and turn-cap calibration possible — in both games.

## Rules

**No timestamps from the engine.** Two runs with the same seed and decisions must diff cleanly, and wall-clock time would defeat that. The `ts` field exists for agent-layer events where latency is genuinely interesting.

**Coordinates are colour-relative.** A token's `position` is `-1` (base), `0`–`50` (circuit, measured from that colour's own start square), `51`–`55` (home column), `56` (home). Absolute board squares (`0`–`51`) appear only in `*_square` fields, for capture logic and rendering. This keeps movement identical for all four colours — see [game-rules.md](../../docs/projects/ludo/game-rules.md).

**Agent claims are not facts.** LUDO's `message_sent` content and ALIBI's suggestion `note` may be deliberately false. Nothing downstream — UI, summaries, eval — may treat them as ground truth.

**In ALIBI, the table is facts and the archive is claims.** `refutation_made` is engine-mediated — the shown exhibit really was shown. `archive_generated` documents are in-fiction testimony, and some contradict the truth by design. The transcript carries both; only one may be trusted, and `game_ended.red_herrings` reveals which documents lied.

**A colour is not a stable identity.** The seat→colour mapping rotates between games ([ADR-0006](../../docs/decisions/adr-0006-seat-rotation.md)). `game_started.players[]` carries both `color` and `seat` for that game; anything comparing models across transcripts must read it rather than assume red is who red was last time. A UI that colour-codes by model and skips this produces a chart that looks fine and is false.

**Every game records what produced it.** `game_started` carries `profile` (which model tier and budget, from `shared/models.yaml`) and `prompt_set` (version plus hash). Prompts and models change; without these, two transcripts are silently incomparable. Both are absent on engine-only runs, which send no prompts at all.

## Changing the schema

Adding an event type or an optional field is cheap. **Changing or removing anything is a breaking change** that all three stacks must land together, and it invalidates previously recorded transcripts.

Before changing an existing event, check whether adding one solves the problem instead.

## Validating

```bash
uv run --directory projects/ludo/engine-python python -m ludo_engine.cli validate <transcript.jsonl>
```

Transcript validation runs in CI against every committed sample game.
