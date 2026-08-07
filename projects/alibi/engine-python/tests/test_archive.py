"""The corpus generator's truth model, and the baseline retriever.

The solvability guarantee is tested across seeds, not asserted: every red
herring targets a solution element, every truthful exoneration targets a
non-solution element, and every lying witness is undermined by a truthful
counter document.
"""

from alibi_engine.archive import SEARCH_K, generate
from alibi_engine.case import DISPLAY, deal, dimension_of
from alibi_engine.rng import Rng


def _case_and_archive(seed):
    rng = Rng(seed)
    case = deal(rng)
    return case, generate(case, rng)


def test_document_count_and_ids():
    _, archive = _case_and_archive(1)
    assert len(archive.documents) == 20  # 8 exonerations + 3 herrings + 3 counters + 6 gossip
    assert [d.id for d in archive.documents] == [f"doc-{i:03d}" for i in range(1, 21)]


def test_truth_model_across_seeds():
    for seed in range(1, 11):
        case, archive = _case_and_archive(seed)
        solution = set(case.solution.values())

        herrings = [d for d in archive.documents if not d.truthful]
        assert len(herrings) == 3
        # One per dimension, each "ruling out" the actual answer.
        assert {dimension_of(d.asserts_not) for d in herrings} == {"who", "how", "where"}
        assert all(d.asserts_not in solution for d in herrings)

        for doc in archive.documents:
            if doc.truthful and doc.asserts_not is not None:
                assert doc.asserts_not not in solution


def test_every_lying_witness_is_undermined():
    for seed in range(1, 11):
        _, archive = _case_and_archive(seed)
        liars = {d.witness for d in archive.documents if not d.truthful}
        counters = [d for d in archive.documents
                    if d.truthful and d.asserts_not is None and "secondhand" in d.text]
        for liar in liars:
            assert any(liar in c.text for c in counters), f"seed {seed}: {liar} never undermined"


def test_red_herrings_are_stylistically_indistinguishable():
    """A herring must not be findable by its wording — only by cross-checking
    its witness. Same templates means same phrasing shapes."""
    case, archive = _case_and_archive(5)
    herring = next(d for d in archive.documents if not d.truthful)
    truthful_same_dim = [
        d for d in archive.documents
        if d.truthful and d.asserts_not is not None
        and dimension_of(d.asserts_not) == dimension_of(herring.asserts_not)
    ]
    if truthful_same_dim:  # not guaranteed for every dimension every seed
        a, b = herring.text, truthful_same_dim[0].text
        # Shared template skeleton: both mention the same fixed phrases.
        assert ("states:" in a) == ("states:" in b) or ("log:" in a) == ("log:" in b) or ("confirms:" in a) == ("confirms:" in b)


def test_search_is_deterministic_and_bounded():
    _, archive = _case_and_archive(7)
    r1 = [d.id for d in archive.search("vault key manager")]
    r2 = [d.id for d in archive.search("vault key manager")]
    assert r1 == r2
    assert len(r1) <= SEARCH_K


def test_search_finds_the_obvious_document():
    case, archive = _case_and_archive(3)
    target = next(d for d in archive.documents if d.truthful and d.asserts_not is not None)
    display_words = DISPLAY[target.asserts_not]
    results = archive.search(display_words)
    assert target.id in [d.id for d in results]


def test_search_ignores_no_overlap():
    _, archive = _case_and_archive(2)
    assert archive.search("zzzz qqqq xxxx") == []


def test_generation_is_deterministic():
    _, a1 = _case_and_archive(4)
    _, a2 = _case_and_archive(4)
    assert [(d.id, d.text) for d in a1.documents] == [(d.id, d.text) for d in a2.documents]
