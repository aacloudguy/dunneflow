"""Joining governance ids across the two stores, and grading what the join finds.

The interesting failures here are not "did the intersection work". They are the three
ways this report could confidently mislead:

* counting one citation twice because two detectors caught it (`ISS-014` matches both
  the ISSUE rule and the general TICKET rule -- 574 such rows on Mensores);
* calling a plan landed because a document mentioned `list`, which is rule 3 wearing a
  new uniform;
* printing a count beside a query that returns a different number, which rule 13 calls
  worse than printing no query at all.

Each has a test. The fixture runs the real extractors rather than writing rows by hand,
because a hand-built store cannot catch a detector that stops firing.
"""

from __future__ import annotations

import pytest

from dunneflow.docstore import DocStore
from dunneflow.render.traceability import render_traceability
from dunneflow.resolve.traceability import (
    CODE_IDS_SQL,
    DOC_IDS_SQL,
    STATES,
    measure,
    normalise,
)
from dunneflow.store import Store
from dunneflow.walk import analyze_docs_tree, analyze_tree

# Distinctive names, so the landed signal has something unambiguous to find. Each is
# defined exactly once, which is what makes it usable as evidence.
PROGRAM = '''
"""A program with governance markers of every standing."""
import os


def enqueue_preflight(name: str) -> None:
    # Implements Plan 01-02. See ADR-0007 for why it fails closed.
    os.environ[name]


def route_architect_escalation(item: str) -> None:
    # ISS-999: no plan document exists for this anywhere.
    os.environ[item]


def reconcile_witness_ledger() -> None:
    # ISS-014 governs this one.
    os.environ["LEDGER"]


class PreFlightBundle:
    """Carries a preflight run."""


class DesignExplorerPayload:
    """Payload for the design explorer."""
'''

# `Plan 01-02` is the subject of its own document -> TRACED.
TRACED_DOC = """# Plan 01-02 — Preflight enqueue

Introduces `enqueue_preflight`, which is the way in.
"""

# `ADR-0007` is only ever mentioned in someone else's prose -> THINLY TRACED.
MENTION_DOC = """# Architecture notes

We fail closed because of ADR-0007, decided last year. TR-5 is tracked elsewhere.
"""

# Subject of a document, cited by no comment, naming three symbols that all exist.
LANDED_DOC = """# Plan 02-01 — Design explorer

Adds `PreFlightBundle`, `DesignExplorerPayload` and `route_architect_escalation`.
"""

# Subject of a document, naming exactly one symbol that exists.
FAINT_DOC = """# Plan 02-02 — Ledger reconciliation

Adds `reconcile_witness_ledger` only.
"""

# Subject of a document, naming nothing that exists.
ABSENT_DOC = """# Plan 02-03 — Never started

Will add `quaesitor_interview_loop` and `tabularium_writer`.
"""

# Rule 3 in a new place: the only symbol named is a builtin the program happens to
# define nothing of. It must not count as evidence that anything landed.
BUILTIN_DOC = """# Plan 02-04 — Listing

Adds `list` handling.
"""


@pytest.fixture(scope="module")
def joined(tmp_path_factory):
    root = tmp_path_factory.mktemp("traceable")
    (root / "prog.py").write_text(PROGRAM, encoding="utf-8")
    docs = root / "docs"
    docs.mkdir()
    for name, body in [
        ("plan-01-02.md", TRACED_DOC),
        ("notes.md", MENTION_DOC),
        ("plan-02-01.md", LANDED_DOC),
        ("plan-02-02.md", FAINT_DOC),
        ("plan-02-03.md", ABSENT_DOC),
        ("plan-02-04.md", BUILTIN_DOC),
    ]:
        (docs / name).write_text(body, encoding="utf-8")

    store = Store(root / "graph.db")
    analyze_tree(root, store)
    doc_store = DocStore(root / "docs.db")
    analyze_docs_tree(docs, doc_store, jobs=1)
    doc_store.mark_duplicates()
    yield store, doc_store, root
    store.close()
    doc_store.close()


def state_of(result, identifier: str) -> str:
    for t in result.ids:
        if t.id == identifier:
            return t.state
    raise AssertionError(f"{identifier} not found in {[t.id for t in result.ids]}")


