"""Which of the program's own documents have anything to do with the thing on screen.

Document mode was a **place**, not a view of the selection: `state.docPath` held whatever
document had last been opened and nothing ever connected it to what the reader had picked.
Tom selected `signator.__main__`, pressed Document, and got a document about PAUL style
rules -- opened twenty minutes earlier from a naming citation and never put away. The mode
toggle's own sentence is *"five ways of reading one selection"*, and one of them was not.

**The obvious relation does not exist, and that is worth writing down so nobody mines it
again.** `doc_refs` holds 37,150 PATH and 114,067 CODE references, which sound exactly like
the answer. They are not: the PATHs are *document* paths -- `INTENT.md`, `GLOSSARY.md` --
and `mensores/signator/__main__.py` matches **zero** of them; the CODE refs are CLI flags and
template placeholders (`--codebase`, `{{ crash_payload }}`), so `WitnessHandler` matches zero
and `main` matches 38, which is rule 5 waiting to happen.

**What does exist is the governance join**, and both halves were already ingested:
`graph.db.annotations` against `docs.db.doc_annotations`, the pair `resolve/traceability.py`
was built on. 6,976 of Mensores' 6,993 code annotations carry an id some document also names.

**But naming an id is not being related, and the numbers say so.** A routine carries a median
of *two* ids, and those two reach a median of **281 documents** -- 14% of the corpus, p90
1,077, max 1,679 of 2,064. A filter that returns a seventh of everything has not filtered.
What is selective is the **intersection**: documents naming *every* id the routine carries
come to a median of **4**, and 617 of the 1,021 routines with two or more ids land between 1
and 10.

So this ranks rather than filters, and the page states both numbers. The band that names all
of them is the answer; the rest is offered and counted, never hidden and never presented as
though it were the answer (design rule 1, and rule 32 -- a count says what it counts).

**Answered per selection, not built at boot.** `traceability.measure()` does the whole join
in 4.7 s, which is right for a report and wrong for a click; the targeted pair of queries here
is **4.9 ms**, measured over 200 routines. What it does borrow is `normalise()` -- `ADR-0001`,
`ADR 1` and `adr_1` are one id and `Plan 01-04` is not `PLAN-01` -- because a second reading
of that rule is a second answer to which ids match (rule 51).
"""

from __future__ import annotations

import json
from typing import Any

from ..docstore import DocStore
from ..resolve.traceability import normalise
from ..store import Store


def _ids_of(store: Store, node_id: str) -> list[str]:
    """The governance ids this node carries, normalised and deduplicated.

    Both `routine` and `structure` owners, because a reader selects either and neither is
    more entitled to an answer. Empty is the ordinary case -- 59% of Mensores' routines carry
    no id at all -- and it is a fact about the code rather than a failure to look.
    """
    rows = store.query(
        "SELECT value FROM annotations WHERE owner_id = :id AND value <> ''", {"id": node_id})
    return sorted({normalise(str(r["value"])) for r in rows} - {""})


def documents_for(store: Store, docs: DocStore | None, node_id: str) -> dict[str, Any]:
    """The documents that name what this node carries, ranked by how much they share.

    `matched` is how many of the node's ids a document names, and the list is ordered by it.
    A document naming every one of them is in the `full` band; the rest are `partial`. Both
    are sent complete -- this is a list and not a diagram, so rule 8's bound does not apply,
    and the largest answer measured is 1,030 rows of four short fields.
    """
    if docs is None:
        return {"found": True, "ids": [], "full": [], "partial": [], "total": 0,
                "reason": "This map was made without reading documentation"}
    ids = _ids_of(store, node_id)
    if not ids:
        return {"found": True, "ids": [], "full": [], "partial": [], "total": 0,
                "reason": "It carries no plan, ticket or decision id, so there is "
                          "nothing for a document to have in common with it"}

    # **Both sides are normalised, and the doc side is cheap enough to do properly.**
    # Matching raw value against raw value would miss the 14 ids whose spelling differs
    # between the two stores; scanning all 88,398 `doc_annotations` and normalising each
    # would be right and slow. There are only **1,470 distinct values**, normalising to
    # 1,456 ids in 2 ms, so the map is built and the raw forms of the wanted ids are what
    # the query asks for.
    forms: dict[str, list[str]] = {}
    for r in docs.query("SELECT DISTINCT value FROM doc_annotations WHERE value <> ''", ()):
        raw = str(r["value"])
        forms.setdefault(normalise(raw), []).append(raw)
    wanted_raw = [raw for i in ids for raw in forms.get(i, [])]
    if not wanted_raw:
        return {"found": True, "ids": ids, "full": [], "partial": [], "total": 0,
                "reason": "No document in this corpus names any of the ids it carries"}

    # Duplicates are excluded, and design rule 1 says the filter is never silent -- the count
    # the page prints is of canonical documents, and `documents.duplicate_of` is what folds
    # a worktree copy of the project's own research into the original.
    rows = docs.query(
        "SELECT a.value AS value, a.doc AS doc, d.title AS title, d.doc_class AS doc_class"
        "  FROM doc_annotations a JOIN documents d ON d.path = a.doc"
        " WHERE d.duplicate_of = '' AND a.value IN (SELECT value FROM json_each(?))",
        (json.dumps(wanted_raw),),
    )
    per: dict[str, dict[str, Any]] = {}
    for r in rows:
        norm = normalise(str(r["value"]))
        seen = per.setdefault(str(r["doc"]), {
            "path": str(r["doc"]), "title": str(r["title"] or ""),
            "class": str(r["doc_class"] or ""), "ids": set(),
        })
        seen["ids"].add(norm)

    ranked = sorted(
        ({**v, "ids": sorted(v["ids"]), "matched": len(v["ids"])} for v in per.values()),
        key=lambda d: (-d["matched"], d["path"]),
    )
    full = [d for d in ranked if d["matched"] == len(ids)]
    partial = [d for d in ranked if d["matched"] < len(ids)]
    return {
        "found": True, "ids": ids, "full": full, "partial": partial,
        "total": len(ranked), "reason": "",
    }
