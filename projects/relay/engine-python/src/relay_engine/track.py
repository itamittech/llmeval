"""The track: stage generation and answer checking.

Every stage is generated forward from the seed, so the answer is known by
construction and never has to be solved by the engine. Three families with a
difficulty ladder, per game-rules.md.

Two properties are load-bearing and easy to break:

- **The prompts are corpus bytes.** They ride inside the transcript, so the
  conformance digest covers them: a Java port that renders one space
  differently fails every vector. Everything here is ASCII, integer-only, and
  built by plain concatenation — no locale-sensitive formatting anywhere.
- **The tier is not in the prompt.** It is metadata the engine keeps and the
  transcript reveals only at `game_ended`. A generator that leaked difficulty
  into the wording (longer sentences for tier 3, say) would quietly hand the
  runners the one thing the game asks them to judge for themselves.
"""

from __future__ import annotations

from dataclasses import dataclass

from .rng import Rng

FAMILIES = ("chain", "cipher", "order")

#: Stages on the track, and the tier multiset dealt across them. The multiset
#: is shuffled, so position tells a runner nothing.
TRACK_STAGES = 10
TIER_MULTISET = (1, 1, 1, 1, 2, 2, 2, 2, 3, 3)

#: chain: how many operations per tier.
CHAIN_STEPS = {1: 2, 2: 4, 3: 6}
#: cipher: which word pool per tier. Tier 3 reuses the long pool and withholds
#: the shift instead — harder by inference, not by length.
CIPHER_SHORT = ("iron", "moss", "lamp", "reed", "sail", "vine", "clay", "dusk")
CIPHER_LONG = ("mariner", "lantern", "kestrel", "harvest", "tundra", "cobalt",
               "quarry", "silence")
#: order: names are single lowercase ASCII words so the answer is one token.
ORDER_NAMES = ("ada", "brun", "cyd", "dev", "esme", "fen", "gil", "hana")
ORDER_ITEMS = {1: 3, 2: 4, 3: 5}
ORDINALS = ("first", "second", "third", "fourth", "fifth")


@dataclass(frozen=True)
class PublicStage:
    """What a runner is allowed to see: the puzzle, and nothing else."""

    id: str
    family: str
    prompt: str


@dataclass(frozen=True)
class Stage:
    id: str
    family: str
    tier: int
    prompt: str
    answer: str

    def public(self) -> PublicStage:
        return PublicStage(self.id, self.family, self.prompt)


def normalise(answer: str) -> str:
    """How an answer is compared. Forgiving about wrapping, strict about the
    token itself — models add trailing full stops and capitals, and neither is
    a wrong answer."""
    return answer.strip().rstrip(".").strip().lower()


def generate(rng: Rng, stages: int = TRACK_STAGES) -> tuple[Stage, ...]:
    """Draw order is spec: tiers first (one shuffle), then each stage's family
    and body in track order."""
    tiers = list(TIER_MULTISET[:stages])
    rng.shuffle(tiers)

    built: list[Stage] = []
    for index in range(stages):
        family = FAMILIES[rng.below(len(FAMILIES))]
        tier = tiers[index]
        prompt, answer = _BUILDERS[family](rng, tier)
        built.append(Stage(f"stage-{index + 1:02d}", family, tier, prompt, answer))
    return tuple(built)


# -- families --------------------------------------------------------------


def _chain(rng: Rng, tier: int) -> tuple[str, str]:
    """Integer arithmetic, applied in order. Mechanical: a program is perfect
    at these, and so is a small model — which is exactly why the track needs
    the other two families."""
    value = rng.between(1, 20)
    parts = [f"Start with {value}."]
    # Multiplying by three only appears at tier 3, where the numbers also get
    # large enough that a careless step compounds.
    kinds = 3 if tier < 3 else 4
    for _ in range(CHAIN_STEPS[tier]):
        kind = rng.below(kinds)
        if kind == 0:
            n = rng.between(2, 10)
            value += n
            parts.append(f"Add {n}.")
        elif kind == 1:
            n = rng.between(2, 10)
            value -= n
            parts.append(f"Subtract {n}.")
        elif kind == 2:
            value *= 2
            parts.append("Double it.")
        else:
            value *= 3
            parts.append("Triple it.")
    parts.append("What number do you end with?")
    return " ".join(parts), str(value)


def _cipher(rng: Rng, tier: int) -> tuple[str, str]:
    """A Caesar shift. Tier 3 withholds the shift and gives a crib instead, so
    the puzzle becomes two steps: recover the shift, then apply it."""
    pool = CIPHER_SHORT if tier == 1 else CIPHER_LONG
    word = pool[rng.below(len(pool))]
    shift = rng.between(1, 25)
    encoded = _caesar(word, shift).upper()

    if tier < 3:
        prompt = (f"Every letter of a word was shifted forward {shift} places "
                  f"through the alphabet, wrapping from z back to a, giving "
                  f"{encoded}. What was the original word?")
    else:
        prompt = (f"Every letter of a word was shifted forward through the "
                  f"alphabet by the same unknown number of places, wrapping "
                  f"from z back to a, giving {encoded}. The original word "
                  f"begins with '{word[0]}'. What was the original word?")
    return prompt, word


def _caesar(word: str, shift: int) -> str:
    out = []
    for ch in word:
        out.append(chr(ord("a") + (ord(ch) - ord("a") + shift) % 26))
    return "".join(out)


def _order(rng: Rng, tier: int) -> tuple[str, str]:
    """Pairwise constraints that pin one total order. The constraints are
    always the n-1 consecutive links — enough for exactly one solution — with
    their statement order shuffled so the reader has to reassemble the chain.
    Tier 3 adds one true-but-redundant negative fact: noise, not ambiguity."""
    count = ORDER_ITEMS[tier]
    order = rng.sample(list(ORDER_NAMES), count)

    facts = [f"{order[i]} is somewhere before {order[i + 1]}."
             for i in range(count - 1)]
    if tier == 3:
        # Any name except the last one; the statement is true, and it rules out
        # nothing the chain did not already rule out.
        not_last = order[rng.below(count - 1)]
        facts.append(f"{not_last} is not last.")
    rng.shuffle(facts)

    position = rng.below(count)
    prompt = (f"{count} runners crossed the line one at a time. "
              + " ".join(facts)
              + f" Who finished {ORDINALS[position]}? "
                f"Answer with one name.")
    return prompt, order[position]


_BUILDERS = {"chain": _chain, "cipher": _cipher, "order": _order}
