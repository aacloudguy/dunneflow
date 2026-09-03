"""Document mode, lane 2: the map's own eight documents.

Lane 1 is the program's prose (`corpus.py`); this is the prose **this tool generates** —
where to start, what it runs, what it holds, what it touches — built from the graph with a
node id on every row. That id is the whole reason `documents.py` does not reuse
`render/markdown.py`: clicking a routine in the text must select *that* routine in the
graph, and matching a name against the store afterwards would light up every `main` in a
program that has a great many (rule 5).

Every test here is a way that can go wrong while looking right:

  - a `Column` whose key no query returns, which renders a blank cell rather than failing —
    the defect that emptied "Where" in every row of all eight documents for as long as the
    family existed, unnoticed because nothing rendered them (design rule 16);
  - a row with an id that is dropped instead of shown unlinked, which is a silently
    shorter table (design rule 1);
  - a grouping column no query selects, which puts every row under one blank heading.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from dunneflow.store import Store
from dunneflow.web import documents


@pytest.fixture()
def store(tmp_path: Path) -> Iterator[Store]:
    """An empty graph. Empty is enough and is the point.

    A prepared statement reports the columns it will return before it returns any, so the
    contract between a query and its `Column` list can be checked without a single row —
    which means this guard cannot be made to pass by a fixture that happens to have the
    right data in it.
    """
    s = Store(tmp_path / "graph.db")
    yield s
    s.close()


def _columns(store: Store, sql: str, params: dict[str, object]) -> set[str]:
    cur = store.conn.execute(sql, params)
    try:
        return {d[0] for d in cur.description}
    finally:
        cur.close()


# ------------------------------------------- the query and its columns agree --- #

def test_every_column_names_something_its_query_returns(store: Store) -> None:
    """The bug this was written from, and the shape of it rather than the instance.

    `where` is a SQL keyword, so all eight statements aliased the location column
    `AS where_` while `documents.py` keyed it `Column("where", …)`. `row.get("where")`
    returned `None` and the "Where" cell of **every row of all eight documents** rendered
    blank — a column that is there, headed, sized, and empty. Nothing noticed for as long
    as the family existed, because nothing rendered these documents.

    A missing key must fail **by name**. Asserted over the whole table rather than for the
    one column that was wrong, because the next mismatch will be a different column and
    naming this one would guard the instance instead of the rule (design rule 16).
    """
    for doc in documents.DOCUMENTS:
        for i, spec in enumerate(doc.sections):
            got = _columns(store, spec.query, spec.params)
            for col in spec.columns:
                assert col.key in got, (
                    f"{doc.id} section {i}: the column headed {col.label!r} reads "
                    f"{col.key!r}, which this query does not return — every row of this "
                    f"document renders that cell blank. Returned: {sorted(got)}"
                )


def test_every_section_can_find_its_identity_and_its_grouping(store: Store) -> None:
    """The two columns that are not headings, and both fail silently when they are wrong.

    `node_col` is what makes a row clickable at all — missing, every row in the document
    is unlinked, which is exactly what a row with a genuinely null id is supposed to look
    like. `group_col` missing puts all 4,733 rows under one blank heading, which reads as a
    document with no structure rather than a document whose grouping broke.
    """
    for doc in documents.DOCUMENTS:
        for i, spec in enumerate(doc.sections):
            got = _columns(store, spec.query, spec.params)
            assert spec.node_col in got, (
                f"{doc.id} section {i}: no {spec.node_col!r} column, so no row can be "
                "clicked — indistinguishable from a document whose rows have no ids"
            )
            if spec.group_col is not None:
                assert spec.group_col in got, (
                    f"{doc.id} section {i}: groups by {spec.group_col!r}, which the query "
                    "does not return — every row lands under one blank heading"
                )


def test_the_location_alias_stays_quoted() -> None:
    """`where` is a keyword, and the quotes are the whole of why this works.

    Unquoted it is a syntax error, which is loud. Renamed back to `where_` — the obvious
    tidy for someone who reads the quotes as noise — it is silent, and the column empties
    again. The guard above catches that too; this one says *why* at the place the tidy
    would happen.
    """
    from dunneflow.web import queries

    for name in dir(queries):
        if not name.startswith("DOC_"):
            continue
        sql = getattr(queries, name)
        if not isinstance(sql, str):
            continue
        assert "AS where_" not in sql, (
            f"{name} aliases the location column `where_` again; `documents.py` keys it "
            '"where" and the cell renders blank in every row'
        )


# ------------------------------------------------------ building a document --- #

def test_an_unknown_document_is_refused_by_name(store: Store) -> None:
    """Rule 30: a label is not an identity, and an id that names nothing must say so."""
    got = documents.build(store, "no-such-document")
    assert got["found"] is False
    assert got["id"] == "no-such-document"
    assert "reason" in got


def test_a_row_with_no_id_is_shown_rather_than_dropped(store: Store) -> None:
    """A silently shorter table is the failure design rule 1 exists to prevent.

    An entrypoint whose routine the resolver could not place is a fact about the program
    either way. Dropped, the document is quietly incomplete; kept with a null id, the
    client draws it without a link and the reader can see there was nothing to link to.
    """
    store.conn.executescript(
        "INSERT INTO entrypoints (id, name, kind, routine_id, evidence, file) VALUES "
        "('ep:ghost', 'ghost', 'script', NULL, 'declared in pyproject.toml', 'setup.py');"
    )
    store.conn.commit()
    got = documents.build(store, "entrypoints")
    rows = [r for g in got["sections"][0]["groups"] for r in g["rows"]]
    assert len(rows) == 1, "the unresolved entrypoint was dropped from the document"
    assert rows[0]["node"] is None, "an unresolved row must not be given an id to link to"
    assert rows[0]["cells"]["name"] == "ghost"
    assert rows[0]["cells"]["where"] == "setup.py:0", (
        "the location cell is blank — the defect this file was written from"
    )


def test_the_index_names_every_document_exactly_once() -> None:
    """`BY_ID` is a lookup built from the tuple, and two documents sharing an id would make
    one of them unreachable while both still appeared in the list."""
    ids = [d["id"] for d in documents.index()]
    assert len(ids) == len(set(ids)), f"two documents share an id: {ids}"
    assert set(ids) == set(documents.BY_ID), "the index and the lookup disagree"
    assert len(ids) == 8, f"the map has {len(ids)} documents, not eight — was one added?"


def test_a_grouped_section_counts_the_rows_it_holds(store: Store) -> None:
    """Rule 32: a count must say what it counts, and rule 13 — beside the rows it counts.

    The group count is `len(g["rows"])` and the section total is the sum of those, so a
    heading saying 12 over 11 rows is impossible by construction rather than by care.
    """
    store.conn.executescript(
        "INSERT INTO entrypoints (id, name, kind, routine_id, evidence, file) VALUES"
        " ('ep:a', 'a', 'cli', NULL, '', 'm.py'),"
        " ('ep:b', 'b', 'cli', NULL, '', 'm.py'),"
        " ('ep:c', 'c', 'script', NULL, '', 'm.py');"
    )
    store.conn.commit()
    section = documents.build(store, "entrypoints")["sections"][0]
    assert section["grouped"] is True
    assert {g["title"]: g["count"] for g in section["groups"]} == {"cli": 2, "script": 1}
    for g in section["groups"]:
        assert g["count"] == len(g["rows"]), (
            f"group {g['title']!r} states {g['count']} and holds {len(g['rows'])}"
        )
    assert section["rows"] == sum(g["count"] for g in section["groups"])


def test_no_document_query_is_bounded() -> None:
    """Rule 8 bounds a diagram and only a diagram; these are reference lists.

    4,734 routines is a large page, and a large page a reader can search is worth more than
    a small one that quietly stopped. The client may page it for the browser's sake; it may
    not decide the content.
    """
    for doc in documents.DOCUMENTS:
        for spec in doc.sections:
            assert "LIMIT" not in spec.query.upper(), (
                f"{doc.id} bounds its own rows — the document would be silently short"
            )


def test_a_query_that_cannot_be_prepared_fails_here_and_not_in_a_pane(
        store: Store) -> None:
    """Every statement in the family, prepared against the real schema.

    A `DOC_*` query naming a column the graph does not have raises `OperationalError` at
    the moment a reader opens that document — one pane, in one mode, that most sessions
    never reach. Preparing all of them here moves that to a test run.
    """
    for doc in documents.DOCUMENTS:
        for i, spec in enumerate(doc.sections):
            try:
                store.conn.execute(spec.query, spec.params).close()
            except sqlite3.Error as exc:                       # pragma: no cover - the msg
                pytest.fail(f"{doc.id} section {i} will not prepare: {exc}")


def test_a_section_that_can_carry_no_node_says_what_its_rows_select() -> None:
    """`NULL AS node` is a decision, and it leaves the rows with nothing to click.

    A declared table is deliberately not a node in the graph — inventing an id to make a row
    clickable would be a link to nothing, which `queries.py` wrote down before anything
    rendered these documents. But selecting a table *is* a real act: it means selecting the
    code that reads and writes it, which `TABLE_ROUTINES` answers and the navigator has done
    since it had a Database group.

    So a section whose query hard-codes a null id must declare what its rows select instead.
    Without it the whole section renders inert, and an inert row is indistinguishable from
    one whose id was lost — 43 of them, in the middle of a document where every other row
    selects.

    Named by the *shape* rather than by the one section: the next query to select `NULL AS
    node` will be a different one, and naming this one would guard the instance.
    """
    for doc in documents.DOCUMENTS:
        for i, spec in enumerate(doc.sections):
            nulled = "NULL      AS node" in spec.query or "NULL AS node" in spec.query
            if not nulled:
                continue
            assert spec.table_col, (
                f"{doc.id} section {i} selects no node id and declares nothing else to "
                "select, so every row in it is inert"
            )


def test_the_table_section_hands_its_rows_a_table_to_select(store: Store) -> None:
    """The same claim exercised, because reading the declaration is not seeing a row carry it.

    `table_col` names a column; the row has to come back with its value under `table`, and
    the section has to say `selects: "table"` so a client routes it to the table door rather
    than the node one. Sniffing a null id for this would be rule 30 — "this row names a
    table" and "this row's node could not be resolved" are different facts that look
    identical on the wire.
    """
    store.conn.executescript(
        "INSERT INTO db_tables (name, file, line) VALUES ('audit_blobs', 'store.py', 12);"
    )
    store.conn.commit()
    section = documents.build(store, "database")["sections"][0]
    assert section["selects"] == "table", "the section does not say its rows name tables"
    row = section["groups"][0]["rows"][0]
    assert row["node"] is None, "a declared table was given a graph node id it does not have"
    assert row["table"] == "audit_blobs", (
        "the row carries no table name, so it can select nothing"
    )
    # And a node-carrying section must not claim to be one.
    other = documents.build(store, "routines")["sections"][0]
    assert other["selects"] == "node"
    assert all("table" not in r for g in other["groups"] for r in g["rows"]), (
        "an ordinary section ships a `table` key, so a client cannot tell the two apart"
    )
