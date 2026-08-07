# 02 — The seal

## The problem, before the solution

RELAY's whole decision — *can I do this?* — evaporates if the runner is told how hard the stage is. So the tier must never reach it.

But your code has the tier. The generator computed it. The engine stores it. The transcript carries it. The UI loads the whole file. At every one of those layers, the fact is *right there*, one attribute access away from leaking.

"Don't put it in the prompt" is not a design. It is a promise, and promises decay.

## Before you scroll

You have a `Stage` object with a `tier` field, and a prompt-rendering function that takes a stage. **How do you make it impossible to render the tier?**

## The answer is a type

```python
@dataclass(frozen=True)
class Stage:
    id: str
    family: str
    tier: int          # <- the secret
    prompt: str
    answer: str        # <- the other secret

    def public(self) -> PublicStage:
        return PublicStage(self.id, self.family, self.prompt)


@dataclass(frozen=True)
class PublicStage:
    id: str
    family: str
    prompt: str
```

`RunnerView` is built from a `PublicStage`. Not from a `Stage` with the fields hidden behind a property, or a dict with keys popped — from an object that **has no such field**.

**The handle: you cannot leak a field the object does not have.** A harness that wanted to cheat would have to be handed a `Stage`, and the only thing holding one is the engine.

There is a test for it, and it is two lines:

```python
public = stage.public()
assert not hasattr(public, "tier")
assert not hasattr(public, "answer")
```

## Four layers, four different enforcements

A type solves it in one layer. The fact travels through four, and each needs its own answer.

| Layer | The risk | The enforcement |
|---|---|---|
| **Engine → runner** | rendering a tier into a prompt | `PublicStage` has no field to render |
| **Transcript** | a replay showing what the runners could not see | `track_generated` carries prompts; `game_ended.track_key` carries tiers, and nothing in between does |
| **Prompts** | a briefing that names a tier, or a manifest declaring `{{tier}}` | `check_prompts.py` fails on either |
| **UI** | the player holds the whole file, `game_ended` included | `replay(events, upTo)` only populates `trackKey` once that event is reached — and the test walks *every* sequence number of every fixture |

Notice that the enforcements are all different in kind: a type, a schema, a linter, and a test over a state machine. The fact does not care which layer it escapes through, so each layer needs the mechanism that actually works there.

## The check that was too clever

The prompt checker's first version banned the phrase "difficulty tier" anywhere in the RELAY prompt set.

It immediately failed the briefing — which *has* to explain that tiers exist, because the runners have to know what they are being asked to judge. Explaining the concept is required; naming which one you are looking at is the leak.

So it now bans two precise things:

```python
TIER_WORDS = ("tier 1", "tier 2", "tier 3", "tier-1", ...)
FORBIDDEN_VARIABLES = {"tier", "difficulty", "answer", "solution", "track_key"}
```

The variable ban is the one that matters more. A template naming "tier 2" is a typo somebody would notice. A manifest quietly declaring `{{tier}}` is a harness change that deletes the game and passes every other check in the file.

**The handle: check the mechanism, not the vocabulary.** Banning words catches the careless; banning the channel catches the plausible.

## What the seal buys

It is not just fairness. Because the tier is revealed at `game_ended` and *only* there, the eval can do something no other project in this repo can: score the **decision** rather than the outcome.

That is [03 — measuring a decision](03-measuring-a-decision.md), and it only works because the runners were genuinely blind.

## Check yourself

1. Why is `PublicStage` a separate class rather than `Stage` with `tier` marked private?
2. `stage_attempted.answer` contains the correct answer when a runner is right. Why is that not a leak?
3. A harness caches a previously committed transcript of the same seed to "speed up testing". What has it just broken?
4. The UI test asserts `trackKey` is absent at every seq before `game_ended`. Why is checking only the final state insufficient?

## Next

[03 — measuring a decision](03-measuring-a-decision.md): precision, recall, fit — and the race where the winner scored zero.
