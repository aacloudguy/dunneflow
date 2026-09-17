"""The code browser: a file, and what the map knows about every line of it.

A reader who reads code but does not write it does not want `less`. What makes this worth
building is that nearly every fact table in the graph carries a `file` **and** a `line` --
30,209 calls, 18,414 comments, 6,949 governance ids, 3,950 boundaries, 2,618 constants,
1,002 SQL operations. Drawn beside the source, those are the map and the code in one place.

Two layers come out of here and they answer different questions, which is why they are not
one list:

* **`links`** are *inline* spans: a name in the source that can be clicked, carrying the
  node id it selects. There is no name matching here at all -- `calls.callee_id` is what
  the resolver already decided, so a link is a lookup (rule 5 never arises).

* **`marks`** are the margin: what a line *is*. A boundary with its direction and target, a
  SQL operation with its table, a constant, an import, a named artefact, a network call
  with its timeout, a governance id. Some carry an id and are clickable there too.

**The rule that decides where a link goes, and it has to be stated on the page.** `calls`
records a line and the expression written at the call site, and **no column**. So a call is
underlined inline only where its expression occurs exactly once on that line; where it
occurs zero times or many, the link goes in the margin instead. Inventing a column to make
a span look precise is inventing a position -- rule 1, and the same argument `queries.py`
already makes about inventing an id to make a row clickable. `placed` and `unplaced` on the
payload say how many went each way, because a silent shortfall is invisible from up there
(design rule 1).

Whole files, never a window. Rule 8: a reference is never bounded, and the client bounds
what it draws rather than being handed a slice it cannot tell from the whole.
"""

from __future__ import annotations

from typing import Any

from ..sourcedb import SourceStore
from ..store import Store
from . import queries

# Line and column are one-based, matching every line number the graph records and every
# gutter a reader has ever seen. Columns are counted in characters, not bytes: the client
# slices a JavaScript string, and a byte offset into a line holding one non-ASCII character
# would place every span after it one to the left.


def _rows(store: Store, sql: str, args: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(r) for r in store.query(sql, args)]


# There is no `_short` here any more, and no `_resolve_path` either. Both existed to
# reconcile a stored absolute path with the relative one a reader should see -- one
# shortening it for the screen, the other guessing which spelling a request meant. Paths
# are stored relative to the tree they were read from, so there is one spelling, it is the
# one a reader wants, and the reconciliation has nothing left to reconcile.


# --------------------------------------------------------------------------- #
# The file list
# --------------------------------------------------------------------------- #

def build_files(store: Store, source: SourceStore | None, *,
                revision: str | None = None) -> dict[str, Any]:
    """Every analysed file, complete and unbounded, with the counts that earn a column.

    The spine is the graph's `files` table rather than the sidecar's paths, because the
    question is "what was analysed" and a map handed over without its source must still be
    able to answer it. Whether the sidecar can *open* each one is a separate flag, and the
    two absences are told apart: no sidecar at all, and a sidecar that does not hold this
    file. Rule 8 -- there is no `LIMIT` here and there is not meant to be one.

    `revision` is **which version's bytes**, and it is the caller's to name. There is one
    sidecar per program holding every revision, so its own default is the newest snapshot
    -- which is the right answer only while the newest is also the version being read. It
    stopped being that the day a reader could switch the base, and this list would then
    have stated the newest snapshot's line counts beside an older version's routine and
    boundary counts: two versions in one row, agreeing about nothing (rule 51).
    """
    lines_by_path = source.held_paths(revision=revision) if source is not None else {}

    def counts(sql: str) -> dict[str, int]:
        return {str(r["file"]): int(r["n"]) for r in _rows(store, sql, {})}

    routines = counts(queries.CODE_FILE_ROUTINE_COUNTS)
    boundaries = counts(queries.CODE_FILE_BOUNDARY_COUNTS)
    ids = counts(queries.CODE_FILE_ID_COUNTS)
    comments = counts(queries.CODE_FILE_COMMENT_COUNTS)

    files: list[dict[str, Any]] = []
    for row in _rows(store, queries.CODE_FILES, {}):
        full = str(row["path"])
        files.append({
            "path": full,
            "module": str(row["module"]),
            "lang": str(row["lang"]),
            "lines": lines_by_path.get(full, 0),
            "routines": routines.get(full, 0),
            "boundaries": boundaries.get(full, 0),
            "ids": ids.get(full, 0),
            "comments": comments.get(full, 0),
            # A file the map read but the sidecar cannot open is a real state: `--no-source`
            # for one file is impossible, but a map handed on without its sidecar is not,
            # and neither is a file that became unreadable during capture.
            "held": full in lines_by_path,
        })

    return {
        "files": files,
        "total": len(files),
        "sidecar": source is not None,
        # The revision these counts are *of*, resolved rather than asked for. Rule 13: the
        # number beside a claim and the claim have to be about the same thing.
        "revision": (source.resolve_revision(revision) if source is not None else None),
    }


