"""LUDO evaluation harness — scoring recorded games, never playing them.

Two layers, per docs/projects/ludo/evaluation.md:

- **Deterministic scoring** reads a transcript and computes position, play
  record, and efficiency per player. Free, instant, identical every replay.
- **The LLM judge** reads an anonymised transcript view and scores the seven
  rubric dimensions the numbers cannot see. Expensive, subjective — so it is
  opt-in, multi-run, citation-enforced, and validated against outcomes.

Everything here consumes the shared event stream and nothing else: no engine
import, no stack import, no model SDK. A transcript in, a schema-validated
result out.
"""
