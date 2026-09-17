"""Schema and statement extraction."""

from __future__ import annotations

from dunneflow import sql


def test_rejects_things_that_are_not_statements():
    assert not sql.looks_like_sql("file:db.sqlite?mode=ro")
    assert not sql.looks_like_sql("hello")
    assert not sql.looks_like_sql("")


def test_classifies_direction():
    assert sql.parse("SELECT a FROM t").direction == sql.READ
    assert sql.parse("INSERT INTO t VALUES (1)").direction == sql.WRITE
    assert sql.parse("UPDATE t SET a = 1").direction == sql.WRITE
    assert sql.parse("DELETE FROM t WHERE a = 1").direction == sql.WRITE
    assert sql.parse("CREATE TABLE t (a INT)").direction == sql.DDL


def test_names_tables():
    assert sql.parse("SELECT a FROM widgets JOIN parts ON 1=1").tables == [
        "widgets", "parts"
    ]
    assert sql.parse("INSERT INTO widgets (a) VALUES (?)").tables == ["widgets"]


def test_reads_a_schema_from_its_create_statement():
    td = sql.parse_table_def(
        "CREATE TABLE IF NOT EXISTS widgets ("
        " id TEXT PRIMARY KEY, name TEXT NOT NULL, qty INTEGER DEFAULT 0,"
        " UNIQUE(name))"
    )
    assert td is not None and td.name == "widgets"
    assert [(c.name, c.type) for c in td.columns] == [
        ("id", "TEXT"), ("name", "TEXT"), ("qty", "INTEGER")
    ]
    assert "PRIMARY KEY" in td.columns[0].constraints


def test_reads_indexes():
    ix = sql.parse_index_defs(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_w ON widgets(name, qty)"
    )
    assert len(ix) == 1
    assert (ix[0].name, ix[0].table, ix[0].unique) == ("ix_w", "widgets", True)


def test_schema_is_extracted_from_the_program(analyzed):
    tables = {r["name"] for r in analyzed.query("SELECT name FROM db_tables")}
    assert "widgets" in tables
    cols = {
        r["name"] for r in analyzed.query("SELECT name FROM db_columns WHERE tbl='widgets'")
    }
    assert {"id", "name", "qty"} <= cols
    idx = analyzed.query("SELECT name, uniq FROM db_indexes WHERE tbl='widgets'")
    assert idx and idx[0]["uniq"] == 1


def test_reads_and_writes_are_attributed(analyzed):
    rows = {
        (r["direction"], r["qualname"])
        for r in analyzed.query(
            "SELECT s.direction, r.qualname FROM sql_ops s"
            " JOIN routines r ON s.routine_id = r.id WHERE s.tbl = 'widgets'"
        )
    }
    assert ("WRITE", "sample.save_widget") in rows
    assert ("READ", "sample.read_widgets") in rows


def test_prose_that_begins_with_a_sql_verb_is_not_sql():
    """Docstrings open with words like Update and Create far more often than SQL does."""
    for prose in (
        "Create the sitecustomize shim directory and return it for the child",
        "Update a field on the org-config and return the new value",
        "release the orchestrator claim so the sidecar tier can proceed",
        "Select the best candidate from the list of reviewers",
        "Delete stale entries from the cache when the run finishes",
    ):
        assert not sql.looks_like_sql(prose), prose


def test_real_statements_still_recognised():
    for stmt in (
        "SELECT a FROM t",
        "SELECT COUNT(*) FROM t",
        "DELETE FROM sessions WHERE expired < ?",
        "ROLLBACK;",
        "CREATE TABLE IF NOT EXISTS tags (name TEXT PRIMARY KEY)",
    ):
        assert sql.looks_like_sql(stmt), stmt


def test_upsert_clause_is_not_a_second_table():
    """`... ON CONFLICT DO UPDATE SET x = ?` must not yield a table called SET."""
    op = sql.parse(
        "INSERT INTO x (a) VALUES (?) ON CONFLICT(a) DO UPDATE SET a = excluded.a"
    )
    assert op is not None and op.tables == ["x"]
