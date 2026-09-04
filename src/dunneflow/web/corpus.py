"""The document corpus: the program's own prose, readable at last.

**Lane 1 of Document mode, and `documents.py` is lane 2 -- a close name for a different
subject, so it is worth being blunt about which is which.** This reads the documents
*somebody wrote* and the scan found beside the source: 2,064 Markdown and text files on
Mensores, mined into `docs.db` for 29,980 headings and 235 definitions and, until this
module, readable nowhere in the tool. `documents.py` builds **the map's** eight documents
out of the graph -- prose this tool generates about the program. Neither is the other's
renderer, and neither can be built from the other's rows.

**Two stores answer together and neither can do it alone.** `docs.db` records what a
document *says* -- its title, its class, its headings and the line each sits on -- and has
no body column at all; `docsource.db` holds the bodies, content-addressed, and knows
nothing about what is in them. So the list is the first store's, the reader is both, and
each absence is a separate state with its own wording (design rule 21, rule 11): a program
analysed with `--no-docs` has no list to show, and one analysed with `--no-doc-source` has
a complete list where nothing opens. Told apart, never blurred into "nothing here".

The SQL lives here rather than in `queries.py`, which is the **graph's** query book down to
its `DOC_*` entries -- those select from `routines` and `boundaries` to build lane 2. A
statement against `docs.db` filed beside statements against `graph.db` would be two schemas
under one heading, and the next person to add a column would have to read both to know
which one they were in.

Whole lists and whole documents, never a window (rule 8). The largest document in the
corpus is 1.33 MB and it is reachable; what is bounded is the *work*, which is chunk 4's
job in the client -- rule 55.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from ..docstore import DocStore
from ..sourcedb import SourceStore

# Every document, in path order. No `LIMIT`, and there is not meant to be one: this is a
# reference, and rule 8 bounds a diagram rather than a list of facts. Duplicates are
# carried rather than filtered -- `duplicate_of` is a fact about the corpus, and a reader
# who cannot see the eight copies cannot tell a deduplicated list from a short one.
CORPUS_DOCUMENTS = """
SELECT path, fmt, title, doc_class, size, words, duplicate_of, errors
  FROM documents
 ORDER BY path
"""

CORPUS_HEADING_COUNTS = "SELECT doc, COUNT(*) n FROM headings GROUP BY doc"
CORPUS_DEFINITION_COUNTS = "SELECT doc, COUNT(*) n FROM definitions GROUP BY doc"

CORPUS_DOCUMENT = """
SELECT path, fmt, title, doc_class, size, words, duplicate_of, errors, mtime_ns
  FROM documents
 WHERE path = ?
"""

# Ordered by line, because that is the order the document is read in and the order a side
# nav has to offer. Not by level: a table of contents sorted by depth is a list of
# headings that no longer describes a document.
CORPUS_HEADINGS = """
SELECT level, text, line
  FROM headings
 WHERE doc = ?
 ORDER BY line, level
