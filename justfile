# Cross-stack task runner. One set of verbs for four toolchains.
#
# `just` is used instead of `make` because this repo is developed on Windows as
# well as Unix. Install: winget install Casey.Just | scoop install just |
# brew install just | cargo install just
#
# Every command a contributor needs belongs here. If a workflow only lives in
# someone's shell history, it isn't documented.

ENGINE_PY := "projects/ludo/engine-python"

default:
    @just --list

# Install all toolchains and dependencies.
setup:
    uv sync --directory {{ENGINE_PY}}

# Run every test suite.
test: test-engine-py

test-engine-py:
    uv run --directory {{ENGINE_PY}} pytest

# Both engines against the shared conformance vectors (ADR-0002).
conformance:
    uv run --directory {{ENGINE_PY}} python -m ludo_engine.cli conformance --check

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

# Verify docs still hang together: links, anchors, mermaid syntax.
# Checks structure, not truth — re-read what you changed. See CLAUDE.md Rule #1.
docs:
    python scripts/check_docs.py

# Everything CI runs. No model calls, no cost.
check: test conformance validate docs
