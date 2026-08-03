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

default:
    @just --list

# Install all toolchains and dependencies.
setup:
    uv sync --directory {{ENGINE_PY}}
    npm ci
    cd {{ENGINE_JAVA}} && ./mvnw -q -B dependency:resolve

# Run every test suite.
test: test-engine-py test-engine-java

test-engine-py:
    uv run --directory {{ENGINE_PY}} pytest

test-engine-java:
    cd {{ENGINE_JAVA}} && ./mvnw -q -B test

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
# both access routes, judge not seated, no secrets in models.yaml.
prompts:
    uv run scripts/check_prompts.py

# Is moving first an advantage? (It isn't — ADR-0006.) Takes ~3 minutes.
turn-order:
    uv run --directory {{ENGINE_PY}} python examples/turn_order.py

# Everything CI runs. No model calls, no cost.
check: test conformance validate docs mermaid prompts
