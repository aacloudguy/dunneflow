"""Search inside source: the text the graph cannot answer about.

The graph already answers a *different* question, and answers it well. `touches`, `impact`
and the glossary search **names and meanings** -- they know that `_emit` is a routine, what
calls it and what the project says the word means. What none of them can find is the word
`emit` inside a comment, inside a string literal, or on a line that carries neither. That
is what this is for, and it is why it cannot be assembled out of the existing queries.

**Files first, then lines, and that decides everything else here.** A search for `quaestor`
on Mensores matches 782 lines in 166 files; a search for `e` matches 133,454 lines in all
626. One flat list of hits is the haystack again -- rule 45's second half, which says the
bound is a better *answer* and not only a cheaper one. So there are two endpoints:

* `search_files()` -- how many lines matched, in which files, with a count on each. 626
  rows at the very worst, and never bounded (rule 8).
* `search_in_file()` -- one file's hits, with **what the map knows about each of them**:
  the marks in its margin, the links on it, and the routine it sits inside.

The second is affordable only because of the first. The margin costs ten queries per file,
so computing it for the 166 files a broad search touches would be 1,660 queries behind a
keystroke; computing it for the one file a reader opened is the 53-59 ms `/api/file`
already measures. **The expensive answer is only ever built for what someone asked to see.**

Both are built from `web/code.py` as it stands -- `_link_spans`, `_margin`,
`CODE_DEFS_ROUTINES` -- rather than from copies of them. Rule 51: a second implementation
agrees with the first until the day one of them is edited, and a margin that disagreed with
the code browser's for the same line would be two answers to one question.

**Cost, measured on Mensores before any of this was designed.** Inflating all 626 blobs is
86 ms and happens once per session; a case-insensitive scan of all 184,722 lines is 20-30
ms, and a regex is 83 ms. Rule 45's fear does not land on the scan -- the whole program is
7.8 MB of text, and reading it is cheap. It lands entirely on what is done with the answer.

**And what is *not* here: an index.** SQLite's FTS5 was the obvious reach and is wrong for
this. It is token-based, so it cannot find `_emit` inside `self._emit`, cannot find a
substring of a string literal, and cannot answer a regex at all -- which between them are
most of what someone searching source is looking for. An index that answers a different
question quickly is not faster, it is wrong. Rule 1: precision first.
"""

from __future__ import annotations

import re
import time
from typing import Any

from ..sourcedb import SourceStore
from ..store import Store
from . import queries
from .code import _link_spans, _margin, _rows

# What a search will open by itself, and it is the same number the routine list uses for
# the same reason. See `SEARCH_OPEN_MAX` in `shell.js`: opening every package a broad query
# matched built 3,413 rows in 483 ms, and 1,924 rows was the worse *answer* as well as the
# slower one. Enforced on the client, where the opening happens; stated here because the
# server is what knows the size before anything is drawn.
BROAD = 200


class BadPattern(ValueError):
    """The query is not a usable pattern. Carries what to tell the reader."""


# --------------------------------------------------------------------------- #
# The matcher
# --------------------------------------------------------------------------- #

def matcher(q: str, *, case: bool = False, word: bool = False,
            regex: bool = False) -> re.Pattern[str]:
    """One compiled pattern, from the four flags, for **both** endpoints.

    One matcher and not two, because rule 13 is about exactly this: the count printed on a
    file row and the lines drawn beneath it are the same claim, and the fastest way to make
    them disagree is to let the cheap pass and the detailed pass decide "matches" for
    themselves. Case folding is the easy place to do it -- `str.lower()` in one and
    `re.IGNORECASE` in the other differ on a handful of characters, and the row would print
    a number the lines under it could not produce.

    Whole-word is `\\b`-delimited around an escaped needle rather than a second code path
    for the same reason.

    **Regex turns whole-word off**, and the caller must say so on the page. A regex writes
    its own `\\b`, so the two controls answer one question -- and rule 46 is that two
    questions sharing an answer is how one of them gets answered by accident.
    """
    if not q:
        raise BadPattern("nothing to search for")
    flags = 0 if case else re.IGNORECASE
    if regex:
        try:
            return re.compile(q, flags)
        except re.error as err:
            # Named, never swallowed. A bad pattern returning no rows is indistinguishable
            # from a good pattern matching nothing, and those are opposite claims -- the
            # `(no rows)` argument rule 20 was written from.
            raise BadPattern(f"that is not a regular expression: {err}") from err
    body = re.escape(q)
    return re.compile(rf"\b{body}\b" if word else body, flags)


