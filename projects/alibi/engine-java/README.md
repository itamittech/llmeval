# alibi-engine (Java)

The Java twin of [`engine-python`](../engine-python/), serving the Spring AI stack
([ADR-0002](../../../docs/decisions/adr-0002-engine-per-language.md)). JDK only —
no LLM SDKs, no network, no JSON library — and held to the same
[conformance vectors](../../../shared/conformance/alibi-vectors.json) as the Python
engine, **corpus bytes included**: the archive rides in the transcript, so the digest
covers every generated sentence. All 20 vectors pass.

## Class map

| Class | Python counterpart |
|---|---|
| `Rng` | `rng.py` — same splitmix64 + xorshift64*, same shuffle order; every right shift is `>>>` |
| `CaseModel` | `case.py` — elements, cast, the even deal |
| `Archive` | `archive.py` — templates byte-identical to Python's, integer-scored retriever |
| `Detective` / `DetectiveView` / `SearchBudget` | the `deciders.py` protocol — but Java needs `implements`, so the Spring AI stack takes a compile-time engine dependency the Python stacks never do (the recorded matrix finding, again) |
| `EliminationBot` | the conformance decider, ported to the query |
| `Game` | `game.py` — payloads built in the same key order, so transcripts stay byte-comparable line by line |
| `Json` | LUDO's hand-rolled writer, plus doubles: belief confidences come from a literal table so `Double.toString` and Python's `repr` agree by construction |
| `EventSink` / `Conformance` / `Cli` | same names, same jobs |

## Run it

From this directory (`projects/alibi/engine-java`):

```bash
./mvnw -B test
```

```bash
./mvnw -q -B exec:java -Dexec.args="conformance --check"
```

```bash
./mvnw -q -B exec:java -Dexec.args="play --seed 7"
```

`validate` is deliberately absent, as in LUDO's Java engine: schema validation needs a
schema library and this engine has no dependencies — the Python CLI owns that job, and
transcripts are engine-neutral.

Design rationale: [engine-design.md](../../../docs/projects/alibi/engine-design.md) —
especially *What the Java port must preserve*, which this module is the proof of.
