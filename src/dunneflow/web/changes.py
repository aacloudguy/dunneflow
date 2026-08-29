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
    SELECT {owner} AS o, {cols} FROM a.{table}
    EXCEPT
    SELECT {owner} AS o, {cols} FROM b.{table}
)
UNION
SELECT o FROM (
    SELECT {owner} AS o, {cols} FROM b.{table}
    EXCEPT
    SELECT {owner} AS o, {cols} FROM a.{table}
)
"""

ADDED = """
SELECT id, name, qualname, module, file, line_start
  FROM b.routines WHERE id NOT IN (SELECT id FROM a.routines)
 ORDER BY module, qualname
"""

REMOVED = """
SELECT id, name, qualname, module, file, line_start
  FROM a.routines WHERE id NOT IN (SELECT id FROM b.routines)
 ORDER BY module, qualname
"""

EDITED = """
SELECT b.id, b.name, b.qualname, b.module, b.file, b.line_start
  FROM a.routines a_r JOIN b.routines b ON b.id = a_r.id
 WHERE a_r.body_hash <> b.body_hash
 ORDER BY b.module, b.qualname
"""

RETURNS_MOVED = """
SELECT b.id AS o FROM a.routines a_r JOIN b.routines b ON b.id = a_r.id
 WHERE IFNULL(a_r.returns, '') <> IFNULL(b.returns, '')
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
    """Both graphs, read-only, in one connection. Neither is opened for writing."""
    # `uri=True` so the two ATTACHes below can carry `mode=ro`. Read-only is not a
    # nicety here: rule 20 says a read may refuse but may never repair, and a diff is
    # the most purely read-only thing this tool does — it must not so much as leave a
    # journal file beside a snapshot someone sealed.
    conn = sqlite3.connect(":memory:", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("ATTACH DATABASE ? AS a", (f"file:{a}?mode=ro",))
    conn.execute("ATTACH DATABASE ? AS b", (f"file:{b}?mode=ro",))
    return conn


def _rows(conn: sqlite3.Connection, sql: str, **kw: Any) -> list[sqlite3.Row]:
    return conn.execute(sql.format(**kw)).fetchall()


def build(before: Path, after: Path) -> dict[str, Any]:
    """The whole change list, both directions, with every row carrying its subject.

    Every row carries the node **id** the rest of the dashboard selects by, never a
    label -- a worklist whose rows cannot be acted on is design rule 16's dead control
    with a count beside it (rule 30).
    """
    conn = _attach(before, after)
    try:
        added = [dict(r) for r in conn.execute(ADDED)]
        removed = [dict(r) for r in conn.execute(REMOVED)]
        edited = {r["id"]: dict(r) for r in conn.execute(EDITED)}

        moved: dict[str, set[str]] = {}
        for table, (owner, cols) in FACTS.items():
            for r in _rows(conn, MOVED, table=table, owner=owner, cols=cols):
                if r["o"]:
                    moved.setdefault(r["o"], set()).add(table)
        for r in conn.execute(RETURNS_MOVED):
            moved.setdefault(r["o"], set()).add("returns")

        # Only routines present in BOTH. A fact belonging to a routine that arrived or
        # went is already stated by its own band, and counting it here would report one
        # change twice -- rule 40's defect, in a diff.
        both = {r["id"] for r in conn.execute(
            "SELECT id FROM a.routines INTERSECT SELECT id FROM b.routines")}
        behaves = {rid: sorted(k) for rid, k in moved.items() if rid in both}

        named = {r["id"]: dict(r) for r in conn.execute(
            "SELECT id, name, qualname, module, file, line_start FROM b.routines")}
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
                    f"SELECT {key} FROM b.{table} "
                    f"WHERE {key} NOT IN (SELECT {key} FROM a.{table}) ORDER BY 1")],
                "removed": [r[0] for r in conn.execute(
                    f"SELECT {key} FROM a.{table} "
                    f"WHERE {key} NOT IN (SELECT {key} FROM b.{table}) ORDER BY 1")],
            }

        return {
            "counts": {
                "added": len(added),
                "removed": len(removed),
                "behaves": len(behaves_rows),
                "edited_only": len(edited_only),
                "routines_before": conn.execute(
                    "SELECT COUNT(*) FROM a.routines").fetchone()[0],
                "routines_after": conn.execute(
                    "SELECT COUNT(*) FROM b.routines").fetchone()[0],
            },
            "added": added,
            "removed": removed,
            "behaves": behaves_rows,
            "edited_only": edited_only,
            "presence": presence,
        }
    finally:
        conn.close()
