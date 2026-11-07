"""What macros do in a program, asked once: the one answer the map page, the agent and the
dashboard all read (rule 51).

A use is a row, so every number here is a query and can open its places (rule 13). What this
does not know is said beside what it does, because a macro page that reads as complete where
an arm was not taken or a header was not found is the failure it exists to prevent: a tree can
look clean because the place that would have shown otherwise was never read.
"""

from __future__ import annotations

from typing import Any

from ..detectors import load_rules
from ..store import Store


def macro_report(store: Store) -> dict[str, Any]:
    """Every definition with what its uses do, leading with the ones that reach something.

    **The order is what a reader came for and is defensible for that reason** (rule 66): most
    macros in any program are a constant or a string wrapper, so a list by use count opens on
    `NULL` and `TEXT`. What leaves the program comes first, then what reaches anything, then
    the most used, and ties go to the name and the place, which never depend on row order.
    """
    defs = store.query("SELECT id, name, file, line, origin FROM macro_defs")
    rows: dict[str, dict[str, Any]] = {
        str(d["id"]): {
            "id": str(d["id"]), "name": str(d["name"]), "file": str(d["file"]),
            "line": int(d["line"]), "origin": str(d["origin"]),
            "uses": 0, "statement": 0, "declaration": 0, "file_scope": 0,
            "routines_written": 0, "structures_named": 0,
            "in_tree": 0, "leaving": 0, "indirect": 0, "boundaries": 0, "kinds": [],
            "shadows": [],
        } for d in defs
    }

    def fill(sql: str, each: Any) -> None:
        for x in store.query(sql):
            row = rows.get(str(x["k"]))
            if row is not None:
                each(row, x)

    def position(row: dict[str, Any], x: Any) -> None:
        row[str(x["position"])] = int(x["n"])
        row["uses"] += int(x["n"])

    fill("SELECT def_id AS k, position, COUNT(*) n FROM macro_sites GROUP BY 1, 2", position)
    fill("SELECT def_id AS k, shadows AS s FROM macro_sites WHERE shadows <> ''"
         " GROUP BY 1, 2 ORDER BY 1, 2",
         lambda r, x: r["shadows"].append(str(x["s"])))
    fill("SELECT body_by AS k, COUNT(*) n FROM routines WHERE body_by <> '' GROUP BY 1",
         lambda r, x: r.__setitem__("routines_written", int(x["n"])))
    fill("SELECT name_by AS k, COUNT(*) n FROM structures WHERE name_by <> '' GROUP BY 1",
         lambda r, x: r.__setitem__("structures_named", int(x["n"])))

    def reach(row: dict[str, Any], x: Any) -> None:
        row["in_tree"] = int(x["in_tree"])
        row["leaving"] = int(x["leaving"])
        row["indirect"] = int(x["indirect"] or 0)

    fill("SELECT def_id AS k,"
         " COUNT(DISTINCT CASE WHEN target_file <> '' THEN callee END) AS in_tree,"
         " COUNT(DISTINCT CASE WHEN target_file = '' AND candidates = 0 AND indirect = 0"
         "       THEN callee END) AS leaving,"
         " SUM(CASE WHEN indirect = 1 THEN count END) AS indirect"
         " FROM macro_callees GROUP BY 1", reach)

    def touches(row: dict[str, Any], x: Any) -> None:
        row["boundaries"] += int(x["n"])
        row["kinds"].append(str(x["kind"]))

    fill("SELECT through_macro AS k, kind, COUNT(*) n FROM boundaries"
         " WHERE through_macro <> '' GROUP BY 1, 2 ORDER BY 1, 2", touches)

    listed = sorted(rows.values(), key=lambda r: (
        -r["boundaries"], -(r["in_tree"] + r["leaving"] + r["indirect"]), -r["uses"],
        r["name"], r["file"], r["line"]))

    langs = [str(x["lang"]) for x in store.query("SELECT DISTINCT lang FROM files ORDER BY 1")]
    said = {lang: load_rules(lang).macro_expansion for lang in langs}
    count = lambda sql: int(store.query(sql)[0]["n"])  # noqa: E731
    return {
        "definitions": listed,
        "summary": {
            "uses": count("SELECT COUNT(*) n FROM macro_sites"),
            "directive_uses": count(
                "SELECT COALESCE(SUM(macro_directive_uses), 0) n FROM files"),
            "routines": count("SELECT COUNT(*) n FROM routines WHERE name <> '<module>'"),
            "routines_written": count("SELECT COUNT(*) n FROM routines WHERE body_by <> ''"),
            "routines_named": count(
                "SELECT COUNT(*) n FROM routines WHERE name_by <> '' AND body_by = ''"),
            "structures_named": count("SELECT COUNT(*) n FROM structures WHERE name_by <> ''"),
            "opaque_asm": count("SELECT COALESCE(SUM(opaque_asm), 0) n FROM routines"),
            "boundaries": count("SELECT COUNT(*) n FROM boundaries WHERE through_macro <> ''"),
        },
        "expansion": {
            "read": [x for x, w in said.items() if w == "read"],
            "named": [x for x, w in said.items() if w == "named"],
        },
        "unread": unread(store),
    }


def unread(store: Store) -> dict[str, Any]:
    """What was not read, which is a different thing from what is not there. Per file, because
    which file is what somebody can go and open."""
    arms = store.query(
        "SELECT path, skipped_lines FROM files WHERE skipped_lines > 0"
        " ORDER BY skipped_lines DESC, path")
    headers = store.query(
        "SELECT first_missing, COUNT(*) n FROM files WHERE first_missing <> ''"
        " GROUP BY 1 ORDER BY n DESC, first_missing")
    missing = store.query(
        "SELECT COUNT(*) n FROM files WHERE first_missing <> ''")[0]["n"]
    return {
        "lines": sum(int(x["skipped_lines"]) for x in arms),
        "arms": [{"file": str(x["path"]), "lines": int(x["skipped_lines"])} for x in arms],
        "files_missing_headers": int(missing),
        "headers": [{"header": str(x["first_missing"]), "files": int(x["n"])} for x in headers],
    }


def macro_places(store: Store, def_id: str) -> dict[str, Any]:
    """One definition's uses and where its expansion goes. The numbers' places (rule 13)."""
    return {
        "uses": [dict(x) for x in store.query(
            "SELECT s.file, s.line, s.position, s.shadows, s.routine_id, r.qualname"
            "  FROM macro_sites s LEFT JOIN routines r ON r.id = s.routine_id"
            " WHERE s.def_id = ? ORDER BY s.file, s.line", (def_id,))],
        "callees": [dict(x) for x in store.query(
            "SELECT callee, target_file, target_line, candidates, indirect,"
            "       SUM(count) AS uses"
            "  FROM macro_callees WHERE def_id = ?"
            " GROUP BY callee, target_file, target_line, candidates, indirect"
            " ORDER BY uses DESC, callee, target_file", (def_id,))],
        "boundaries": [dict(x) for x in store.query(
            "SELECT kind, direction, target, evidence, file, line, routine_id"
            "  FROM boundaries WHERE through_macro = ?"
            " ORDER BY file, line, kind, evidence", (def_id,))],
    }
