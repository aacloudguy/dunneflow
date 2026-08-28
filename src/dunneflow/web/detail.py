"""What the inspector shows about one selected thing.

**Flow-first, not signature-first.** The order is fixed and it is the argument the whole
tool makes: how a thing is reached, what it does next, what it touches, and why it is
there. A signature says what types cross the boundary of a function; it does not say what
moves through the program, so it is demoted into the params view rather than leading.

Nothing here interprets facts into a story -- it collects the rows the store already
holds and labels them. Two disciplines carry over from the renderers:

* **Provenance travels with every claim** (design rule 13). A boundary keeps the evidence
  that admitted it, a call keeps its confidence and the expression at the call site, and
  everything keeps its file and line. A reader who cannot get back to where a fact came
  from cannot check it, and an unheckable claim is an assertion wearing a uniform.

* **Nothing is silently dropped** (design rule 1, and rule 8). Lists are returned whole.
  Where the client will bound a list for space, it is the client's job to say what it
  left out -- this module never decides that on its behalf, because a shortfall invented
  down here is invisible from up there.
"""

from __future__ import annotations

from typing import Any

from ..sourcedb import SourceStore
from ..store import Store
from . import queries

# How many lines either side of a definition the source view offers by default. A
# definition plus its immediate surroundings is the unit a reader actually wants; the
# whole file is one click further and never the default, because a routine shown inside
# four hundred lines of neighbours is a routine you have to find twice.
SOURCE_MARGIN = 3


def _rows(store: Store, sql: str, args: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(r) for r in store.query(sql, args)]


def _one(store: Store, sql: str, args: dict[str, Any]) -> dict[str, Any] | None:
    rows = _rows(store, sql, args)
    return rows[0] if rows else None


# --------------------------------------------------------------------------- #
# Identity
#
# The graph mints one id space over five kinds of thing, so the first job is to
# read a kind back out of an id. Routines and structures carry opaque hashes and
# are told apart by looking; the other three are prefixed.
#
# The constant split is on the *last* dot deliberately: a module path holds dots
# and an identifier does not, so `const:mensores.agent.JTBD_OPENERS` is the module
# `mensores.agent` and the name `JTBD_OPENERS`, and no other split is right.
# --------------------------------------------------------------------------- #

def classify(node_id: str) -> tuple[str, dict[str, Any]]:
    """The kind of thing an id names, and the parameters that will find it."""
    if node_id.startswith("const:"):
        rest = node_id[len("const:"):]
        module, _, name = rest.rpartition(".")
        return "CONSTANT", {"module": module, "name": name}
    if node_id.startswith("bnd:"):
        # Split at most twice: a target may itself hold colons -- a URL, a host:port --
        # and eating them would look up an endpoint the program never touched.
        _, _, rest = node_id.partition(":")
        kind, _, target = rest.partition(":")
        return "BOUNDARY", {"kind": kind, "target": target}
    if node_id.startswith("art:"):
        return "ARTEFACT", {"name": node_id[len("art:"):]}
    return "OPAQUE", {"id": node_id}


# --------------------------------------------------------------------------- #
# Routines
# --------------------------------------------------------------------------- #

def _routine(store: Store, node_id: str) -> dict[str, Any] | None:
    ident = _one(store, queries.ROUTINE_DETAIL, {"id": node_id})
    if ident is None:
        return None
    args = {"id": node_id}
    return {
        "kind": "ROUTINE",
        "id": node_id,
        "label": ident["name"],
        "identity": ident,
        "params": _rows(store, queries.ROUTINE_PARAMS, args),
        "in": {
            "callers": _rows(store, queries.ROUTINE_CALLERS, args),
            "entrypoints": _rows(store, queries.ROUTINE_ENTRYPOINTS, args),
        },
        "out": {"calls": _rows(store, queries.ROUTINE_CALLEES, args)},
        "touches": {
            "boundaries": _rows(store, queries.ROUTINE_BOUNDARIES, args),
            "sql": _rows(store, queries.ROUTINE_SQL_OPS, args),
            "net": _rows(store, queries.ROUTINE_NET_CALLS, args),
            "artefacts": _rows(store, queries.ROUTINE_ARTEFACTS, args),
        },
        "governance": {
            "annotations": _rows(store, queries.ROUTINE_ANNOTATIONS, args),
            "comments": _rows(store, queries.ROUTINE_COMMENTS, args),
        },
        "where": {
            "file": ident["file"],
            "first": ident["line_start"],
            "last": ident["line_end"],
        },
    }


def _structure(store: Store, node_id: str) -> dict[str, Any] | None:
    ident = _one(store, queries.STRUCTURE_DETAIL, {"id": node_id})
    if ident is None:
        return None
    args = {"id": node_id}
    return {
        "kind": "STRUCTURE",
        "id": node_id,
        "label": ident["name"],
        "identity": ident,
        "fields": _rows(store, queries.STRUCTURE_FIELDS, args),
        "governance": {
            "annotations": _rows(store, queries.STRUCTURE_ANNOTATIONS, args),
            "comments": [],
        },
        "where": {"file": ident["file"], "first": ident["line"], "last": ident["line"]},
    }