# --------------------------------------------------------------------------- #
# Normalising
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ADR-0001", "ADR-1"),
        ("ADR 1", "ADR-1"),
        ("adr_1", "ADR-1"),
        ("ADR-1", "ADR-1"),
        ("Plan 01-04", "PLAN-1-4"),
        ("Plan 87-02c", "PLAN-87-2C"),
        ("G11", "G-11"),
        ("ISS-001", "ISS-1"),
    ],
)
def test_separator_and_padding_do_not_make_two_ids(raw, expected):
    assert normalise(raw) == expected


def test_segment_count_is_not_normalised_away():
    """`Plan 01-04` is a two-part id; `PLAN-01` is a different, one-part id.

    Collapsing them would silently merge a plan with a phase and claim a trace that
    does not exist -- rule 1, where a false edge costs more than a missing one.
    """
    assert normalise("Plan 01-04") != normalise("PLAN-01")
    assert normalise("PLAN-01") == normalise("PLAN-1")


# --------------------------------------------------------------------------- #
# The spectrum
# --------------------------------------------------------------------------- #


def test_every_band_is_reachable(joined):
    """Each state is evidenced by a real fixture, not merely defined."""
    store, docs, _ = joined
    result = measure(store, docs)
    assert state_of(result, "PLAN-1-2") == "TRACED"
    assert state_of(result, "ADR-7") == "THINLY_TRACED"
    assert state_of(result, "ISS-999") == "UNDOCUMENTED_WORK"
    assert state_of(result, "PLAN-2-1") == "LIKELY_LANDED"
    assert state_of(result, "PLAN-2-2") == "POSSIBLY_LANDED"
    assert state_of(result, "PLAN-2-3") == "NO_TRACE_IN_CODE"
    assert state_of(result, "TR-5") == "PASSING_REFERENCE"


def test_every_id_lands_in_exactly_one_band(joined):
    store, docs, _ = joined
    result = measure(store, docs)
    counts = result.counts()
    assert sum(counts.values()) == len(result.ids)
    assert set(counts) == {s.key for s in STATES}


def test_a_builtin_is_never_evidence_that_work_landed(joined):
    """Rule 3. One id's entire claim to having landed was the word `list`."""
    store, docs, _ = joined
    result = measure(store, docs)
    plan = next(t for t in result.ids if t.id == "PLAN-2-4")
    assert plan.landed == []
    assert plan.state == "NO_TRACE_IN_CODE"


def test_landed_evidence_is_only_distinctive_symbols(joined):
    store, docs, _ = joined
    result = measure(store, docs)
    landed = next(t for t in result.ids if t.id == "PLAN-2-1")
    assert set(landed.landed) == {
        "PreFlightBundle", "DesignExplorerPayload", "route_architect_escalation",
    }


# --------------------------------------------------------------------------- #
# The three ways this could mislead
# --------------------------------------------------------------------------- #


def test_one_marker_caught_by_two_detectors_is_one_citation(joined):
    """`ISS-014` matches the ISSUE rule and the general TICKET rule both.

    The extractor rightly records both readings. Counting them as two citations would
    report a plan as governing twice as much code as it does -- 574 such rows on
    Mensores, every one of them a single comment.
    """
    store, docs, _ = joined
    result = measure(store, docs)
    iss = next(t for t in result.ids if t.id == "ISS-14")
    assert len(iss.kinds) > 1, "fixture no longer exercises double detection"
    assert len(iss.code) == 1
    sites = {(c.file, c.line) for c in iss.code}
    assert len(sites) == 1


def test_printed_counts_and_shipped_queries_agree(joined):
    """Rule 13, applied across the ATTACH.

    A query that disagrees with the number beside it invites a reader to check, and
    then misleads them. Three of the first twenty-seven measured naming conventions
    shipped one; this asserts the traceability page never does.
    """
    store, docs, root = joined
    result = measure(store, docs)
    store.conn.execute("ATTACH DATABASE ? AS docs", (str(root / "docs.db"),))
    try:
        assert len(store.query(CODE_IDS_SQL)) == result.code_annotations
        assert len(store.query(DOC_IDS_SQL)) == result.doc_annotations
    finally:
        store.conn.execute("DETACH DATABASE docs")


