# Shared Schemas

The integration contract between the three stack implementations, the UI, and the evaluation harness ([ADR-0003](../../docs/decisions/adr-0003-shared-event-stream.md)).

| File | Purpose |
|---|---|
| [`event.schema.json`](event.schema.json) | One LUDO transcript event. JSON Schema 2020-12. |

## Transcript format

A game is a **JSON Lines** file — one event object per line, ordered by `seq`:

```jsonl
{"seq":0,"turn":0,"type":"game_started","payload":{...}}
{"seq":1,"turn":1,"type":"turn_started","payload":{"player":"red"}}
{"seq":2,"turn":1,"type":"dice_rolled","payload":{"player":"red","value":6,"roll_index":0}}
```

JSONL rather than a single JSON array so transcripts can be streamed as a game plays, appended to without a rewrite, and read line-by-line without loading the whole file.

## Who emits what

**Engine events** — `game_started`, `turn_started`, `dice_rolled`, `move_made`, `token_captured`, `token_home`, `extra_roll_granted`, `illegal_move_rejected`, `turn_ended`, `player_finished`, `game_ended`.

Emitted by `engine-python` and `engine-java`. Deterministic: same seed plus same decisions produces a byte-identical sequence.

**Agent events** — `agent_reasoning`, `message_sent`, `memory_write`, `context_compacted`, `llm_call`, `guardrail_triggered`.

Emitted by the stack implementations. Non-deterministic by nature.

The split matters: an engine-only run (random bots, no models) produces a valid transcript containing no agent events at all. That's what makes fast, free rule testing and turn-cap calibration possible.

## Rules

**No timestamps from the engine.** Two runs with the same seed and decisions must diff cleanly, and wall-clock time would defeat that. The `ts` field exists for agent-layer events where latency is genuinely interesting.

**Coordinates are colour-relative.** A token's `position` is `-1` (base), `0`–`50` (circuit, measured from that colour's own start square), `51`–`55` (home column), `56` (home). Absolute board squares (`0`–`51`) appear only in `*_square` fields, for capture logic and rendering. This keeps movement identical for all four colours — see [game-rules.md](../../docs/projects/ludo/game-rules.md).

**Agent claims are not facts.** `message_sent` content may be deliberately false. Nothing downstream — UI, summaries, eval — may treat it as ground truth.

## Changing the schema

Adding an event type or an optional field is cheap. **Changing or removing anything is a breaking change** that all three stacks must land together, and it invalidates previously recorded transcripts.

Before changing an existing event, check whether adding one solves the problem instead.

## Validating

```bash
uv run --directory projects/ludo/engine-python python -m ludo_engine.cli validate <transcript.jsonl>
```

Transcript validation runs in CI against every committed sample game.