def _constant(store: Store, params: dict[str, Any]) -> dict[str, Any] | None:
    ident = _one(store, queries.CONSTANT_DETAIL, params)
    if ident is None:
        return None
    return {
        "kind": "CONSTANT",
        "id": f"const:{params['module']}.{params['name']}",
        "label": ident["name"],
        "identity": ident,
        # A constant's comment is its WHY and there is nowhere else to look for it:
        # 1,030 of Mensores' 2,618 carry one, and that is the whole reason rule 19
        # was worth the work.
        "governance": {
            "annotations": [],
            "comments": ([{"line": ident["line"], "text": ident["comment"],
                           "leading": 1}] if ident["comment"] else []),
        },
        "where": {"file": ident["file"], "first": ident["line"], "last": ident["line"]},
    }


def _boundary(store: Store, node_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """An external endpoint. The question here is who reaches it, not what it is.

    Always answers, even with no touchers: a boundary node exists because the graph
    built one, and an empty list is a fact about the program rather than a miss.
    """
    touchers = _rows(store, queries.BOUNDARY_TOUCHERS, params)
    return {
        "kind": "BOUNDARY",
        "id": node_id,
        "label": params["target"] or f"({params['kind']}, unnamed)",
        # Design rule 8: an external is badged as outside our control. Nothing here has
        # been analysed, so nothing here may claim to have been.
        "identity": {"bkind": params["kind"], "target": params["target"],
                     "source_status": "OPAQUE"},
        "in": {"callers": touchers, "entrypoints": []},
        "where": None,
    }


def _artefact(store: Store, node_id: str, params: dict[str, Any]) -> dict[str, Any]:
    mentions = _rows(store, queries.ARTEFACT_NAMERS, params)
    return {
        "kind": "ARTEFACT",
        "id": node_id,
        "label": params["name"],
        "identity": {"name": params["name"], "source_status": "OPAQUE",
                     "mentions": len(mentions)},
        "in": {"callers": mentions, "entrypoints": []},
        "where": None,
    }


# --------------------------------------------------------------------------- #
# Source
# --------------------------------------------------------------------------- #

def attach_source(detail: dict[str, Any], source: SourceStore | None) -> None:
    """Add the lines a node was read from, or say plainly why they are not here.

    Three different absences, and they are not the same thing to a reader:

    * no sidecar at all -- the map was analysed with `--no-source`, or handed over
      without its `source.db`;
    * a sidecar that does not hold this path -- the file was unreadable when the map
      was built, and `analyze` said so at the time;
    * a node with no file at all -- an external. Nothing was ever read, by definition.

    Design rule 13 asks that provenance *opens*. Where it cannot, it has to say which of
    these it is, because "no source shown" read as "no source exists" is exactly the
    silent wrong answer this project keeps paying for.
    """
    where = detail.get("where")
    if not where or not where.get("file"):
        detail["source"] = {"available": False,
                            "reason": "this is outside the program — nothing was read"}
        return
    if source is None:
        detail["source"] = {
            "available": False,
            "reason": "no source sidecar beside this map — re-run `dunneflow analyze` "
                      "without `--no-source`, or ask for `source.db`",
            "file": where["file"],
        }
        return
    first = max(1, int(where["first"] or 1) - SOURCE_MARGIN)
    last = int(where["last"] or where["first"] or 1) + SOURCE_MARGIN
    lines = source.lines(where["file"], first, last)
    if not lines:
        detail["source"] = {
            "available": False,
            "reason": "the sidecar does not hold this file — it was unreadable when the "
                      "map was built",
            "file": where["file"],
        }
        return
    detail["source"] = {
        "available": True,
        "file": where["file"],
        "first": lines[0][0],
        "last": lines[-1][0],
        "focus": [where["first"], where["last"]],
        "lines": [{"n": n, "text": t} for n, t in lines],
    }


# --------------------------------------------------------------------------- #
# The one way in
# --------------------------------------------------------------------------- #

def describe(store: Store, node_id: str,
             source: SourceStore | None = None) -> dict[str, Any]:
    """Everything the inspector shows about one node.

    An id that finds nothing returns `found: False` rather than an empty shape that
    looks like a thing with no callers. The two are indistinguishable on screen
    otherwise, and one of them means the map is wrong.
    """
    kind, params = classify(node_id)

    detail: dict[str, Any] | None
    if kind == "CONSTANT":
        detail = _constant(store, params)
    elif kind == "BOUNDARY":
        detail = _boundary(store, node_id, params)
    elif kind == "ARTEFACT":
        detail = _artefact(store, node_id, params)
    else:
        # An opaque id is a routine or a structure. Routines first: there are seven
        # times as many of them, and the two id spaces do not overlap.
        detail = _routine(store, node_id) or _structure(store, node_id)

    if detail is None:
        return {"found": False, "id": node_id,
                "reason": "no such node in this map"}

    detail["found"] = True
    attach_source(detail, source)
    return detail