def test_copies_of_a_document_are_counted_once(joined):
    """Worktree copies would otherwise inflate every mention count."""
    store, docs, _ = joined
    result = measure(store, docs)
    for t in result.ids:
        seen = [s.doc for s in t.documents()]
        assert len(seen) == len(set(seen))


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def test_no_documentation_is_not_reported_as_drift(joined, tmp_path):
    """Rule 11. Documentation may be absent, and absence is never a finding.

    Saying "59 ids were built without a plan" when no corpus was read would be a
    fabricated finding of exactly the kind this tool exists not to produce.
    """
    store, _, root = joined
    path = render_traceability(store, None, tmp_path, "sample", "stamp")
    text = path.read_text(encoding="utf-8")
    assert "No documentation was read" in text
    assert "Nothing here is a finding about drift" in text
    # The page still opens by naming the question it exists to answer; what must be
    # absent is any *answer* to it -- the findings, the spectrum, the counts.
    assert "## The two findings" not in text
    assert "## The spectrum" not in text
    assert "Undocumented work" not in text


def test_every_band_states_its_blind_spot(joined, tmp_path):
    """A finding without its blind spot is a guess wearing a uniform."""
    store, docs, root = joined
    path = render_traceability(store, docs, tmp_path, "sample", "stamp")
    text = path.read_text(encoding="utf-8")
    for s in STATES:
        assert s.label in text
        assert s.blind_spot in text


def test_every_id_appears_in_the_report(joined, tmp_path):
    """Rule 8. A reference list is never bounded."""
    store, docs, root = joined
    result = measure(store, docs)
    path = render_traceability(store, docs, tmp_path, "sample", "stamp")
    text = path.read_text(encoding="utf-8")
    for t in result.ids:
        assert f"`{t.id}`" in text, f"{t.id} is missing from the report"


# --------------------------------------------------------------------------- #
# Composed identity: marked as an inference, never blurred with a quotation
# --------------------------------------------------------------------------- #

# A plan document in the shape that made 15 ids read as unplanned work: it declares
# itself in frontmatter and in its filename, and never writes the id in its prose.
FRONTMATTER_PLAN = """---
phase: 68-front-door-extraction
plan: 03
type: execute
---

# Front-door extraction

Adds `enqueue_preflight` handling. Nothing here writes the plan id in words.
"""


@pytest.fixture(scope="module")
def composed(tmp_path_factory):
    root = tmp_path_factory.mktemp("composed")
    (root / "prog.py").write_text(PROGRAM, encoding="utf-8")
    docs = root / "docs"
    docs.mkdir()
    (docs / "68-03-PLAN.md").write_text(FRONTMATTER_PLAN, encoding="utf-8")
    (docs / "plan-01-02.md").write_text(TRACED_DOC, encoding="utf-8")
    store = Store(root / "graph.db")
    analyze_tree(root, store)
    doc_store = DocStore(root / "docs.db")
    analyze_docs_tree(docs, doc_store, jobs=1)
    doc_store.mark_duplicates()
    yield store, doc_store, root
    store.close()
    doc_store.close()


def test_an_id_stated_only_in_frontmatter_is_found(composed):
    """`Plan 68-03` appears nowhere in the corpus as prose, and the document exists."""
    store, docs, _ = composed
    result = measure(store, docs)
    plan = next((t for t in result.ids if t.id == "PLAN-68-3"), None)
    assert plan is not None, "composed identity did not reach the join"
    assert plan.subjects, "the document should count as being about the id"


def test_a_composed_id_is_marked_as_an_inference(composed):
    """Rule 6. The document is real; nothing in it says this in words."""
    store, docs, _ = composed
    result = measure(store, docs)
    plan = next(t for t in result.ids if t.id == "PLAN-68-3")
    assert plan.by_inference_only
    assert not plan.stated_anywhere
    assert all(not site.stated for site in plan.documents())
    assert result.inferred_annotations >= 1


def test_a_written_id_is_never_marked_inferred(composed):
    """`Plan 01-02` is written out in its document's heading, so it is a quotation."""
    store, docs, _ = composed
    result = measure(store, docs)
    plan = next(t for t in result.ids if t.id == "PLAN-1-2")
    assert plan.stated_anywhere
    assert not plan.by_inference_only