def word_applies(q: str) -> bool:
    """Can a whole-word search of this needle match anything at all?

    `\\b` sits between a word character and a non-word one, so `\\b(\\)\\b` can never match
    and whole-word `()` silently answers nothing. Told apart from a real empty result rather
    than blurred with it, which is the same distinction `BadPattern` exists for.
    """
    return bool(q) and (bool(re.match(r"\w", q[0])) or bool(re.search(r"\w$", q)))


# --------------------------------------------------------------------------- #
# The file-level answer
# --------------------------------------------------------------------------- #

def search_files(store: Store, source: SourceStore | None, q: str, *,
                 case: bool = False, word: bool = False,
                 regex: bool = False, revision: str | None = None) -> dict[str, Any]:
    """Which files hold a match, and how many lines each.

    **Complete and unbounded** -- rule 8 bounds diagrams, and 626 rows with a count on each
    is a reference list. What is bounded is how many the *client* opens by itself, which is
    a different decision made in a different place and stated where it happens.

    Every count here says what it counted (rule 32). `total` is matching **lines**, not
    matches -- a line holding the needle three times is one line and the reader will see one
    row for it. `bodies` is distinct file *contents* inflated, which is smaller than
    `scanned` on any program holding the same file at two paths.
    """
    started = time.perf_counter()
    if source is None:
        return {"ok": False, "q": q,
                "reason": "no source sidecar beside this map — there is no text to search"}
    try:
        pattern = matcher(q, case=case, word=word, regex=regex)
    except BadPattern as err:
        return {"ok": False, "q": q, "reason": str(err)}

    modules = {str(r["path"]): str(r["module"]) for r in _rows(store, queries.CODE_FILES, {})}

    rows: list[dict[str, Any]] = []
    total = scanned = lines_seen = 0
    bodies: set[str] = set()
    search = pattern.search
    for path, content_hash, lines in source.bodies(revision=revision):
        scanned += 1
        lines_seen += len(lines)
        bodies.add(content_hash)
        hits = [i for i, text in enumerate(lines, 1) if search(text)]
        if not hits:
            continue
        total += len(hits)
        rows.append({
            "path": path,
            "module": modules.get(path, ""), "n": len(hits), "first": hits[0],
        })

    # Most matches first, then by path. A reader searching a word wants the file that is
    # *about* it, and on Mensores that is the file the count puts at the top -- the same
    # ranking the routine list gives packages, and for the same reason.
    rows.sort(key=lambda r: (-int(r["n"]), str(r["path"])))

    # An analysed file the sidecar cannot open was searched by nobody, and a search that
    # quietly covered 620 of 626 files is a silent filter (design rule 1).
    analysed = len(modules)
    return {
        "ok": True, "q": q, "case": case, "word": word, "regex": regex,
        "wordable": word_applies(q) if (word and not regex) else True,
        "total": total, "files": len(rows), "broad": total > BROAD,
        "scanned": scanned, "analysed": analysed, "unheld": max(0, analysed - scanned),
        "lines": lines_seen, "bodies": len(bodies),
        # Which version's text was scanned. The sidecar holds every revision, so a search
        # that did not name one searched the newest snapshot -- and answered about it while
        # the reader was reading another (rule 51).
        "revision": source.resolve_revision(revision),
        "rows": rows,
        "ms": round((time.perf_counter() - started) * 1000, 1),
    }


# --------------------------------------------------------------------------- #
# One file's hits, with what the map knows about them
# --------------------------------------------------------------------------- #

def containing_routine(defs: list[dict[str, Any]], line: int) -> dict[str, Any] | None:
    """The innermost routine whose span holds this line.

    A **range lookup**, and never a name match -- there is no name in the question. Rule 5
    does not arise for the same reason it does not arise for a link: the store already
    recorded where every routine begins and ends, so this only has to read it.

    **Innermost**, which is rule 10 in a lookup. Seven closures called `_close_ladybug` are
    seven routines with seven spans, all of them inside their factory's span; answering with
    the factory would name the enclosing scope rather than the code the line is in. The
    innermost span is the one that starts latest among those that contain the line, because
    a nested definition cannot begin before the one it is nested in.

    `<module>` is a real answer and is kept. It is the scope that owns what no function does
    (rule 18), so a line at module level genuinely sits in it -- returning nothing there
    would say the map knows less than it does.
    """
    best: dict[str, Any] | None = None
    for d in defs:
        if int(d["line"]) <= line <= int(d["line_end"]) and (
                best is None or int(d["line"]) > int(best["line"])):
            best = d
    return best


