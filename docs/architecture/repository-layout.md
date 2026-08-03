# Repository Layout

Single repository (see [ADR-0001](../decisions/adr-0001-monorepo.md)). Three stacks that must stay in lockstep are far easier to keep honest in one tree than across six.

```
llmeval/
├── README.md
├── CLAUDE.md                     # guidance for Claude Code sessions
├── justfile                      # cross-stack task runner (see environment-strategy.md)
├── package.json                  # repo tooling ONLY (the mermaid parser) — not the UI
├── .env.example                  # every required secret, by name
│
├── docs/
│   ├── vision.md
│   ├── open-questions.md
│   ├── roughidea.txt             # the original brief; kept for provenance
│   ├── architecture/
│   ├── decisions/                # ADRs
│   ├── topics/
│   └── projects/<project>/       # per-project design docs
│
├── shared/                       # stack-neutral, language-neutral contracts
│   ├── schemas/                  # JSON Schema: events, transcripts, eval results
│   ├── prompts/
│   │   └── ludo/
│   │       ├── manifest.yaml     # what to load, and each file's variables
│   │       ├── system/           # stable within a game  → prompt-cacheable
│   │       └── turn/             # rebuilt every turn     → never cached
│   ├── conformance/              # golden vectors both engines must reproduce
│   └── models.yaml               # seat → provider/model/route, plus profiles
│
├── projects/
│   └── ludo/
│       ├── engine-python/        # shared by BOTH Python stacks
│       ├── engine-java/
│       ├── stack-strands/
│       ├── stack-langgraph/
│       ├── stack-springai/
│       ├── eval/                 # LLM-as-judge + deterministic scoring
│       ├── ui/
│       └── games/                # recorded event streams (sample matches)
│
├── scripts/
│   ├── check_docs.py             # links, anchors, mermaid structure — Rule #1
│   ├── check_mermaid.mjs         # parses diagrams with real mermaid; needs node
│   └── check_prompts.py          # shared/ invariants — parity depends on these
│
├── platform/                     # code that graduated out of a project
│   └── (empty for now)
│
└── infra/                        # AWS IaC, introduced when first deployed
```

## Conventions

**`shared/` is a contract, not a library.** It holds schemas, prompts, and test vectors — data, not executable code. Anything in here that changes is a coordinated change across all three stacks. Nothing in `shared/` imports from `projects/`.

That constraint is why prompt templates use literal `{{name}}` substitution with **no conditionals or loops**: template logic would have to be implemented twice, in two languages, and the places they disagreed would be invisible parity breaks. If a section needs logic, the stack renders it and passes the result in as one variable. See [shared/prompts/README.md](../../shared/prompts/README.md); [`check_prompts.py`](../../scripts/check_prompts.py) enforces it.

**Stack directories are self-contained and independently runnable.** `stack-strands/` must build, test, and run a game without `stack-langgraph/` present. Each owns its dependency manifest and lockfile. They never import each other — a shortcut between stacks would destroy the comparison.

**Engines are libraries with no LLM dependency.** `engine-python/` and `engine-java/` know nothing about agents, prompts, or providers. They should be testable at speed with zero API calls, and a human-vs-random-bot game should be runnable straight from the engine. If an engine ever needs to import an LLM SDK, something has gone wrong.

**`platform/` starts empty on purpose.** Cross-project abstractions get *extracted* after a second project proves they generalise, not designed upfront. Premature shared infrastructure is how teaching repos become unreadable.

**Recorded games are committed.** A few representative matches live in `projects/ludo/games/` so the UI, the eval harness, and new readers all work offline with no API keys. This is what makes the repo explorable for someone who just wants to look around.

**Naming.** Directories `kebab-case`. Python packages `snake_case`, Java packages `com.llmeval.<project>.<stack>`. Stack directories are always `stack-<name>`, engine directories `engine-<language>` — the prefix makes the layout scannable and greppable.

## Per-project structure

Every project under `projects/` follows the same shape: `engine-*`, `stack-*`, `eval/`, `ui/`, `games/`. Consistency across projects matters more than a bespoke fit for each one — a reader who has understood LUDO should be able to navigate project two without re-learning anything.

## Related

- [Architecture overview](overview.md) — why the layers are split this way
- [Environment strategy](environment-strategy.md) — how these directories build without conflicting