# --------------------------------------------------------------------------- #
# One file
# --------------------------------------------------------------------------- #

def _place(text: str, needle: str) -> int | None:
    """The column of `needle` in `text`, but only when there is exactly one of it.

    `None` means "somewhere on this line, and this file cannot say where" -- which is a
    different answer from "not on this line", and the caller keeps them apart. Plain string
    counting rather than a regular expression, because an expression written at a call site
    is full of dots and brackets and would have to be escaped to be searched for literally.
    """
    if not needle or text.count(needle) != 1:
        return None
    return text.index(needle) + 1


def _link_spans(lines: list[str], calls: list[dict[str, Any]],
                defs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Inline spans, and how many wanted one and could not have it.

    Overlaps are dropped rather than drawn. Two spans claiming the same characters cannot
    both be right, and a link whose text belongs to another link is a click that lands
    somewhere the reader did not aim -- the same argument rule 47 makes about two pickable
    layers reporting through one handler.
    """
    wanted: list[dict[str, Any]] = []

    for c in calls:
        if not c.get("id"):
            continue                        # external or unresolved: real, and not a link
        n = int(c["line"])
        if not (1 <= n <= len(lines)):
            continue
        col = _place(lines[n - 1], str(c["expr"]))
        if col is None:
            continue
        wanted.append({"line": n, "col": col, "len": len(str(c["expr"])),
                       "id": str(c["id"]), "kind": "call", "label": str(c["expr"]),
                       "confidence": str(c.get("confidence") or "")})

    for d in defs:
        n = int(d["line"])
        if not (1 <= n <= len(lines)):
            continue
        col = _place(lines[n - 1], str(d["name"]))
        if col is None:
            continue
        wanted.append({"line": n, "col": col, "len": len(str(d["name"])),
                       "id": str(d["id"]), "kind": "def", "label": str(d["name"]),
                       "confidence": "CERTAIN"})

    by_line: dict[int, list[dict[str, Any]]] = {}
    for s in wanted:
        by_line.setdefault(int(s["line"]), []).append(s)

    placed: list[dict[str, Any]] = []
    dropped = 0
    for n in sorted(by_line):
        taken: list[tuple[int, int]] = []
        for s in sorted(by_line[n], key=lambda x: (int(x["col"]), -int(x["len"]))):
            a, b = int(s["col"]), int(s["col"]) + int(s["len"])
            if any(a < y and x < b for x, y in taken):
                dropped += 1
                continue
            taken.append((a, b))
            placed.append(s)
    return placed, dropped


def build_file(store: Store, source: SourceStore | None,
               asked: str, *, revision: str | None = None) -> dict[str, Any]:
    """One file, whole, with its links and its margin.

    Three absences, told apart rather than blurred, exactly as `/api/source` tells them
    apart: no sidecar beside this map, a sidecar that does not hold this file, and a path
    the map never analysed.

    `revision` names which version's bytes to lay the map over, and getting it wrong is
    not a subtle failure. Serving Mensores' older graph while the sidecar defaulted to its
    newest snapshot returned `_queue.py` at **674 lines with the 595-line version's marks
    on it** -- every link past the first divergence underlining the wrong characters, and
    a footer naming the revision the bytes came from while the margin came from another.
    Nothing raised, and the page looked exactly like a page that worked.
    """
    if not asked:
        return {"available": False, "reason": "no path asked for"}
    full = asked
    rows = _rows(store, "SELECT module, lang, errors FROM files WHERE path = :p",
                 {"p": full})
    if not rows:
        return {"available": False, "file": asked,
                "reason": "this map did not analyse that file"}
    meta = rows[0]

    if source is None:
        return {"available": False, "file": full,
                "module": str(meta["module"]),
                "reason": "no source sidecar beside this map"}
    body = source.text(full, revision=revision)
    if body is None:
        return {"available": False, "file": full,
                "module": str(meta["module"]),
                "reason": "the sidecar does not hold this file"}

    # An array of strings rather than `{n, text}` objects, and `first` says where it starts.
    # A whole file always starts at line one, so the number on every object would be its own
    # index -- half the payload of the largest file spent restating what counting says.
    lines = body.split("\n")

    calls = _rows(store, queries.CODE_CALLS, {"file": full})
    routines = _rows(store, queries.CODE_DEFS_ROUTINES, {"file": full})
    structures = _rows(store, queries.CODE_DEFS_STRUCTURES, {"file": full})

    # `<module>` is the synthetic scope that owns what no function does (rule 18). It is a
    # real node and the reader can select it, but it does not have a `def` line to underline.
    named = [r for r in routines if str(r["name"]) != "<module>"]
    links, unplaced = _link_spans(lines, calls, named + [
        {"line": s["line"], "name": s["name"], "id": s["id"]} for s in structures
    ])

    defs = [{
        "id": str(r["id"]), "name": str(r["name"]), "qualname": str(r["qualname"]),
        "line": int(r["line"]), "line_end": int(r["line_end"]),
        "kind": "module" if str(r["name"]) == "<module>" else (
            "method" if int(r["is_method"] or 0) else "routine"),
        "class_name": str(r["class_name"]), "visibility": str(r["visibility"]),
        "nested": bool(r["is_nested"]),
    } for r in routines] + [{
        "id": str(s["id"]), "name": str(s["name"]), "qualname": str(s["name"]),
        "line": int(s["line"]), "line_end": int(s["line"]),
        "kind": str(s["kind"]).lower(), "class_name": "", "visibility": "",
        "nested": False,
    } for s in structures]
    defs.sort(key=lambda d: (int(d["line"]), str(d["name"])))

    marks = _margin(store, full)

    return {
        "available": True,
        "file": full,
        "module": str(meta["module"]), "lang": str(meta["lang"]),
        "errors": str(meta["errors"] or "[]"),
        "first": 1,
        "lines": lines,
        "defs": defs,
        "links": links,
        "marks": marks,
        # Design rule 1: a link that could not be placed is not a link that is missing, and
        # the page says so rather than leaving the reader to notice a name is not clickable.
        "placed": len(links),
        "unplaced": unplaced,
        "resolved": sum(1 for c in calls if c.get("id")),
        "calls": len(calls),
        "revision": source.resolve_revision(revision),
    }


def _margin(store: Store, full: str) -> list[dict[str, Any]]:
    """What each line *is*, for the gutter beside it.

    **Rule 40 is enforced here.** A boundary already named by a more specific record on the
    same line is not counted again: 991 of Mensores' 1,316 DATABASE boundaries sit on a line
    with a `sql_ops` row, and all twenty NETWORK ones sit on a `net_calls` row. Two correct
    numbers about one act, neither saying what it counted. The tolerance is one line and is
    a judgment: the detectors disagree by a line on a multi-line statement, one recording
    the call site and the other the statement's start.

    And its companion, which the first attempt at that rule got wrong: excluding the general
    record must not lose what only it recorded. A DATABASE boundary on a routine with no SQL
    at all -- 43 of them open a connection and run nothing -- keeps its mark.
    """
    marks: list[dict[str, Any]] = []

    sql_lines: set[int] = set()
    for o in _rows(store, queries.CODE_SQL_OPS, {"file": full}):
        n = int(o["line"])
        sql_lines |= {n - 1, n, n + 1}
        marks.append({"line": n, "kind": "sql", "label": str(o["operation"]),
                      "detail": str(o["tbl"]), "note": str(o["direction"])})

    net_lines: set[int] = set()
    for x in _rows(store, queries.CODE_NET_CALLS, {"file": full}):
        n = int(x["line"])
        net_lines |= {n - 1, n, n + 1}
        detail = " ".join(p for p in [str(x["verb"]), str(x["destination"])] if p)
        note = ", ".join(
            p for p in [f"timeout {x['timeout']}" if x["timeout"] else "",
                        f"{x['retries']} retries" if x["retries"] else ""] if p)
        marks.append({"line": n, "kind": "net", "label": str(x["protocol"]),
                      "detail": detail, "note": note})

    for b in _rows(store, queries.CODE_BOUNDARIES, {"file": full}):
        n = int(b["line"])
        kind = str(b["kind"])
        if kind == "DATABASE" and n in sql_lines:
            continue
        if kind in ("NETWORK", "LLM_API") and n in net_lines:
            continue
        marks.append({"line": n, "kind": "boundary", "label": kind,
                      "detail": str(b["target"]), "note": str(b["direction"])})

    for k in _rows(store, queries.CODE_CONSTANTS, {"file": full}):
        marks.append({"line": int(k["line"]), "kind": "constant", "label": str(k["name"]),
                      "detail": str(k["type"]),
                      "note": "final" if int(k["is_final"] or 0) else "",
                      "id": f"const:{k['module']}.{k['name']}"})

    for i in _rows(store, queries.CODE_IMPORTS, {"file": full}):
        detail = str(i["module"]) + ("." + str(i["name"]) if int(i["is_from"] or 0) else "")
        marks.append({"line": int(i["line"]), "kind": "import", "label": "import",
                      "detail": detail,
                      "note": f"as {i['alias']}" if i["alias"] != i["name"] else ""})

    for a in _rows(store, queries.CODE_ARTEFACTS, {"file": full}):
        marks.append({"line": int(a["line"]), "kind": "artefact", "label": str(a["name"]),
                      "detail": str(a["kind"]),
                      "note": "pattern" if int(a["is_pattern"] or 0) else ""})

    for t in _rows(store, queries.CODE_DB_TABLES, {"file": full}):
        marks.append({"line": int(t["line"]), "kind": "table", "label": str(t["name"]),
                      "detail": "CREATE TABLE",
                      "note": "temporary" if int(t["temporary"] or 0) else ""})

    for a in _rows(store, queries.CODE_ANNOTATIONS, {"file": full}):
        marks.append({"line": int(a["line"]), "kind": "id", "label": str(a["value"]),
                      "detail": str(a["kind"]), "note": ""})

    # A call into somebody else's code, pinned by an import (see `CODE_LIBRARY_CALLS`).
    #
    # The first version of this marked every `external` call, and the readout said what was
    # wrong with it: `int` on its own line, labelled *leaves the program*. Rule 26 is about
    # a call whose far end we cannot see; a builtin is not that, and `len(x)` is internal
    # computation, which this tool exists not to report. It also stated boundary touches a
    # third time, beside the boundary mark and the SQL mark for the same act -- rule 40, in
    # the same function as the test written for it. 798 marks on `audit.py` became 210.
    for x in _rows(store, queries.CODE_LIBRARY_CALLS, {"file": full}):
        marks.append({"line": int(x["line"]), "kind": "library", "label": str(x["expr"]),
                      "detail": f"into {x['via']}", "note": ""})

    marks.sort(key=lambda m: (int(m["line"]), str(m["kind"]), str(m["label"])))
    return marks