def test_the_report_separates_the_two_tiers(composed, tmp_path):
    store, docs, root = composed
    path = render_traceability(store, docs, tmp_path, "sample", "stamp")
    text = path.read_text(encoding="utf-8")
    assert "What was read, and what was inferred" in text
    assert "*(inferred)*" in text
    assert "entire documentary standing is composed" in text


def test_a_corpus_with_no_composed_ids_says_so(joined, tmp_path):
    """No filter is ever silent, and neither is an empty one."""
    store, docs, root = joined
    result = measure(store, docs)
    assert result.inferred_annotations == 0
    path = render_traceability(store, docs, tmp_path, "sample", "stamp")
    assert "Nothing here was inferred" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("meta", "basename", "expected"),
    [
        # The corpus writes `plan:` two ways. A single pattern read `06-02` as `06`
        # and composed `Plan 06-06`, an id that does not exist anywhere.
        ({"phase": "06-pm-agent-dogfood", "plan": "06-02"}, "notes.md", "Plan 06-02"),
        ({"phase": "01-foundation", "plan": "1"}, "notes.md", "Plan 01-01"),
        ({"phase": "68-front-door-extraction", "plan": "03"}, "x.md", "Plan 68-03"),
        # A sub-plan belongs to its parent; the code-side vocabulary has no third
        # segment, so the fraction is deliberately dropped rather than invented.
        ({}, "85-08.1-PLAN.md", "Plan 85-08"),
    ],
)
def test_an_id_is_composed_from_either_convention(meta, basename, expected):
    from dunneflow.detectors import identify_document
    assert [a.value for a in identify_document(meta, basename)] == [expected]


def test_a_document_matching_no_convention_composes_nothing():
    """Half an id is not an id, and a guess is worse than a gap."""
    from dunneflow.detectors import identify_document
    assert identify_document({}, "async-neo4j-writer-test-idiom.md") == []
    assert identify_document({"phase": "06-x"}, "README.md") == []   # no `plan` key
    assert identify_document({"plan": "2"}, "README.md") == []       # no `phase` key


def test_every_composed_id_is_marked_inferred():
    """Rule 6, at the point of creation rather than only at the point of display."""
    from dunneflow.detectors import identify_document
    from dunneflow.schema import Confidence
    made = identify_document({"phase": "68-a", "plan": "03"}, "68-03-PLAN.md")
    assert made
    assert all(a.confidence == Confidence.INFERRED for a in made)
    assert all(a.line == 0 for a in made), "a composed id has no line to point at"


def test_a_program_that_cites_no_id_in_code_is_reported_rather_than_a_crash(tmp_path):
    """`analyze` raised `ZeroDivisionError` here, and the program was ordinary.

    The headline divides the ids findable in documentation by the ids cited in code. A
    program whose comments name no governance id at all makes that denominator zero -- which
    is not an exotic corpus, it is every program that has not adopted this discipline. Found
    by pointing the tool at a four-file fixture, the first thing it had ever been given with
    none; Mensores cites 593 and could not reach it.

    **Stated as an absence, never filled with a plausible 0%** (rule 49). "No ids are cited
    in code" and "none of the ids cited in code are documented" are opposite findings, and a
    bare 0% asserts the second.
    """
    root = tmp_path / "quiet"
    root.mkdir()
    (root / "prog.py").write_text(
        "# An ordinary comment that names no plan.\n"
        "def go():\n    return 1\n", encoding="utf-8")
    docs = root / "docs"
    docs.mkdir()
    (docs / "readme.md").write_text("# A document that names no plan either.\n",
                                    encoding="utf-8")

    store = Store(root / "graph.db")
    analyze_tree(root, store)
    doc_store = DocStore(root / "docs.db")
    analyze_docs_tree(docs, doc_store, jobs=1)
    doc_store.mark_duplicates()
    try:
        assert measure(store, doc_store).in_code() == 0, (
            "this fixture cites an id after all, so it does not test the empty case"
        )
        text = render_traceability(store, doc_store, tmp_path, "quiet", "stamp"
                                   ).read_text(encoding="utf-8")
    finally:
        store.close()
        doc_store.close()

    assert "No governance ids are cited in code at all" in text, (
        "the report does not say that nothing here names a plan"
    )
    assert "0%) are findable" not in text, (
        "a share of nothing is rendered as 0%, which claims that ids were cited and none "
        "of them documented — the opposite finding"
    )
