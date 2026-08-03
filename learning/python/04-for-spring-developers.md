# Python for the Spring Developer

For readers arriving from Java and Spring — `implements`, containers, `@Qualifier`, Maven — who keep looking for machinery this codebase doesn't have.

This doc exists because a Spring developer read the harness and asked, in exactly this order: *where is `implements`? where is the container? where is `@Qualifier`? and how does the harness's output even reach the engine?* Each section is one of those questions. None of the answers is "Python can't" — every one is "Python **chose not to**", and knowing the choice is what makes the code readable.

The [reading rule](README.md) applies: when a section says **Before you scroll**, commit to an answer first.

## The Rosetta table

| Spring / Java | Here | Where to see it |
|---|---|---|
| `interface Decider` | `Decider` **Protocol** — satisfied by shape, no declaration | [deciders.py](../../projects/ludo/engine-python/src/ludo_engine/deciders.py) |
| The concrete bean | `_Decider` — a plain class, no marker of any kind | [harness.py](../../projects/ludo/stack-strands/src/ludo_strands/harness.py) |
| The client coded to the interface | the engine: `Game.play(deciders)` never learns the concrete type | [game.py](../../projects/ludo/engine-python/src/ludo_engine/game.py) |
| The container | **none** — a `main()` calling constructors | [demo.py](../../projects/ludo/stack-strands/src/ludo_strands/demo.py) |
| `@Configuration` / bean wiring | the **composition root**: `LudoHarness.__init__` | [harness.py](../../projects/ludo/stack-strands/src/ludo_strands/harness.py) |
| `@Qualifier("strands")` | **which program you run** — see §3 | the `uv run --directory` commands |
| `@Bean` factory method | a factory function with an `if` | [`build_model()`](../../projects/ludo/stack-strands/src/ludo_strands/strands_client.py) |
| `@Profile("dev")` | `models.yaml` profiles — select models and budgets, never the framework | [shared/models.yaml](../../shared/models.yaml) |
| Maven's shared `~/.m2` | per-project `.venv` — the **opposite** model | [doc 03](03-environments-and-packaging.md) |
| A JAR from a repository | a path dependency in `pyproject.toml` | [doc 00](00-files-and-folders.md#how-another-project-uses-this-package) |

## 1. "Where is `implements`?"

Side by side — the plugged class in both worlds:

```java
class StrandsDecider implements Decider {            // the line Java demands
    private final LudoHarness harness;
    public Move choose(TurnContext ctx) {
        return harness.choose(ctx);
    }
}
```

```python
class _Decider:                                      # no implements — the whole difference
    def __init__(self, harness, color, label):
        self._harness = harness
    def choose(self, ctx):
        return self._harness.choose(ctx)
```

Everything you know still happens: instantiate, store under an interface-shaped type, virtual dispatch follows the object. What moves is **when conformance is checked**. Java answers "is it a `Decider`?" at compile time, from the declaration. Python answers it at each call — `decider.choose(ctx)` looks the method up by name, right then, and a mismatch is an `AttributeError` at the call site instead of a red squiggle. For the *optional* methods the engine goes one step further and asks before calling: `isinstance(decider, Negotiator)` on a `@runtime_checkable` Protocol means "does a `negotiate` method exist?" — names only, signatures unchecked.

The consequence is architectural, not cosmetic: no Python agent needs the engine on its "classpath", while every Java agent does — the first row of the [capability matrix](../../docs/architecture/stack-comparison.md), and [learning/java/01 §3](../java/01-same-engine-twice.md) walks the same boundary from the other side.

> **The line to keep: fitting is decided at the call, not at the declaration.**

## 2. "Where is the container?"

**Before you scroll:** without a container, *something* still has to `new` the deciders and hand them over. Name the place.

```java
@Configuration
class Wiring {
    @Bean Map<Color, Decider> deciders(LudoHarness h) {
        Map<Color, Decider> d = new EnumMap<>(Color.class);
        for (Color c : Color.values()) d.put(c, new StrandsDecider(h, c));
        return d;
    }
}
```

```python
# harness.py — LudoHarness.__init__ is the composition root
self.deciders = {color: _Decider(self, color, label) for color in COLORS}
self.game     = Game(config, self.sink)          # constructor injection, by hand

def play(self):
    return self.game.play(self.deciders)         # the handover
```

The place you named is the **composition root** — the one spot where the object graph gets built. Spring hides it inside the container; Python writes it as an ordinary function. No scanning, no proxies, no bean lifecycle: construction order is the file's line order, and you can step through all of it in a debugger. What you give up is real — lazy initialisation, scoped beans, AOP. What you get is wiring with no magic to misconfigure. At four agents and a game engine, that trade isn't close.

> **The line to keep: the composition root is a function you can read.**

## 3. "Where is `@Qualifier`?"

Two beans, one interface — Spring picks with a qualifier. Python's in-process equivalent is disarmingly literal, because **`import` is an ordinary runtime statement** and may sit inside an `if`:

```python
if args.stack == "strands":
    from ludo_strands.harness import LudoHarness as Harness     # this IS the qualifier
else:
    from ludo_langgraph.harness import LudoHarness as Harness

game.play(Harness(profile, prompts, models, sink).deciders)
```

Or a dict literal as the bean registry: `HARNESSES = {"strands": ..., "langgraph": ...}` then `HARNESSES[name](...)`.

**This repo deliberately uses neither.** The two frameworks may never share a process — one merged dependency tree would destroy the isolation the [environment strategy](../../docs/architecture/environment-strategy.md) exists to protect — so selection is pushed all the way out to the shell. Two programs, one shared engine library, and the qualifier is the command:

```bash
uv run --directory projects/ludo/stack-strands python -m ludo_strands.demo out.jsonl
```

In Spring terms: two Spring Boot applications sharing a JAR — not one application with two qualified beans.

## 4. "How does the output travel back?"

It doesn't *travel* — there is nothing to cross. Engine and harness are objects in one process on one call stack, and the "channel" is a return value:

```
Game._decide()                    engine frame — holds a reference to YOUR object
  └─ _Decider.choose(ctx)         harness frame — engine called into harness code
       └─ LudoHarness.choose()    renders the prompt, calls the model
            └─ Agent.__call__()   framework frame — HTTP happens below here
```

The only network boundary in the whole system sits *below* the harness: the LLM is not a component, it's a remote text API behind the `Model` seam — exactly a `PaymentProvider` interface whose implementation calls Stripe. The caller neither knows nor cares that a wire sits behind the method, which is also why a [scripted fake](../strands/00-the-agent-loop.md) can replace it without anything above noticing.

> **The line to keep: the answer comes home as a return value.**

## 5. Annotations are documentation

`deciders: dict[Color, Decider]` looks like `Map<Color, Decider>` and checks **nothing**. Hand it a dict of strings and Python runs happily until the first `.choose(...)` raises. This is the trade Java people feel most, so look at what the repo does about it rather than pretending it away:

- **The engine re-validates every move** an agent returns — partly because a type hint guarantees nothing ([the walkthrough](01-walkthrough-game.md) makes this point twice).
- **Tests assert what signatures can't.** `test_strands_client.py` constructs every seat's model and reads the settings back, because a wrong config key here is silently *ignored*, not rejected — a [matrix finding](../../docs/architecture/stack-comparison.md) that would make a Spring developer wince, correctly.
- Static checkers (`mypy`, `pyright`) exist and would catch much of this at edit time; this repo hasn't wired one up yet.

## 6. Where your Spring instincts still pay

Don't unlearn everything — three habits transfer at full value:

- **Program to an interface.** Still the entire design; the interface is just structural. The engine/`Decider` boundary *is* your ports-and-adapters reflex.
- **Constructor injection.** The only DI here. Every dependency in the stack arrives through `__init__` parameters, never reached for globally.
- **Design test seams in advance.** Python let the engine's tests monkeypatch `game.dice` on a live object; Java refused, forcing a deliberate `IntSupplier` seam — and that *discipline* produced the better design ([learning/java/01 §7](../java/01-same-engine-twice.md#7-testing--the-difference-that-changes-the-design)). Bring the instinct even where the language doesn't force it.

And bring your **expectation of loud failure**. Spring rejects an unknown property; this ecosystem sometimes warns and continues. Assume nothing is checked until you have watched it fail.

## Check yourself

1. Two implementations of one interface, no container: name Python's two in-process selection idioms, and the third mechanism this repo actually uses. → [§3](#3-where-is-qualifier)
2. What replaces the compile error when a "bean" doesn't fit the interface — and *when* does it fire? → [§1](#1-where-is-implements)
3. Rewrite `@Qualifier("strands")` as a shell command. → [§3](#3-where-is-qualifier)
4. Which Spring habit produced better *Java engine* code here, even though Python never needed it? → [§6](#6-where-your-spring-instincts-still-pay)

## Related

- [learning/java](../java/) — the same boundary crossed in the other direction
- [learning/strands](../strands/) — what the harness does once it's plugged in
- [Environment strategy](../../docs/architecture/environment-strategy.md) — why framework selection lives at the process level
- [How the teaching is done](../../docs/vision.md#how-the-teaching-is-done) — the principles this doc follows
