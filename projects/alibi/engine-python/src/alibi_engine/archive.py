"""The archive: generated testimony, and the baseline retriever.

Everything here is deterministic from the game seed — templates and draws, no
LLM anywhere (the engine rule). The Java engine reproduces this byte for byte,
so the draw order is spec:

    1. shuffle the 16 non-solution elements, take 8  -> the exonerated set
    2. shuffle the witness pool                      -> first 3 lie, rest are honest
    3. one neutral-spot pick per who-dimension exoneration, in build order
    4. per gossip document: one template pick, one suspect pick
    5. one final shuffle over all assembled documents, then ids doc-001..

The truth model is deliberately simple enough to teach:

- An **exoneration** truthfully rules one non-solution element out. Only 8 of
  the 16 get one — the archive alone can never solve the case; the table can.
- A **red herring** uses the *same templates* to "rule out" each solution
  element. Indistinguishable by style, on purpose: the only way to catch one
  is cross-checking its witness.
- Every red herring's witness is undermined by exactly one truthful
  **counter** document — the solvability guarantee of game-rules.md.
- **Gossip** asserts nothing eliminable. It exists so retrieval has noise to
  rank against, and so the fiction breathes.

Which documents lied is revealed only in `game_ended.red_herrings`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .case import DISPLAY, WHO, Case, dimension_of
from .rng import Rng

#: Default results per search, and the per-turn allowance lives in GameConfig.
SEARCH_K = 3

WITNESSES: tuple[str, ...] = (
    "head waiter Colin Pereira",
    "security guard Asha Nair",
    "pianist Leo Fernandes",
    "housekeeper Rekha Iyer",
    "bartender Sam Dutta",
    "florist Maria Gomes",
    "doorman Ravi Menon",
    "sous-chef Priya Nayak",
)

#: Locations that are deliberately NOT place elements, so an alibi for a
#: suspect never accidentally says anything about a place.
NEUTRAL_SPOTS: tuple[str, ...] = ("main stage", "reception desk", "front lawn", "buffet line")

#: Why each method was impossible — true of every method except the one used.
METHOD_FACTS: dict[str, str] = {
    "sleight-of-hand": "the display case was fitted with a weight sensor, and it never tripped — nothing was lifted by hand",
    "duplicate-key": "the vault key never left the manager's chain, and the hourly key checks all passed",
    "service-hatch": "the service hatch was bolted and painted shut since the spring renovation",
    "blackout": "the generators kept every light burning all evening; there was no blackout",
    "forged-pass": "every pass scanned that night matched the printed guest register exactly",
}

GOSSIP_TEMPLATES: tuple[str, ...] = (
    "{witness} remarks: {suspect} seemed nervous all evening, checking the time again and again.",
    "{witness} recalls: {suspect} asked twice when the sapphire viewing would end.",
    "{witness} mentions: {suspect} and the auctioneer argued about money earlier in the week.",
    "{witness} says: {suspect} left the centenary toast early, glass still full.",
)


@dataclass(frozen=True)
class Document:
    """One archive entry. Only id/kind/text ever reach the transcript;
    the truth fields exist for game_ended, the eval, and the tests."""

    id: str
    kind: str
    text: str
    asserts_not: str | None  # element this doc claims to rule out, if any
    truthful: bool
    witness: str | None

    def payload(self) -> dict:
        return {"id": self.id, "kind": self.kind, "text": self.text}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class Archive:
    """The generated corpus plus the baseline retriever."""

    def __init__(self, documents: list[Document]) -> None:
        self.documents = documents
        self._by_id = {d.id: d for d in documents}
        self._doc_tokens = {d.id: _tokens(d.text) for d in documents}

    def get(self, doc_id: str) -> Document:
        return self._by_id[doc_id]

    def red_herrings(self) -> list[str]:
        return [d.id for d in self.documents if not d.truthful and d.asserts_not is not None]

    def search(self, query: str, k: int = SEARCH_K) -> list[Document]:
        """Deterministic keyword retrieval — integers only, so the Java port
        cannot drift. Score = overlap of unique query tokens with the
        document's tokens; ties break toward shorter documents, then id order.
        """
        want = set(_tokens(query))
        scored = []
        for doc in self.documents:
            toks = self._doc_tokens[doc.id]
            score = len(want & set(toks))
            if score > 0:
                scored.append((-score, len(toks), doc.id))
        scored.sort()
        return [self._by_id[doc_id] for _, _, doc_id in scored[:k]]


def _exoneration(element: str, witness: str, spot: str | None) -> tuple[str, str]:
    """Template shared by truths and red herrings — style must not leak truth."""
    dim = dimension_of(element)
    if dim == "who":
        return ("witness_statement",
                f"{witness} states: {DISPLAY[element]} never left the {spot} "
                f"between ten and midnight — half the room can confirm it.")
    if dim == "how":
        return ("forensic_note", f"{witness} confirms: {METHOD_FACTS[element]}.")
    return ("staff_log",
            f"{witness}'s log: {DISPLAY[element]} was locked and under continuous "
            f"watch from nine o'clock; nobody entered.")


def generate(case: Case, rng: Rng) -> Archive:
    non_solution = [d for d in _all_elements() if d not in case.solution.values()]
    exonerated = sorted(rng.sample(non_solution, 8), key=_all_elements().index)

    pool = list(WITNESSES)
    rng.shuffle(pool)
    liars, honest = pool[:3], pool[3:]

    docs: list[tuple[str, str, str | None, bool, str | None]] = []

    for i, element in enumerate(exonerated):
        witness = honest[i % len(honest)]
        spot = NEUTRAL_SPOTS[rng.below(len(NEUTRAL_SPOTS))] if dimension_of(element) == "who" else None
        kind, text = _exoneration(element, witness, spot)
        docs.append((kind, text, element, True, witness))

    for i, dim in enumerate(("who", "how", "where")):
        element = case.solution[dim]
        witness = liars[i]
        spot = NEUTRAL_SPOTS[rng.below(len(NEUTRAL_SPOTS))] if dim == "who" else None
        _, text = _exoneration(element, witness, spot)
        docs.append(("witness_statement", text, element, False, witness))

    for i, liar in enumerate(liars):
        counter = honest[i % len(honest)]
        text = (f"{counter} notes: {liar} left the gala before ten and spent the "
                f"evening in the car park — whatever {liar} says about that night "
                f"is secondhand at best.")
        docs.append(("staff_log", text, None, True, counter))

    for _ in range(6):
        template = GOSSIP_TEMPLATES[rng.below(len(GOSSIP_TEMPLATES))]
        suspect = WHO[rng.below(len(WHO))]
        witness = honest[rng.below(len(honest))]
        text = template.format(witness=witness, suspect=DISPLAY[suspect])
        docs.append(("gossip", text, None, True, witness))

    rng.shuffle(docs)
    return Archive([
        Document(f"doc-{i + 1:03d}", kind, text, asserts, truthful, witness)
        for i, (kind, text, asserts, truthful, witness) in enumerate(docs)
    ])


def _all_elements() -> tuple[str, ...]:
    from .case import ALL_ELEMENTS
    return ALL_ELEMENTS
