"""Which documents have anything to do with the thing on screen.

Tom selected `cantator.__main__`, pressed Document, and got a document about PAUL style
rules — opened twenty minutes earlier from a naming citation and never put away. Document
mode was a *place*, and the mode toggle's own sentence is *"five ways of reading one
selection"*.

Two properties matter, and the second is the one measurement forced.

**A node with nothing to relate says so.** 59% of Lictores' routines carry no governance id
at all, so it is the common case; an empty list with no sentence reads as *"nothing was
found"* rather than *"there is nothing to find"* (design rule 21).

**Ranked, never filtered.** A routine carries a median of two ids and those two are named by
a median of **281** documents — 14% of the corpus. Calling that "related" is a filter that
filters nothing. The intersection is what is selective: documents naming *every* id come to a
median of 4. So the full band is the answer, the rest is counted and offered, and both
numbers are on the page (design rule 1, rule 32).
"""

from __future__ import annotations

import pytest

from dunneflow.docstore import DocStore
from dunneflow.store import Store
from dunneflow.walk import analyze_docs_tree
from dunneflow.web.related import documents_for

PLAN = """---
phase: 75
---

# Plan 75-01 — the widget

This plan is tracked as PLAN-75-1 and closes CW-2.
"""

# **Written the way the scanner actually reads a plan id**, which is `Plan 75-01` and not
# `PLAN-75-1`: in prose the latter is mined as the ticket `PLAN-75`, and only the spelled-out
# form normalises to `PLAN-75-1`. The first draft of this fixture used the wrong one and the
# test failed for a reason that was about the fixture rather than the code — worth keeping,
# because it is the same trap a reader of the real corpus would hit.
ROADMAP = """# Roadmap

Plan 75-01 and CW-2 both land this quarter.
"""

ELSEWHERE = """# Something else

This one mentions CW-2 only.
"""

UNRELATED = """# Style rules

Nothing here names any governance id at all.
"""


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    root = tmp_path_factory.mktemp("reldocs")
    (root / "75-01-PLAN.md").write_text(PLAN, encoding="utf-8")
    (root / "ROADMAP.md").write_text(ROADMAP, encoding="utf-8")
    (root / "elsewhere.md").write_text(ELSEWHERE, encoding="utf-8")
    (root / "style.md").write_text(UNRELATED, encoding="utf-8")
    docs = DocStore(root / "docs.db")
    analyze_docs_tree(root, docs, jobs=1)
    yield docs
    docs.close()


@pytest.fixture(scope="module")
def graph(tmp_path_factory):
    db = tmp_path_factory.mktemp("reldocsgraph") / "graph.db"
    store = Store(db)
    # Written straight into the table the resolver reads. `Store` has no public writer for
    # annotations -- they arrive with a file's facts -- and standing up a whole source tree
    # to plant three ids would put the fixture's subject somewhere other than the join.
    store.conn.executemany(
        "INSERT INTO annotations(owner_id, owner_kind, kind, value, line, text)"
        " VALUES (?,?,?,?,?,?)",
        [("both", "routine", "PLAN", "PLAN-75-1", 1, "see PLAN-75-1"),
         ("both", "routine", "TICKET", "CW-2", 2, "closes CW-2"),
         ("one", "routine", "TICKET", "CW-2", 1, "closes CW-2")])
    store.conn.commit()
    yield store
    store.close()


def test_a_node_with_no_governance_id_is_told_why_not(graph: Store, corpus: DocStore) -> None:
    """59% of routines. The sentence is the whole answer (design rule 21)."""
    got = documents_for(graph, corpus, "carries-nothing")
    assert got["ids"] == [] and got["total"] == 0
    assert got["reason"], "an empty answer with no reason reads as a failed search"


def test_a_map_with_no_documentation_says_that_instead(graph: Store) -> None:
    got = documents_for(graph, None, "both")
    assert got["total"] == 0 and "without reading documentation" in got["reason"]


def test_documents_naming_every_id_are_the_answer(graph: Store, corpus: DocStore) -> None:
    """The intersection, which is what turned a 281-document median into a 4-document one."""
    got = documents_for(graph, corpus, "both")
    assert got["ids"] == ["CW-2", "PLAN-75-1"]
    full = {d["path"] for d in got["full"]}
    assert full == {"75-01-PLAN.md", "ROADMAP.md"}, f"got {full}"
    assert all(d["matched"] == 2 for d in got["full"])


def test_what_only_partly_matches_is_counted_and_kept(graph: Store, corpus: DocStore) -> None:
    """Design rule 1: offered and counted, never hidden and never called the answer."""
    got = documents_for(graph, corpus, "both")
    partial = {d["path"] for d in got["partial"]}
    assert partial == {"elsewhere.md"}, f"got {partial}"
    assert got["total"] == len(got["full"]) + len(got["partial"])


def test_a_document_naming_nothing_is_never_related(graph: Store, corpus: DocStore) -> None:
    """The document Tom was shown. It shares no id with anything and must never appear."""
    got = documents_for(graph, corpus, "both")
    everywhere = {d["path"] for d in [*got["full"], *got["partial"]]}
    assert "style.md" not in everywhere


def test_one_id_yields_no_intersection_and_says_so_by_its_numbers(
        graph: Store, corpus: DocStore) -> None:
    """With a single id every document naming it is a "full" match, which is honest but not
    selective — so the page leans on the counts rather than on the band."""
    got = documents_for(graph, corpus, "one")
    assert got["ids"] == ["CW-2"]
    assert {d["path"] for d in got["full"]} == {"75-01-PLAN.md", "ROADMAP.md", "elsewhere.md"}
    assert got["partial"] == []


def test_every_row_carries_the_ids_that_put_it_there(graph: Store, corpus: DocStore) -> None:
    """Rule 13: the claim beside a row is the thing that produced it, so it can be checked."""
    got = documents_for(graph, corpus, "both")
    for d in [*got["full"], *got["partial"]]:
        assert d["ids"] and d["matched"] == len(d["ids"])
        assert set(d["ids"]) <= set(got["ids"])
