"""Edges a reader's own toolchain handed over: the lookup, the store, and the arithmetic.

`tests/test_typescript.py` presses the **reader** — that the checker resolves an import
alias, a method through a typed receiver, an overload set. This presses everything on the
host's side of the pipe, and it does it without a toolchain: rows are written into the
store directly, exactly as `test_resolve_split.py` does, because what is under test is the
lookup from a location to an id and that is the host's alone.

**The four outcomes are four tests and not one**, because three of them are honest forms of
*no* and collapsing any two of them is how *"we could not see the far end"* comes to read as
*"there is nothing there"* (design rule 21).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow.resolve import calls as driver
from dunneflow.resolve.contract import CallRow, Decision, Edge, NoEdge
from dunneflow.resolve.typescript import calls as tsr
from dunneflow.schema import Confidence, SuppliedEdge
from dunneflow.store import Store


def _map(tmp_path: Path) -> Store:
    """Two TypeScript files: a caller and a callee, and one call between them.

    `b.ts` holds two routines so the span fallback has something to be wrong about, and
    `save` deliberately starts at line 20 while the file runs to 40 — a location inside
    `save` is not a location at `save`.
    """
    store = Store(tmp_path / "graph.db")
    c = store.conn
    for path in ("a.ts", "b.ts"):
        c.execute("INSERT INTO files(path, lang, module, content_hash) VALUES (?,?,?,?)",
                  (path, "typescript", path[:-3], "h"))
    rows = [
        ("a:caller", "caller", "a.ts", 1, 9),
        ("b:save", "save", "b.ts", 20, 40),
        ("b:inner", "inner", "b.ts", 25, 30),
    ]
    for rid, name, file, start, end in rows:
        c.execute(
            "INSERT INTO routines(id, name, qualname, module, file, line_start,"
            " line_end, lang) VALUES (?,?,?,?,?,?,?,'typescript')",
            (rid, name, f"{file[:-3]}.{name}", file[:-3], file, start, end),
        )
    c.execute(
        "INSERT INTO calls(file, caller_id, callee_expr, line, confidence, at_boundary,"
        " site_id) VALUES ('a.ts','a:caller','save',3,?,0,'site-1')",
        (Confidence.INFERRED.value,),
    )
    c.commit()
    return store


def _resolve(store: Store) -> Decision:
    rows = [CallRow(file="a.ts", caller_id="a:caller", callee_expr="save",
                    site_id="site-1")]
    return tsr.resolve(store, "typescript", rows)[0]


@pytest.fixture
def mapped(tmp_path: Path):
    store = _map(tmp_path)
    yield store
    store.close()


# --------------------------------------------------------------- the lookup --- #

def test_a_location_this_map_holds_a_routine_at_is_an_edge(mapped):
    """The ordinary answer, and the one the whole chunk exists for."""
    mapped.replace_supplied_edges("typescript", [
        SuppliedEdge(site_id="site-1", caller_id="a:caller", file="b.ts", line=20,
                     name="save", how="signature"),
    ])
    d = _resolve(mapped)
    assert isinstance(d, Edge)
    assert d.target == "b:save"
    assert d.confidence is Confidence.CERTAIN
    assert d.supplied is True
    assert tsr.LAST.exact == 1
    assert tsr.LAST.by_span == 0


def test_a_call_site_the_reader_said_nothing_about_is_left_external(mapped):
    """Never guessed by name — that refusal is the payoff of using the toolchain (rule 1).

    `b.ts` holds a routine called `save` and the call expression is `save`. A resolver that
    fell back to a name would resolve it; this one does not, because nothing resolved it.
    """
    mapped.replace_supplied_edges("typescript", [])
    d = _resolve(mapped)
    assert isinstance(d, NoEdge)
    assert d.candidates == 0
    assert tsr.LAST.unsupplied == 1


def test_several_declarations_is_no_edge_with_the_count_kept(mapped):
    """Ambiguous, exactly as a Python name collision is — and never `INFERRED` (rule 6)."""
    mapped.replace_supplied_edges("typescript", [
        SuppliedEdge(site_id="site-1", caller_id="a:caller", candidates=3, how="symbol"),
    ])
    d = _resolve(mapped)
    assert isinstance(d, NoEdge)
    assert d.candidates == 3
    assert tsr.LAST.ambiguous == 1


def test_a_location_this_map_holds_no_routine_at_is_external(mapped):
    """Rule 26 by construction: the call happens and the far end is not here."""
    mapped.replace_supplied_edges("typescript", [
        SuppliedEdge(site_id="site-1", caller_id="a:caller",
                     file="node_modules/lib/index.d.ts", line=4, name="save"),
    ])
    d = _resolve(mapped)
    assert isinstance(d, NoEdge)
    assert tsr.LAST.no_routine == 1


# ------------------------------------------------------------ the two guards --- #

def test_a_line_inside_a_routine_falls_back_to_the_innermost_span(mapped):
    """Counted rather than trusted, because it should never fire (rule 49).

    On DunneNote it fires nought times out of 1,935, which is what says the reader and the
    extractor agree about where a declaration begins. It exists for the shapes that
    measurement has not met, and the count is how anybody would find out.
    """
    mapped.replace_supplied_edges("typescript", [
        SuppliedEdge(site_id="site-1", caller_id="a:caller", file="b.ts", line=27,
                     name="inner"),
    ])
    d = _resolve(mapped)
    assert isinstance(d, Edge)
    assert d.target == "b:inner", "line 27 is inside `inner`, which is inside `save`"
    assert tsr.LAST.by_span == 1
    assert tsr.LAST.exact == 0


def test_a_target_whose_routine_is_called_something_else_is_refused(mapped):
    """A silently wrong edge is worse than a missing one (rule 1).

    A line that has drifted lands on *some* routine. Without the name there is nothing to
    notice that with, and the map would carry an edge nobody can tell is wrong.
    """
    mapped.replace_supplied_edges("typescript", [
        SuppliedEdge(site_id="site-1", caller_id="a:caller", file="b.ts", line=20,
                     name="somethingElse"),
    ])
    d = _resolve(mapped)
    assert isinstance(d, NoEdge)
    assert tsr.LAST.name_mismatch == 1


# ------------------------------------------------------------------ the store --- #

def test_the_set_is_replaced_whole_and_per_language(tmp_path):
    """A checker answers about a compilation, so half a set is the stale half.

    And a reader that supplies **nothing** still clears its own rows: a plugin whose checker
    stopped resolving would otherwise keep answering out of the last run that worked.
    """
    store = Store(tmp_path / "graph.db")
    store.replace_supplied_edges("typescript", [
        SuppliedEdge(site_id="one", caller_id="c", file="b.ts", line=1, name="x"),
        SuppliedEdge(site_id="two", caller_id="c", file="b.ts", line=2, name="y"),
    ])
    store.replace_supplied_edges("rust", [
        SuppliedEdge(site_id="three", caller_id="c", file="b.rs", line=3, name="z"),
    ])
    assert store.counts()["supplied_edges"] == 3

    assert store.replace_supplied_edges("typescript", []) == 0
    held = [r["site_id"] for r in store.query("SELECT site_id FROM supplied_edges")]
    assert held == ["three"], "typescript cleared whole; rust untouched"
    store.close()


def test_forgetting_a_file_does_not_touch_the_supplied_edges(tmp_path):
    """Deliberate, and the one table a file's facts do not own.

    Its rows are keyed by language because a checker answers about a compilation: an edge
    out of this file was computed from every other file, and a row naming *this* file as a
    target belongs to a caller somewhere else. Deleting either half per file leaves the
    other half stale with nothing to say so.
    """
    store = Store(tmp_path / "graph.db")
    store.conn.execute(
        "INSERT INTO files(path, lang, module, content_hash) VALUES ('a.ts','typescript','a','h')"
    )
    store.replace_supplied_edges("typescript", [
        SuppliedEdge(site_id="one", caller_id="a:f", file="b.ts", line=1, name="x"),
    ])
    store.forget_file("a.ts")
    assert store.counts()["supplied_edges"] == 1
    store.close()


# ------------------------------------------------------------- the arithmetic --- #

def test_the_printed_figures_add_up_to_the_total_and_match_the_store(tmp_path):
    """Rule 13: a claim's query must return exactly what is printed beside it.

    `certain + inferred + external` was **not** the total from the chunk 6 split until chunk
    10, and nothing noticed for three chunks. v1 counted an external call in the tail every
    no-target path fell through; the split gave each `NoEdge` its own branch and kept the
    count only on the boundary one. Comitia read *4,063 external* over 30,544 calls of which
    24,103 leave the program — 4,063 being the `at_boundary` count wearing another word.

    It was found by chunk 10's gate rather than by a test, because a resolution rate is the
    first figure anybody checks the arithmetic of. This is that test.
    """
    store = _map(tmp_path)
    store.conn.execute(
        "INSERT INTO calls(file, caller_id, callee_expr, line, confidence, at_boundary,"
        " site_id) VALUES ('a.ts','a:caller','fetch',4,?,1,'site-2')",
        (Confidence.INFERRED.value,),
    )
    store.conn.execute(
        "INSERT INTO calls(file, caller_id, callee_expr, line, confidence, at_boundary,"
        " site_id) VALUES ('a.ts','a:caller','whoKnows',5,?,0,'site-3')",
        (Confidence.INFERRED.value,),
    )
    store.conn.commit()
    store.replace_supplied_edges("typescript", [
        SuppliedEdge(site_id="site-1", caller_id="a:caller", file="b.ts", line=20,
                     name="save", how="signature"),
    ])

    stats = driver.resolve_calls(store)
    assert stats.certain + stats.inferred + stats.external == stats.total == 3
    stored = store.conn.execute(
        "SELECT COUNT(*) AS n FROM calls WHERE external = 1"
    ).fetchone()["n"]
    assert stats.external == stored
    assert stats.supplied == 1, "counted apart from `certain`, which it also is"
    store.close()
