# Learning from ALIBI

LUDO's learning folders teach a language ([python](../python/), [java](../java/)) or a framework ([strands](../strands/), [springai](../springai/), [langgraph](../langgraph/)). This folder teaches the **two new hard things project two exists for** — retrieval and agent-as-tool — plus the two disciplines building it forced: scoring against an answer key, and generating one corpus from two languages.

Everything here is checked against the built [ALIBI code](../../projects/alibi/) and its committed fixtures. Like the framework folders, there is **no examples directory**: these docs teach against the project's own tests and CLIs, which run in the project venvs — a retrieval example without the engine would be a toy about a different system.

## Read in this order

| Doc | Question it answers |
|---|---|
| [00 — retrieval before embeddings](00-retrieval-before-embeddings.md) | What retrieval actually is, taught on a retriever small enough to hand-compute — and why the top-ranked answer to red's first question was a lie |
| [01 — the archivist, three ways](01-the-archivist-agent-as-tool.md) | One tool, three frameworks: where each one *executes* it, and why the same story meters 22, 22, and 20 model calls |
| [02 — scoring with an answer key](02-scoring-with-an-answer-key.md) | Why ALIBI needs no LLM judge: Brier calibration, exposure vs. belief, and a scorer that checks itself against the referee |
| [03 — one corpus, two languages](03-one-corpus-two-languages.md) | How Python and Java write byte-identical fiction: the draw order is the spec, floats come from a table, and a comma is a conformance failure |

The design these docs walk is in [engine-design.md](../../docs/projects/alibi/engine-design.md) and the [harness contract](../../docs/projects/alibi/harness-contract.md); the findings they end at live in [the matrix's second act](../../docs/architecture/stack-comparison.md#alibi-the-second-act).

## The handles, up front

One phrase per concept, expanded in the docs:

- **Retrieval is a ranking, not an oracle** — a search engine returns the most *similar* documents, not the most *true* ones.
- **A tool is a seam, not a feature** — all three frameworks "have tools"; what differs is what happens around the seam, and what a "call" even means.
- **An answer key turns judging into arithmetic** — ground truth is what lets ALIBI's eval retire the judge.
- **The draw order is the spec** — cross-language determinism is a property of *when* you consume randomness, not just which generator you use.
