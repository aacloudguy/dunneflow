"""A set of ids larger than SQLite's parameter limit is not a different code path.

Unreal's `Engine/Source/Runtime`, read by the C and C++ reader on 2026-11-03: 2h19m of
extraction, the graph written, and then `dunneflow analyze` died in `render/markdown.py`'s
`_flow_inventory` with `sqlite3.OperationalError: too many SQL variables` -- one generated
`?` per routine a way in reaches, and a way into Runtime reaches more than 32,766 of them.

Every query keyed by a set the *data* sizes now takes that set as one JSON array through
`json_each`, the idiom `web/queries.py`'s folds have used since they were written. A set
sized by a constant -- a list of kinds, of saliences -- keeps its placeholders: it cannot
grow with the tree. Rule 55: a bound must be on the work, and here the work is a set no
test of a toy program ever made big enough to fail.

Each function is driven past the limit and asked for an answer it can be checked against,
because a query that no longer raises but quietly returns nothing is rule 49's shape.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from dunneflow.store import Store

#: Past the limit of the SQLite this suite runs on, with margin, and checked against it so
#: the test cannot pass merely because a later SQLite raised the ceiling.
N = 33_000


def _limit() -> int:
    return sqlite3.connect(":memory:").getlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER)


def _star(path: Path, *, docstring: str = "said", file_hash: str = "h") -> Store:
    """One root that calls `N` leaves, each in its own file, every leaf touching a file."""
    store = Store(path)
    leaves = [f"leaf{i:05d}" for i in range(N)]
    c = store.conn
    c.execute("INSERT INTO routines(id, name, qualname, module, file, line_start, line_end,"
              " lang) VALUES('root', 'main', 'main', 'm', 'main.c', 1, 2, 'cpp')")
    c.executemany(
        "INSERT INTO routines(id, name, qualname, module, file, line_start, line_end, lang,"
        " docstring) VALUES(?, ?, ?, 'm', ?, 1, 2, 'cpp', ?)",
        [(lf, lf, lf, f"{lf}.c", docstring) for lf in leaves])
    c.executemany(
        "INSERT INTO files(path, lang, module, content_hash, doc) VALUES(?, 'cpp', 'm', ?, ?)",
        [(f"{lf}.c", file_hash, docstring) for lf in leaves])
    c.executemany(
        "INSERT INTO calls(file, caller_id, callee_expr, callee_id, line, confidence)"
        " VALUES('main.c', 'root', ?, ?, 1, 'CERTAIN')", [(lf, lf) for lf in leaves])
    c.executemany(
        "INSERT INTO boundaries(file, routine_id, kind, direction, target, line)"
        " VALUES(?, ?, 'FILE', 'OUT', 'out.txt', 1)", [(f"{lf}.c", lf) for lf in leaves])
    c.executemany(
        "INSERT INTO entrypoints(id, kind, name, routine_id) VALUES(?, 'CLI', ?, ?)",
        [(f"ep-{lf}", lf, lf) for lf in leaves])
    c.executemany(
        "INSERT INTO annotations(owner_id, owner_kind, kind, value, line)"
        " VALUES(?, 'routine', 'PLAN', ?, 1)", [(lf, f"PLAN-{lf}") for lf in leaves])
    c.commit()
    return store


@pytest.fixture(scope="module")
def star(tmp_path_factory) -> Iterator[Store]:
    assert _limit() < N, f"N={N} no longer exceeds SQLite's limit of {_limit()}"
    store = _star(tmp_path_factory.mktemp("star") / "graph.db")
    yield store
    store.close()


def test_a_way_in_reaching_more_routines_than_sqlite_takes_parameters_renders(star):
    """The crash itself: Runtime's flows page."""
    from dunneflow.render.markdown import _flow_inventory

    text = _flow_inventory(star, {"name": "main", "roots": ["root"]})
    assert f"({N + 1:,})" in text
    assert text.count("FILE→out.txt") == N


def test_the_reach_query_takes_a_seed_set_past_the_limit(star, monkeypatch):
    """The recursive query is the path every walk without an in-memory graph takes."""
    leaves = [f"leaf{i:05d}" for i in range(N)]
    monkeypatch.setattr(star, "_reach_graph", lambda cross=True: None)
    assert star.reachable_from_many(leaves) == set(leaves)
    assert len(star.boundaries_reached_many(leaves)) == N


def test_the_flow_helpers_take_a_set_past_the_limit(star):
    from dunneflow.resolve.flows import governance_over, trace_flow, ways_in_affected

    leaves = [f"leaf{i:05d}" for i in range(N)]
    assert len(ways_in_affected(star, leaves)) == N
    assert len(governance_over(star, leaves)) == N
    # Wider than any bound in one level: the frontier query is asked with all of it.
    flow = trace_flow(star, "root", "main", max_nodes=N + 1)
    assert len(flow.edges) == N


def test_the_ways_in_pane_takes_a_set_past_the_limit(star):
    from dunneflow.web.waysin import _routines

    leaves = [f"leaf{i:05d}" for i in range(N)]
    assert len(_routines(star, leaves)) == N


def test_a_comparison_whose_changed_files_pass_the_limit_still_reads_them(tmp_path):
    """Every file differs, and so does every docstring: each lane must find all of them."""
    from dunneflow.web import changes

    base = _star(tmp_path / "base.db", docstring="before", file_hash="a")
    compared = _star(tmp_path / "compared.db", docstring="after", file_hash="b")
    base.close()
    compared.close()
    conn = changes._attach(tmp_path / "compared.db", tmp_path / "base.db")
    try:
        assert len(changes._changed_files(conn, "compared", "base")) == N
        assert len(changes._docstrings_moved(conn, "compared", "base")) == N
        assert len(changes._module_docs_moved(conn, "compared", "base")) == N
        assert changes._comments_moved(conn, "compared", "base") == set()
        assert changes._structure_docs_moved(conn, "compared", "base") == set()
    finally:
        conn.close()
