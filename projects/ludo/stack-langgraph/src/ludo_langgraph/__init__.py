"""LUDO agent harness on LangGraph — the third build of the same game.

Same shared prompts, same ``models.yaml``, same event schema as the Strands
and Spring AI stacks; the framework is the only variable. The harness answers
the engine's three hooks (negotiate / choose / reflect) with LangGraph's own
primitives, per ADR-0008.
"""
