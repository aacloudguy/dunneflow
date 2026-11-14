"""One database table, described as the thing it is.

**A table is not a node, and it is not the routines that touch it.** Selecting one used
to fetch `TABLE_ROUTINES` and then *throw the table away*: `selectFromNav` replaced the
whole request with `{nodes}`, so the crumb named a table and the inspector answered about
whichever routine sorted first. A true answer about something nobody clicked, which is
`detail.fold`'s defect and `plate.py`'s (rules 32 and 74), arriving a third time in the
one surface a reader reaches by clicking the busiest thing on the cover.

This file is what that fix looks like the third time. `plate.py` is the argument written
out; `documents.py:table_col` is the sentence about why a table has no node id to borrow.

**It has no id of its own, and none is minted.** `id` is the table's *name*, which is
what the program itself says, and `kind: "TABLE"` is what stops a reader of the payload
taking that name for a node id (rule 30). Inventing `tbl:<name>` would be a second id
space for a fact the program already states, and every surface would then have to know to
strip the prefix before asking a question about it.

**Where it is declared is a real absence, not a miss.** `db_tables` is filled by `sql.py`
reading the `CREATE TABLE` statements the code *contains*, so a program that only ever
reads somebody else's schema declares nothing -- and 12 of Comitia's 65 tables are that.
Three states and not two (design rule 21): declared once, declared in more than one file,
and never declared here. Only the first can hand the source pane a place to open, and it
is the only one that does.
"""

from __future__ import annotations

from typing import Any

from ..store import Store
from . import queries
from .shape import loops_around


def _rows(store: Store, sql: str, args: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(r) for r in store.query(sql, args)]


def describe(store: Store, name: str) -> dict[str, Any]:
    """The table, in the shape every other specimen uses.

    Answers for a table this program only *touches* as readily as for one it declares,
    because those are the two halves of what a table is here and a pane that refused the
    first would go blank on the ones a reader most wants explained.

    `found: False` is kept for a name nothing in the map mentions at all -- a different
    answer from a real table nothing loops over, which `_r_table` already keeps apart and
    the client already words differently.
    """
    declared = _rows(store, queries.TABLE_DECLARED, {"name": name})
    touchers = _rows(store, queries.TABLE_TOUCHERS, {"name": name})
    if not declared and not touchers:
        return {"found": False, "kind": "TABLE", "id": name, "label": name,
                "reason": f"nothing in this map declares or touches a table "
                          f"called {name!r}"}

    columns = _rows(store, queries.TABLE_COLUMNS, {"name": name})
    writes = sum(1 for t in touchers if t["direction"] == "WRITE")
    reads = sum(1 for t in touchers if t["direction"] == "READ")
    # Everything that is neither, named rather than left as the difference between two
    # numbers a reader would have to subtract. 7 of `worktree_allocations`' 27 operations
    # are `CREATE TABLE`, `BEGIN` and `COMMIT` -- transaction control and DDL, which are
    # not reads and are not writes, and a pane printing "27 operations, 12 writes, 8
    # reads" has silently filtered a third of them (design rule 1).
    other = len(touchers) - writes - reads

    return {
        "kind": "TABLE",
        "id": name,
        "label": name,
        "found": True,
        "identity": {
            "table": name,
            "declared": declared,
            # Stated rather than left to be counted off `declared`, because the three
            # states read differently and a client counting a list will get the wording
            # right for two of them and silently wrong for the third.
            "origin": ("declared here" if len(declared) == 1 else
                       "declared in more than one file" if declared else
                       "not declared in this program — it is only read and written"),
            "temporary": bool(declared and all(d["temporary"] for d in declared)),
            "columns": columns,
            # **Operations, not routines.** `COVER_TABLES` counts operations and the
            # navigator's row carries that number, so counting routines here would put
            # two different figures under one name (rule 32). `in.callers` is one row
            # per operation too, and the pane says which it is showing.
            "ops": len(touchers),
            "writes": writes,
            "reads": reads,
            "other": other,
        },
        # The same question a boundary answers, and deliberately the same key: a table
        # is an endpoint the program talks to, and `viewInspector` already knows how to
        # draw "who reaches this".
        "in": {"callers": touchers, "entrypoints": []},
        "out": {"calls": []},
        "touches": {"boundaries": [], "sql": [], "net": [], "artefacts": []},
        "governance": {"annotations": [], "comments": []},
        # **The links back** (ALGORITHMS chunk 5). A reader standing at a table asks what
        # loops over them, which is the reverse of the question the Algorithms page puts
        # to a loop. Answered on demand with the pane, because a session either opens a
        # table or never does (rule 45), and bounded by the routines that touch this one.
        "loops": loops_around(store, table=name),
        # A place to open, only where there is exactly one and it is therefore not a
        # nomination. Two `CREATE TABLE`s for one name are two answers, and picking the
        # first would be rule 1's position mistaken for a meaning.
        "where": ({"file": declared[0]["file"], "first": declared[0]["line"],
                   "last": declared[0]["line"]} if len(declared) == 1 else None),
    }
