# One Corpus, Two Languages

LUDO's conformance vectors held two engines to the same *dice*. ALIBI raised the stakes in a way that is easy to miss: its archive — twenty documents of generated English prose — rides inside the transcript, and the transcript is inside the conformance digest. So the Python and Java engines must write **byte-identical fiction**, from the same seed, forever.

A comma out of place in one language's template fails all twenty vectors. This page is the three disciplines that make that survivable — and they generalise to any system that must reproduce itself across runtimes.

## Discipline 1: the draw order is the spec

Both engines share LUDO's portable PRNG (splitmix64 + xorshift64*, [rng.py](../../projects/alibi/engine-python/src/alibi_engine/rng.py) / [Rng.java](../../projects/alibi/engine-java/src/main/java/com/llmeval/alibi/engine/Rng.java)). Same algorithm, same seed, same stream — necessary, and nowhere near sufficient.

**Before you scroll:** the Java port uses the identical generator but its Fisher–Yates shuffle iterates upward, `0..n-1`, instead of Python's `n-1..1`. Same seed, same algorithm, same number of draws. What happens?

Every case in the repository changes. The generator emits the same numbers — but a shuffle is numbers *applied in an order*, and a different order is a different permutation. Which is why the shuffle direction is written into the spec itself:

```python
for i in range(len(items) - 1, 0, -1):   # high index down — iteration order is spec
    j = self.below(i + 1)
```

```java
for (int i = items.size() - 1; i > 0; i--) {   // the same loop, or nothing works
    int j = below(i + 1);
```

And it goes further: the whole *sequence of consumers* is spec. Deal first (solution picks in who/how/where order, one shuffle), then archive (sample shuffle, witness shuffle, spot picks in build order, gossip picks, final shuffle). One draw consumed out of order shifts every draw after it — the corpus equivalent of an off-by-one that rewrites the book. The [engine design](../../docs/projects/alibi/engine-design.md#what-the-java-port-must-preserve) lists the order as a port obligation, and the old Java trap from LUDO still applies underneath (`>>>`, never `>>`).

> **The draw order is the spec.** Determinism is a property of when you consume randomness, not just which generator you use.

## Discipline 2: floats you never compute

`belief_declared.confidence` is the one floating-point field engine bots emit, and it sits inside the digest. The obvious implementation — `1.0 / candidates` — puts two languages' float division *and* float formatting on the conformance path.

The fix is to refuse to play: both engines carry the same **literal table** —

```
1: 1.0   2: 0.5   3: 0.3333   4: 0.25   5: 0.2   6: 0.1667   7: 0.1429   8: 0.125
```

— so no confidence is ever the *result* of arithmetic. Python's `repr` and Java's `Double.toString` both print the shortest digits that round-trip, so for these constants they agree by construction ([Json.java](../../projects/alibi/engine-java/src/main/java/com/llmeval/alibi/engine/Json.java) documents the one place ALIBI extended LUDO's writer). LLM detectives may declare any confidence they like — their events are outside the vectors, which is exactly where free-form floats belong.

## Discipline 3: bytes, not glyphs

The templates contain an em-dash. In the transcript it appears as the six ASCII characters `\u2014`, because the canonical JSON writers on both sides escape all non-ASCII (Python's `ensure_ascii=True`; the Java writer mirrors it). In the Java *source*, the string literal is spelled `\u2014` as well — not for the compiler, which handles UTF-8 fine, but so no editor, diff tool, or platform encoding setting between here and the reader can ever silently change the byte the digest depends on. When bytes are the contract, spell the fragile ones in ASCII.

**Named and killed:** "the digests match, so the transcripts match" is NOT the full guarantee — the digest strips one field (`game_started.engine`, which *must* differ) and covers canonical serialisation. The stronger, line-level claim — same key order, same bytes per line — is held separately, by the engines building every payload in the same insertion order. LUDO learned that lesson the expensive way; ALIBI inherited both halves.

## What it buys

The Java engine matched all twenty Python-recorded vectors — prose, deal, beliefs, standings — **on its first build**. Not because porting is easy, but because every decision above was made *before* the port existed: the RNG spec'd, the draw order documented, the floats tabled, the fragile bytes escaped. Cross-language determinism is cheap exactly once — at design time.

## Run it

Both engines against the same twenty vectors:

```bash
uv run --directory projects/alibi/engine-python python -m alibi_engine.cli conformance --check
```

From `projects/alibi/engine-java`:

```bash
./mvnw -q -B exec:java -Dexec.args="conformance --check"
```

## Check yourself

1. Same generator, same seed, upward shuffle: what breaks, and why does the generator not notice? ([answer](#discipline-1-the-draw-order-is-the-spec))
2. Why is `1.0 / n` forbidden in engine bots but fine in an LLM detective's reply? ([answer](#discipline-2-floats-you-never-compute))
3. Why does the Java source spell an em-dash `\u2014` when the compiler reads UTF-8? ([answer](#discipline-3-bytes-not-glyphs))
4. The digest excludes one field. Which, and what would including it make the vectors? ([answer](#what-it-buys))

Back to [the folder map](README.md) — or up to [the matrix](../../docs/architecture/stack-comparison.md#alibi-the-second-act), where these disciplines become findings.
