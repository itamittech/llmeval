# Learning from RELAY

The second **topic** folder. [learning/alibi](../alibi/) taught retrieval and agent-as-tool; this one teaches the two hard things project three exists for — **running a model at the edge** and **deciding when to escalate** — plus the discipline building it forced: measuring a decision, not just an outcome.

Everything here is checked against the built [RELAY code](../../projects/relay/) and its committed fixtures. Like every framework and topic folder, there is **no examples directory**: these docs teach against the project's own tests and CLIs, which run in the project venvs.

## Read in this order

| Doc | Question it answers |
|---|---|
| [00 — knowing what you don't know](00-knowing-what-you-dont-know.md) | Why "should I escalate?" is a real decision and not a lookup — and why the bench found that knowing your limits *loses* if you are bad enough |
| [01 — fallback is not escalation](01-fallback-is-not-escalation.md) | Three frameworks, three fallback stories, and why none of them fits: every `with_fallbacks` in the world triggers on an exception |
| [02 — the seal](02-the-seal.md) | How to hide something from an agent when your own code holds it: a type, a schema, a checker, and a UI test |
| [03 — measuring a decision](03-measuring-a-decision.md) | Precision, recall, and fit — and what happened when the winning lane scored zero on precision |

The design these docs walk is in [engine-design.md](../../docs/projects/relay/engine-design.md) and the [harness contract](../../docs/projects/relay/harness-contract.md); the findings they end at live in [the matrix's third act](../../docs/architecture/stack-comparison.md#relay-the-third-act).

## The handles, up front

One phrase per concept, expanded in the docs:

- **Escalation is a judgement, not a failure** — every framework's fallback primitive fires on an error; choosing a bigger model on purpose is your code.
- **Hard is relative to the runner** — a tier-1 puzzle is impossible for a model that cannot do that kind of puzzle at all, and the ladder does not know that.
- **The seal is a type** — you cannot leak a field that the object handed out does not have.
- **A commons makes cost adversarial** — one shared pool turns "what does this cost?" into "what does this cost *them*?", which is what makes it a game.

## Before you scroll

Three predictions. Write them down; the docs tell you which held.

1. Four runners of equal skill, one of whom always knows when a stage is beyond it. How much more often does it win than the one guessing at random — 2×, 4×, never?
2. Two frameworks, one carrying an unbounded conversation and one a bounded window. How far apart are their token counts?
3. A runner escalates every stage it cannot personally do, and none of them happens to be top-tier. What is its escalation precision?

## Related

- [ADR-0011](../../docs/decisions/adr-0011-project-three-relay.md) — why this game, and the bench result nobody predicted
- [Game rules](../../docs/projects/relay/game-rules.md) — normative, with the numbers
- [learning/alibi](../alibi/) — the first topic folder
