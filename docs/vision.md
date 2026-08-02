# Vision

## The problem this repo exists to solve

LLM engineering content usually comes in two unhelpful shapes: a toy notebook that ignores everything hard about production, or a framework tutorial that teaches you one library's worldview without ever telling you which parts were fundamental.

We want a third shape: **a real, non-trivial problem, solved three different ways, with the differences made visible.**

## Three commitments

### 1. Gamification is the constant

Every project is a game. Games give us:

- **A natural fitness function.** Who won? By how much? That's an eval target you don't have to invent.
- **Adversarial pressure.** Agents competing produce more interesting behaviour than agents answering questions.
- **A reason to keep reading.** Nobody finishes a tutorial about document summarisation. People finish a story about four AIs betraying each other over a board game.

### 2. Teaching is a first-class deliverable

Working code that nobody understands is a failed deliverable here. That means:

- **Concise, not verbose.** Over-commented code teaches worse than well-named code. Explain *why*, not *what* — the *what* should be legible from the code itself.
- **The docs are part of the product.** Architecture is documented so a reader can understand the system without reading every file.
- **The UI teaches too.** It doesn't just show the game — it explains the architecture behind it and flags where frameworks fell short.
- **Production practices apply.** These are experiments, but they are not throwaways. Someone should be able to lift a pattern from here into real work.

### 3. The comparison must be honest

A three-way comparison is only worth anything if the three implementations differ *only* in the thing being compared. If our LangGraph version loses because we wrote a worse dice roller, we've learned nothing.

This is why the architecture is built around **controlling everything except the agent framework** — see [architecture/overview.md](architecture/overview.md). It's the single most important constraint in the repo.

It also means **negative results are results.** If Spring AI has no equivalent of a feature the Python stacks get for free, we don't quietly hand-roll a substitute and pretend parity. We build the workaround, measure what it cost us, and write it down in the [capability matrix](architecture/stack-comparison.md).

## What "fun" is allowed to override

Nothing about correctness or clarity. But when there's a choice between the boring-correct option and the interesting-correct option, take the interesting one. Agents that can lie to each other are more instructive *and* more fun than agents that can't.

## Audience

Someone who can already write code, has used an LLM API at least once, and now wants to know what changes when you go from one API call to a system of agents with memory, budgets, guardrails, and evaluation. We do not assume they know AWS, any of the three frameworks, or Ludo.

## Non-goals

- **Not a benchmark suite.** We're not producing leaderboard numbers for models. The evals exist to make the *games* judgeable and to teach eval technique.
- **Not a framework endorsement.** The goal is an informed reader, not a winner.
- **Not exhaustive per project.** No single project covers all 17 [topics](topics/roadmap.md). Each picks a coherent subset.
- **Not a playable product.** Humans watch; agents play.
