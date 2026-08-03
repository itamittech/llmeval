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

#### How the teaching is done

The techniques below are not style preferences — each one exists because of how memory actually works. Explanations are forgotten; *answers you committed to* and *problems you felt* are not. Applied throughout [learning/](../learning/) and the design docs, and expected of new material:

- **Problem before solution.** Show the itch before the scratch. A concept lands only when it answers a question the reader already has — which is why [class-design §7](projects/ludo/class-design.md#7-design-patterns-from-the-problem-up) names each pattern *last*, after the problem that forces it.
- **Predict, then verify.** Where a doc says **Before you scroll** — stop and commit to an answer. Being asked *before* being told is what turns reading into learning, and a wrong guess corrected is the strongest memory hook there is.
- **Name the wrong model, then kill it.** A misconception survives silent correction; it dies when stated. Hence the "NOT what the engine does" blocks, and findings that keep the earlier wrong claim visible.
- **One handle per concept.** A phrase that fits in your head outlives any paragraph: *the reset is the delivery* · *gaps are results* · *claims are claims, not facts* · *the engine judges, the harness narrates*.
- **Three encodings.** Prose, a picture or table, and something runnable. Never trust an explanation you can't execute — every learning doc ends with a command.
- **Anchor in what the reader already knows.** Java is taught against Python, `uv` against Maven, the agent loop against the engine's turn loop. New ideas stick to old ones, not to nothing.
- **Close with retrieval.** "Check yourself" questions at the end, answers as links back in. Rereading *feels* like learning; recalling *is* learning.
- **Let concepts return in new clothes.** Hashability appears as a dataclass footnote, then as `set(moves)`, then as Java's `hashCode` contract. Meeting an idea three times in three contexts beats one thorough lecture.

The boundary still holds: **verbosity is not pedagogy.** Every one of these techniques is a few lines. A doc that doubles in length to "teach better" has done the opposite.

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
