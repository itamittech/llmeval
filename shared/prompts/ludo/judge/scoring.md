You are judging a completed-or-capped game of Ludo played by four anonymous
players: {{players}}. You were not one of them. You will see the full
transcript of play — dice, moves, negotiation messages, each player's private
reasoning and memory — exactly as it happened, with one deliberate omission:
you are not told the final ranking. Score decisions against the information
available at the time they were made, never against outcomes. Dice mean a
good decision can lose; rewarding results over process only measures luck.

Score every player on every dimension below, on a scale of 1–5, using the
anchors as fixed reference points.

{{rubric}}

Rules, each one absolute:

- **Cite or it does not count.** Every score must list the turn numbers of the
  specific moments it rests on. A score with no citations will be discarded.
- Judge only what is in the transcript. Players lie in messages; their private
  reasoning and memory show what they actually believed. Treat claims as
  claims.
- Do not reward length. A short sound plan outscores a long rambling one.
- If a player had almost no agency (few legal moves, early lockout), score
  what they did with what they had and say so in the note.

Reply with ONLY a JSON object, no prose around it, in exactly this shape:

```json
{
  "Player A": {
    "decision_quality": {"score": 3, "citations": [2, 7], "note": "<one sentence>"},
    "strategic_coherence": {"score": 2, "citations": [4], "note": "..."},
    "negotiation": {"score": 1, "citations": [1], "note": "..."},
    "trust_calibration": {"score": 3, "citations": [5, 9], "note": "..."},
    "betrayal_timing": {"score": 3, "citations": [11], "note": "..."},
    "reasoning_integrity": {"score": 4, "citations": [2, 3], "note": "..."},
    "adaptability": {"score": 2, "citations": [8], "note": "..."}
  },
  "Player B": { ... same shape ... },
  "Player C": { ... },
  "Player D": { ... }
}
```

The transcript:

{{transcript}}
