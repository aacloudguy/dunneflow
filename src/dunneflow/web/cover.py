"""The cover: the first screen, and the one that decides how the tool gets used.

Observed rather than assumed. The reader opens the map, reads the cover, works out how
the thing hangs together, and only then starts exploring -- and when they do, the graph
is one instrument among several rather than the destination. Some readers will never open
it at all, and the tool has to be worth having for them too.

So this answers four questions in the order they are actually asked: what am I looking
at, where do I start, what does it touch, and what looks wrong. Each is a real
measurement over the store; none is a summary the tool made up.

Built once when the server starts, beside the graph payload, because nothing here changes
while the map is open -- and a cover that recomputed 175 reachability queries on every
navigation would make the first screen the slowest one.
"""

from __future__ import annotations

from typing import Any

from ..anomalies import BROKEN, INFO, SUSPECT, detect
from ..resolve.flows import ways_in
from ..sourcedb import SourceStore
from ..store import Store
from . import queries


def _lines(source: SourceStore | None) -> int | None:
    """How many lines were read, from the sidecar that holds them.

    None when there is no sidecar -- `--no-source`, or a map handed over without it. The
    cover then says nothing about lines rather than guessing from file sizes, because a
    number a reader cannot check is worse than a number that is absent.
    """
    if source is None:
        return None
    row = source.conn.execute(
        "SELECT COALESCE(SUM(b.lines), 0) FROM paths p JOIN blobs b ON b.hash = p.hash "
        "WHERE p.revision = ''"
    ).fetchone()
    return int(row[0]) if row else None


def build(store: Store, source: SourceStore | None, program: str) -> dict[str, Any]:
    """Everything the first screen shows."""
    counts = store.counts()

    # Ways in, already deduplicated and ranked by reach. One entry is commonly detected
    # three ways at once, and listing it three times buries the others.
    entrypoints = [
        {
            "name": w["name"],
            "kind": w["kind"],
            "reach": w["reach"],
            # The boundary kinds this way in ends up touching, as plain words. An em dash
            # rather than an empty string when it touches nothing: a way in that reaches
            # the world nowhere is a fact worth seeing, not a blank.
            "touches": " ".join(k.value for k in w["kinds"]) or "—",
            "aliases": w.get("aliases", []),
        }
        for w in ways_in(store)
    ]

    boundaries = [
        {"kind": r["kind"], "n": r["n"], "common": r["common"] or "—"}
        for r in store.query(queries.COVER_BOUNDARIES)
    ]

    packages = [{"id": r["pkg"], "n": r["n"]} for r in store.query(queries.COVER_PACKAGES)]
    tables = [{"name": r["name"], "n": r["n"]} for r in store.query(queries.COVER_TABLES)]

    rep = detect(store)
    ac = rep.counts()

    return {
        "program": program,
        "stats": {
            "files": counts["files"],
            "lines": _lines(source),
            "routines": counts["routines"],
            "boundaries": counts["boundaries"],
            "structures": counts["structures"],
            "entrypoints": counts["entrypoints"],
            "analysed": store.get_meta("analysed_at"),
            "source_root": store.get_meta("source_root"),
        },
        "entrypoints": entrypoints,
        "boundaries": boundaries,
        "packages": packages,
        "tables": tables,
        # Severity and confidence are different questions and the cover keeps them apart:
        # this is severity only, and the worklist is where confidence appears.
        "anomalies": {
            "broken": ac.get(BROKEN, 0),
            "suspect": ac.get(SUSPECT, 0),
            "info": ac.get(INFO, 0),
        },
    }


def anomalies(store: Store) -> list[dict[str, Any]]:
    """The findings themselves, worst first.

    Every one carries its blind spot. `anomalies.py` exists under that single rule, and a
    finding that reached the screen without it would be a guess wearing a uniform -- the
    client has no way to invent one, so it must never be optional here.
    """
    return [
        {
            "kind": a.kind,
            "severity": a.severity,
            "confidence": a.confidence,
            "title": a.title,
            "detail": a.detail,
            "blind_spot": a.blind_spot,
            "subject": a.subject,
            "file": a.file,
            "line": a.line,
            "count": a.count,
        }
        for a in detect(store).sorted()
    ]
