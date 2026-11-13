"""One act, one row: a chain spelt through a call is the call, not a second touch.

**The dotted contract folds a call in the middle of a chain into its callee** (clause 2 of
`ingest/dotted.py`), so `conn.execute(q).fetchone()` is spelt `conn.execute.fetchone` and
`http.Get(u).Body.Close()` is `http.Get.Body.Close`. The fold is deliberate -- it is how
`Path(p).read_text()` is seen at all -- but it also means the outer name *extends* the
inner one, and a rule that matched the inner call matches the outer one again. Comitia had
259 DATABASE boundaries that were a `fetchone` or a `fetchall` on the `execute` written on
the same line; rain's Go had `http.Get(...)` recorded as two network calls.

That is rule 40 at the write: *a boundary already named by a more specific record on the
same line is not counted again*. Here the record that names it is the inner call, and
what is dropped is the row whose evidence is that call's spelling and more. **Per
routine, per line and per kind**, so a `read_text` and a `write_text` chained on one line
stay two -- they are two kinds -- and a chain written over two lines stays two rows, which
is what a reader of the source would count.

Decided here, once, for every reader, because this is the one place both kinds of reader
pass through (rule 51); a reader that already avoids the fold (Rust's, since 4a: a method
on a value is matched by `method:` alone) loses nothing to it.
"""

from __future__ import annotations

from collections import defaultdict

from ..detectors import EVIDENCE_NOTE
from ..schema import BoundaryHit, FileFacts, NetworkCall


def _extends(longer: str, shorter: str) -> bool:
    return bool(shorter) and longer.startswith(shorter + ".")


def _spelling(evidence: str) -> str:
    """The call's dotted spelling, without a rule's note or blind spot after it."""
    return evidence.split(EVIDENCE_NOTE, 1)[0]


def one_act(ff: FileFacts) -> None:
    """Drop each boundary and remote call that is a chain on another one's call."""
    by_line: dict[tuple[str, str, int], list[BoundaryHit]] = defaultdict(list)
    for b in ff.boundaries:
        by_line[(b.routine_id, str(b.kind), b.line)].append(b)
    kept_b = [
        b for b in ff.boundaries
        if not any(_extends(_spelling(b.evidence), _spelling(o.evidence))
                   for o in by_line[(b.routine_id, str(b.kind), b.line)] if o is not b)
    ]
    if len(kept_b) != len(ff.boundaries):
        ff.boundaries = kept_b

    calls: dict[tuple[str, int], list[NetworkCall]] = defaultdict(list)
    for n in ff.network:
        calls[(n.routine_id, n.line)].append(n)
    kept_n = [
        n for n in ff.network
        if not any(_extends(n.expr, o.expr)
                   for o in calls[(n.routine_id, n.line)] if o is not n)
    ]
    if len(kept_n) != len(ff.network):
        ff.network = kept_n
