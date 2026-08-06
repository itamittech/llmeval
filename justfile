# Cross-stack task runner. One set of verbs for four toolchains.
#
# `just` is used instead of `make` because this repo is developed on Windows as
# well as Unix. Install: winget install Casey.Just | scoop install just |
# brew install just | cargo install just
#
# Every command a contributor needs belongs here. If a workflow only lives in
# someone's shell history, it isn't documented.

ENGINE_PY := "projects/ludo/engine-python"
ENGINE_JAVA := "projects/ludo/engine-java"
STACK_STRANDS := "projects/ludo/stack-strands"
STACK_LANGGRAPH := "projects/ludo/stack-langgraph"
STACK_SPRINGAI := "projects/ludo/stack-springai"
EVAL := "projects/ludo/eval"
UI := "projects/ludo/ui"
GAMES := "projects/ludo/games"

default:
    @just --list

# Install all toolchains and dependencies.
setup:
    uv sync --directory {{ENGINE_PY}}
    uv sync --directory {{STACK_STRANDS}}
    uv sync --directory {{STACK_LANGGRAPH}}
    uv sync --directory {{EVAL}}
    npm ci
    npm ci --prefix {{UI}}
    cd {{ENGINE_JAVA}} && ./mvnw -q -B install -DskipTests
    cd {{STACK_SPRINGAI}} && ./mvnw -q -B dependency:resolve

# Run every test suite: engines, all three stacks, eval, UI.
test: test-engine-py test-engine-java test-strands test-langgraph test-springai test-eval test-ui

test-engine-py:
    uv run --directory {{ENGINE_PY}} pytest

test-engine-java:
    cd {{ENGINE_JAVA}} && ./mvnw -q -B test

test-strands:
    uv run --directory {{STACK_STRANDS}} pytest

test-langgraph:
    uv run --directory {{STACK_LANGGRAPH}} pytest

# Needs the engine installed locally once: `just setup` (or the install line in it).
test-springai:
    cd {{STACK_SPRINGAI}} && ./mvnw -q -B test

test-eval:
    uv run --directory {{EVAL}} pytest

test-ui:
    npm test --prefix {{UI}}

# BOTH engines against the shared conformance vectors (ADR-0002). Running only
# one defeats the point — the vectors exist to catch them disagreeing.
conformance: conformance-py conformance-java

conformance-py:
    uv run --directory {{ENGINE_PY}} python -m ludo_engine.cli conformance --check

conformance-java:
    cd {{ENGINE_JAVA}} && ./mvnw -q -B exec:java -Dexec.args="conformance --check"

# Regenerate vectors. Only after a DELIBERATE rule change.
conformance-generate:
    uv run --directory {{ENGINE_PY}} python -m ludo_engine.cli conformance --generate

# Regenerate every stack's committed fixture — byte-identical unless behaviour
# changed, and if it changed, the diff is the review.
fixtures:
    uv run --directory {{STACK_STRANDS}} python -m ludo_strands.demo ../games/scripted-strands-seed7.jsonl
    uv run --directory {{STACK_LANGGRAPH}} python -m ludo_langgraph.demo ../games/scripted-langgraph-seed7.jsonl
    cd {{STACK_SPRINGAI}} && ./mvnw -q -B compile exec:java -Dexec.args="../games/scripted-springai-seed7.jsonl"

# Play one random-bot game. `just play 7` to pick a seed.
play seed="1":
    uv run --directory {{ENGINE_PY}} python -m ludo_engine.cli play --seed {{seed}}

# Record a game to projects/ludo/games/.
record seed="1":
    uv run --directory {{ENGINE_PY}} python -m ludo_engine.cli play --seed {{seed}} --out ../games/sample-seed{{seed}}.jsonl

# Game-length statistics, for sizing the turn cap from data.
bench games="500":
    uv run --directory {{ENGINE_PY}} python -m ludo_engine.cli bench --games {{games}} --max-turns 2000

# Validate recorded transcripts against the shared schema.
validate:
    uv run --directory {{ENGINE_PY}} python -m ludo_engine.cli validate ../games/*.jsonl

# Deterministic scoring of one recorded game — free, no keys.
score game="projects/ludo/games/scripted-strands-seed7.jsonl":
    uv run --directory {{EVAL}} python -m ludo_eval score {{game}}

# The repo's real question: the same matchup across the three stacks.
compare:
    uv run --directory {{EVAL}} python -m ludo_eval compare {{GAMES}}/scripted-strands-seed7.jsonl {{GAMES}}/scripted-langgraph-seed7.jsonl {{GAMES}}/scripted-springai-seed7.jsonl

# Harness-contract §8: normalise and diff the three stacks' event sequences.
conformance-stacks:
    uv run --directory {{EVAL}} python -m ludo_eval conformance {{GAMES}}/scripted-strands-seed7.jsonl {{GAMES}}/scripted-langgraph-seed7.jsonl {{GAMES}}/scripted-springai-seed7.jsonl

# Watch recorded games in the browser.
ui:
    npm run dev --prefix {{UI}}

# Verify docs still hang together: links, anchors, mermaid structure.
# Checks structure, not truth — re-read what you changed. See CLAUDE.md Rule #1.
docs:
    python scripts/check_docs.py

# Parse every mermaid block with the real renderer, so a broken diagram fails
# here instead of on GitHub. Needs `npm ci` once; `just docs` does not cover it.
mermaid:
    node scripts/check_mermaid.mjs

# Verify shared/ still holds its invariants: no template logic, declared
# variables match used ones, prompt rule numbers match the engine, one model on
# both access routes, judge not seated, judge prompt's fixed contract, no
# secrets in models.yaml.
prompts:
    uv run scripts/check_prompts.py

# Is moving first an advantage? (It isn't — ADR-0006.) Takes ~3 minutes.
turn-order:
    uv run --directory {{ENGINE_PY}} python examples/turn_order.py

# Everything CI runs. No model calls, no cost.
check: test conformance validate docs mermaid prompts
