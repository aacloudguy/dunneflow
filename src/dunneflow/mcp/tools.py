"""The tool bodies: plain dictionaries in, plain dictionaries out.

**This module knows the map and nothing about the wire.** It imports no `jsonrpc`, builds
no envelope and raises ordinary exceptions; `server.py` turns what comes back into content
and what is raised into a refusal. That is `prose.js`' boundary one subject over, and it is
what makes a second API surface a second caller rather than a second assembly of the same
steps (rule 51).

**Nothing here is new logic.** Every body calls the function the dashboard calls —
`web/cover.py`, `web/detail.py`, `web/shape.py`, `web/search.py`, `resolve/flows.py`,
`lookup.py` — and the three answers that were reachable from one surface only were moved
out to where both callers pass *before* this module existed, because the cheapest moment to
move a rule is before the caller that would have copied it. An agent and a reader looking
at the same map must not be told different things about it.

**A tool is small and sharp, not one per endpoint.** The dashboard has forty-odd routes
because a page is assembled from parts; an agent asks a question and wants the answer, so
`routine` is a signature *and* its comments *and* its boundaries *and* its shape, in one
call.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .. import sql as sqlmod
from ..lookup import find_routine, search_said
from ..resolve.flows import GOVERNANCE_KINDS, entry_reach, governance_over, ways_in_affected
from ..resolve.macros import macro_places, macro_report
from ..web.detail import describe
from ..web.search import search_files, search_in_file
from ..web.serve import glossary_sidecars
from ..web.shape import outline_for
from . import Refused
from .session import Session

#: How many matches a name search returns when the caller does not say. The cap is the
#: caller's and is stated in the answer either way, because a bounded answer that does not
#: say it is bounded is the silence `Found.total` exists to break (rule 32).
DEFAULT_LIMIT = 5

#: How many rows `query` returns when the caller does not say. Unlike a diagram, a result
#: set has no natural bound (rule 8) -- but this one crosses a pipe into a context window,
#: so the bound is the *channel's* and the answer says how many it did not send.
DEFAULT_ROWS = 100
MAX_ROWS = 2000
# How long one `query` statement may run before it is interrupted (rule 55).
QUERY_SECONDS = 20


@dataclass(frozen=True, slots=True)
class Tool:
    """One thing an agent can ask for.

    `schema` is JSON Schema as MCP wants it. It is written out beside the body rather than
    derived from the signature: what a parameter *means* to a reader is the half a
    signature cannot carry, and it is the half the model actually reads.
    """

    name: str
    description: str
    body: Callable[[Session, dict[str, Any]], dict[str, Any]]
    properties: dict[str, Any] = field(default_factory=dict)
    required: tuple[str, ...] = ()

    def as_mcp(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": self.properties,
                "required": list(self.required),
            },
        }


def _want(args: dict[str, Any], key: str) -> str:
    """A required string argument, refused by name when it is missing or blank.

    Never defaulted. A tool that answers about *something* when it was asked about nothing
    is the fallback rule 49 is about, and here the plausible answer would be whichever
    routine sorted first.
    """
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise Refused(f"{key} is required, and must be a non-empty string")
    return value.strip()


def _limit(args: dict[str, Any], default: int = DEFAULT_LIMIT) -> int:
    value = args.get("limit", default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise Refused("limit must be a whole number of at least 1")
    return value


def _hit(hit: Any) -> dict[str, Any]:
    """A `BoundaryHit` as plain data."""
    return {"routine": hit.routine_id, "kind": hit.kind.value,
            "direction": hit.direction.value, "target": hit.target, "line": hit.line,
            "evidence": hit.evidence, "salience": hit.salience}


def _matched(session: Session, needle: str, limit: int) -> tuple[list[dict], dict]:
    """The routines a name search found, and **what has to be said about the search**.

    `search_said` travels with the rows and is not optional. `find_routine` falls back to a
    substring match when nothing is named exactly, and that fallback once answered
    `touches --routine mensores.cli.app` about `mensores.cli.apply.apply` with a reach of 1.
    A tool that returned `matches` and dropped the caveat would hand a model a plausible
    answer to a question it did not ask.
    """
    found = find_routine(session.store, needle)
    shown = found.matches[:limit]
    note = {
        "exact": found.exact,
        "matched": found.total,
        "showing": len(shown),
        "said": search_said(needle, found, len(shown)),
    }
    if found.module:
        note["module"] = {"name": found.module, "file": found.module_file,
                          "routines": found.module_routines}
    return shown, note


# ---- what is open --- #


def _overview(session: Session, _args: dict[str, Any]) -> dict[str, Any]:
    """The cover: where to start, what is biggest, what it touches, how much there is."""
    base = session.base
    languages = {row["lang"]: row["n"] for row in session.store.query(
        "SELECT lang, count(*) AS n FROM files GROUP BY lang ORDER BY lang")}
    return {
        **base.cover,
        "revision": base.revision,
        # **What was read, by language.** One entry today and the count says so rather than
        # the sentence claiming the tool reads everything. The declined-and-unclaimed halves
        # arrive with the plugin registry; a count that says what it counts is right at
        # every stage (rule 32).
        "languages": languages,
    }


def _programs(session: Session, _args: dict[str, Any]) -> dict[str, Any]:
    return session.programs()


def _open(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    return session.open(program=str(args.get("program", "") or ""),
                        revision=str(args.get("revision", "") or ""))


# ---- one routine, three questions --- #


def _touches(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    """What does this reach, and what does it end up touching outside itself."""
    needle = _want(args, "routine")
    shown, note = _matched(session, needle, _limit(args))
    store = session.store
    out = []
    for match in shown:
        reach, kinds = entry_reach(store, match["id"])
        out.append({
            "routine": match["qualname"], "id": match["id"],
            "file": match["file"], "line": match["line_start"],
            "reaches": reach,
            "boundary_kinds": [k.value for k in kinds],
            "boundaries": [_hit(h) for h in
                           store.boundaries_reached_many([match["id"]], through_macros=True)],
            # Where the reach stops, and why, as far as the readers said (schema 17).
            "frontier": store.frontier_reached(match["id"]),
            # Where the reach crosses into another process by a command's name, and where
            # a name was sent that links to nothing. The `how` is on every row, because a
            # string equal to a name is not a reference (`resolve/ipc.py`).
            "by_name": [_sent(x) for x in store.ipc_sent(store.reachable_from(match["id"]))],
            # Where the reach went on into the bodies a dispatched call may run. Already
            # inside `reaches`; listed so a reader can see which of it is *may* rather
            # than *does* (`resolve/dispatch.py`).
            "by_dispatch": [
                {"call": x["callee_expr"], "caller": x["caller"], "file": x["file"],
                 "line": x["line"], "bodies": x["bodies"], "how": x["how"]}
                for x in store.dispatched(store.reachable_from(match["id"]))
            ],
        })
    return {"asked": needle, **note, "routines": out}


def _sent(x: Any) -> dict[str, Any]:
    return {"command": x["command"], "status": x["status"], "how": x["how"],
            "confidence": x["confidence"], "sender": x["sender"],
            "file": x["file"], "line": x["line"], "answered_by": x["command_qualname"]}


def _impact(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    """What breaks if this changes — and which ways in, and what was decided about it."""
    needle = _want(args, "routine")
    shown, note = _matched(session, needle, _limit(args))
    store = session.store
    out = []
    for match in shown:
        callers = store.callers_of(match["id"])
        out.append({
            "routine": match["qualname"], "id": match["id"],
            "file": match["file"], "line": match["line_start"],
            "dependents": len(callers),
            # The dependents that reach this from another process, by a command's name.
            # Already inside `dependents`; listed so the crossing is not hidden in a count.
            "by_name": [_sent(x) for x in store.ipc_received([match["id"], *callers])],
            # The dependents that reach this only as one of the bodies a dispatched call
            # may run. Already inside `dependents`, and listed for `by_name`'s reason.
            "by_dispatch": [
                {"call": x["callee_expr"], "caller": x["caller"], "file": x["file"],
                 "line": x["line"], "body": x["body"], "how": x["how"]}
                for x in store.dispatched_into([match["id"], *callers])
            ],
            # Calls with no edge that use this routine's name: undrawn possibilities, by
            # reason, and never counted among the dependents.
            "unresolved_by_name": dict(store.unresolved_named(match["name"])),
            "ways_in": ways_in_affected(store, callers),
            "governance": governance_over(store, callers),
            # Stated, so a reader of the answer knows what was asked rather than inferring
            # it from what came back (rule 41).
            "governance_kinds": list(GOVERNANCE_KINDS),
        })
    return {"asked": needle, **note, "routines": out}


def _routine(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    """One routine whole: what it is, what it says, what it touches, and its shape."""
    needle = _want(args, "routine")
    shown, note = _matched(session, needle, 1)
    if not shown:
        return {"asked": needle, **note, "found": False}
    base = session.base
    node = shown[0]["id"]
    return {
        "asked": needle, **note, "found": True,
        "detail": describe(base.store, node, session.live.source,
                           revision=base.source_revision),
        "shape": outline_for(base.store, node),
    }


# ---- the two searches, which are different questions --- #


def _find(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    """Names **and** text, because the graph cannot answer the second.

    `touches`, `impact` and `glossary` search names and meanings. Nothing in the graph can
    find a word inside a comment, inside a string literal, or on a line that carries
    neither — that is what the source sidecar is for, and it is a different question rather
    than a wider one.

    With a `file`, the same search one level down: that file's matching lines, each with
    the routine it sits in.
    """
    needle = _want(args, "q")
    base = session.base
    flags = {"case": bool(args.get("case", False)),
             "word": bool(args.get("word", False)),
             "regex": bool(args.get("regex", False))}
    path = str(args.get("file", "") or "")
    if path:
        return {"asked": needle, "file": path,
                "text": search_in_file(base.store, session.live.source, needle, path,
                                       revision=base.source_revision, **flags)}
    names, note = _matched(session, needle, _limit(args))
    return {
        "asked": needle,
        "names": {**note, "routines": names},
        "text": search_files(base.store, session.live.source, needle,
                             revision=base.source_revision, **flags),
    }


def _macros(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    """What the program's macros do, and what the map could not see of them."""
    store = session.base.store
    report = macro_report(store)
    wanted = str(args.get("macro", "") or "").strip()
    limit = int(args.get("limit") or DEFAULT_LIMIT)
    head = {"summary": report["summary"], "expansion": report["expansion"],
            "unread": {**report["unread"], "arms": report["unread"]["arms"][:limit],
                       "headers": report["unread"]["headers"][:limit]}}
    if not wanted:
        return {**head, "total": len(report["definitions"]),
                "definitions": report["definitions"][:limit]}
    found = [d for d in report["definitions"] if d["name"] == wanted]
    return {**head, "asked": wanted, "found": bool(found),
            "definitions": [{**d, **macro_places(store, d["id"])} for d in found[:limit]]}


