"""What moved between two points in time.

The interesting change is not *these lines moved* -- `git diff` says that better -- but
**what moves changed**: a routine that arrived, one that now writes to a table it did
not, a signature whose types moved, a call that stopped resolving. That is the half a
text diff cannot state, and it is the whole reason this view exists.

Four bands, and the order is the order they are worth reading in:

* **added** and **removed** -- presence, by id. `make_id` derives an id from a qualified
  name and never from a file position, so a routine keeps its identity when anything
  above it moves. A rename still reads as a removal plus an addition, which is honest:
  nothing in the source says the two are the same thing.
* **behaves differently** -- the same routine, and something it *does* has moved.
* **edited only** -- the body changed and nothing it does did. This band is the largest
  in ordinary work and the least interesting, and saying so is the point: a routine
  whose internal computation changed is exactly what this tool exists not to report.

**No comparison key contains a position.** `calls`, `boundaries` and `sql_ops` all carry
a line, and a key including one makes every fact below an inserted import read as
changed -- thousands of false differences from one blank line. That is the argument
`make_id` was written from, one level further down, and it is the single easiest way to
render this whole view as noise.

The two graphs are joined with `ATTACH`, the same way `docs.db` has always been joined
to `graph.db`. Neither snapshot is copied, moved or rewritten to be compared.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# What a routine *does*, stated per fact table as (owner column, compared columns).
#
# Every column that says what the routine does, and none that says where it sits.
# `file` and `line` are absent from every row here, deliberately -- see the module
# docstring. `calls.callee_id` is in, because a call that stopped resolving is a real
# change to what the program can be shown to do (it is how four of Mensores' routines
# changed without being edited); `callee_expr` is in beside it so a call whose *target*
# was rewritten is not silently equal to one whose resolution merely improved.
# --------------------------------------------------------------------------- #

FACTS: dict[str, tuple[str, str]] = {
    "calls":      ("caller_id",  "callee_id, callee_expr, external, at_boundary"),
    "boundaries": ("routine_id", "kind, direction, target"),
    "sql_ops":    ("routine_id", "operation, direction, tbl"),
    "net_calls":  ("routine_id", "protocol, verb, destination, port, timeout, retries"),
    "params":     ("routine_id", "idx, name, type, dflt, kind"),
}

# Owners whose facts differ between the two graphs, **either way round**. A fact that
# was dropped and a fact that was gained are both "this routine does something else
# now", so both halves are asked and unioned.
#
# Each half is a complete sub-select, and that is not a matter of taste. SQLite's
# compound operators are **left-associative**, so
#
#     SELECT a EXCEPT SELECT b UNION ALL SELECT b EXCEPT SELECT a
#
# parses as `((A EXCEPT B) UNION ALL B) EXCEPT A`, which reduces to `B EXCEPT A` -- the
# gained half alone. Written that way this view reported every fact a routine acquired
# and no fact it lost, and nine tests passed over it because every one of them added
# something (rule 37). Parenthesising by putting each half in its own FROM is what makes
# the query say what its name says.
MOVED = """
SELECT o FROM (
    SELECT {owner} AS o, {cols} FROM {A}.{table}
    EXCEPT
    SELECT {owner} AS o, {cols} FROM {B}.{table}
)
UNION
SELECT o FROM (
    SELECT {owner} AS o, {cols} FROM {B}.{table}
    EXCEPT
    SELECT {owner} AS o, {cols} FROM {A}.{table}
)
"""

ADDED = """
SELECT id, name, qualname, module, file, line_start
  FROM {B}.routines WHERE id NOT IN (SELECT id FROM {A}.routines)
 ORDER BY module, qualname
"""

REMOVED = """
SELECT id, name, qualname, module, file, line_start
  FROM {A}.routines WHERE id NOT IN (SELECT id FROM {B}.routines)
 ORDER BY module, qualname
"""

EDITED = """
SELECT y.id, y.name, y.qualname, y.module, y.file, y.line_start
  FROM {A}.routines x JOIN {B}.routines y ON y.id = x.id
 WHERE x.body_hash <> y.body_hash
 ORDER BY y.module, y.qualname
"""

RETURNS_MOVED = """
SELECT y.id AS o FROM {A}.routines x JOIN {B}.routines y ON y.id = x.id
 WHERE IFNULL(x.returns, '') <> IFNULL(y.returns, '')
