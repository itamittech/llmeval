# LUDO Engine — Low-Level Class Design

The object graph as actually built, at method granularity: who owns what, who calls what, which relationships are inheritance versus something looser, and [which design patterns are genuinely in play](#7-design-patterns-from-the-problem-up).

**New to design patterns?** [Section 7](#7-design-patterns-from-the-problem-up) is written for you — each pattern starts from a problem this engine actually hit, shows the code you'd write first, shows what breaks, and only then names the thing.

**This is a living document.** Sections 1–8 are the engines. The agent stacks attach to them at a single dashed arrow, and all three are now drawn on the far side of it: [§9](#9-the-harness-layer-the-same-turn-on-strands) is the same turn on Strands, [§10](#10-the-harness-layer-second-take-the-same-turn-on-spring-ai) on Spring AI, [§11](#11-the-harness-layer-third-take-the-same-turn-on-langgraph) on LangGraph — read together, they are the framework comparison at class level, and §11.4 ends in the three-grain table the whole repo builds toward.

Companion docs: [engine-design.md](engine-design.md) explains *why* these shapes were chosen; this one shows *how they connect*. For Python syntax itself, see [learning/python](../../../learning/python/).

---

## 1. The object graph

Methods only — field types are in the [reference table](#5-class-reference). Private helpers prefixed `_`.

```mermaid
classDiagram
    direction TB

    class Game {
        +play(deciders) Outcome
        -_play_turn(color, decider)
        -_roll_loop(color, decider, view) str
        -_apply(color, move) bool
        -_decide(color, decider, die, moves, view) Move
        -_next_player() Color
        -_emit(type, payload)
        -_emit_start(deciders)
    }

    class GameConfig {
        +seed
        +max_turns
        +ruleset
        +stack
        +players
    }

    class Outcome {
        +reason
        +turns_played
        +standings
        +winner Color
    }

    class GameState {
        +tokens
        +stats
        +finished
        +tokens_home(color) int
        +progress(color) int
        +has_finished(color) bool
        +snapshot() Snapshot
        +restore(snap)
    }

    class Snapshot {
        <<frozen>>
        +tokens
        +stats
        +finished
    }

    class PlayerStats {
        +captures_made
        +captures_suffered
        +turns_forfeited
    }

    class Dice {
        +seed
        +rolls
        +roll() int
    }

    class Move {
        <<frozen>>
        +token
        +frm
        +to
    }

    class Capture {
        <<frozen>>
        +victim
        +victim_token
        +square
    }

    class TurnContext {
        <<frozen>>
        +state
        +color
        +die
        +legal_moves
        +turn
        +attempt
    }

    class StateView {
        <<read-only>>
        +tokens(color) tuple
        +board() dict
        +tokens_home(color) int
        +progress(color) int
        +has_finished(color) bool
        +finished() tuple
        +stats(color) PlayerStats
    }

    class Decider {
        <<Protocol>>
        +choose(ctx) Move
    }

    class Negotiator {
        <<Protocol, optional>>
        +negotiate(start) None
    }

    class Reflector {
        <<Protocol, optional>>
        +reflect(end) None
    }

    class FirstLegal {
        +name
        +choose(ctx) Move
    }

    class RandomBot {
        +name
        +choose(ctx) Move
    }

    class EventSink {
        +emit(type, payload, turn) dict
        -_write(event)
    }

    class ListSink {
        +events
        -_write(event)
    }

    class JsonlSink {
        -_write(event)
    }

    class TeeSink {
        -_write(event)
    }

    Game *-- GameConfig : owns
    Game *-- GameState : creates
    Game *-- Dice : creates
    Game o-- EventSink : injected
    Game ..> Outcome : returns
    Game ..> TurnContext : builds per attempt
    Game ..> Decider : calls choose, per ROLL
    Game ..> Negotiator : calls negotiate, per TURN
    Game ..> Reflector : calls reflect, per TURN
    Game ..> Move : validates

    GameState *-- PlayerStats : one per colour
    GameState ..> Snapshot : creates and consumes

    TurnContext --> StateView : read-only board
    TurnContext --> Move : list of legal
    StateView --> GameState : wraps, exposes no mutation

    Decider <|.. FirstLegal : structural
    Decider <|.. RandomBot : structural
    RandomBot *-- Dice : own seeded stream

    EventSink <|-- ListSink : inherits
    EventSink <|-- JsonlSink : inherits
    EventSink <|-- TeeSink : inherits
    TeeSink o-- EventSink : fans out to many

    Capture ..> Move : produced by applying
```

### Reading the arrows

| Arrow | Means | Where it's used here |
|---|---|---|
| `<\|--` | **Inheritance** | Only `EventSink` → its three subclasses. The single hierarchy in the engine. |
| `<\|..` | **Realization** | `FirstLegal`/`RandomBot` satisfy `Decider`. Dotted because in Python this is *structural* — neither class names `Decider` anywhere. |
| `*--` | **Composition** | Owner creates it and controls its lifetime. `Game` creates its own `GameState` and `Dice`. |
| `o--` | **Aggregation** | Holds something it did not create. `Game` receives its `EventSink` from outside. |
| `..>` | **Dependency** | Uses transiently — constructs, returns, or calls, without holding. |

The two dotted-inheritance arrows are the design's centre of gravity. `FirstLegal` contains no reference to `Decider`; it qualifies purely by having a `choose` method of the right shape. That's what lets an agent in a completely separate package plug in without importing the engine.

---

## 2. The two extension points, zoomed in

Everything above is fixed machinery except these. They're where other code attaches.

```mermaid
classDiagram
    direction LR

    class Decider {
        <<Protocol>>
        +choose(ctx) Move
    }
    class FirstLegal {
        <<deterministic>>
        +choose(ctx) Move
    }
    class RandomBot {
        <<seeded random>>
        +choose(ctx) Move
    }
    class StrandsAgent {
        <<built — §9>>
        +choose(ctx) Move
        +negotiate(start) None
        +reflect(end) None
    }
    class LangGraphAgent {
        <<built — §11>>
        +choose(ctx) Move
        +negotiate(start) None
        +reflect(end) None
    }

    Decider <|.. FirstLegal
    Decider <|.. RandomBot
    Decider <|.. StrandsAgent
    Decider <|.. LangGraphAgent

    note for Decider "Structural typing: no import, no inheritance.<br/>One method is the entire agent contract."
```

The Java engine exposes the same two ports, spelled as that language demands: `Decider` is an `interface`, and the Spring AI stack writes the line Python never needs — `SpringDecider implements Decider` ([§10.1](#101-the-harness-object-graph)).

```mermaid
classDiagram
    direction LR

    class EventSink {
        +emit(type, payload, turn)
        -_write(event)
    }
    class ListSink {
        <<in memory>>
        -_write(event)
    }
    class JsonlSink {
        <<to a file>>
        -_write(event)
    }
    class TeeSink {
        <<fan out>>
        -_write(event)
    }

    EventSink <|-- ListSink
    EventSink <|-- JsonlSink
    EventSink <|-- TeeSink
    TeeSink o-- EventSink

    note for EventSink "Template method: emit assigns seq,<br/>_write is the only thing subclasses change."
```

`TeeSink` both **inherits from** `EventSink` and **holds** several — so `TeeSink(ListSink(), JsonlSink(fh))` writes to memory and disk under one shared sequence counter. It deliberately calls each child's `_write`, not `emit`, so children never renumber.

---

## 3. One turn, as calls

The interaction the class diagram can't show. This is `Game._play_turn` for a single turn that captures a token and earns an extra roll.

```mermaid
sequenceDiagram
    autonumber
    participant G as Game
    participant S as GameState
    participant D as Dice
    participant M as moves module
    participant A as Decider
    participant E as EventSink

    G->>E: emit turn_started
    opt decider implements Negotiator
        G->>A: negotiate(TurnStart)
        Note over G,A: once per TURN, before any roll
    end
    G->>S: snapshot()
    S-->>G: Snapshot

    loop until turn ends
        G->>D: roll()
        D-->>G: die
        G->>E: emit dice_rolled

        alt third consecutive six
            G->>S: restore(snapshot)
            G->>E: emit turn_ended three_sixes
        end

        G->>M: legal_moves(state, color, die)
        M->>S: read tokens
        M-->>G: list of Move

        alt no legal moves
            G->>E: emit turn_ended no_legal_move
        end

        G->>G: _decide(...)
        G->>A: choose(TurnContext)
        A-->>G: Move

        alt move not in legal set
            G->>E: emit illegal_move_rejected
            Note over G,A: retry once, then forfeit
        end

        G->>M: apply_move(state, color, move)
        M->>S: write tokens, bump stats
        M-->>G: list of Capture
        G->>E: emit move_made
        G->>E: emit token_captured

        G->>E: emit extra_roll_granted
    end

    G->>E: emit turn_ended
    opt decider implements Reflector
        G->>A: reflect(TurnEnd)
        Note over G,A: once per TURN, after it resolves
    end
```

Three things this makes obvious that prose does not:

- **`Decider.choose` is the only inbound arrow that changes the game.** The two optional hooks sit *outside* the roll loop and return nothing — they exist so a harness can talk and remember at the right moments, and everything they produce reaches the world as events rather than as state.
- **The loop is where per-roll and per-turn diverge.** `choose` is inside it, `negotiate` and `reflect` are outside. A six or a capture re-enters the loop; if negotiation were inside, an agent on a hot streak would get a free multiplier on influence and cost.
- **The agent never touches `GameState`.** Only `moves` and `Game` write to it; the decider receives a read-only [`StateView`](engine-design.md#one-honest-limit-on-the-guardrail). That's the structural guardrail of [ADR-0004](../../decisions/adr-0004-structural-guardrails.md).

---

## 4. Who calls what

Method-level, engine only.

| Caller | Calls | For |
|---|---|---|
| `Game.play` | `Game._emit_start`, `_next_player`, `_play_turn` · `standings()` · `EventSink.emit` · `Outcome()` | the outer loop |
| `Game._play_turn` | `StateView()` · **`Negotiator.negotiate`** · `Game._roll_loop` · **`Reflector.reflect`** · `EventSink.emit` | one turn, with the optional hooks around the roll loop |
| `Game._roll_loop` | `Dice.roll` · `GameState.snapshot`/`restore`/`has_finished` · `legal_moves()` · `Game._decide`/`_apply` · `EventSink.emit` | roll, decide, resolve — repeating on a six or capture. Returns the end reason so the turn has one exit and `reflect` can't be skipped |
| `Game._decide` | `TurnContext()` · **`Decider.choose`** · `EventSink.emit` | ask the agent, validate |
| `Game._apply` | `apply_move()` · `to_square()` · `EventSink.emit` | move and report |
| `Game._next_player` | `GameState.has_finished` | rotate, skipping finishers |
| `GameState.snapshot` / `restore` | `Snapshot()`, `PlayerStats()` | copy in, copy out |
| `moves.legal_moves` | `to_square()`, `_can_land`, `_path_clear` | rule check |
| `moves.apply_move` | `to_square()`, `is_safe()` | move, capture, count |
| `RandomBot.choose` | `Dice.roll` | its own seeded stream |
| `TeeSink._write` | each child's `_write` | fan out, shared seq |
| `conformance.run_vector` | `Game.play`, `ListSink`, `digest()` | one deterministic game |

Note `board` is called by everyone and calls nobody — it's leaf-level pure functions.

---

## 5. Class reference

| Class | Kind | Module | Mutable | Purpose |
|---|---|---|---|---|
| `Game` | plain class | `game.py` | yes | the turn loop |
| `GameConfig` | dataclass | `game.py` | yes | seed, cap, player metadata |
| `Outcome` | dataclass | `game.py` | yes | result + `winner` property |
| `GameState` | dataclass | `state.py` | yes | tokens, stats, finish order |
| `PlayerStats` | dataclass | `state.py` | yes | three counters per colour |
| `Snapshot` | dataclass | `state.py` | frozen | turn-start copy for rollback |
| `Move` | dataclass | `moves.py` | frozen | must be hashable for `set` |
| `Capture` | dataclass | `moves.py` | frozen | what a move knocked out |
| `Dice` | plain class | `dice.py` | yes | portable seeded PRNG |
| `TurnStart` | dataclass | `deciders.py` | frozen | handed to `negotiate`, before the first roll |
| `TurnContext` | dataclass | `deciders.py` | frozen | everything an agent may see when choosing |
| `TurnEnd` | dataclass | `deciders.py` | frozen | handed to `reflect`: end reason + the turn's engine events |
| `StateView` | plain class | `deciders.py` | read-only | the board, inspectable but not writable |
| `Decider` | **Protocol** | `deciders.py` | — | the agent contract — `choose`, required |
| `Negotiator` | **Protocol** | `deciders.py` | — | optional `negotiate` hook, once per turn |
| `Reflector` | **Protocol** | `deciders.py` | — | optional `reflect` hook, once per turn |
| `FirstLegal` | plain class | `deciders.py` | no | deterministic, for vectors |
| `RandomBot` | plain class | `deciders.py` | yes | seeded random, for benchmarks |
| `EventSink` | base class | `events.py` | yes | sequence numbering |
| `ListSink` / `JsonlSink` / `TeeSink` | subclasses | `events.py` | yes | memory / file / fan-out |

---

## 6. Module layering

Dependencies point one way only.

```mermaid
flowchart TD
    subgraph leaf["leaf, pure functions"]
        board[board.py]
    end

    subgraph core["core"]
        state[state.py]
        moves[moves.py]
        dice[dice.py]
        events[events.py]
    end

    subgraph orch["orchestration"]
        deciders[deciders.py]
        game[game.py]
    end

    subgraph tools["tools"]
        conformance[conformance.py]
        cli[cli.py]
    end

    outside["agent stacks<br/>Strands §9 · Spring AI §10 · LangGraph §11"]

    state --> board
    moves --> board
    moves --> state
    deciders --> dice
    deciders --> moves
    deciders --> state
    game --> board
    game --> state
    game --> moves
    game --> dice
    game --> events
    game --> deciders
    conformance --> game
    conformance --> events
    cli --> game
    cli --> conformance
    outside -.->|implements Decider| deciders

    style outside stroke-dasharray: 5 5
```

No arrow ever points back up, and nothing in the engine points at an agent framework. The only inbound edge from outside is dashed: a stack implements `Decider`. That is the whole integration surface.

---

## 7. Design patterns, from the problem up

### First — what *is* a design pattern?

A design pattern is **a named solution to a problem that keeps coming back**. Not a library, not a rule you must follow — a description of a shape that has repeatedly turned out to work.

The idea didn't start in software. In 1977 the architect **Christopher Alexander** published *A Pattern Language*, cataloguing recurring solutions in building design: "light on two sides of every room", "a six-foot balcony". His argument was that good design is rarely invention — it's recognising a situation you've seen before and remembering what worked.

In 1994 four authors — universally called the **Gang of Four** — did the same for object-oriented software and catalogued 23 patterns. Strategy, Template Method, Memento and Composite below all come from that book. **Value Object** is later, from Eric Evans's *Domain-Driven Design* (2003). **Ports and Adapters** is Alistair Cockburn's (2005).

Two things worth knowing before you read on.

**The names are most of the value.** Saying "make that a Strategy" replaces three paragraphs of explanation between two people who both know the word. The code shapes themselves are things a good programmer often arrives at anyway — the shared vocabulary is what you're really gaining.

**Patterns are descriptions, not prescriptions.** The Gang of Four catalogued what already worked; they didn't hand out a checklist. Reaching for a pattern *because it's in the book* is one of the reliable ways to make a codebase unreadable. Everything below is here because a concrete problem pushed us into it — and [section 8](#8-patterns-deliberately-not-used) lists the ones we deliberately didn't use, which is just as instructive.

### How each one below is laid out

The usual way patterns get taught is backwards: here's a name, here's a definition, here's a diagram. But a pattern is an **answer**, and an answer means nothing until you've felt the question. So each one starts with a problem this engine actually hit, shows the code you'd reasonably write first, shows what breaks — and only then names the thing, explains where that odd name comes from, and gives you a rule of thumb for spotting the situation again.

Already know the patterns? Skip to the [recap](#79-recap).

---

### 7.1 Four players, four different brains → **Strategy**

**The problem.** `Game` has to ask each player "what's your move?" But the players are wildly different things. Two ship with the engine: `RandomBot` (picks at random, for benchmarking) and `FirstLegal` (always takes the first option, so conformance vectors stay reproducible). The rest are LLM agents, each on a different framework — and all three have since arrived: Strands ([§9](#9-the-harness-layer-the-same-turn-on-strands)), Spring AI in *Java* ([§10](#10-the-harness-layer-second-take-the-same-turn-on-spring-ai)), and LangGraph ([§11](#11-the-harness-layer-third-take-the-same-turn-on-langgraph)).

How does the turn loop ask the question without knowing who it's asking?

**What you'd write first.** The honest first attempt is a branch:

```python
# NOT what the engine does
if player_type == "random":
    move = random.choice(moves)
elif player_type == "first_legal":
    move = moves[0]
elif player_type == "strands":
    prompt = build_prompt(state, moves)
    reply = bedrock.invoke(prompt)        # <-- the engine now needs boto3
    move = parse(reply)
elif player_type == "langgraph":
    ...
```

Perfectly reasonable code. It also quietly destroys the project.

**What breaks.**

- The engine now imports an LLM SDK — [the one rule it must never break](../../architecture/repository-layout.md).
- Every new agent means editing `game.py`, the file whose correctness the conformance vectors depend on.
- Tests can't run without mocking a model provider.
- Adding a fourth agent means a fifth branch, forever.

**The fix.** Turn the question into a one-method contract, and let the caller supply the answerer:

```python
class Decider(Protocol):
    def choose(self, ctx: TurnContext) -> Move: ...
```

```python
move = decider.choose(ctx)      # game.py — every player, one line
```

Now `Game` *cannot* know what it's talking to. That inability is the feature.

```mermaid
flowchart TB
    subgraph before["BEFORE — Game knows every kind of player"]
        direction TB
        g1["Game._decide"] --> q{"what kind<br/>of player?"}
        q -->|random| b1["pick at random"]
        q -->|first legal| b2["take the first move"]
        q -->|strands| b3["build prompt<br/>call Bedrock<br/>parse reply"]
        q -->|langgraph| b4["build graph<br/>invoke<br/>parse reply"]
    end

    subgraph after["AFTER — Game knows one method"]
        direction TB
        g2["Game._decide"] --> ask["decider.choose(ctx)"]
        ask -.-> a1["RandomBot"]
        ask -.-> a2["FirstLegal"]
        ask -.-> a3["StrandsAgent"]
        ask -.-> a4["LangGraphAgent"]
    end
```

**Where the name comes from.** A *strategy* is a plan of action. The insight the name captures: make the plan a **separate, swappable object** rather than logic baked into whoever executes it. The general doesn't change; the battle plan does.

**The everyday version.** A power drill with swappable bits. The drill's job — spin — never changes. What you attach decides whether you're drilling masonry or driving a screw. The drill needs to know nothing about the bit beyond "it fits the chuck." `choose(ctx) -> Move` is our chuck.

**Reach for it when** you have an `if`/`elif` branching on a *kind of thing*, where every branch does the same job a different way. That's a Strategy waiting to be extracted.

**Don't when** there's only ever going to be one implementation. An interface with a single implementer is ceremony, not design.

---

### 7.2 Every event needs a number, but events go to different places → **Template Method**

**The problem.** The [event schema](../../../shared/schemas/README.md) requires `seq` to start at 0 and never skip. But events go to different destinations: memory during tests, a `.jsonl` file when recording a game, sometimes both at once.

**What you'd write first.** Give each destination its own emit method:

```python
# NOT what the engine does
class ListSink:
    def emit(self, type_, payload, turn=0):
        self.events.append({"seq": self._seq, "turn": turn, ...})
        self._seq += 1

class JsonlSink:
    def emit(self, type_, payload, turn=0):
        self._stream.write(json.dumps({"seq": self._seq, ...}) + "\n")
        self._seq += 1
```

**What breaks.** The numbering logic is now copy-pasted, and copy-pasted logic drifts. Someone increments before building the envelope, or forgets `turn`, or resets the counter on flush. The transcript then fails schema validation — and it fails *silently*, staying wrong until the UI tries to replay it and hits a gap.

**The fix.** Write the algorithm once and leave exactly one hole:

```python
class EventSink:
    def emit(self, type_, payload, turn=0):
        event = {"seq": self._seq, "turn": turn, "type": type_, "payload": payload}
        self._seq += 1              # the invariant: fixed, shared, unbypassable
        self._write(event)          # the hole: the only thing that varies

    def _write(self, event):
        raise NotImplementedError
```

A subclass can't break `seq`, because it never gets to touch it.

```mermaid
flowchart LR
    caller["Game._emit"] --> emit["EventSink.emit — FIXED<br/>build envelope<br/>assign seq<br/>increment"]
    emit --> hole{{"_write event<br/>the only variable step"}}
    hole -.-> ls["ListSink<br/>append to a list"]
    hole -.-> js["JsonlSink<br/>write one line"]
    hole -.-> ts["TeeSink<br/>hand to children"]
```

**Where the name comes from.** "Template" in the everyday sense — a form with blanks. The base class writes the form; subclasses fill in the blanks. "Method" because the template *is* a method (`emit`), not a class or a file.

**The everyday version.** A recipe that reads: *preheat oven, season **your choice of protein**, roast 40 minutes, rest 10 minutes.* Four steps fixed, one is yours. Crucially, nobody can accidentally skip the resting step — the recipe owns it. That's exactly what stops a subclass breaking `seq`.

**Reach for it when** two or more methods are ~90% identical and differ in one step. Hoist the sameness into a base class, leave a hole.

**Don't when** the shared skeleton is trivial. If two lines are common and ten differ, inheritance costs more than the duplication did.

#### Easily confused: Strategy vs Template Method

These trip up almost everyone, because both are "some behaviour varies."

```mermaid
flowchart LR
    subgraph strat["STRATEGY — composition"]
        direction TB
        ctx["Game"] -->|holds a| sif["Decider"]
        sif -.-> s2["RandomBot"]
        sif -.-> s3["StrandsAgent"]
        sn["the WHOLE algorithm<br/>is replaced"]
    end

    subgraph tmpl["TEMPLATE METHOD — inheritance"]
        direction TB
        base["EventSink.emit<br/>fixed skeleton"] --> step{{"_write<br/>ONE step"}}
        step -.-> t1["ListSink"]
        step -.-> t2["JsonlSink"]
        tn["the skeleton is FIXED,<br/>one step varies"]
    end
```

**The mnemonic:** Template Method uses **inheritance** and varies **one step inside a fixed algorithm**. Strategy uses **composition** and varies **the whole algorithm**. If you find yourself asking which you need, ask instead: *how much is allowed to change?*

---

### 7.3 Three sixes cancel the turn — including the capture → **Memento**

**The problem.** [The rules](game-rules.md) say three consecutive sixes forfeit the turn, and *everything done during it is cancelled*. By the time that third six lands, the player may have moved two tokens and captured an opponent. All of it must be undone.

**What you'd write first.** Two obvious approaches:

```python
# Attempt A — record what changed, reverse it
undo_log.append(("move", token, old_position))
undo_log.append(("capture", "green", 2, 44))
for action in reversed(undo_log):
    reverse(action)
```

```python
# Attempt B — let Game reset the fields directly
game.state.tokens[color] = saved_tokens
game.state.stats[color].captures_made = saved_captures
```

**What breaks.**

*Attempt A:* every rule now needs a matching un-rule, and the two must stay in sync forever. Add blocks, and you need un-block. Miss one and the board is subtly wrong, with no exception raised.

*Attempt B:* `Game` now knows the internal shape of `GameState`. Add a field to `GameState` and rollback silently stops restoring it. Nothing fails — the board is just quietly corrupt. That's the worst kind of bug, and [example 04](../../../learning/python/examples/04_mutability_and_copying.py) reproduces exactly this failure.

**The fix.** Let `GameState` package its own state into an opaque object, and let `Game` hold it *without ever looking inside*:

```python
before = self.state.snapshot()      # Game receives a sealed box
...
self.state.restore(before)          # and hands it back, unopened
```

`Game` never reads `before`. It couldn't corrupt the board through it if it tried. And when `GameState` grows a new field, only `snapshot`/`restore` change — the one place that already knows about it.

```mermaid
sequenceDiagram
    autonumber
    participant G as Game
    participant S as GameState

    Note over G,S: red's turn begins
    G->>S: snapshot()
    S-->>G: Snapshot — a sealed copy
    Note over G: Game stores it.<br/>It never opens it.

    G->>S: rolls 6 — moves token 0 out of base
    G->>S: rolls 6 — moves token 0, captures green
    Note over G,S: rolls a third 6 — the turn is void

    G->>S: restore(before)
    Note over S: token back in base,<br/>green's token back on the board,<br/>capture counters back to zero
```

**Where the name comes from.** A *memento* is a keepsake — a ticket stub or a pebble you keep to remember a day by. You don't take the day apart and store its pieces; you keep one small token that can bring the whole thing back. That is precisely what `Snapshot` is, and why the pattern isn't called "Undo" or "Backup": the emphasis is on the **opaque token**, not the restoring.

**The everyday version.** A save point in a video game. You have no idea how the game serialises its world, and you don't need to — you have "the save", and you can load it. If the game later adds weather, your save still works, because the game owns the format.

**Reach for it when** you need to restore a previous state **and** the undo logic would otherwise leak into whoever is calling. The second half matters: if the caller can already see all the state legitimately, you may just need a copy.

**Don't when** you need fine-grained, step-by-step undo — that's *Command* with an `undo()` per action. Memento restores a whole moment, not one step. Ludo cancels the entire turn, so Memento fits; a text editor's Ctrl-Z does not.

**The trap.** The memento must be a genuine **copy**, not a reference to live state. Get that wrong and `restore()` appears to work while doing nothing. See [example 04](../../../learning/python/examples/04_mutability_and_copying.py).

---

### 7.4 Record to a file *and* keep events in memory → **Composite**

**The problem.** The CLI needs both at once: stream the transcript to disk *and* keep the events in memory to print a summary when the game ends.

**What you'd write first.** Let `Game` hold a list of sinks:

```python
# NOT what the engine does
def __init__(self, config, sinks: list[EventSink]):
    self.sinks = sinks
...
for sink in self.sinks:
    sink.emit(...)
```

**What breaks.** Two things, and the second is nastier.

*`Game` now has two shapes to handle.* Every caller has to know whether it's holding one sink or several:

```python
if isinstance(sink, list):
    for s in sink:
        s.emit(type_, payload, turn)
else:
    sink.emit(type_, payload, turn)
```

*The sequence numbers diverge.* Each sink owns its own `_seq` counter, so calling `emit` on three sinks produces three independent numberings. The file and the in-memory copy stop agreeing about what event #7 was — and the [schema](../../../shared/schemas/README.md) requires one contiguous sequence.

---

#### The fix, and the shape that makes it work

Build a sink that **is** a sink and **contains** sinks:

```python
class TeeSink(EventSink):              # IS-A: usable anywhere a sink is
    def __init__(self, *sinks):
        self._sinks = sinks            # HAS-A: holds other sinks

    def _write(self, event):
        for sink in self._sinks:
            sink._write(event)         # pass the FINISHED event down
```

Two facts, and it's the **combination** that makes the pattern:

```mermaid
classDiagram
    class EventSink {
        <<the common type>>
        +emit(type, payload, turn)
        -_write(event)
    }
    class ListSink {
        <<leaf>>
        -_write(event)
    }
    class JsonlSink {
        <<leaf>>
        -_write(event)
    }
    class TeeSink {
        <<composite>>
        -_sinks
        -_write(event)
    }

    EventSink <|-- ListSink : is-a
    EventSink <|-- JsonlSink : is-a
    EventSink <|-- TeeSink : is-a
    TeeSink o--> EventSink : has-many

    note for TeeSink "TeeSink IS an EventSink, and HOLDS EventSinks.<br/>That loop back to its own base type is the entire pattern."
```

A class that is-a `X` *and* has-many `X` is an unusual shape, and it's worth pausing on — **that self-reference is Composite.** Everything else follows from it.

#### Why the loop buys you nesting for free

`TeeSink` accepts *any* `EventSink`. And `TeeSink` **is** an `EventSink`. So a `TeeSink` can hold a `TeeSink` — without anyone writing a line of code to allow it:

```python
sink = TeeSink(
    ListSink(),                                  # a leaf
    TeeSink(                                     # a composite INSIDE a composite
        JsonlSink(open("game.jsonl", "w")),
        JsonlSink(open("backup.jsonl", "w")),
    ),
)

game = Game(config, sink)      # Game's code does not change. At all.
```

```mermaid
flowchart TD
    game["Game<br/>holds exactly ONE sink"] --> t1["TeeSink<br/>composite"]

    t1 --> l1["ListSink<br/>leaf"]
    t1 --> t2["TeeSink<br/>composite again"]

    t2 --> j1["JsonlSink<br/>leaf"]
    t2 --> j2["JsonlSink<br/>leaf"]

    note1["Game's code is byte-identical whether it was<br/>handed the whole tree or a single ListSink"]
    game -.- note1
```

Depth is unlimited, and no code anywhere counts levels. Recursion falls out of the type structure rather than being programmed.

#### You already know this shape

```mermaid
flowchart TB
    subgraph fs["A file system — the shape you already know"]
        direction TB
        d1["Documents — folder"] --> f1["notes.txt — file"]
        d1 --> d2["Projects — folder"]
        d2 --> f2["main.py — file"]
        d2 --> d3["tests — folder"]
        d3 --> f3["test_main.py — file"]
    end

    subgraph sinks["This engine — the same shape"]
        direction TB
        s1["TeeSink — composite"] --> s2["ListSink — leaf"]
        s1 --> s3["TeeSink — composite"]
        s3 --> s4["JsonlSink — leaf"]
        s3 --> s5["JsonlSink — leaf"]
    end
```

A folder **contains** files and folders, and a folder **is** a file-system entry. That's the same is-a/has-a loop. It's why you can copy, move, rename, zip, or delete a folder using exactly the same command as a single file — and why nobody had to write a special "copy a folder five levels deep" feature.

#### One call, the whole tree

`Game` calls `emit` **once**. It has no idea how far the event travels:

```mermaid
sequenceDiagram
    autonumber
    participant G as Game
    participant T1 as TeeSink outer
    participant L as ListSink
    participant T2 as TeeSink inner
    participant J1 as JsonlSink game
    participant J2 as JsonlSink backup

    G->>T1: emit move_made
    Note over T1: assigns seq ONCE<br/>then delegates
    T1->>L: _write(event)
    T1->>T2: _write(event)
    T2->>J1: _write(event)
    T2->>J2: _write(event)
    Note over G: Game made one call and is done.<br/>Four destinations, one sequence number.
```

Note the detail that makes it correct: children receive `_write`, not `emit`. `emit` is where `seq` is assigned, so routing through it would let every child renumber independently — reintroducing exactly the bug the list version had.

---

**Where the name comes from.** "Composite" simply means *made up of parts*. The bit people miss is what the name is really asserting: the composite is **the same kind of thing as its parts**. A group of sinks isn't a new concept called "sink group" — it's just a sink. That sameness is what lets every caller stop caring.

**The everyday version.** A folder, as above. Also a moving box: a box of boxes is still just a box you pick up. And a company org chart — a department contains people and departments, and "headcount" works the same on either.

**Reach for it when** the caller keeps having to ask *"is this one, or many?"* — especially when you see `isinstance` checks or two parallel code paths that do the same thing at different arities. Make many *be* one.

**Don't when** parts and wholes genuinely behave differently. Forcing a uniform interface then produces methods that are meaningless for half the tree; the classic symptom is a leaf's `add_child()` that exists only to raise an exception.

### 7.5 "Is this one of the moves I allowed?" → **Value Object**

**The problem.** An agent hands back a `Move`. The engine must confirm it's one of the legal ones and reject it otherwise, because [an agent must not be able to cheat](../../decisions/adr-0004-structural-guardrails.md).

**What you'd write first.** The obvious check:

```python
if move in moves:      # with an ordinary class, `in` compares by IDENTITY
```

**What breaks.** The agent didn't return one of *our* objects — it built its own `Move(0, 3, 5)`. Same numbers, different object in memory. Identity comparison says "not legal", and **every legal move gets rejected**. Every turn forfeits. The game never progresses.

**The fix.** Make `Move` a *value*: immutable, with equality based on contents.

```python
@dataclass(frozen=True)
class Move:
    token: int
    frm: int
    to: int

Move(0, 3, 5) == Move(0, 3, 5)      # True — same value means same move
```

`frozen=True` does two jobs here. It makes equality-by-value safe, because the contents can't change after comparison. And it makes `Move` **hashable**, which unlocks the faster, clearer check the engine actually uses:

```python
allowed = set(moves)
if move in allowed: ...
```

**Where the name comes from.** From Domain-Driven Design, where things divide into **values** and **entities**. A value is defined entirely by *what it is*; an entity by *which one it is*. The name is doing real work — it's telling you identity is irrelevant.

**The everyday version.** A £10 note is a value: any £10 note is as good as any other, and you'd never demand *your specific* note back from a shopkeeper. Your passport is an entity: a perfect copy with identical details is emphatically **not** the same passport.

In this engine, `Move` and `Snapshot` are £10 notes. `Game` and `GameState` are passports — two `GameState`s holding identical tokens are still two different games.

**Reach for it when** you can answer "no" to: *if I swapped this for an identical-looking one, would anyone care?*

**Don't when** identity genuinely matters, or the object is large and copied constantly — immutability means every change allocates a new one.

---

### 7.6 "The engine must never import an LLM SDK" → **Ports and Adapters**

**The problem.** That rule is easy to state and easy to break by accident — one convenient import during a late-night debugging session and it's gone. How do you make it *structural* instead of a note in a README?

**The fix.** Notice the engine only ever needs two things from the outside world:

1. Someone to answer **"what's your move?"**
2. Somewhere to put **"here's what happened"**

Give each one an abstraction the core calls out through — a **port** — and let anything at all implement it — an **adapter**. The core's import list is then closed by construction.

```mermaid
flowchart LR
    cli[CLI]
    conf[conformance]
    tests[tests]

    subgraph core["engine core — imports nothing from outside"]
        direction TB
        game[Game]
        gstate[GameState]
        moves[moves]
        board[board]
        dice[Dice]
    end

    dport{{"PORT<br/>Decider"}}
    eport{{"PORT<br/>EventSink"}}

    fl[FirstLegal]
    rb[RandomBot]
    agents["agent harnesses<br/>Strands §9 · Spring AI §10 · LangGraph §11"]

    ls[ListSink]
    js[JsonlSink]
    ts[TeeSink]

    cli --> game
    conf --> game
    tests --> game

    game --> dport
    game --> eport

    dport -.-> fl
    dport -.-> rb
    dport -.-> agents
    eport -.-> ls
    eport -.-> js
    eport -.-> ts
```

**Reading it.** Adapters on the **left** are *driving* — they call into the engine. Adapters on the **right** are *driven* — the engine calls out to them. The distinction is just direction of control.

**Where the name comes from.** The metaphor is a physical device. A **port** is a socket of a defined shape that the device owns; an **adapter** is whatever plugs into it. You'll also see this called **Hexagonal Architecture** — Cockburn drew a hexagon purely so he could show several different ports around one core without implying a top-to-bottom stack. **The number six means nothing.** He later said he wished he'd led with "ports and adapters", because people kept asking why six.

**The everyday version.** Your laptop's USB-C port. The laptop defines the socket's shape and the protocol. It has no idea whether you'll plug in a monitor, a drive, or a charger — and it doesn't need to. Adding a new kind of peripheral never requires opening the laptop.

**Reach for it when** you have a rule of the form "X must never depend on Y." Turn the dependency into a port that X owns, and the rule stops being aspirational and starts being structural.

**Don't when** the program is small and each port will only ever have one adapter. Then it's indirection with nothing behind it.

**Why it matters here.** Two ports is the *entire* outside surface of the engine. That single fact is why the engine has no LLM dependency and can't acquire one by accident; why the UI and eval harness consume recorded games without importing a single engine class; and why the Java engine can be a straight port, with nothing framework-specific to translate.

---

### 7.7 The principles underneath

The six patterns above aren't six unrelated inventions. They're applications of a smaller set of ideas, usually taught as **SOLID**. Checked honestly against this engine:

| Principle | Plain English | Here |
|---|---|---|
| **S**ingle Responsibility | one reason to change | ✅ `board` geometry · `moves` rules · `dice` randomness · `events` output · `game` sequencing |
| **O**pen/Closed | extend without editing | ✅ New sinks and new agents need zero edits to `Game` |
| **L**iskov Substitution | any subtype works where the type is expected | ✅ Any `EventSink` for any other; same for `Decider` |
| **I**nterface Segregation | small interfaces beat big ones | ✅ `Decider` has exactly one method |
| **D**ependency Inversion | depend on abstractions, not concretions | ✅ `Game` depends on `Decider`, never on `RandomBot` |

**The thing worth actually remembering:** Strategy, Template Method and Ports & Adapters are all the *same two principles* — Open/Closed and Dependency Inversion — applied at different scales. One method, one class, one whole subsystem. If you internalise "depend on the shape, not the thing", you'll reinvent all three without needing the names.

**Where it's bent.** One genuine violation, left in deliberately:

```python
self.state.stats[color].turns_forfeited += 1        # game.py
```

Four levels of reaching through another object's internals. This breaks the **Law of Demeter** — "only talk to your immediate neighbours" — and "tell, don't ask" would put a `record_forfeit(color)` method on `GameState` instead. It's small enough to have been left alone, but if `Game` starts poking at more of `GameState`'s internals, that's the signal to fix it.

---

### 7.8 Rules of thumb, collected

If you remember nothing else:

| Pattern | The everyday version | Reach for it when… |
|---|---|---|
| **Strategy** | swappable drill bits | an `if`/`elif` branches on a *kind of thing*, each branch doing the same job differently |
| **Template Method** | a recipe with one step left to you | two methods are ~90% identical and differ in one step |
| **Memento** | a video-game save point | you need to restore a past state without the undo logic leaking to the caller |
| **Composite** | a folder holding files and folders | the caller keeps asking "is this one, or many?" |
| **Value Object** | a £10 note (vs a passport) | you'd never care *which* copy you got |
| **Ports & Adapters** | a USB-C socket | you have a rule "X must never depend on Y" and want it enforced, not hoped for |

And the one anti-rule: **if you can't name the problem that pushed you to it, you don't need the pattern.**

---

### 7.9 Recap

| Pattern | Source | Fit |
|---|---|---|
| **Strategy** | GoF behavioural | textbook |
| **Template Method** | GoF behavioural | textbook |
| **Memento** | GoF behavioural | textbook |
| **Composite** | GoF structural | textbook |
| **Value Object** | Evans, DDD | textbook |
| **Ports & Adapters** | Cockburn | textbook |
| **Dependency Injection** | — | textbook — `Game` is handed its sink rather than choosing one |
| **Facade** | GoF structural | *approximate* — `Game.play` is one call over the subsystem, but hides nothing you're forbidden to touch |
| **Event Sourcing** | Fowler | *approximate* — consumers rebuild from the log, but the engine keeps authoritative state too |

"Textbook" means all the pattern's roles are present and doing their job. "Approximate" means the shape rubs off but calling it the pattern would be a stretch. Most "patterns in our codebase" documents skip this distinction and over-claim — every dictionary becomes a Registry, every function a Factory.

## 8. Patterns deliberately not used

| Not used | Why |
|---|---|
| Abstract base classes (`ABC`) | `Protocol` gives the contract without forcing agents to import the engine |
| **Observer** | Sounds right for events, but there's no runtime subscribe/unsubscribe — one injected sink, composed statically by `TeeSink`. Registration would add lifecycle bugs for no gain. |
| **Factory / Abstract Factory** | Construction is trivial and explicit. A factory here would be indirection with nothing behind it. |
| **Singleton** | Everything hangs off a `Game` instance, so tests run independently and games can run in parallel. A singleton engine would make both impossible. |
| **Command** | `Move` is data, not an object with `execute()`/`undo()`. Undo is handled by Memento at turn granularity, which is what the rules actually need. |
| Multiple inheritance / mixins | Nothing needs it; it would obscure a codebase meant to be read |
| Class hierarchies for data | Records are flat dataclasses. Composition instead of an inheritance tree. |
| Exceptions for control flow | A failed turn returns `None`; only genuinely exceptional agent errors are caught |

One inheritance hierarchy, one protocol, everything else composition. That's the whole structural vocabulary — and the patterns above are descriptions of what emerged from the constraints, not a checklist that was applied up front.

---

## 9. The harness layer: the same turn, on Strands

Everything above ends at one dashed arrow: the engine calls a `Decider` and waits. This section is what now sits on the other side of that arrow in the first stack — the classes, who calls whom, and where the *framework* takes over from our code. The line-by-line walkthrough lives in [learning/strands](../../../learning/strands/), and [its doc 03](../../../learning/strands/03-the-full-picture.md) draws the same machine as a guided tour — construction wiring, the turn as a flowchart, and the memory map; these here are the reference diagrams.

One orientation rule before the diagrams: in the engine, our code calls our code. In the harness, the interesting arrows are the ones where **Strands calls us** — the `Model.stream()` it invokes, the lifecycle events it fires into `GameHooks`, the agents its `Swarm` activates. Framework programming is mostly arranging to be called well.

### 9.1 The harness object graph

```mermaid
flowchart LR
    subgraph eng ["engine — deterministic, no SDKs"]
        Game
    end

    subgraph strands ["stack-strands"]
        Dec["_Decider ×4"]
        H["LudoHarness"]
        P["Agent ×4 — the players"]
        SW["Swarm — fresh per turn"]
        GH["GameHooks"]
        SM["ScriptedModel"]
        PM["BedrockModel / AnthropicModel"]
        Tee["TeeSink"]
        Win["_EventWindow"]
    end

    Game -- "negotiate / choose / reflect" --> Dec
    Dec --> H
    H -- "agent(prompt) in choose, reflect" --> P
    H -- "constructs, one per negotiation" --> SW
    SW -- "activates, resets, hands off" --> P
    P -- "stream()" --> SM
    P -- "stream()" --> PM
    P -. "lifecycle events" .-> GH
    Game -- "engine events" --> Tee
    GH -- "llm_call, message_sent" --> Tee
    H -- "agent_reasoning, memory_write" --> Tee
    Tee --> Win
```

Reading the arrows:

- **The engine's world is unchanged.** It still talks to a `Decider` and a sink, and nothing else — every class on the right could be swapped for LangGraph's without the left half noticing. That is [ADR-0002](../../decisions/adr-0002-engine-per-language.md)'s boundary holding under load.
- **The dashed arrow is the framework calling us.** `GameHooks` never appears in the turn loop's code; the four `Agent`s fire events into it at Strands' own lifecycle points. Metering, the budget ceiling, and message capture all live on that arrow.
- **One `TeeSink`, three writers.** Engine events, hook events, and harness events interleave on a single sequence — which is what makes the transcript one ordered record instead of three ([ADR-0003](../../decisions/adr-0003-shared-event-stream.md)).
- **`Swarm` is not a member, it's a per-turn guest.** Constructed fresh each negotiation phase over the same four persistent agents, then discarded. Why that matters is §9.3.

### 9.2 One `choose`, as calls

The §3 diagram's `choose(TurnContext)` arrow, expanded. This is the only path that changes the game.

```mermaid
sequenceDiagram
    autonumber
    participant G as Game
    participant H as LudoHarness
    participant A as Agent red
    participant K as GameHooks
    participant M as Model
    participant E as TeeSink

    G->>H: choose(TurnContext)
    opt conversation over max_context_tokens
        H->>A: reduce_context — agent summarises ITSELF (one metered llm_call)
        H->>E: emit context_compacted
    end
    H->>H: render decide.md — board, legal moves, recent events, memory
    H->>A: agent(prompt)
    A->>K: BeforeModelCallEvent
    Note over K: budget spent? cancel the call
    A->>M: stream(messages, tools, system prompt)
    M-->>A: text events, then usage metadata
    A->>K: AfterModelCallEvent
    K->>E: emit llm_call — per-call usage, off the message
    A-->>H: AgentResult
    H->>E: emit agent_reasoning
    H-->>G: Move
    Note over G,H: engine validates. Illegal? attempt 2 renders retry.md into the SAME conversation, so the model sees its own rejected answer
```

What this makes obvious:

- **The harness never judges the move.** It parses, matches against the legal list, and returns — an unmatched reply goes back *as is*, because rejecting is the engine's job ([ADR-0004](../../decisions/adr-0004-structural-guardrails.md)).
- **`llm_call` is emitted by the hook, not the caller.** The turn loop cannot forget to meter a call, because it was never responsible for metering at all.
- **The budget gate sits inside the framework's loop.** `BeforeModelCallEvent.cancel` fires on *every* model invocation — including ones a swarm makes mid-conversation, where the harness has no line of code running.

### 9.3 One negotiation phase, as calls

The floor-passing table of [ADR-0009](../../decisions/adr-0009-swarm-negotiation.md): red opens, blue answers, red closes.

```mermaid
sequenceDiagram
    autonumber
    participant H as LudoHarness
    participant SW as Swarm
    participant R as Agent red
    participant B as Agent blue
    participant K as GameHooks
    participant E as TeeSink

    H->>R: seed briefing — memory, inbox
    H->>B: seed briefing
    H->>SW: construct — snapshots all four agents
    H->>SW: run(task)
    SW->>R: reset to snapshot, activate with the task
    R->>R: model calls handoff_to_agent(blue, message, table note)
    R->>K: AfterToolCallEvent
    K->>E: message_sent to blue, and to null for the note
    SW->>B: reset to snapshot, activate with the handoff message
    B->>B: model hands back to red
    B->>K: AfterToolCallEvent
    K->>E: message_sent to red
    SW->>R: reset AGAIN, activate
    R-->>SW: no handoff — conversation over
    SW-->>H: done
```

- **The harness's only moves are before the swarm exists** — seed briefings, construct, run. From then on the *models* steer, and the orchestrator enforces the floor, the cap, and the ending.
- **Step 15's "reset AGAIN" is the strangest and most important arrow.** Red's second activation starts from the construction snapshot — its briefing — not from what it said earlier in the phase. The reset that looks like a bug is the briefing delivery mechanism, and the reason durable memory is written at `reflect`, outside the swarm. [learning/strands/02](../../../learning/strands/02-the-swarm-table.md) walks the timeline.
- **Spoken words become events at the tool boundary.** No negotiation reply is ever parsed; the handoff tool call *is* the message, captured by the hook.

### 9.4 Who calls whom, harness edition

| Caller | Callee | When |
|---|---|---|
| `Game` | `_Decider` → `LudoHarness` | the three engine hooks, per turn |
| `LudoHarness` | `Agent.__call__` | choose, reflect |
| `LudoHarness` | `SummarizingConversationManager.reduce_context` | once per turn, when the conversation is over budget |
| `LudoHarness` | `Swarm` construct + run | once per negotiation phase |
| `Swarm` | `Agent` (reset, activate) | per floor holding |
| **Strands** | `Model.stream()` | every model invocation |
| **Strands** | `GameHooks` callbacks | before/after every model call, before every tool call (the guardrail gate), after every tool call |
| `GameHooks`, `LudoHarness`, `Game` | `TeeSink.emit` | one shared sequence |

The bolded rows are the framework calling us — the arrows that make this a *harness* rather than a library of helpers.

---

## 10. The harness layer, second take: the same turn on Spring AI

Same contract, same prompts, same events — a different country. §9's orientation rule was that framework programming under Strands is mostly *arranging to be called well*: the framework owns the loop and fires lifecycle events at you. Spring AI has the opposite grain, and it will feel familiar to anyone arriving from Spring: **you hold the objects and you call them** — a `ChatClient` per agent, one `ChatMemory` behind all four conversations, an advisor wiring them together per call. The framework calls back into harness code in exactly **one** place, and finding that place is the point of this section.

The stack's [README](../../../projects/ludo/stack-springai/README.md) states the design decisions; these are the reference diagrams. (`learning/springai` follows once the code stops moving.)

### 10.1 The harness object graph

```mermaid
flowchart LR
    subgraph eng ["engine-java — deterministic, no SDKs"]
        JG["Game"]
    end

    subgraph spring ["stack-springai"]
        SD["SpringDecider ×4"]
        HA["Harness"]
        CC["ChatClient ×4"]
        ADV["MessageChatMemoryAdvisor"]
        CM["ChatMemory<br/>one conversation per colour"]
        PF["pass_floor<br/>FunctionToolCallback"]
        TCM["ToolCallingManager"]
        SCM["ScriptedChatModel /<br/>AnthropicChatModel"]
        GR["Guardrails"]
        MEM["Memory ×4"]
        SES["Session — opt-in<br/>JdbcChatMemoryRepository → H2 file<br/>+ beliefs.json"]
        TEE["EventSink.TeeSink"]
        WIN["RecentWindow"]
    end

    JG -- "negotiate / choose / reflect" --> SD
    SD -- "implements Decider" --> HA
    HA -- "prompt()…call() in choose, reflect" --> CC
    HA -- "constructs, one per table run" --> PF
    CC -- "advised calls" --> ADV
    ADV -- "load before, save after" --> CM
    CM -. "backed by, when a session dir is given" .-> SES
    HA -- "persist() saves beliefs" --> SES
    CC -- "call(Prompt)" --> SCM
    SCM -. "executeToolCalls" .-> TCM
    TCM -. "execute" .-> PF
    PF -- "check every message" --> GR
    HA -- "write / render beliefs" --> MEM
    JG -- "engine events" --> TEE
    HA -- "llm_call, message_sent, memory_write" --> TEE
    TEE --> WIN
```

Reading the arrows:

- **The engine's half is untouched again — but this time the plug is written down.** `SpringDecider implements Decider` is a line the Python stacks never needed: Java's nominal typing demands it, and because of it the whole stack depends on the engine jar. The [capability matrix](../../architecture/stack-comparison.md#finding-the-java-agent-must-depend-on-the-engine-the-python-agents-need-not) predicted that row before any stack existed.
- **The dashed arrows are the only place the framework calls us.** In §9.1 the dashed arrow carried *every* lifecycle event. Here there is a single callback path: the model answers with a tool call, and the framework's `ToolCallingManager` executes `pass_floor` — harness code — before the caller ever sees a response.
- **Memory splits across two boxes — and the split runs all the way down into persistence.** The framework's `ChatMemory` holds *conversations* — decide and reflect, one per colour, selected per call by a conversation id. The hand-rolled `Memory` holds *beliefs* — notes and durable facts rendered into `{{memory}}`. Spring AI has no `AgentState` equivalent, so the second box is plain Java, recorded as **Manual** in the matrix. Give the harness a session directory and each box persists on its own terms: the conversation box backs itself with the framework's `JdbcChatMemoryRepository` (an embedded H2 file, written through on every exchange — no sync moment exists), while the belief box is saved by `Harness.persist()` in `play()`'s finally and reloaded at construction. Skip the save and conversations survive while beliefs vanish — the [recorded finding](../../architecture/stack-comparison.md#finding-spring-ai-persists-the-conversation-into-a-database--and-nothing-else), pinned by `SessionTest`.
- **The harness taps the stream by being a sink.** `RecentWindow extends EventSink`, and the tee's second child is the harness's own rolling window — the same trick as the Python stack's `_EventWindow`, spelled as inheritance because that's the Java engine's extension point (§2).

### 10.2 One `choose`, as calls

The same arrow as §3 and §9.2 — the only path that changes the game. The budget ceiling and the compaction check both live here.

```mermaid
sequenceDiagram
    autonumber
    participant G as Game
    participant H as Harness
    participant CC as ChatClient red
    participant ADV as MemoryAdvisor
    participant CM as ChatMemory
    participant M as ChatModel
    participant E as TeeSink

    G->>H: choose(TurnContext) via SpringDecider
    alt token ceiling spent
        H--xG: throw BudgetSpent — the engine records a forfeit, the game runs on
    end
    opt attempt 1, conversation over max_context_tokens
        H->>CC: askOneShot — summarise the oldest exchanges (metered, purpose compact)
        H->>CM: clear, rebuild as summary + "Noted." + recent 4
        H->>E: emit context_compacted
    end
    H->>H: render decide.md — board, legal moves, recent events, memory
    H->>CC: prompt().advisors(memoryAdvisor).call()
    CC->>ADV: around the call
    ADV->>CM: get(conversation "red")
    CM-->>ADV: history
    ADV->>M: call(Prompt — system + history + user)
    M-->>ADV: ChatResponse
    ADV->>CM: add the new exchange
    CC-->>H: ChatResponse
    H->>E: emit llm_call — usage from response metadata
    H->>E: emit agent_reasoning
    H-->>G: Move
    Note over G,H: engine validates. Illegal? attempt 2 sends retry.md down the SAME conversation — ChatMemory is why the model sees its own rejected answer
```

What this makes obvious:

- **The advisor *is* the conversation memory.** The harness never prepends history; it names a conversation (`CONVERSATION_ID = "red"`) and `MessageChatMemoryAdvisor` loads it before the call and saves the exchange after — Native, and genuinely free. It is also *all* Spring AI offers: the summarisation above it is harness code, because the framework's only management strategy is silent truncation — exactly what [harness-contract §5](harness-contract.md) forbids passing off as compaction.
- **Metering is at the call site, not in a hook.** `meter()` runs because `askInConversation` calls it — discipline, where Strands' `AfterModelCallEvent` made forgetting impossible. Whichever seam you pick, one `ChatResponse` is the unit of observation; §10.3 shows when that unit conceals more than one model invocation.
- **The budget exit is an exception.** `BudgetSpent` crosses the `implements` boundary and the engine turns it into the defined in-game outcome — a forfeited turn, not a crashed game (harness-contract §6).

### 10.3 One table round, as calls — and the hidden invocation

The floor-passing table of ADR-0009 again — but inverted. §9.3 was framework orchestration (`Swarm`) around our agents; this is harness orchestration (`runTable`'s loop) around a framework **action** (`pass_floor`). Watching one floor pass end-to-end also surfaces this stack's best finding.

```mermaid
sequenceDiagram
    autonumber
    participant H as Harness.runTable
    participant CC as ChatClient red
    participant SM as ScriptedChatModel
    participant TCM as ToolCallingManager
    participant PF as pass_floor tool
    participant GR as Guardrails
    participant E as TeeSink

    H->>H: render briefings ×4 and the shared task
    H->>CC: prompt().toolCallbacks(passFloor).call()
    CC->>SM: call(Prompt)
    SM->>SM: invocation 1 — AssistantMessage carrying a tool call
    SM->>TCM: executeToolCalls(prompt, response)
    TCM->>PF: execute(to, message, note)
    PF->>PF: floor cap? addressee valid? length cap?
    PF->>GR: check(message), check(note)
    alt out-of-fiction attack
        GR-->>PF: Violation
        PF->>E: emit guardrail_triggered
        PF-->>TCM: "message not delivered: reason"
    else clean — in-game cunning included
        PF->>E: emit message_sent (and the table note, to null)
        PF->>PF: fan out to inboxes, advance the floor
        PF-->>TCM: "delivered to blue"
    end
    TCM-->>SM: conversation history + tool result
    SM->>SM: invocation 2 — the reply, usage aggregated
    SM-->>CC: ONE ChatResponse
    CC-->>H: ChatResponse
    H->>E: emit llm_call — one event covering both invocations
    H->>H: delivered and under the cap? loop with the next holder's client
```

- **The action is Native even though the loop is Manual.** Spring AI has no swarm orchestrator, so the while-loop over floor holders is harness code — the honest, recorded gap this stack was always expected to produce. But the pass itself belongs to the framework: `pass_floor`'s schema reaches the model as framework-authored text (ADR-0009's parity boundary), and the framework executes it.
- **The guardrail gate is the tool body.** Strands offered a cancellable `BeforeToolCallEvent`; Spring AI has no interception point, so the gate moved *inside* the tool — which reads better, not worse: the tool's return string is the truth about delivery, and a model whose message bounced is told why in the same breath.
- **Everything between `call(Prompt)` and the single returned `ChatResponse` is invisible to the caller.** Two model invocations produced one `ChatResponse`. Usage is aggregated, so nothing goes unmetered — but per-invocation granularity is gone, and no seam available to the harness sees the middle. That is the [recorded finding](../../architecture/stack-comparison.md#finding-spring-ais-internal-tool-execution-hides-model-invocations-from-the-caller); live play will set `internalToolExecutionEnabled(false)` to get the granularity back.
- **The tool holds the table.** `pass_floor` is built fresh per table run and closes over the `TableState` — holder, pass count, delivery flag. The framework executes the action; the state it acts on stays the harness's.

### 10.4 Who calls whom — and the same turn on two grains

| Caller | Callee | When |
|---|---|---|
| `Game` | `SpringDecider` → `Harness` | the three engine hooks, per turn — through a written `implements` |
| `Harness` | `ChatClient.prompt()…call()` | choose and reflect (advised), table and compaction (one-shot) |
| `ChatClient` | `MessageChatMemoryAdvisor` → `ChatMemory` | around every advised call — history in before, exchange saved after |
| `ChatClient` | `ChatModel.call(Prompt)` | every model invocation the harness *makes* |
| **Spring AI** | `pass_floor` — harness code | when the model answers with a tool call: the framework's one call into us |
| `pass_floor` | `Guardrails.check` | every message and table note, before anything delivers |
| `Harness.persist()` | `Session.saveBeliefs` | `play()`'s finally — the half the framework cannot save |
| `Harness`, `pass_floor`, `Game` | `EventSink.TeeSink.emit` | one shared sequence |

One bolded row, where §9.4 had three — and that count *is* the comparison, at class level:

| | Strands (§9) | Spring AI (§10) |
|---|---|---|
| The framework calls us… | model stream, every lifecycle hook, every swarm activation | during tool execution — once |
| Negotiation | `Swarm` orchestrates; the harness seeds briefings and stands back | the harness loop orchestrates; the framework executes the pass |
| Conversation memory | the `Agent` *is* its conversation | `ChatMemory`, selected per call through an advisor |
| Compaction | Native summariser — with the hook-bypass trap | hand-rolled — the framework only truncates |
| Metering seam | `AfterModelCallEvent`: impossible to forget | the call site: disciplined, and blind to internal invocations |
| Session persistence | `FileSessionManager`: one store, everything, on the framework's sync schedule | JDBC repository: conversations write through continuously; beliefs saved by hand |

Neither column is "the better framework" — the [capability matrix](../../architecture/stack-comparison.md) keeps the full scoreboard, with evidence links. What the two sections show side by side is the **grain**: Strands is a loop you decorate; Spring AI is a toolkit you drive.

---

## 11. The harness layer, third take: the same turn on LangGraph

Third framework, third grain. Strands was *a loop you decorate* — the framework runs the show and fires hooks at you. Spring AI was *a toolkit you drive* — you hold the objects and call them. LangGraph is **a graph you draw**: you declare nodes and edges, hand the drawing to a runtime, and the framework executes *your* control flow over state *it* owns. Almost nothing in this stack is a method call on an object the harness holds — it is state moving through a machine the harness declared. The stack's [README](../../../projects/ludo/stack-langgraph/README.md) states the design decisions; these are the reference diagrams. (`learning/langgraph` follows once the code stops moving.)

### 11.1 The harness object graph

```mermaid
flowchart LR
    subgraph eng ["engine-python — deterministic, no SDKs"]
        PG["Game"]
    end

    subgraph lg ["stack-langgraph"]
        DEC["_Decider ×4"]
        LH["LudoHarness"]
        PA["player agents ×4<br/>create_agent — compiled graphs"]
        MW["BudgetGate + Compactor<br/>middleware"]
        CP["checkpointer<br/>one thread per colour"]
        ST["Store<br/>('beliefs', colour) namespaces"]
        TB["Table — a fresh StateGraph per turn<br/>brief → speak → tools"]
        PF["pass_floor tool"]
        GR["guardrails"]
        MT["Meter — callback handler"]
        SM["ScriptedChatModel /<br/>ChatAnthropic"]
        TEE["TeeSink"]
        WIN["_EventWindow"]
    end

    PG -- "negotiate / choose / reflect" --> DEC
    DEC --> LH
    LH -- "invoke(thread_id=colour) in choose, reflect" --> PA
    PA -- "before_model" --> MW
    PA -- "load state before, save after every step" --> CP
    PA -- "model calls" --> SM
    LH -- "draws, one per negotiation" --> TB
    TB -- "speak: one call per floor holding" --> SM
    TB -. "ToolNode executes" .-> PF
    PF --> GR
    LH -- "write_note / render_memory" --> ST
    MW -- "absorb summaries" --> ST
    SM -. "on_llm_end" .-> MT
    PG -- "engine events" --> TEE
    MT -- "llm_call" --> TEE
    LH -- "agent_reasoning, memory_write" --> TEE
    PF -- "message_sent, guardrail_triggered" --> TEE
    TEE --> WIN
```

Reading the arrows:

- **The engine's half is untouched a third time** — same `Protocol`, same three hooks, and every box on the right could be swapped for either other stack's without the left half noticing. Three stacks in, that boundary has now held under three different architectures.
- **The harness holds no conversation.** `invoke(thread_id="red")` *selects* one — the checkpointer owns the state and loads/saves it around every step. Spring AI's `CONVERSATION_ID` was the same idea one layer up; Strands' agent-owns-its-messages was the opposite.
- **Two dashed arrow families, both the framework calling us:** `ToolNode` executing `pass_floor` (as Spring AI's `ToolCallingManager` did), and the callback system firing `on_llm_end` into the `Meter` for *every* model call made anywhere under an invoke — the summariser's included, which is precisely the property Strands' summariser lacked.
- **Beliefs finally have a first-class home.** The `Store` is the only dedicated belief-store primitive among the three frameworks — Strands repurposed `AgentState`, Spring AI hand-rolled a class. Both the harness (reflect notes) and the middleware (compaction summaries) write to it.

### 11.2 One `choose`, as calls

Same arrow as §3, §9.2, §10.2. The budget gate and the compactor ride *inside* the framework's loop as middleware — the harness checks nothing at call time.

```mermaid
sequenceDiagram
    autonumber
    participant G as Game
    participant H as LudoHarness
    participant A as player agent red
    participant BG as BudgetGate
    participant CM as Compactor
    participant CP as checkpointer
    participant M as model
    participant MT as Meter
    participant E as TeeSink

    G->>H: choose(TurnContext) via _Decider
    alt token ceiling spent
        H--xG: raise BudgetExceeded — the engine records a forfeit
    end
    H->>H: render decide.md — board, legal moves, recent events, memory
    H->>A: invoke(messages=[prompt], thread_id=red, callbacks=[Meter])
    A->>CP: load thread state
    A->>BG: before_model — ceiling spent mid-phase? jump to end
    A->>CM: before_model — thread over max_context_tokens?
    opt over budget
        CM->>M: summary call (the agent's own model)
        M-->>MT: on_llm_end — llm_call, purpose compact
        CM->>CM: rewrite thread: RemoveMessage(ALL) + summary + preserved
        CM->>E: emit context_compacted, absorb summary into Store
    end
    A->>M: model call
    M-->>MT: on_llm_end — llm_call, purpose move
    A->>CP: save the new exchange
    A-->>H: final state
    H->>E: emit agent_reasoning
    H-->>G: Move
    Note over G,H: engine validates. Illegal? attempt 2 invokes the SAME thread with retry.md — the model sees its own rejected answer because the checkpointer says so
```

What this makes obvious:

- **Middleware is where hooks and advisors were.** The budget backstop and the compactor sit at the framework's documented extension point, inside its loop — the same job `GameHooks` did by event and `MessageChatMemoryAdvisor` did by wrapping, done here by declaration.
- **The compaction moment belongs to the framework.** The harness never checks the budget before a call the way the other two stacks do — the middleware fires inside the invocation when its trigger says so. The trigger is the *game's* number; the moment is the framework's.
- **Metering is subscription, not discipline.** One callback handler passed at the top propagates to every model call underneath, however deep. Strands made forgetting impossible by hook; Spring AI made it a call-site habit; LangGraph makes it a property of config propagation.

### 11.3 One table round — the protocol as a drawn graph

The other two stacks *describe* ADR-0009's floor-passing protocol in code. This stack **draws it** — the graph below is not documentation of `table.py`, it *is* `table.py`, node for node, edge for edge:

```mermaid
flowchart LR
    S((START)) --> B["brief<br/>wipe the channel, seed the<br/>holder's PRIVATE context"]
    B --> K["speak<br/>one model call,<br/>pass_floor bound"]
    K -- "tool call" --> T["tools<br/>ToolNode runs pass_floor:<br/>cap · validity · guardrail · deliver"]
    K -- "plain text — the floor lapses" --> E((END))
    T -- "delivered, under the cap<br/>(floor moves via Command)" --> B
    T -- "blocked — the model reads why" --> K
    T -- "pass cap reached" --> E
```

And one delivered pass through it, as calls:

```mermaid
sequenceDiagram
    autonumber
    participant H as LudoHarness
    participant TG as Table graph
    participant M as model (holder)
    participant TN as ToolNode
    participant PF as pass_floor
    participant GR as guardrails
    participant E as TeeSink

    H->>TG: invoke(holder=red, callbacks=[Meter], recursion_limit)
    TG->>TG: brief — RemoveMessage(ALL) + red's briefing, task, incoming message
    TG->>M: speak — bind_tools([pass_floor]), one call
    M-->>TG: AIMessage with a pass_floor tool call
    TG->>TN: route: tools_condition
    TN->>PF: execute(to=blue, message, note)
    PF->>GR: check(message), check(note)
    alt out-of-fiction attack
        PF->>E: emit guardrail_triggered
        PF-->>TN: "message not delivered: reason" — state unchanged
        Note over TG: edge routes back to speak — same holder reads why
    else clean — cunning included
        PF->>E: emit message_sent (and the note, to null)
        PF-->>TN: Command(update: holder=blue, passes+1, delivered)
        Note over TG: edge routes to brief — the floor has moved
    end
```

- **The framework executes the tool and applies its state update.** `pass_floor` returns a `Command` — the same mechanism the rejected swarm package's handoff uses — and `ToolNode` folds it into graph state. The harness wrote the tool body; everything around it is the framework's.
- **Privacy is a wipe, not a wall.** `brief` starts every holding with `RemoveMessage(REMOVE_ALL_MESSAGES)` — the identical primitive the framework's own summariser rewrites history with — so no holder ever sees another's words except the one message addressed to them. This is what `langgraph-swarm` structurally could not do, and why it was [rejected on evidence](../../architecture/stack-comparison.md#finding-langgraph-swarm-cannot-carry-ludos-negotiation-protocol--the-primitive-underneath-can).
- **Every invocation is visible.** A delivered pass is one metered call; a blocked attempt is two (the model reads the rejection and answers again). Spring AI's internal tool execution hid the middle of exactly this loop; LangGraph's graph *is* the middle, drawn.
- **The runaway bound is the framework's.** A live model stuck retrying a blocked pass burns down `recursion_limit` and the phase is abandoned (harness-contract §2.1) — no hand-rolled attempt counter.

### 11.4 Who calls whom — and the same turn on three grains

| Caller | Callee | When |
|---|---|---|
| `Game` | `_Decider` → `LudoHarness` | the three engine hooks, per turn — by shape, no `implements` |
| `LudoHarness` | `player_agent.invoke(thread_id=colour)` | choose and reflect — the framework loads and saves the thread |
| **LangGraph** | `BudgetGate` / `Compactor` `.before_model` | inside every player invocation — middleware, the extension point |
| **LangGraph** | `pass_floor` — harness code | when the table model calls the tool: `ToolNode` executes it |
| **LangChain** | `Meter.on_llm_end` | after every model call anywhere under an invoke — summariser included |
| `LudoHarness`, `Compactor` | `Store.put` / `search` | reflect notes, compaction folds, memory renders |
| `pass_floor`, `Meter`, `LudoHarness`, `Game` | `TeeSink.emit` | one shared sequence |

Three bolded rows — between §9's three and §10's one — and now the full comparison the two earlier sections could only start:

| | Strands (§9) | LangGraph (§11) | Spring AI (§10) |
|---|---|---|---|
| The grain | a loop you decorate | a graph you draw | a toolkit you drive |
| The framework calls us… | at every lifecycle point | at middleware, tools, callbacks | during tool execution — once |
| Negotiation | prebuilt `Swarm` orchestrates | the protocol drawn as a `StateGraph` | harness while-loop orchestrates |
| Conversation memory | the `Agent` *is* its conversation | a checkpointer thread, selected per call | `ChatMemory`, selected per call via advisor |
| Beliefs | `AgentState`, repurposed | the `Store` — a dedicated primitive | hand-rolled class — nothing to repurpose |
| Compaction | Native summariser, hook-bypass trap | Native middleware, no trap — both pre-registered questions answered yes | hand-rolled — the framework only truncates |
| Metering seam | `AfterModelCallEvent`: unforgettable | callback propagation: subscription | the call site: discipline, blind to internal invocations |
| Session persistence | one store, everything, framework's sync schedule | swap two stores for sqlite twins — **no save call exists** | conversations write through; beliefs saved by hand |

No column wins — the [capability matrix](../../architecture/stack-comparison.md) keeps the scoreboard with evidence. What the three sections show together is that the *same observable game* — same prompts, same events, same protocol — sits naturally on three architectures that agree about almost nothing else.

---

## What comes next

This diagram will grow. Expected additions, roughly in build order:

| Component | Shape it will take |
|---|---|
| **Agent stacks** | ✅ All three drawn — `stack-strands` (§9), `stack-springai` (§10), `stack-langgraph` (§11) — ending in §11.4's three-grain table. The diffs between the sections are [capability-matrix](../../architecture/stack-comparison.md) material, and every future stack-side change updates its section in the same commit. |
| **`engine-java`** | ✅ **Built.** Mirrors this graph, with `Protocol` becoming an `interface` and frozen dataclasses becoming `record`s — see [engine-design.md](engine-design.md#porting-to-java). The optional hooks became `default` methods, and `Game` gained an `IntSupplier` seam Python did not need. |
| **Eval harness** | ✅ **Built** ([`projects/ludo/eval`](../../../projects/ludo/eval/README.md)) — and the prediction held: it reads transcripts only, with *no* arrow into the engine, no stack imports, no SDK. Its fold self-verifies against `game_ended.standings`, which is the discipline that replaces the arrow. |
| **UI** | ✅ Same — consumes the event stream, never the classes. Proven three times over by fixture growth without source changes (ADR-0007). |

If a future component needs an arrow *into* the engine that isn't `Decider`, that's worth challenging: it likely means something is bypassing the event stream.

---

## Viewing these diagrams

The blocks above are [Mermaid](https://mermaid.js.org/). They render automatically on GitHub, in VS Code with a Markdown preview extension, and in most JetBrains IDEs. In a plain terminal you'll see the source — which is still readable, and is why the tables duplicate the key relationships in text.

If one of them ever shows an error box instead of a picture, that's a bug worth reporting: every block on this page is parsed by mermaid itself in CI ([`scripts/check_mermaid.mjs`](../../../scripts/check_mermaid.mjs)), so a diagram that doesn't render should not have reached you.
