# Retrieval Before Embeddings

Here is the moment this page exists to explain. On turn 1 of [the committed fixture](../../projects/alibi/games/scripted-strands-seed7.jsonl), red asks the archivist:

> *photographer cloakroom service hatch*

and the top-ranked answer — `doc-016`, *"the service hatch was bolted and painted shut since the spring renovation"* — is a **lie**. So is the third result. Red's belief that turn ends up wrong in all three dimensions.

Nothing malfunctioned. That is retrieval working exactly as designed, and understanding *why* is most of understanding RAG.

## What retrieval is

Strip every acronym away and RAG is two steps:

1. **Retrieve** — rank a corpus by similarity to the question; take the top k.
2. **Generate** — put those k documents into the prompt and let the model answer *from them*.

Everything interesting lives in step 1's one-word trap: **similar**. A ranking function measures how much a document *resembles the question* — it has no opinion about whether the document is true. A lie written about exactly your topic outranks a truth written about something else, every time, in every retriever from this one to the largest embedding index in production.

> **Retrieval is a ranking, not an oracle.**

## A retriever small enough to hand-compute

ALIBI's engine ships the simplest retriever that is still honestly a retriever — [`archive.py → search`](../../projects/alibi/engine-python/src/alibi_engine/archive.py):

```
tokens  = lowercase runs of [a-z0-9]+
score   = |unique query tokens ∩ document tokens|
ranking = score desc, then fewer document tokens, then id
return top k = 3, score > 0 only
```

Integers only — no floats, no model, no network — because this retriever sits on the cross-engine conformance path ([doc 03](03-one-corpus-two-languages.md)) and two languages must rank identically forever.

Now hand-compute red's query. Its token set is `{photographer, cloakroom, service, hatch}`. Four documents in the seed-7 archive overlap it at all:

| doc | overlaps | score | doc tokens | rank |
|---|---|---|---|---|
| `doc-016` | service, hatch | **2** | 17 | 1 |
| `doc-018` | photographer | 1 | 16 | 2 |
| `doc-013` | cloakroom | 1 | 20 | 3 |
| `doc-002` | photographer | 1 | 24 | **cut by k=3** |

Two things worth staring at:

- `doc-016` and `doc-013` are two of the case's three **red herrings** — and they rank 1 and 3. Of course they do: a red herring is *written about the solution*, and red asked about the solution. The most relevant lies are the best-ranked ones.
- `doc-002` — the third herring — missed the cut on the **tie-break**: same score as `doc-013`, four tokens longer. One adjective of witness verbosity decided what red never saw. Retrieval results are this contingent even when fully deterministic.

**Named and killed:** this is NOT a weakness keyword search has and embeddings fix. An embedding index ranks by semantic similarity to the question — a fluent lie about your exact topic is *more* semantically similar than a dry truth about an adjacent one. Upgrading the retriever upgrades the ranking, not the epistemology.

## So how is the game still winnable?

Because the corpus generator plants the antidote where only deliberate behaviour finds it. Every lying witness is undermined by one truthful counter-document — but the counter is about *the witness*, not about the case, so it never surfaces on case-shaped queries. Compare red's two searches in the fixture:

| turn | query | results | what it was about |
|---|---|---|---|
| 1 | *photographer cloakroom service hatch* | 016, 018, 013 | the case → fed two lies |
| 5 | *security guard Asha Nair* | 002, **009** | the **witness** → the lie and its refutation, side by side |

`doc-009`: *"Asha Nair left the gala before ten … whatever she says about that night is secondhand at best."* Cross-checking is not a virtue the prompt requests; it is a **query strategy** — asking about provenance instead of content. That is the retrieval lesson ALIBI is built to make playable: *the table is facts, the archive is claims*, and claims are checked by asking who made them.

## Why the engine has no embeddings

**Before you scroll:** the live tier will use embedding retrieval. Why does the *engine* refuse to — what two repo rules would it break?

Both of the engine's founding constraints: embeddings need a model call (the engine never imports an LLM SDK, never touches the network) and their scores are floats from a model that can change (the retriever is inside the conformance digest, which must replay byte-identically forever). So the deterministic keyword retriever is the engine's **baseline profile**, shared by all three stacks in every scripted game — and embedding/hybrid/reranked retrieval is a *harness* concern for live play, governed by [open question 23](../../docs/open-questions.md#-23-retrieval-parity--what-must-be-pinned-and-what-is-allowed-to-be-the-finding): pin the inputs, let the strategies differ, record the differences as findings.

## Run it

Recompute the table above from nothing but a seed:

```bash
uv run --directory projects/alibi/engine-python python -c "from alibi_engine.rng import Rng; from alibi_engine.case import deal; from alibi_engine.archive import generate; rng = Rng(7); a = generate(deal(rng), rng); print([d.id for d in a.search('photographer cloakroom service hatch')])"
```

## Check yourself

1. A document scores highest for your query. What, precisely, has been established about it? ([answer](#what-retrieval-is))
2. Why did red never see `doc-002` on turn 1, despite it mentioning the photographer? ([answer](#a-retriever-small-enough-to-hand-compute))
3. What made turn 5's query structurally different from turn 1's? ([answer](#so-how-is-the-game-still-winnable))
4. Would swapping in embeddings have protected red from the herrings? ([answer](#a-retriever-small-enough-to-hand-compute))

Next: [the archivist, three ways](01-the-archivist-agent-as-tool.md) — how this retriever gets behind a tool, and what each framework does around the seam.