def _glossary(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    """What the program's words mean, and who says so.

    The `sidecars` block rides along for the same reason it rides on `/api/glossary`: it is
    a **capability** — whether the corpus a provenance tier quotes has a sidecar this base
    can read — and without it every citation is a claim nothing can open (design rule 13).
    """
    base = session.base
    payload = {**base.glossary, "sidecars": glossary_sidecars(
        session.live.source, session.live.docsource,
        base.source_revision, base.docsource_revision)}
    term = str(args.get("term", "") or "").strip()
    if not term:
        return payload
    wanted = term.lower()
    hits = [t for t in payload.get("terms", []) if str(t.get("term", "")).lower() == wanted]
    return {"term": term, "found": bool(hits), "terms": hits,
            "sidecars": payload["sidecars"],
            "coverage": payload.get("coverage")}


# ---- the escape hatch --- #

#: The one direction a statement may have. `sql.parse` classifies READ / WRITE / DDL /
#: CONTROL and returns `None` for a leading verb it does not know.
READ = sqlmod.READ


def _query(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    """Raw SQL against the graph. **Two gates, because neither one is enough.**

    Measured, not assumed:

    * `mode=ro` refuses every write to the map, including
      `WITH x AS (SELECT 1) DELETE FROM t` — which the classifier below reads as READ,
      since it classifies the leading verb and nothing else.
    * the classifier refuses `ATTACH`, which `mode=ro` **allows** and which would let a
      second call write to a database that is not this one.
    * Python's own `sqlite3` refuses more than one statement per `execute`, so neither gate
      has to.

    So each catches what the other misses, which is what makes belt and braces here a
    measurement rather than a habit. The residue is stated rather than implied:
    `PRAGMA writable_schema=ON` passes both and does nothing, because every write is still
    refused.

    A statement `parse` cannot classify at all is **refused**, not admitted for looking
    harmless (rule 49).
    """
    statement = _want(args, "sql")
    parsed = sqlmod.parse(statement)
    if parsed is None:
        raise Refused(
            "that statement could not be classified, so it is refused — this tool runs "
            "reads, and a statement it cannot name the direction of is not one it can "
            "call a read")
    if parsed.direction != READ:
        raise Refused(
            f"this tool runs reads; that is {parsed.operation} ({parsed.direction}). The "
            f"connection would refuse a write in any case — the statement is refused here "
            f"so the reason names the statement rather than the database")

    rows_wanted = _limit(args, DEFAULT_ROWS)
    if rows_wanted > MAX_ROWS:
        raise Refused(f"limit must be at most {MAX_ROWS:,}")

    # **Bounded on the work, not only on the answer (rule 55).** This fetched every row
    # into a list and then showed a hundred of them, with no clock: a recursive CTE with no
    # end, or a join of `calls` with itself, held the server for as long as it liked and
    # every other tool with it. Rows are counted as they come and only the ones shown are
    # kept, and a statement still running after `QUERY_SECONDS` is interrupted and said so.
    conn = session.store.conn
    deadline = time.monotonic() + QUERY_SECONDS
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 20_000)
    shown: list[dict[str, Any]] = []
    total = 0
    try:
        for row in conn.execute(statement):
            total += 1
            if len(shown) < rows_wanted:
                shown.append(dict(row))
    except sqlite3.OperationalError as exc:
        if "interrupt" not in str(exc).lower():
            raise
        raise Refused(
            f"that statement was still running after {QUERY_SECONDS} seconds and was "
            f"stopped; {total:,} rows had come back. Narrow it with a WHERE or a LIMIT"
        ) from exc
    finally:
        conn.set_progress_handler(None, 0)
    return {
        "sql": parsed.sql,
        "operation": parsed.operation,
        "tables": parsed.tables,
        # A count that says what it counts: how many there were, and how many crossed.
        "rows": total,
        "returned": len(shown),
        "truncated": total > len(shown),
        "results": shown,
    }


# ---- making a map --- #


def _analyze(session: Session, args: dict[str, Any]) -> dict[str, Any]:
    """Read a source tree into a map. A long job, so it returns a handle."""
    return session.analyze(path=_want(args, "path"),
                           name=str(args.get("name", "") or ""),
                           # An absent parameter means the caller did not say, and
                           # documentation is an input this tool reads by default
                           # (design rule 11).
                           docs=bool(args.get("docs", True)))


def _analysis_status(session: Session, _args: dict[str, Any]) -> dict[str, Any]:
    return session.analysis_status()


def _analysis_stop(session: Session, _args: dict[str, Any]) -> dict[str, Any]:
    return session.analysis_stop()


# ---- the table --- #

TOOLS: tuple[Tool, ...] = (
    Tool("overview",
         "The cover of the open map: the ways in ranked by how much of the program each "
         "commands, the biggest packages and tables, what it touches outside itself, the "
         "counts, and which languages were read. Start here.",
         _overview),
    Tool("programs",
         "Every map under this output root, with its revisions, and which one is open.",
         _programs),
    Tool("open",
         "Read a different program or a different revision. Name either or both. The map "
         "on screen is replaced only if the new one builds; a failure leaves what you had.",
         _open,
         {"program": {"type": "string",
                      "description": "a program name as `programs` lists it"},
          "revision": {"type": "string",
                       "description": "a revision as `programs` lists it; omit for newest"}}),
    Tool("touches",
         "What does this routine reach, and what does it end up touching outside the "
         "program — files, databases, the network, the environment, other processes.",
         _touches,
         {"routine": {"type": "string",
                      "description": "a name or a qualified name. An inexact match is "
                                     "answered and said to be inexact."},
          "limit": {"type": "integer",
                    "description": f"matches to report (default {DEFAULT_LIMIT})"}},
         ("routine",)),
    Tool("impact",
         "What breaks if this routine changes: how many routines depend on it, which ways "
         "in are disturbed, and what plans or decisions are recorded against any of them.",
         _impact,
         {"routine": {"type": "string", "description": "a name or a qualified name"},
          "limit": {"type": "integer",
                    "description": f"matches to report (default {DEFAULT_LIMIT})"}},
         ("routine",)),
    Tool("routine",
         "One routine whole: signature, docstring, comments, the calls in and out, the "
         "boundaries it touches, the source, and its shape — the loops, decisions, guards "
         "and handlers it is made of.",
         _routine,
         {"routine": {"type": "string", "description": "a name or a qualified name"}},
         ("routine",)),
    Tool("find",
         "Search names and the text of the source together. The text half is the question "
         "the graph cannot answer: a word inside a comment, inside a string literal, or on "
         "a line that carries neither. Give a file to get that file's matching lines.",
         _find,
         {"q": {"type": "string", "description": "what to look for"},
          "file": {"type": "string",
                   "description": "a path as the fileless answer lists it; narrows to that "
                                  "file's lines"},
          "case": {"type": "boolean", "description": "match case (default false)"},
          "word": {"type": "boolean", "description": "whole words only (default false)"},
          "regex": {"type": "boolean", "description": "read q as a regular expression"},
          "limit": {"type": "integer", "description": f"name matches (default {DEFAULT_LIMIT})"}},
         ("q",)),
    Tool("macros",
         "What the program's macros do where they are used, leading with those that reach "
         "something, and what could not be seen: arms not taken, headers not found. Name a "
         "macro for every definition of it, each with its places.",
         _macros,
         {"macro": {"type": "string",
                    "description": "a macro's name, exactly. A name is not an identity, so "
                                   "each definition of it comes back separately."},
          "limit": {"type": "integer",
                    "description": f"rows to report (default {DEFAULT_LIMIT})"}},
         ()),
    Tool("glossary",
         "What the program's words mean and who says so — every definition carries where "
         "it came from. Name a term for one, or omit it for the whole vocabulary with its "
         "coverage.",
         _glossary,
         {"term": {"type": "string", "description": "one word; omit for all of them"}}),
    Tool("query",
         "Ask the graph directly with SQL. Reads only: anything that is not a read is "
         "refused by name, and the connection is read-only underneath in any case. The "
         "schema is available as a resource.",
         _query,
         {"sql": {"type": "string", "description": "one SELECT, WITH or PRAGMA statement"},
          "limit": {"type": "integer",
                    "description": f"rows to return (default {DEFAULT_ROWS}, max {MAX_ROWS})"}},
         ("sql",)),
    Tool("analyze",
         "Read a source tree into a new map under this output root. A long job: this "
         "returns straight away with a handle, and `analysis_status` says how it is going. "
         "Analysing into a name that already exists rewrites that program's working "
         "snapshot, and the answer says so.",
         _analyze,
         {"path": {"type": "string",
                   "description": "an absolute path to the source tree to read"},
          "name": {"type": "string",
                   "description": "what to call the program (default: the directory's name)"},
          "docs": {"type": "boolean",
                   "description": "read documentation as well as source (default true)"}},
         ("path",)),
    Tool("analysis_status",
         "How the running analysis is going, or how the last one ended. Carries the "
         "child's own progress: the step, how many of them, and how long it has been "
         "silent.",
         _analysis_status),
    Tool("analysis_stop",
         "End the running analysis. What it has written so far is marked unfinished, so "
         "no reader can mistake it for a map of the whole program.",
         _analysis_stop),
)

BY_NAME: dict[str, Tool] = {tool.name: tool for tool in TOOLS}
