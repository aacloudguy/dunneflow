"""The text lane of a comparison: which files differ, and where in one of them.

`changes.py` is the other lane and it is the half nothing else can give -- what a routine
*does* differently, which `git diff` cannot state at all. This is the ordinary half, and
saying so plainly is the point: a reader comparing two versions wants both, and only one
of them is worth being clever about.

**The file-level answer costs no body reads at all.** `source.db` is content-addressed --
`paths(revision, path) -> hash` and one blob per unique body -- so a file that did not
change holds the *same hash* at both revisions. Comparing the two path maps is therefore
the file-level diff, exactly, with nothing inflated and no text compared. Two indexed
queries over 628 rows each answer "which twelve of these 628 files are worth reading".

That is also what makes the expensive lane affordable: `difflib` only ever runs on a file
the reader has opened, and only when the hashes already say it differs.

**Neither end is claimed to be older**, the same as everywhere else in this comparison.
The `base` is the version the map is showing -- and, here, the version whose *bytes are on
screen* -- and the `compared` is what it is held against. A line the base has and the
compared does not was deleted or added depending on an assumption the reader owns and the
strip states; this module says only which side a line is on. `only_in_base` and
`only_in_compared`, never `added` and `removed` (rule 65).

**`autojunk=False`, and that is measured rather than preferred.** `SequenceMatcher`'s
heuristic treats a line appearing in more than 1% of a sequence longer than 200 lines as
junk, and in source that is every blank line, every bare `)` and every `return` -- so it
aligns worse where source is most repetitive. On Lictores' twelve modified files it cost
10 ms with the heuristic and 59 ms without, and without it `cli/scribe.py` reports 57
removed lines rather than 60 and `_migrations.py` 13 rather than 15. Three false removals
in one file for 49 ms across the whole set is not a trade worth taking, and the worst
single file -- `mcp/_server.py`, 5,838 lines against 5,903 -- is 40 ms.
"""

from __future__ import annotations

import difflib
import time
from typing import Any

from ..sourcedb import SourceStore

# What a path is, across two snapshots. Named for **where it is**, never for what befell
# it -- rule 65, and the same four words the change worklist uses, so a reader meets one
# vocabulary rather than two. `same` is a real answer and the commonest one: 613 of
# Lictores' 628 files, and a comparison that could not say so would be reporting only the
# exceptions and calling it a comparison.
SAME = "same"
MODIFIED = "modified"
ONLY_IN_BASE = "only_in_base"
ONLY_IN_COMPARED = "only_in_compared"
STATUSES = (SAME, MODIFIED, ONLY_IN_BASE, ONLY_IN_COMPARED)

_HELD = ("SELECT p.path AS path, p.hash AS hash, b.lines AS lines "
         "FROM paths p JOIN blobs b ON b.hash = p.hash WHERE p.revision = ?")


def _held(source: SourceStore, revision: str) -> dict[str, tuple[str, int]]:
    """Every path one revision maps, as `path -> (hash, lines)`. No body is read.

    The line count rides on the blob because `add_blob` recorded it, so a file list with
    a size beside every row costs one join rather than 628 decompressions.
    """
    return {str(r["path"]): (str(r["hash"]), int(r["lines"]))
            for r in source.conn.execute(_HELD, (revision,))}


def pair(source: SourceStore | None, base: str | None,
         compared: str | None) -> dict[str, Any]:
    """Every file in either version, and which of the four states it is in.

    Complete and unbounded -- rule 8. 628 rows with a status on each is a reference list,
    and the 613 that did not change are not noise to be filtered out: *nothing happened
    here* is the answer to most of the question, and a list holding only the exceptions
    cannot be told from a list that lost some.

    Three refusals, told apart, because "there is no comparison" and "the comparison found
    nothing" are opposite claims (design rule 1): no sidecar, a revision this sidecar does
    not hold, and the same revision on both ends.
    """
    started = time.perf_counter()
    if source is None:
        return {"available": False,
                "reason": "no source sidecar beside this map — the bodies it would "
                          "compare were never kept"}
    if not base or not compared:
        return {"available": False, "reason": "two versions are needed to compare"}
    if base == compared:
        return {"available": False,
                "reason": "a version compared with itself has nothing to say"}
    for which, rev in (("base", base), ("compared", compared)):
        if not source.holds_revision(rev):
            return {"available": False,
                    "reason": f"this sidecar holds no source for the {which} version "
                              f"({rev}) — it was analysed with `--no-source`, or its "
                              f"bodies were never captured"}

    b, c = _held(source, base), _held(source, compared)
    rows: list[dict[str, Any]] = []
    counts = dict.fromkeys(STATUSES, 0)
    for path in sorted(set(b) | set(c)):
        in_b, in_c = b.get(path), c.get(path)
        if in_b is None:
            status = ONLY_IN_COMPARED
        elif in_c is None:
            status = ONLY_IN_BASE
        else:
            # The whole file-level diff, and it is a string comparison. Two paths holding
            # one body are one blob, so equal hashes are equal bytes -- not "probably",
            # since the hash is what the store keyed the body by in the first place.
            status = SAME if in_b[0] == in_c[0] else MODIFIED
        counts[status] += 1
        rows.append({
            "path": path,
            "status": status,
            "base_lines": in_b[1] if in_b else 0,
            "compared_lines": in_c[1] if in_c else 0,
        })

    return {
        "available": True,
        "base": base,
        "compared": compared,
        "counts": counts,
        "total": len(rows),
        "identical": counts[SAME] == len(rows),
        "rows": rows,
        "ms": round((time.perf_counter() - started) * 1000, 1),
    }


