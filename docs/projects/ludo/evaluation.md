# LUDO — Evaluation

Most of our games will not finish. The turn cap will hit first, and we still need to say who played best. That constraint is what makes this project a real evaluation exercise rather than a scoreboard.

Two layers do the work: **deterministic scoring** (cheap, objective, reproducible) and an **LLM judge** (expensive, subjective, catches what numbers can't). Neither alone is enough — and understanding *why* is one of the things this project teaches.

## Layer 1 — deterministic scoring

Computed from the event stream with no model calls. Free, instant, identical every replay.

**Position** — the state of the board when the game ended:

| Signal | Weight |
|---|---|
| Tokens home | Dominant |
| Total token progress (sum of steps travelled) | Secondary |
| Tokens still in base | Penalty |

**Play record** — what happened along the way: captures made, captures suffered, blocks established, home entries, turns forfeited (illegal moves, timeouts).

**Efficiency** — progress per turn, progress per 1K tokens spent, cost per unit of progress. This is where a stack that burns 5× the tokens for the same board position gets caught.

Deterministic scoring is the **primary** signal. A finished game has a winner and the judge does not get to overrule it.

## Layer 2 — LLM as judge

The numbers can't see whether an agent played *well*. A player can be ahead on luck alone, or behind after a brilliant coalition that just didn't pay off in time. The judge reads the transcript — moves, reasoning, messages, memory — and scores what the metrics miss:

| Dimension | Question |
|---|---|
| **Decision quality** | Given the legal moves available, were the choices sound? |
| **Strategic coherence** | Was there a plan across turns, or turn-by-turn improvisation? |
| **Negotiation** | Did alliances actually achieve anything for this agent? |
| **Trust calibration** | Did it detect deception? Was it repeatedly fooled by the same opponent? |
| **Timing of betrayal** | Only one player wins, so every alliance ends. Was the break well-timed or panicked? |
| **Reasoning integrity** | Does the stated reasoning match the action taken? |
| **Adaptability** | Did it respond to a changed board, or keep running a dead plan? |

Each dimension is scored against a rubric with explicit anchors and must cite specific turns. **An unsourced judgement is discarded** — the same rule as the [capability matrix](../../architecture/stack-comparison.md).

Crucially, the judge scores **decisions against the information available at the time**, not against outcomes. Dice mean a good decision can lose. Rewarding outcomes over process would just be measuring luck.

## Judge bias — and what we do about it

An LLM judge is a measuring instrument with known defects. Naming and mitigating them is core teaching content here:

| Bias | Mitigation |
|---|---|
| **Self-preference** — favours output from its own model family | Judge model is from a family not playing; also cross-judged by a second family |
| **Position bias** — favours whoever is presented first | Agent order randomised per judging run |
| **Verbosity bias** — mistakes length for quality | Rubric scores substance; reasoning length reported separately as its own metric |
| **Identity leakage** — knowing "this is Claude" colours the score | Agents anonymised: colours and model identities stripped, relabelled per run |
| **Outcome bias** — rationalises the winner as the best player | Judge scores decisions blind to final standing where feasible |
| **Instability** — same input, different scores | Multiple runs; report the spread, not just the mean |

Anonymisation is the important one. The judge sees four anonymous players and a transcript. It does not know which agent came through Bedrock, which model was behind it, or who won.

## Evaluating the judge

An eval you haven't validated is a number with a false sense of authority. Three checks:

1. **Agreement on decided games.** On games that *do* finish, does the judge's ranking correlate with the actual result? Systematic disagreement means the rubric is wrong.
2. **Inter-judge agreement.** Two judge models on the same transcript. Low agreement means the rubric is too vague to be reproducible.
3. **Human spot-checks.** A small hand-labelled set. Slow, and the only real ground truth available.

Results go in the eval report alongside the scores. A judge with poor validation numbers is reported as such rather than quietly trusted.

## Comparing the three stacks

Two separate questions, easy to conflate:

**Which agent played best?** Compare agents within one game. Model and access route are the variables.

**Which stack ran the game best?** Compare the *same matchup* across all three implementations — same seed, same models, same prompts. Differences here are attributable to the framework: token overhead, latency, cache hit rate, forfeits from timeouts or malformed tool calls, and whether the harness (memory, compaction) actually held up under pressure.

The second is the repo's real question. The first is what makes it fun to watch.

## Reporting

Every game produces a machine-readable eval result validated against a schema in `shared/schemas/`, plus a human-readable summary rendered in the UI: final standing, decisive moments, alliance history, judge scores with citations, and full cost and token accounting.

Because evaluation runs entirely off recorded event streams, **rubrics can be revised and re-run against past games for free** (aside from judge calls). Games are recorded once; evals are cheap to iterate. That separation is deliberate, and it's the single most useful habit to carry into other projects.

## Status

Built, in [`projects/ludo/eval`](../../../projects/ludo/eval/README.md) — a standalone consumer of the event stream with no engine, stack, or SDK imports (the no-arrow rule held). **Layer 1 runs in full** on every committed game, and its fold self-verifies against `game_ended.standings` — which is how we learned the engine does not count three-sixes as a forfeited turn. **Layer 2's machinery is built and tested through scripted judges**: anonymisation (colour words inside message text included), per-run label shuffles, citation enforcement with discards counted, mean-and-spread aggregation, and outcome agreement via Kendall's tau on finished games. The rubric lives in [`shared/prompts/ludo/judge/scoring.md`](../../../shared/prompts/ludo/judge/scoring.md) and its hash rides every judged result. The position weights in `scoring.py` are provisional, like every number in `models.yaml`. The UI renders each committed game's eval result below the player (`games/<name>.eval.json` — the pipeline's second artifact), with the judge section honestly pending. Still waiting: the judge model id (the live OpenAI caller fails loudly until it lands) and the validation runs that need live games.

## Related

- [Brief](brief.md) · [Agent design](agent-design.md) · [Game rules](game-rules.md)
- [Stack capability matrix](../../architecture/stack-comparison.md)