"""

# What each absence is called. Written once because both routes and both stores say them,
# and three spellings of "there is no document sidecar here" is three things a guard has
# to know about (rule 51).
NO_DOCS = "this map was made without reading documentation (--no-docs)"
NO_SIDECAR = "no document bodies were captured beside this map (--no-doc-source)"
NO_REVISION = "the document sidecar holds no bodies for the version on screen"
NOT_HELD = "the document sidecar does not hold this file at this revision"
NOT_SCANNED = "the documentation scan did not read this file"


def serving(bodies: SourceStore | None, revision: str | None, *,
            absent: str = NO_SIDECAR,
            stale: str = NO_REVISION) -> tuple[SourceStore | None, str | None]:
    """The sidecar to read *this version's* prose out of, or the reason there is none.

    **The whole of this function is one `None` that means two things.** `_sidecar_revision`
    returns `None` for "this sidecar cannot serve the version on screen"; every store here
    reads `revision=None` as "the current one" and resolves it to the newest snapshot. The
    two met, and the newer meaning won: serving Mensores' 2026-08-26 graph, whose document
    bodies were never captured, listed all 2,041 of its documents as openable and served
    the **2026-08-29** prose under them -- every heading's line number landing wherever the
    text had since moved. Rule 70, one corpus over from where it was first paid for, and
    invisible until a base switch and a curl put the two side by side.

    So `revision` is unambiguous from here down: a string is a snapshot, and `None` is a
    refusal with a sentence to go with it. Its own function because three readers need the
    same decision (rule 51), and because the states it separates are the ones design rule
    21 exists for -- an absence with no reason reads as an empty program.

    The two sentences are arguments with document-corpus defaults, because the *decision*
    is the same for both sidecars and only the wording differs. `/api/source` and the
    glossary's capability block ask this question of `source.db` and have their own two
    spellings; a second implementation of the decision beside them would be correct on the
    day it was written and would be the thing that drifts (rule 51).
    """
    if bodies is None:
        return None, absent
    if revision is None:
        return None, stale
    return bodies, None


def _errors(raw: str) -> list[Any]:
    """The recorded errors, or none -- a malformed column is never an exception here.

    Ingest records a failure rather than dropping the document, so this column is the one
    place a broken document announces itself. Refusing to list the whole corpus because one
    row's JSON is unreadable would hide 2,063 documents behind the one that is already
    known to be damaged.
    """
    try:
        got = json.loads(raw or "[]")
    except ValueError:
        return []
    return got if isinstance(got, list) else []


def _counts(docs: DocStore, sql: str) -> dict[str, int]:
    return {str(r["doc"]): int(r["n"]) for r in docs.query(sql)}


# --------------------------------------------------------------------------- #
# The list
# --------------------------------------------------------------------------- #

def build_corpus(docs: DocStore | None, bodies: SourceStore | None, *,
                 revision: str | None = None) -> dict[str, Any]:
    """Every document the scan read, complete, with the counts that earn a column.

    `revision` is **which version's bodies**, and it is the caller's to name for the same
    reason `build_files` insists on it: there is one document sidecar per program holding
    every revision, so its own default is the newest snapshot -- right only while the
    newest is also the version being read (rule 70). Reading it wrong here would mark a
    document openable that this version's map has no line numbers for.

    The class breakdown is a `Counter` over the rows this returns, **not** a second
    `GROUP BY`. Rule 13: the number printed beside a group and the rows behind it have to
    be the same query, or a filter added to one and not the other puts a count of 1,601
    over a list of 1,600 and nothing anywhere is wrong enough to notice.
    """
    if docs is None:
        return {"available": False, "reason": NO_DOCS}

    # Taken *before* the decision below, because the two say different things. `sidecar`
    # is whether this program has document bodies at all -- a fact about the directory,
    # and the one that decides whether re-analysing would help. Whether they can be read
    # at the version on screen is `reason`'s question, and answering both with one flag
    # would report a program that has a sidecar as one that does not (rule 32).
    has_sidecar = bodies is not None
    bodies, why = serving(bodies, revision)
    held = bodies.held_paths(revision=revision) if bodies is not None else {}
    headings = _counts(docs, CORPUS_HEADING_COUNTS)
    definitions = _counts(docs, CORPUS_DEFINITION_COUNTS)

    documents: list[dict[str, Any]] = []
    classes: Counter[str] = Counter()
    for row in docs.query(CORPUS_DOCUMENTS):
        path = str(row["path"])
        classes[str(row["doc_class"])] += 1
        documents.append({
            "path": path,
            "fmt": str(row["fmt"]),
            "title": str(row["title"]),
            "class": str(row["doc_class"]),
            "size": int(row["size"]),
            "words": int(row["words"]),
            "headings": headings.get(path, 0),
            "definitions": definitions.get(path, 0),
            "duplicateOf": str(row["duplicate_of"]),
            "errors": _errors(str(row["errors"])),
            # Line counts come off the blob, so this is the sidecar's own answer rather
            # than a guess from `size`. A document the scan read but the sidecar cannot
            # open is a real state -- a map handed on without its document bodies -- and
            # it is a different one from a corpus with no sidecar at all.
            "lines": held.get(path, 0),
            "held": path in held,
        })

    return {
        "available": True,
        "documents": documents,
        "total": len(documents),
        # Ordered by size, largest first, because that is the order the reader wants a
        # 1,601-strong group offered in. Ties broken by name so the order is total: two
        # classes of equal size would otherwise come back in whatever order the `Counter`
        # was filled, which is stable only until a document is added.
        "classes": [{"name": name, "n": n}
                    for name, n in sorted(classes.items(), key=lambda kv: (-kv[1], kv[0]))],
        "sidecar": has_sidecar,
        "openable": sum(1 for d in documents if d["held"]),
        "reason": why,
        # The revision these line counts are *of*, resolved rather than asked for (rule 13).
        "revision": bodies.resolve_revision(revision) if bodies is not None else None,
    }


# --------------------------------------------------------------------------- #
# One document
# --------------------------------------------------------------------------- #

def build_document(docs: DocStore | None, bodies: SourceStore | None, path: str, *,
                   revision: str | None = None) -> dict[str, Any]:
    """One document: what the scan said about it, its headings, and its text.

    The body is sent **whole and as one string**, unlike `/api/source`'s numbered lines,
    and the difference is what reads it. A renderer needs the document entire because
    block structure spans lines -- a fenced block cut in half is not a fenced block -- and
    it re-derives the line numbers itself from `token.map`, which is the property
    `markdown-it` was chosen for. Numbering here would be a second answer to a question
    the renderer has to answer anyway (rule 13).

    Three absences, three sentences. No documentation scanned; a document the scan never
    read; a document read but whose body was never captured. They look identical on a
    blank pane and they are three different things to do about it.
    """
    if not path:
        return {"available": False, "reason": "no document asked for"}
    if docs is None:
        return {"available": False, "path": path, "reason": NO_DOCS}

    rows = docs.query(CORPUS_DOCUMENT, (path,))
    if not rows:
        return {"available": False, "path": path, "reason": NOT_SCANNED}
    row = rows[0]

    return {
        "available": True,
        "document": {
            "path": path,
            "fmt": str(row["fmt"]),
            "title": str(row["title"]),
            "class": str(row["doc_class"]),
            "size": int(row["size"]),
            "words": int(row["words"]),
            "duplicateOf": str(row["duplicate_of"]),
            "errors": _errors(str(row["errors"])),
        },
        "headings": [{"level": int(h["level"]), "text": str(h["text"]),
                      "line": int(h["line"])}
                     for h in docs.query(CORPUS_HEADINGS, (path,))],
        "body": body_of(bodies, path, revision=revision),
    }


def body_of(bodies: SourceStore | None, path: str, *,
            revision: str | None = None) -> dict[str, Any]:
    """The text of one document, or the reason there is none.

    Its own function because `/api/doc` and `/api/docsource` both need exactly this
    decision and there are three ways to get it wrong -- an absent sidecar, a sidecar with
    nothing for the version on screen, and a sidecar that does not hold this path. Same
    shape, different wording, and rule 51: the rule lives where all the callers pass.
    """
    bodies, why = serving(bodies, revision)
    if bodies is None:
        return {"available": False, "reason": why}
    text = bodies.text(path, revision=revision)
    if text is None:
        return {"available": False, "reason": NOT_HELD}
    return {"available": True, "text": text, "lines": text.count("\n") + 1}