def lines(source: SourceStore | None, path: str, base: str | None,
          compared: str | None) -> dict[str, Any]:
    """One file's text difference, as something that can be drawn over the base's lines.

    The shape is decided by what the code browser already is: a list of the **base's**
    lines, numbered from one, with the map's marks in the margin. So the answer is not a
    unified diff to render instead -- it is two things to lay over the lines already on
    screen.

    * **`base_only`** -- line numbers of the base that the compared version does not have.
      A number, because the client has the text.
    * **`inserts`** -- runs of the *compared* version's lines, each anchored `after` a
      base line number (`0` meaning before the first). The text travels because the client
      does not have it: these lines are not in the file it is showing.

    Anchoring an insert to a base line is the one position invented here, and it is not
    invented -- `SequenceMatcher` states exactly where a run belongs relative to both
    sequences, and `i1` is that place. What is *not* claimed is a column, a routine or an
    identity for those lines; they are lines from another version, drawn as such.

    A `replace` opcode is a deletion and an insertion at the same place and is recorded as
    both, rather than as a third kind. Two rewritten lines are not "one changed line" in
    any way this can defend -- their contents may share nothing -- and inventing a pairing
    between them is inventing an identity (rule 30's shape in a diff).
    """
    started = time.perf_counter()
    if source is None:
        return {"available": False, "file": path,
                "reason": "no source sidecar beside this map"}
    if not base or not compared:
        return {"available": False, "file": path,
                "reason": "two versions are needed to compare"}
    a_lines = source.path_lines(path, revision=base)
    b_lines = source.path_lines(path, revision=compared)
    if a_lines is None and b_lines is None:
        return {"available": False, "file": path,
                "reason": "neither version holds this file"}
    # A file on one side only is a real answer and it is *this* function's to give, not a
    # caller's to infer from a missing one: the code browser is showing the base, so a
    # file the base does not have has no lines to overlay and a file the compared does not
    # have is entirely one side's. Both are stated rather than returned as an absence.
    if a_lines is None:
        return {"available": True, "file": path, "base": base, "compared": compared,
                "status": ONLY_IN_COMPARED, "base_only": [], "inserts": [],
                "counts": {"base_only": 0, "compared_only": len(b_lines or []),
                           "same": 0},
                "base_lines": 0, "compared_lines": len(b_lines or []),
                "ms": round((time.perf_counter() - started) * 1000, 1)}
    if b_lines is None:
        return {"available": True, "file": path, "base": base, "compared": compared,
                "status": ONLY_IN_BASE,
                "base_only": list(range(1, len(a_lines) + 1)), "inserts": [],
                "counts": {"base_only": len(a_lines), "compared_only": 0, "same": 0},
                "base_lines": len(a_lines), "compared_lines": 0,
                "ms": round((time.perf_counter() - started) * 1000, 1)}

    if source.hash_of(path, revision=base) == source.hash_of(path, revision=compared):
        # Answered from the hashes, without comparing a line. Stated as `same` rather than
        # as an empty diff for the same reason `changes.py` states `identical`: no marks
        # and no reason reads as a comparison that failed.
        return {"available": True, "file": path, "base": base, "compared": compared,
                "status": SAME, "base_only": [], "inserts": [],
                "counts": {"base_only": 0, "compared_only": 0, "same": len(a_lines)},
                "base_lines": len(a_lines), "compared_lines": len(b_lines),
                "ms": round((time.perf_counter() - started) * 1000, 1)}

    base_only: list[int] = []
    inserts: list[dict[str, Any]] = []
    same = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
            None, a_lines, b_lines, autojunk=False).get_opcodes():
        if tag == "equal":
            same += i2 - i1
            continue
        if tag in ("delete", "replace"):
            base_only.extend(range(i1 + 1, i2 + 1))       # one-based, like every line here
        if tag in ("insert", "replace"):
            inserts.append({
                # Which base line this run follows. `i1` is where the run belongs in the
                # base, so `0` is genuinely "before the first line" and not a sentinel.
                "after": i1,
                "first": j1 + 1,                          # its own number, over there
                "lines": b_lines[j1:j2],
            })
    return {
        "available": True, "file": path, "base": base, "compared": compared,
        "status": MODIFIED,
        "base_only": base_only,
        "inserts": inserts,
        "counts": {"base_only": len(base_only),
                   "compared_only": sum(len(i["lines"]) for i in inserts),
                   "same": same},
        "base_lines": len(a_lines), "compared_lines": len(b_lines),
        "ms": round((time.perf_counter() - started) * 1000, 1),
    }
