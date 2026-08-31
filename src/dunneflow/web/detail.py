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

import json
from typing import Any

from ..schema import signature_parts
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
    if node_id.startswith("mod:"):
        # The stack's other altitude. A dotted module name holds no colon, so this needs
        # none of `bnd:`'s care about splitting.
        return "MODULE", {"module": node_id[len("mod:"):]}
    if node_id.startswith("outside:"):
        return "OUTSIDE", {"kind": node_id[len("outside:"):]}
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
        # The same pieces `/api/hover` sends, from the same renderer, so the inspector's
        # signature and the card's invocation line cannot disagree about one routine.
        #
        # This was raw `params` rows, and the pane read `p.annotation` and `p.default`
        # against a query that sends `type` and `dflt` -- so **every parameter in the
        # inspector rendered as a bare name**, with no type and no default, from the day it
        # was written. Rule 44 in the pane the whole design points at: `NaN` renders as
        # nothing, and a missing type looks exactly like a routine that has none.
        "params": signature_parts([
            (r["name"], r["type"], r["dflt"], r["kind"])
            for r in _rows(store, queries.ROUTINE_PARAMS, args)
        ]),
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


def _module(store: Store, node_id: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """One file, as the module level draws it: what it declares and who it talks to.

    Neighbours are **modules, not routines**, and that is the altitude rather than a
    summary: at this height "who calls this" is answered by 85 names a reader can act on,
    where the 1,400 calls under them are the haystack (rule 45). The routines are listed
    in full beneath -- rule 8, a reference list is never bounded -- and each one is an
    ordinary node id, so opening it is the same selection every other row makes.

    A module the fold invented but the store has never heard of returns `None`, the same
    as any other id that finds nothing: `found: false` and an empty shape are different
    claims and only one of them means the map is wrong.
    """
    args = {"module": params["module"]}
    routines = _rows(store, queries.MODULE_ROUTINES, args)
    structures = _rows(store, queries.MODULE_STRUCTURES, args)
    constants = _rows(store, queries.MODULE_CONSTANTS, args)
    if not (routines or structures or constants):
        return None

    ident = _one(store, queries.MODULE_DETAIL, args) or {}
    inner = _one(store, queries.MODULE_INNER_CALLS, args) or {}
    return {
        "kind": "MODULE",
        "id": node_id,
        "label": params["module"].rpartition(".")[2] or params["module"],
        "identity": {
            "module": params["module"],
            "file": ident.get("file") or "",
            "doc": ident.get("doc") or "",
            # What the node on the plate stands for. Stated rather than left to be counted
            # off the lists below, because the lists are what the reader scrolls and the
            # number is what the picture drew (design rule 1).
            #
            # **A kind it holds none of is absent, never zero**, and the two are one shape
            # because `graph.py` builds the same map by counting what is there. Written
            # with three fixed keys it disagreed with the picture on the first module that
            # declares only routines -- which is rule 13 between a card and a node, and the
            # guard caught it.
            "holds": {k: v for k, v in (("ROUTINE", len(routines)),
                                        ("STRUCTURE", len(structures)),
                                        ("CONSTANT", len(constants))) if v},
            "folded": len(routines) + len(structures) + len(constants),
            # The calls that never leave: counted here and drawn nowhere, which is the
            # same decision `_add_edges` makes and the same number.
            "inner_calls": int(inner.get("calls") or 0),
        },
        "holds": {"routines": routines, "structures": structures,
                  "constants": constants},
        "in": {"callers": _rows(store, queries.MODULE_CALLERS, args), "entrypoints": []},
        "out": {"calls": _rows(store, queries.MODULE_CALLEES, args)},
        "touches": {
            "boundaries": _rows(store, queries.MODULE_BOUNDARIES, args),
            "sql": [], "net": [],
            "artefacts": _rows(store, queries.MODULE_ARTEFACTS, args),
        },
        # The whole file, so the code browser opens it rather than a span inside it.
        "where": {"file": ident.get("file") or "", "first": 0, "last": 0},
    }


def _outside(store: Store, node_id: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """One boundary kind, as the module level draws it: everything the program touches
    through this door.

    A different question from `bnd:`, which answers for **one endpoint**. This node stands
    for 991 of them, so it counts them and lists them in full rather than borrowing the
    endpoint card with a wildcard -- a card saying "3 callers" where the truth is 214 is
    worse than one saying nothing (rule 32).
    """
    kind = params["kind"]
    artefacts = kind == "ARTEFACT"
    row = _one(store, queries.OUTSIDE_ARTEFACT_DETAIL if artefacts
               else queries.OUTSIDE_DETAIL, params) or {}
    if not int(row.get("hits") or 0):
        return None
    targets = _rows(store, queries.OUTSIDE_ARTEFACT_TOP if artefacts
                    else queries.OUTSIDE_TOP_TARGETS, params)
    modules = _rows(store, queries.OUTSIDE_ARTEFACT_MODULES if artefacts
                    else queries.OUTSIDE_MODULES, params)
    return {
        # ARTEFACT keeps its own kind here as it does on the plate: naming a file is a
        # choice the authors made and touching one is something the code does, and rule 17
        # is why the difference is worth a separate node.
        "kind": "ARTEFACT" if artefacts else "BOUNDARY",
        "id": node_id,
        "label": kind,
        "identity": {
            "bkind": kind,
            # Design rule 8: nothing out here was analysed, so nothing out here may claim
            # to have been.
            "source_status": "OPAQUE",
            "folded": int(row.get("targets") or 0),
            "hits": int(row.get("hits") or 0),
            "callers": int(row.get("callers") or 0),
            "direction": row.get("direction") or "",
        },
        "holds": {"targets": targets},
        "in": {"callers": modules, "entrypoints": []},
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

def attach_source(detail: dict[str, Any], source: SourceStore | None,
                  *, revision: str | None = None) -> None:
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
    lines = source.lines(where["file"], first, last, revision=revision)
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
# The hover card
#
# What the pop-up says about a node the cursor is passing over. It is a different
# question from the inspector's, not a smaller version of it: the inspector answers
# "what is this thing", at length, for something deliberately chosen; the card
# answers "is this worth stopping for" in the second before the cursor moves on.
#
# Three disciplines, and each of them is a rule this project has already paid for.
#
# * **It does not count callers or callees.** The picture holds those numbers, in the
#   very maps the selection is drawn from, and the navigator already shows them as
#   `3<- 5->`. A second count taken from `calls` here would be over a different
#   population -- externals resolve to no node and are not drawn -- so the two would
#   differ, both correct, about things neither of them named. That is rule 32
#   exactly, and the fix is not to take the count twice.
#
# * **Every number says what it counted.** "3 boundaries" is not something a reader
#   can act on; "2 ENV, 1 FILE" is the shape of what this routine reaches. So the
#   touches come back grouped and named, each with one example, and the card renders
#   a list rather than a total.
#
# * **The WHY says where it came from.** A docstring is the routine explaining
#   itself; a leading comment is the author explaining it from outside; a comment
#   forty lines in is about a statement and is being *quoted*, not summarised. The
#   card must be able to say which, so `why.source` travels with the text -- design
#   rule 13 in the smallest space this product has.
# --------------------------------------------------------------------------- #


def _hover_touches(store: Store, node_id: str) -> list[dict[str, Any]]:
    """What a routine reaches outside itself, grouped by what kind of thing it is.

    Order is fixed rather than by count: tables, then boundaries, then remotes, then
    the files it names. A card whose rows reshuffle between two similar routines is a
    card the reader has to read rather than recognise.
    """
    args = {"id": node_id}
    out: list[dict[str, Any]] = []

    for r in _rows(store, queries.HOVER_TABLES, args):
        # Direction is the point of a table row. A table this writes and a table this
        # reads are different neighbours, and it is the distinction the database
        # report and the boundary threads are both built on.
        out.append({"what": "table", "kind": "", "n": 1, "first": r["name"],
                    "writes": int(r["writes"] or 0), "reads": int(r["reads"] or 0)})

    for r in _rows(store, queries.HOVER_SQL_UNTABLED, args):
        # Statements with no table of their own. They are still database work and the
        # card would otherwise state three tables and drop ten of seventeen operations
        # -- the silent omission design rule 1 exists to prevent.
        out.append({"what": "sql", "kind": r["kind"], "n": int(r["n"]),
                    "first": r["first"] or ""})

    for r in _rows(store, queries.HOVER_BOUNDARY_KINDS, args):
        out.append({"what": "boundary", "kind": r["kind"], "n": int(r["n"]),
                    "first": r["first"] or ""})

    for r in _rows(store, queries.HOVER_NET, args):
        out.append({"what": "net", "kind": r["kind"], "n": int(r["n"]),
                    "first": r["first"] or ""})

    art = _one(store, queries.HOVER_ARTEFACTS, args)
    # A COUNT with no GROUP BY always returns a row, so zero has to be filtered here
    # or every routine in the program claims to name a file.
    if art and int(art["n"] or 0):
        out.append({"what": "artefact", "kind": "", "n": int(art["n"]),
                    "first": art["first"] or ""})

    return out


def _hover_why(ident: dict[str, Any], comment: dict[str, Any] | None) -> dict[str, Any] | None:
    """One line saying why this exists, and which kind of evidence it is.

    A docstring wins because it is the thing that was written to answer this question.
    Below it, a leading comment. Below that, the first comment inside the body -- which
    is a quotation about a statement and is labelled as one, because presenting it as a
    summary of the routine would be this tool writing prose and attributing it to the
    author.
    """
    doc = str(ident.get("docstring") or "").strip()
    if doc:
        first = doc.split("\n", 1)[0].strip()
        if first:
            return {"text": first, "source": "docstring", "line": ident.get("line_start")}
    if comment and str(comment.get("text") or "").strip():
        leading = bool(comment.get("leading"))
        return {"text": str(comment["text"]).strip(),
                "source": "leading comment" if leading else "comment",
                "line": comment.get("line")}
    return None


def hover_card(store: Store, node_id: str) -> dict[str, Any]:
    """The compact answer behind the pop-up.

    Answers for every node kind with whatever that kind actually has, rather than
    returning a routine-shaped object with fields missing -- the same discipline
    `describe()` states, and for the same reason: a blank field and an absent one are
    different claims.
    """
    kind, params = classify(node_id)

    if kind == "MODULE":
        detail = _module(store, node_id, params)
        if detail is None:
            return {"found": False, "id": node_id, "reason": "no such node in this map"}
        ident = detail["identity"]
        return {"found": True, "id": node_id, "kind": "MODULE",
                "name": detail["label"], "module": ident["module"],
                "file": ident["file"],
                "holds": ident["holds"], "folded": ident["folded"],
                "inner_calls": ident["inner_calls"],
                "callers": len(detail["in"]["callers"]),
                "callees": len(detail["out"]["calls"]),
                # Grouped by kind with the targets counted, which is the same shape
                # `_hover_touches` sends for a routine so the card renders one way.
                "touches": [{"kind": str(b["kind"]), "n": int(b["targets"] or 0)}
                            for b in detail["touches"]["boundaries"]],
                "gov": [],
                # A module's docstring is the one thing here that says *why the file
                # exists*, and it is the only WHY at this altitude -- a module has no
                # leading comment of its own.
                "why": ({"text": str(ident["doc"]).strip().split("\n")[0],
                         "source": "module docstring", "line": 1}
                        if str(ident.get("doc") or "").strip() else None)}

    if kind == "OUTSIDE":
        detail = _outside(store, node_id, params)
        if detail is None:
            return {"found": False, "id": node_id, "reason": "no such node in this map"}
        ident = detail["identity"]
        return {"found": True, "id": node_id, "kind": detail["kind"],
                "source_status": "OPAQUE",
                "bkind": ident["bkind"], "target": "",
                "folded": ident["folded"],
                "hits": ident["hits"], "callers": ident["callers"],
                "direction": ident["direction"],
                "touches": [], "gov": [], "why": None}

    if kind == "BOUNDARY":
        row = _one(store, queries.HOVER_BOUNDARY_NODE, params) or {}
        return {"found": True, "id": node_id, "kind": "BOUNDARY",
                # Design rule 8: nothing here was analysed, so nothing here may claim
                # to have been.
                "source_status": "OPAQUE",
                "bkind": params["kind"], "target": params["target"],
                "hits": int(row.get("hits") or 0),
                "callers": int(row.get("callers") or 0),
                "direction": row.get("direction") or "",
                "touches": [], "gov": [], "why": None}

    if kind == "ARTEFACT":
        row = _one(store, queries.HOVER_ARTEFACT_NODE, params) or {}
        return {"found": True, "id": node_id, "kind": "ARTEFACT",
                "source_status": "OPAQUE",
                "name": params["name"], "ext": row.get("ext") or "",
                "akind": row.get("akind") or "",
                "mentions": int(row.get("mentions") or 0),
                "namers": int(row.get("namers") or 0),
                "touches": [], "gov": [], "why": None}

    if kind == "CONSTANT":
        const = _one(store, queries.HOVER_CONSTANT, params)
        if const is None:
            return {"found": False, "id": node_id, "reason": "no such node in this map"}
        # A constant's comment is its WHY and there is nowhere else to look: 1,030 of
        # Mensores' 2,618 carry one, which is the whole reason rule 19 was worth the work.
        note = str(const["comment"] or "").strip()
        return {"found": True, "id": node_id, "kind": "CONSTANT",
                "name": const["name"], "module": const["module"],
                "file": const["file"], "line": const["line"],
                "value": const["value"], "type": const["type"] or "",
                "is_final": bool(const["is_final"]), "private": bool(const["private"]),
                "touches": [], "gov": [],
                "why": ({"text": note, "source": "comment", "line": const["line"]}
                        if note else None)}

    routine = _one(store, queries.HOVER_ROUTINE, {"id": node_id})
    if routine is not None:
        anns = _rows(store, queries.HOVER_ANNOTATIONS, {"id": node_id})
        comment = _one(store, queries.HOVER_WHY_COMMENT, {"id": node_id})
        start, end = routine["line_start"], routine["line_end"]
        return {
            "found": True, "id": node_id, "kind": "ROUTINE",
            # What moves in, and what comes back out. This is the subject of the whole
            # tool, and until now the one thing about a routine the card never said.
            #
            # Sent as **pieces**, not as a rendered line, so the card can colour the name
            # apart from the types -- and rendered by `schema.signature_parts`, which is the
            # same function the Markdown documents go through, so the two cannot disagree
            # about where a `*` belongs. The alternative was splitting a finished string
            # back into its parts in JavaScript, which is a second parser of something the
            # first one had already taken apart.
            "params": signature_parts([
                (r["name"], r["type"], r["dflt"], r["kind"])
                for r in _rows(store, queries.ROUTINE_PARAMS, {"id": node_id})
            ]),
            "returns": routine["returns"] or "",
            "name": routine["name"], "qualname": routine["qualname"],
            "module": routine["module"], "file": routine["file"],
            "line_start": start, "line_end": end,
            "lines": (int(end) - int(start) + 1) if (start and end) else None,
            "is_async": bool(routine["is_async"]), "is_method": bool(routine["is_method"]),
            "class_name": routine["class_name"] or "", "visibility": routine["visibility"],
            "comments": int(routine["n_comments"] or 0),
            # Not a second count of the callees -- these are the calls the graph *cannot*
            # draw, because they leave the program and resolve to no node. Stating them is
            # what makes the card's `5->` and the inspector's `Out 8` add up rather than
            # disagree (rule 32), and design rule 8 says an external is first-class.
            "externals": int(routine["n_external"] or 0),
            "touches": _hover_touches(store, node_id),
            "gov": [{"value": a["value"], "kind": a["kind"]} for a in anns],
            "why": _hover_why(dict(routine), comment),
        }

    struct = _one(store, queries.HOVER_STRUCTURE, {"id": node_id})
    if struct is not None:
        return {"found": True, "id": node_id, "kind": "STRUCTURE",
                "name": struct["name"], "struct_kind": struct["kind"],
                "module": struct["module"], "file": struct["file"], "line": struct["line"],
                "fields": int(struct["n_fields"] or 0), "bases": struct["bases"] or "",
                "touches": [], "gov": [],
                "why": _hover_why({"docstring": struct["docstring"], "line_start": struct["line"]},
                                  None)}

    # An id that finds nothing is a fact about the map. Saying "found: False" rather
    # than returning an empty card keeps it distinguishable from a node that genuinely
    # has nothing to say, which is the distinction every empty answer here turns on.
    return {"found": False, "id": node_id, "reason": "no such node in this map"}


# --------------------------------------------------------------------------- #
# The one way in
# --------------------------------------------------------------------------- #

def describe(store: Store, node_id: str,
             source: SourceStore | None = None, *,
             revision: str | None = None) -> dict[str, Any]:
    """Everything the inspector shows about one node.

    An id that finds nothing returns `found: False` rather than an empty shape that
    looks like a thing with no callers. The two are indistinguishable on screen
    otherwise, and one of them means the map is wrong.
    """
    kind, params = classify(node_id)

    detail: dict[str, Any] | None
    if kind == "MODULE":
        detail = _module(store, node_id, params)
    elif kind == "OUTSIDE":
        detail = _outside(store, node_id, params)
    elif kind == "CONSTANT":
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
    attach_source(detail, source, revision=revision)
    return detail


# --------------------------------------------------------------------------- #
# Folds -- a set of routines asked about as one thing
#
# A diagram box is a class and its methods, or a file and its loose functions. It
# has no id in the store, so `describe()` cannot answer about one: `classify()`
# reads a kind out of an id, and a fold's id is a *drawing's* id.
#
# It answers in the **same shape** every other specimen uses, and that is the whole
# point rather than a convenience. `viewInspector` has one rendering path with a
# default for every key (rule 51 -- one truth about what the inspector shows), so a
# fold that fills `in`, `out`, `touches`, `governance` and `holds` renders through
# the code that already exists. A second shape would be a second answer to "what is
# selected", and the diagram is where that mistake was made once already: it set
# `state.selected` to one arbitrary member and the inspector answered, truthfully,
# about something nobody clicked.
#
# `holds` is the `_module` builder's own key, not a new one. The module altitude has
# been sending it since the day it was built and nothing has ever rendered it, so
# the section this adds gives both a fold and a module node the same answer.
# --------------------------------------------------------------------------- #

def _by_owner(rows: list[dict[str, Any]], key: str = "routine_id"
              ) -> dict[str, list[dict[str, Any]]]:
    """Group set-scoped rows back to the member each came from."""
    out: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(str(r.get(key) or ""), []).append(r)
    return out


def fold(store: Store, box: dict[str, Any], flow: dict[str, Any],
         source: SourceStore | None = None, *,
         revision: str | None = None) -> dict[str, Any]:
    """A diagram box, described as the thing it stands for.

    `box` is the drawing's own record -- its id, label, kind and the member ids it
    folds -- and `flow` is what the compartment already knows about what reaches it
    and what it reaches. Neither is recomputed here: the diagram is built from the
    graph model in one pass, and a second walk to recover what a box holds would be
    a second answer to the same question (rule 13).

    A member list is **never bounded** (rule 8). Sixty-one methods is sixty-one rows;
    the reader came here to find one of them.
    """
    ids = json.dumps(list(box.get("members") or []))
    args = {"ids": ids}

    members = _rows(store, queries.FOLD_MEMBERS, args)
    params_by = _by_owner(_rows(store, queries.FOLD_PARAMS, args))
    comments_by = {str(r["routine_id"]): int(r["n"] or 0)
                   for r in _rows(store, queries.FOLD_COMMENTS, args)}
    anns = _rows(store, queries.FOLD_ANNOTATIONS, args)
    anns_by = _by_owner(anns)

    held = []
    for m in members:
        mid = str(m["id"])
        held.append({
            **m,
            # The same pieces the hover card and the single-routine inspector send,
            # from the same renderer -- so a member's invocation line here and its
            # signature one click in cannot disagree (rule 13).
            "params": signature_parts([
                (r["name"], r["type"], r["dflt"], r["kind"])
                for r in params_by.get(mid, [])
            ]),
            "comments": comments_by.get(mid, 0),
            "annotations": len(anns_by.get(mid, [])),
        })

    detail: dict[str, Any] = {
        # The kind a fold reports is the kind of thing it *is*, and it is not one of
        # the six `classify()` knows. Named rather than borrowed: calling a class box
        # a ROUTINE would put the wrong word in the inspector's head and the wrong
        # answer in every check that reads it.
        "kind": "FOLD",
        "id": str(box.get("id") or ""),
        "label": str(box.get("label") or ""),
        "identity": {
            "fold": str(box.get("kind") or ""),          # class | file | touch
            "module": box.get("module") or "",
            "class_name": box.get("class_name") or "",
            "qualname": _fold_qualname(box),
            "file": members[0]["file"] if members else "",
            "folded": len(held),
            "plate": str(box.get("id") or "").partition("|")[0],
        },
        "holds": {"routines": held},
        "in": {"callers": flow.get("in") or [], "entrypoints": []},
        "out": {"calls": flow.get("out") or []},
        "touches": {
            "boundaries": _rows(store, queries.FOLD_BOUNDARIES, args),
            "sql": _rows(store, queries.FOLD_SQL_OPS, args),
            "net": _rows(store, queries.FOLD_NET_CALLS, args),
            "artefacts": _rows(store, queries.FOLD_ARTEFACTS, args),
        },
        # Annotations whole, comments counted. A fold's comments are hundreds of
        # sentences each explaining one line of one member, and the inspector places
        # a comment against the line it is about -- which is an answer about a
        # routine, not about a class. The count rides on the member row instead.
        "governance": {"annotations": anns, "comments": []},
        "where": _fold_where(members),
        "found": True,
    }
    # The span of a class is the span of what it holds, so the source pane opens on
    # the definition rather than on whichever member happened to sort first.
    attach_source(detail, source, revision=revision)
    return detail


def _fold_qualname(box: dict[str, Any]) -> str:
    """What to call a fold in the inspector's head, spelled the way the code is."""
    module = str(box.get("module") or "")
    cls = str(box.get("class_name") or "")
    if module and cls:
        return f"{module}.{cls}"
    return module or str(box.get("label") or "")


def _fold_where(members: list[dict[str, Any]]) -> dict[str, Any]:
    """The file a fold lives in, and the span its members cover.

    All of a class's methods and all of a file's loose functions sit in one file by
    construction, so the file is the first member's. The span is the outermost pair
    rather than the first member's own, because a fold is the whole of what it holds
    and a source pane opened on one method is an answer about that method.
    """
    if not members:
        return {"file": "", "first": 0, "last": 0}
    first = min(int(m["line_start"] or 0) for m in members)
    last = max(int(m["line_end"] or 0) for m in members)
    return {"file": members[0]["file"], "first": first, "last": last}
