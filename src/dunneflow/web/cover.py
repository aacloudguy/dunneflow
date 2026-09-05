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
from .graph import pkg_params, root_package


def _root(store: Store) -> str:
    """The one leading segment every module shares, or `""` when they do not share one.

    What it is *for*: a field too narrow for a module path has to drop something, and the
    only defensible thing to drop first is the part that is the same on every row. All 566
    of Mensores' modules begin `mensores.`, so a head-and-leaf shortening spends nine
    characters saying nothing and then elides `disceptator` -- the package, the one segment
    that separates this module from the other 565 -- to afford them.

    **Not "a segment that names a package".** That test was tried and is wrong: `mensores`
    is itself a package in `COVER_PACKAGES`, because the modules sitting directly under it
    belong to one, so it matches at position 0 and nothing is ever stripped. It looked
    right, changed nothing, and reported no error -- found by reading 1,019 rows in the
    navigator that still said `mensores.….\\_advance_gate`.

    Empty rather than a guess when the program has more than one top-level name, and empty
    when the shared head is a module in its own right -- stripping `mensores` from the
    module `mensores` leaves nothing to show. A reader then sees whole module paths
    shortened by the ordinary rule, which is worse-looking and still true.
    """
    heads = [(r["head"], r["n"]) for r in store.query(queries.COVER_ROOT)]
    if len(heads) != 1:
        return ""
    head = str(heads[0][0] or "")
    return head if head else ""


def _lines(source: SourceStore | None, revision: str | None) -> int | None:
    """How many lines were read, from the sidecar that holds them.

    None when there is no sidecar -- `--no-source`, or a map handed over without it. The
    cover then says nothing about lines rather than guessing from file sizes, because a
    number a reader cannot check is worse than a number that is absent.
    """
    if source is None:
        return None
    # Which version's lines, named by the caller -- the version the cover is *of*, never
    # whichever snapshot happens to be newest. This was `WHERE p.revision = ''` -- the
    # legacy revision, from before a snapshot had a name -- so from the day revisions
    # landed the cover said "0 lines" about every program analysed since. Mensores is
    # 186,786. Nothing failed and nothing was empty: a zero on the first screen reads as a
    # program with no source, which is a claim, and a wrong one. Found by serving a copied
    # program directory and looking at the cover.
    #
    # `resolve_revision` is deliberately **not** used: it answers `''` for a sidecar that
    # holds nothing, which would put that same zero back. A sidecar with nothing in it and
    # a program with no lines are different claims, and only one of them is ever true here.
    if revision is None:
        revision = source.current_revision()
    if revision is None:
        return None
    row = source.conn.execute(
        "SELECT COALESCE(SUM(b.lines), 0) FROM paths p JOIN blobs b ON b.hash = p.hash "
        "WHERE p.revision = ?", (revision,)
    ).fetchone()
    return int(row[0]) if row else None


def build(store: Store, source: SourceStore | None, program: str, *,
          vocabulary: dict[str, int] | None = None,
          revision: str | None = None) -> dict[str, Any]:
    """Everything the first screen shows.

    `vocabulary` is the three lanes' *sizes* only -- how many conventions were measured,
    how many naming rules the documents state, how many words the program uses as names,
    how many of those anything defines. The lanes themselves are a quarter of a megabyte
    and are fetched when their pages are opened; these numbers ride with the cover because
    the navigator states a count beside every other row, and a blank beside "Glossary"
    reads as "nothing there" rather than as "not asked for yet". Those are opposite claims
    and must not look alike.

    **`stated` is a zero worth sending.** Most programs state no naming rule at all, and a
    navigator row reading 0 beside "Stated naming rules" is the honest answer -- it is the
    row being *absent* that would mislead, by reading as a lane nobody has measured yet.
    """
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
            # The routines this way in actually starts. `ways_in` has already computed
            # them -- an app object contributes every command hung off it -- and the
            # cover used to drop them on the floor, which left the navigator listing six
            # ways in that could not say *which* one had been clicked. A label is not an
            # identity: without these the four subject-setting routes had no subject.
            "nodes": list(w["roots"]),
        }
        for w in ways_in(store)
    ]

    boundaries = [
        {"kind": r["kind"], "n": r["n"], "common": r["common"] or "—"}
        for r in store.query(queries.COVER_BOUNDARIES)
    ]

    # The disks' own decomposition, asked for with the disks' own parameters. This used to
    # be a bare `store.query(COVER_PACKAGES)` over a query that took the second dotted
    # segment on its own -- a second definition of "package", which the navigator then
    # selected plates by. See the note above `COVER_PACKAGES`.
    pkg_p = pkg_params(root_package(store))
    packages = [{"id": r["pkg"], "n": r["n"]}
                for r in store.query(queries.COVER_PACKAGES, pkg_p)]
    tables = [{"name": r["name"], "n": r["n"]} for r in store.query(queries.COVER_TABLES)]

    rep = detect(store)
    ac = rep.counts()

    return {
        "program": program,
        # The program's own namespace, so a narrow field can drop it before it drops
        # anything that tells two modules apart. A fact about the program, measured once
        # here rather than inferred per list in the browser -- the same name must shorten
        # the same way wherever it appears (rule 24).
        "root": _root(store),
        "stats": {
            "files": counts["files"],
            "lines": _lines(source, revision),
            "routines": counts["routines"],
            "boundaries": counts["boundaries"],
            "structures": counts["structures"],
            "entrypoints": counts["entrypoints"],
            "analysed": store.get_meta("analysed_at"),
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
        # Absent, not zero, when the lanes have not been measured. Zero conventions is a
        # finding about a program; an absent count is a fact about this request.
        "vocabulary": dict(vocabulary) if vocabulary else {},
    }


def anomalies(store: Store) -> list[dict[str, Any]]:
    """The findings themselves, worst first.

    Every one carries its blind spot. `anomalies.py` exists under that single rule, and a
    finding that reached the screen without it would be a guess wearing a uniform -- the
    client has no way to invent one, so it must never be optional here.
    """
    return [
        {
            # What makes this finding *this* finding, so a triage decision can be filed
            # against it and a second version's findings paired with it. Sent as well as
            # the parts it is derived from, because the pairing is a claim and the parts
            # are how a reader sees why it was made (design rule 13).
            "ident": a.ident,
            "ident_parts": list(a.ident_parts),
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