"""

# Presence-only tables. Each is keyed by the thing a reader would name it by, never by a
# row id, because an id that includes a position moves for the same reason routines' did.
PRESENCE: dict[str, str] = {
    "db_tables":   "name",
    "entrypoints": "id",
    "artefacts":   "name",
    "constants":   "module || '.' || name",
}


def _attach(a: Path, b: Path) -> sqlite3.Connection:
    """Both graphs, read-only, in one connection. Neither is opened for writing.

    `uri=True` so the ATTACHes can carry `mode=ro`. Read-only is not a nicety: rule 20
    says a read may refuse but may never repair, and a diff is the most purely
    read-only thing this tool does — it must not leave so much as a journal file beside
    a snapshot someone sealed.

    **Only for graphs this process does not already hold open.** See `build`.
    """
    conn = sqlite3.connect(":memory:", uri=True)
    conn.row_factory = sqlite3.Row
    # Absolute, because a relative path inside a `file:` URI is not the same path --
    # it produced `unable to open database: file:output/mensores/graph@...db`, which
    # names the file it could not open and still does not say why.
    conn.execute("ATTACH DATABASE ? AS a", (f"file:{a.resolve()}?mode=ro",))
    conn.execute("ATTACH DATABASE ? AS b", (f"file:{b.resolve()}?mode=ro",))
    return conn


def _rows(conn: sqlite3.Connection, sql: str, **kw: Any) -> list[sqlite3.Row]:
    return conn.execute(sql.format(**kw)).fetchall()


def build(before: Path, after: Path,
          *, serving: sqlite3.Connection | None = None) -> dict[str, Any]:
    """The whole change list, both directions, with every row carrying its subject.

    Every row carries the node **id** the rest of the dashboard selects by, never a
    label -- a worklist whose rows cannot be acted on is design rule 16's dead control
    with a count beside it (rule 30).

    `serving` is a connection this process **already holds open on `after`**, and passing
    it is worth 36x. A second, read-only handle to a database this process has open in
    WAL mode cannot join the shared-memory WAL index -- it has no write access to the
    `-shm` -- so it re-derives it on every query. Measured on Mensores, one `calls`
    comparison: **8,855 ms with the dashboard holding the graph open, 242 ms with it
    stopped, 137 ms attached onto the connection that already had it.** Same query, same
    files, same page cache.

    That is worth stating plainly because the slow path is the *careful* one, and it is
    only slow while the tool is doing the thing it exists to do. Opened standalone it
    measures fine, which is exactly how it would have been recorded as fast and shipped:
    every measurement in this module before this one was taken with the server stopped.
    """
    conn = serving if serving is not None else _attach(before, after)
    # When we are riding the server's connection, the graph it serves is already `main`;
    # only the other end needs attaching, and it is one this process does not hold open.
    A, B = ("chgbefore", "main") if serving is not None else ("a", "b")
    if serving is not None:
        # A plain path, not a `mode=ro` URI, and both halves of that are deliberate.
        # `Store` opens without `uri=True`, so a URI here is taken as a literal filename
        # -- and read-only is what made this slow in the first place, so buying it back
        # on the connection the whole dashboard shares would spread the 36x to every
        # other query rather than remove it.
        #
        # The guarantee is kept the way rule 25 keeps it for `sourcedb`: by a test that
        # this module contains no write statement at all, because what is being guarded
        # against is a future edit rather than a present bug. Nothing here is conditional
        # and nothing here migrates; it is SELECTs and one DETACH.
        conn.execute("ATTACH DATABASE ? AS chgbefore", (str(before.resolve()),))
    try:
        added = [dict(r) for r in conn.execute(ADDED.format(A=A, B=B))]
        removed = [dict(r) for r in conn.execute(REMOVED.format(A=A, B=B))]
        edited = {r["id"]: dict(r) for r in conn.execute(EDITED.format(A=A, B=B))}

        moved: dict[str, set[str]] = {}
        for table, (owner, cols) in FACTS.items():
            for r in _rows(conn, MOVED, table=table, owner=owner, cols=cols,
                           A=A, B=B):
                if r["o"]:
                    moved.setdefault(r["o"], set()).add(table)
        for r in conn.execute(RETURNS_MOVED.format(A=A, B=B)):
            moved.setdefault(r["o"], set()).add("returns")

        # Only routines present in BOTH. A fact belonging to a routine that arrived or
        # went is already stated by its own band, and counting it here would report one
        # change twice -- rule 40's defect, in a diff.
        both = {r["id"] for r in conn.execute(
            f"SELECT id FROM {A}.routines INTERSECT SELECT id FROM {B}.routines")}
        behaves = {rid: sorted(k) for rid, k in moved.items() if rid in both}

        named = {r["id"]: dict(r) for r in conn.execute(
            f"SELECT id, name, qualname, module, file, line_start FROM {B}.routines")}
        behaves_rows = [
            {**named[rid], "moved": kinds}
            for rid, kinds in sorted(behaves.items(),
                                     key=lambda kv: named.get(kv[0], {}).get("qualname", ""))
            if rid in named
        ]
        edited_only = [row for rid, row in edited.items() if rid not in behaves]

        presence = {}
        for table, key in PRESENCE.items():
            presence[table] = {
                "added": [r[0] for r in conn.execute(
                    f"SELECT {key} FROM {B}.{table} "
                    f"WHERE {key} NOT IN (SELECT {key} FROM {A}.{table}) ORDER BY 1")],
                "removed": [r[0] for r in conn.execute(
                    f"SELECT {key} FROM {A}.{table} "
                    f"WHERE {key} NOT IN (SELECT {key} FROM {B}.{table}) ORDER BY 1")],
            }

        return {
            "counts": {
                "added": len(added),
                "removed": len(removed),
                "behaves": len(behaves_rows),
                "edited_only": len(edited_only),
                "routines_before": conn.execute(
                    f"SELECT COUNT(*) FROM {A}.routines").fetchone()[0],
                "routines_after": conn.execute(
                    f"SELECT COUNT(*) FROM {B}.routines").fetchone()[0],
            },
            "added": added,
            "removed": removed,
            "behaves": behaves_rows,
            "edited_only": edited_only,
            "presence": presence,
        }
    finally:
        # The server's connection outlives this call and must be handed back exactly as
        # it was found: an alias left attached makes the next comparison fail, and a
        # connection closed here would take the whole dashboard down with it.
        if serving is not None:
            conn.execute("DETACH DATABASE chgbefore")
        else:
            conn.close()
