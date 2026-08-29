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
