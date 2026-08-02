# Shared Prompts

The prompts every stack sends, byte-for-byte identical. If Strands and Spring AI ran different prompts, the framework comparison would measure the prompts instead — so these live here, outside all three stacks, and no stack may edit them for itself.

Project-scoped: [`ludo/`](ludo/). A second project gets its own directory.

## Layout mirrors the cache boundary

```
ludo/
  manifest.yaml     what to load, in what order, and which variables each file takes
  system/           never changes within a game   -> prompt-cacheable
  turn/             rebuilt every turn            -> never cached
```

That split is the whole reason the directories exist. The system layer is concatenated once and stays byte-identical for the rest of the game, which is what lets a provider cache it. Put a per-turn value in `system/` and caching silently stops working — cost jumps, nothing errors, and you find out from a bill.

## Substitution is literal, and that is deliberate

`{{name}}` is replaced with a string. That is the entire template language.

**No conditionals, no loops, no filters.** Not because they wouldn't be convenient, but because Python and Java would have to implement them identically and they wouldn't. Jinja2 has no exact JVM twin; Mustache implementations disagree at the edges on whitespace and empty values. Every one of those disagreements would be an invisible parity break in the one file that is supposed to guarantee parity.

So the rule is: **if a section needs logic, the code renders it and passes the result in as one variable.** A list of legal moves is formatted by the stack and arrives as `{{legal_moves}}`, already a string.

The cost is about ten lines per language:

```python
def render(template: str, values: dict[str, str]) -> str:
    for name, value in values.items():
        template = template.replace("{{" + name + "}}", str(value))
    return template
```

## One agent prompt, not four

[`system/identity.md`](ludo/system/identity.md) takes `{{color}}` and nothing else. There is no per-colour prompt and no assigned persona — no "you are the aggressive one."

Whether four models given identical instructions develop distinguishable playing styles is one of the things this project is actually trying to find out. Writing the personalities in would answer the question before asking it. [`check_prompts.py`](../../scripts/check_prompts.py) enforces the single-file rule, because it is exactly the kind of thing that erodes at 2am while debugging one agent's bad play.

## Rules in the prompt are consequence-only

[`system/rules.md`](ludo/system/rules.md) does not teach legality. It doesn't need to: the engine validates every move and only ever offers the agent choices that are already legal ([ADR-0004](../../docs/decisions/adr-0004-structural-guardrails.md)). An agent never has to work out whether it may leave base on a 3, because that option is simply not in the list.

What it *does* teach is consequence — what capture costs, what a safe square protects, why three sixes is a trap. That is a much smaller prompt, fully cached, and it drifts less because there is less of it.

The trailing **numbers table** is checked against the engine's constants on every CI run. Two rulebooks that disagree would have agents playing a game the engine won't allow — which looks like the agents being stupid, not like a bug in a markdown file.

The normative rules remain [game-rules.md](../../docs/projects/ludo/game-rules.md). This file is a briefing derived from it.

## Provenance

Prompts change. Transcripts recorded under an older set are not comparable with newer ones, and nothing about a JSONL file makes that visible on its own.

So a stack hashes the prompt set at load and emits it in `game_started`:

```json
"prompt_set": {"version": 1, "hash": "sha256:1f4a…"}
```

A version number alone can be forgotten on the way out the door. A hash cannot.

## Changing a prompt

Same discipline as the [event schema](../schemas/README.md): all three stacks land together, and previously recorded transcripts become historical rather than comparable. Bump `version` in `manifest.yaml` when the meaning changes, not when a typo is fixed — the hash already covers exact bytes.

Then:

```bash
uv run scripts/check_prompts.py
```

## Not written yet

**The judge prompt.** It belongs with the [evaluation harness](../../docs/projects/ludo/evaluation.md), which doesn't exist. Writing it now would mean guessing at the shape of an interface nothing implements. `shared/models.yaml` already reserves the judge seat.