def search_in_file(store: Store, source: SourceStore | None, q: str, asked: str, *,
                   case: bool = False, word: bool = False,
                   regex: bool = False, revision: str | None = None) -> dict[str, Any]:
    """One file's matching lines, each with its margin, its links and its routine.

    The three absences `/api/file` and `/api/source` already tell apart are told apart here
    too, in the same words: no sidecar beside this map, a sidecar that does not hold this
    file, and a path the map never analysed. Repeating the wording is what keeps them
    distinguishable to a reader who meets them one at a time.
    """
    started = time.perf_counter()
    if source is None:
        return {"ok": False, "q": q, "file": asked,
                "reason": "no source sidecar beside this map"}
    full = asked
    if not _rows(store, "SELECT 1 FROM files WHERE path = :p", {"p": full}):
        return {"ok": False, "q": q, "file": asked,
                "reason": "this map did not analyse that file"}
    lines = source.path_lines(full, revision=revision)
    if lines is None:
        return {"ok": False, "q": q, "file": full,
                "reason": "the sidecar does not hold this file"}
    try:
        pattern = matcher(q, case=case, word=word, regex=regex)
    except BadPattern as err:
        return {"ok": False, "q": q, "file": full, "reason": str(err)}

    hits = [n for n, text in enumerate(lines, 1) if pattern.search(text)]
    if not hits:
        return {"ok": True, "q": q, "file": full,
                "n": 0, "hits": [], "ms": round((time.perf_counter() - started) * 1000, 1)}

    # Everything below is `build_file`'s own machinery, narrowed to the matching lines.
    # Same functions, same store, same rules -- including rule 40's anti-join in `_margin`,
    # which is the reason this is not a fresh set of queries with the same names.
    routines = _rows(store, queries.CODE_DEFS_ROUTINES, {"file": full})
    structures = _rows(store, queries.CODE_DEFS_STRUCTURES, {"file": full})
    calls = _rows(store, queries.CODE_CALLS, {"file": full})
    named = [r for r in routines if str(r["name"]) != "<module>"]
    spans, _ = _link_spans(lines, calls, named + [
        {"line": s["line"], "name": s["name"], "id": s["id"]} for s in structures
    ])

    defs = [{"id": str(r["id"]), "name": str(r["name"]), "qualname": str(r["qualname"]),
             "line": int(r["line"]), "line_end": int(r["line_end"])} for r in routines]

    by_line: dict[int, list[dict[str, Any]]] = {}
    for s in spans:
        by_line.setdefault(int(s["line"]), []).append(s)
    marks_by_line: dict[int, list[dict[str, Any]]] = {}
    for m in _margin(store, full):
        marks_by_line.setdefault(int(m["line"]), []).append(m)

    out: list[dict[str, Any]] = []
    for n in hits:
        where = containing_routine(defs, n)
        # The whole line, never a window around the match. Rule 8 says never truncate at
        # ingest, and a line cut to fit a pane is a value shortened before it reaches the
        # reader; the pane can scroll, and the code browser is one click away regardless.
        out.append({
            "line": n, "text": lines[n - 1],
            # Where to mark, one-based, as (column, length). A zero-width match is dropped
            # rather than sent as a length of nothing: `a*` genuinely matches at every
            # position, and a mark with no text under it is a highlight over the character
            # beside it -- inventing a position, which is the same thing rule 1 refuses
            # when a call site has no column.
            "at": [[m.start() + 1, m.end() - m.start()]
                   for m in pattern.finditer(lines[n - 1]) if m.end() > m.start()],
            "links": by_line.get(n, []),
            "marks": marks_by_line.get(n, []),
            "in": None if where is None else {
                "id": where["id"], "name": where["name"], "qualname": where["qualname"],
            },
        })

    return {
        "ok": True, "q": q, "file": full,
        "n": len(out), "lines": len(lines), "hits": out,
        "revision": source.resolve_revision(revision),
        "ms": round((time.perf_counter() - started) * 1000, 1),
    }
