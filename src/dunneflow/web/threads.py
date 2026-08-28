"""Threads to pull: the reasons a neighbour is worth a detour.

Design rule 15 asks for adjacency by *interest*, not only by edge, and says why: the way
this tool actually gets used is see something, get curious, notice something beside it,
pull the thread. The call graph cannot answer that. It says what runs next, which is a
different question from what is *related* -- and the most useful relations in a real
codebase are not calls at all. Two routines that never call each other and both write
`audit_events` are coupled through the store. Nine routines carrying the same plan id were
one piece of work. Neither is an edge anywhere.

So a thread is a row that says: **this thing over there, and why it is beside you.**

Three disciplines, and every one of them was a defect first.

* **A thread must lead somewhere.** Every thread carries a `subject` -- an identity the
  router can act on -- and never a bare label. The shell's previous threads panel was six
  hand-written rows for one Mensores routine, and clicking any of them set
  `state.view = "curiosities"` and landed on a page that says it has nothing computed.
  It rendered, it highlighted, it was entirely dead. Rule 30.

* **A thread states its size, and the smallest sorts first.** "9 other routines carry this
  plan" and "312 other routines carry this plan" are different invitations. Nothing is
  thresholded away -- that would be a filter the reader cannot see -- but rarity sorts to
  the top, because a thing shared with three routines is work you can hold in your head
  and a thing shared with three hundred is a category.

* **Nothing here is generated.** Every row is a row the store already holds, counted. A
  thread that reads like an insight and came from a template is the same failure as a
  definition without its provenance: an assertion wearing a uniform.
"""

from __future__ import annotations

from typing import Any

from ..store import Store
from . import queries, vocabulary

# How the panel groups them. Order is fixed here rather than left to the client so that
# two readers of the same routine see the same list in the same order -- a panel that
# reshuffles between visits is one nobody builds a memory of.
KIND_ORDER = ("governance", "boundary", "vocabulary", "outlier")


def _rows(store: Store, sql: str, args: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(r) for r in store.query(sql, args)]


def _one(store: Store, sql: str, args: dict[str, Any]) -> dict[str, Any] | None:
    rows = _rows(store, sql, args)
    return rows[0] if rows else None


def _plural(n: int, one: str, many: str = "") -> str:
    return f"{n:,} {one}" if n == 1 else f"{n:,} {many or one + 's'}"


# --------------------------------------------------------------------------- #
# The subject
#
# What following a thread selects. Three shapes, because there are genuinely three
# kinds of thing at the far end and pretending otherwise is what rule 30 warns
# against: a package is a plate, a routine is a node, and a governance id is
# neither -- `Plan 56-02` is not a node at all, so following it means selecting
# the code that carries it. `queries.py` wrote that reasoning down for tables
# before anything needed it: inventing an id to make a row clickable would be a
# link to nothing.
# --------------------------------------------------------------------------- #

def _node(node_id: str) -> dict[str, Any]:
    """A thing that is already in the graph. One hop, selected as itself."""
    return {"type": "node", "id": node_id}


def _cohort(kind: str, key: str, label: str) -> dict[str, Any]:
    """A set of routines that share something. Resolved on demand, never shipped.

    The ids are deliberately *not* inline. A plan carried by three hundred routines
    would put three hundred ids in a payload built for a panel showing four rows, and
    the reader who never clicks it pays for all of them. `/api/thread` answers the one
    they do click, which is the same bargain the hover card makes.
    """
    return {"type": "cohort", "kind": kind, "key": key, "label": label}


# --------------------------------------------------------------------------- #
# Governance kin
# --------------------------------------------------------------------------- #

def _governance(store: Store, node_id: str) -> list[dict[str, Any]]:
    out = []
    for r in _rows(store, queries.THREAD_GOVERNANCE, {"id": node_id}):
        value, kind, others = r["value"], str(r["kind"] or "").lower(), int(r["others"])
        noun = {"plan": "plan", "adr": "decision record", "issue": "issue",
                "ticket": "ticket", "gate": "gate", "decision": "decision"}.get(kind, "id")
        out.append({
            "kind": "governance",
            "label": value,
            "why": f"{_plural(others, 'other routine')} carr"
                   f"{'ies' if others == 1 else 'y'} this {noun}",
            "count": others,
            "subject": _cohort("governance", value, value),
        })
    return out


# --------------------------------------------------------------------------- #
# The other end of a boundary
#
# The thread kind that finds code with **no call edge to the subject at all**. Two
# routines that never call each other and both write the same table are coupled
# through the store, and no call graph can say so; this is the only place in the
# product that can.
# --------------------------------------------------------------------------- #

def _boundary(store: Store, node_id: str) -> list[dict[str, Any]]:
    out = []

    for r in _rows(store, queries.THREAD_TABLES, {"id": node_id}):
        others = int(r["others"])
        # Three counts that do not partition -- a routine reading and writing the same
        # table is in two of them -- so each says what it counted and none of them
        # claims to be a share of the total. Presented as a sum they would be wrong.
        parts = [p for p in (
            f"{int(r['readers']):,} read it" if r["readers"] else "",
            f"{int(r['writers']):,} write it" if r["writers"] else "",
            f"{int(r['declarers']):,} declare it" if r["declarers"] else "",
        ) if p]
        if r["i_write"] and r["i_read"]:
            mine = "you write and read it"
        elif r["i_write"]:
            mine = "you write it"
        elif r["i_read"]:
            mine = "you read it"
        else:
            mine = "you touch it"
        # "of 6 others, 3 read it and 3 declare it" rather than a bare list, so the
        # total and its parts are visibly the same claim. They still do not partition --
        # a routine that reads and writes is in two groups -- which is why it is "of",
        # not a sum.
        rest = (f"of {_plural(others, 'other')}, " + " and ".join(parts)) if parts \
            else f"{_plural(others, 'other routine')} touch it"
        out.append({
            "kind": "boundary",
            "label": r["name"],
            "why": f"{mine} · {rest}",
            "count": others,
            # A table is not a node in the graph, so selecting one means selecting the
            # code that reads and writes it.
            "subject": _cohort("table", r["name"], r["name"]),
        })

    for r in _rows(store, queries.THREAD_BOUNDARIES, {"id": node_id}):
        kind, target, others = r["kind"], r["target"], int(r["others"])
        out.append({
            "kind": "boundary",
            "label": target,
            "why": f"{_plural(others, 'other routine')} also "
                   f"{'reach' if others != 1 else 'reaches'} this {kind.lower()}",
            "count": others,
            # An endpoint *is* a node, so it is selected as itself rather than through
            # a set standing in for it.
            "subject": _node(f"bnd:{kind}:{target}"),
        })

    for r in _rows(store, queries.THREAD_ARTEFACTS, {"id": node_id}):
        others = int(r["others"])
        out.append({
            "kind": "boundary",
            "label": r["name"],
            "why": f"{_plural(others, 'other routine')} name"
                   f"{'s' if others == 1 else ''} this file",
            "count": others,
            "subject": _node(f"art:{r['name']}"),
        })

    for r in _rows(store, queries.THREAD_NET, {"id": node_id}):
        others = int(r["others"])
        out.append({
            "kind": "boundary",
            "label": r["target"],
            "why": f"{_plural(others, 'other routine')} also "
                   f"{'call' if others != 1 else 'calls'} this {r['protocol']} destination",
            "count": others,
            "subject": _cohort("net", r["target"], r["target"]),
        })

    out.sort(key=lambda t: (t["count"], t["label"]))
    return out


# --------------------------------------------------------------------------- #
# Outliers nearby
#
# Design rule 15's curiosities, scoped to the package the reader is standing in:
# what came out furthest from the middle *here*. Not problems -- doorways.
#
# Each carries its number, because "the most commented routine in this package" is
# a claim the reader cannot weigh without it, and 264 comments and 7 comments are
# not the same discovery.
# --------------------------------------------------------------------------- #

def _package_of(module: str, root: str) -> str:
    """The segment just under the program root -- the plate the reader is standing on.

    Taken from the data rather than assumed: `mensores.cli` and `dunneflow.cli` are both
    one segment deep, so a hard-coded prefix length works on exactly one program.
    """
    if not module or not root:
        return module
    if module == root or not module.startswith(root + "."):
        return module
    rest = module[len(root) + 1:]
    head = rest.split(".", 1)[0]
    return f"{root}.{head}"


def _label_of(row: dict[str, Any]) -> str:
    """A name a reader can recognise.

    `<module>` is a real node -- the synthetic module scope that owns everything no
    function does (rule 18) -- and it is genuinely often the most commented thing in a
    package. On its own the name says nothing, so it is shown as the module it *is*.
    """
    name = str(row.get("name") or "")
    if name == "<module>":
        qual = str(row.get("qualname") or "")
        return qual[: -len(".<module>")] if qual.endswith(".<module>") else qual
    return name


def _outliers(store: Store, node_id: str, module: str, root: str) -> list[dict[str, Any]]:
    pkg = _package_of(module, root)
    args = {"id": node_id, "pkg": pkg, "pkg_dot": f"{pkg}.%"}
    here = pkg.rsplit(".", 1)[-1] if "." in pkg else pkg
    out = []

    r = _one(store, queries.THREAD_MOST_COMMENTED, args)
    if r and int(r["n"]) > 0:
        out.append({"kind": "outlier", "label": _label_of(r),
                    "why": f"{_plural(int(r['n']), 'comment')} — the most in {here}",
                    "count": int(r["n"]), "subject": _node(str(r["id"]))})

    r = _one(store, queries.THREAD_MOST_CALLED, args)
    if r and int(r["n"]) > 0:
        out.append({"kind": "outlier", "label": _label_of(r),
                    "why": f"called from {_plural(int(r['n']), 'place')} — the most in {here}",
                    "count": int(r["n"]), "subject": _node(str(r["id"]))})

    r = _one(store, queries.THREAD_DEEPEST, args)
    if r and int(r["depth"]) > 1:
        out.append({"kind": "outlier", "label": _label_of(r),
                    "why": f"nested {_plural(int(r['depth']), 'level')} deep — "
                           f"the deepest closure in {here}",
                    "count": int(r["depth"]), "subject": _node(str(r["id"]))})

    r = _one(store, queries.THREAD_LOPSIDED_TABLE, args)
    if r:
        w, rd = int(r["writes"]), int(r["reads"])
        # Only when it is actually lopsided. A table written five times and read four is
        # not a doorway, and calling it one would be this module manufacturing interest --
        # which is precisely what "nothing here is generated" forbids.
        if max(w, rd) >= 3 * max(1, min(w, rd)):
            which = "written" if w > rd else "read"
            out.append({
                "kind": "outlier", "label": str(r["name"]),
                "why": f"{which} {max(w, rd) // max(1, min(w, rd))}× as often as it is "
                       f"{'read' if w > rd else 'written'} in {here} "
                       f"({w} write{'' if w == 1 else 's'}, {rd} read{'' if rd == 1 else 's'})",
                "count": max(w, rd),
                "subject": _cohort("table", str(r["name"]), str(r["name"])),
            })

    return out


# --------------------------------------------------------------------------- #
# Vocabulary and kin by name
#
# The two lanes of the naming standard, read as adjacency. A routine ending `_cmd`
# has 98 relatives it never calls; a routine whose module is `disceptator` is using
# a word the project defines in a document, with a file and a line.
#
# This is the only thread kind that ties the graph to the glossary and naming
# pages, which until now were reachable only from their own screens -- and which,
# in the shell, had never been served at all.
#
# It reads precomputed reports rather than the store, because both passes cost more
# than a per-selection request may (2.5 s together on Mensores). They are handed in
# rather than fetched here, so this module stays a set of queries and the decision
# about *when* to pay for them stays at the server, where it belongs.
# --------------------------------------------------------------------------- #

def _vocabulary(name: str, module: str, naming: dict[str, Any] | None,
                glossary: dict[str, Any] | None) -> list[dict[str, Any]]:
    out = []

    for c in vocabulary.conventions_for(naming or {}, name):
        others = max(0, int(c["total"]) - 1)
        if not others:
            continue                      # a convention of one is not a thread
        # The claim, the rating and the count travel together. "A routine ending `_cmd`
        # is registered as a way in" is a sentence; "97 of 99" is what makes it a claim
        # a reader can weigh, and rule 13 says the query that produced it must be
        # reachable -- it is, on the naming page, and `sql` is what gets it there.
        out.append({
            "kind": "vocabulary",
            "label": c["glob"],
            "why": f"{c['claim'].rstrip('.')} — {c['holds']:,} of {c['total']:,}"
                   f" ({c['rating']}); {_plural(others, 'other')} named this way",
            "count": others,
            "subject": _cohort("convention", c["glob"], c["glob"]),
        })

    for t in vocabulary.terms_in(glossary or {}, name, module):
        senses = t.get("senses") or []
        if senses:
            first = senses[0]
            why = (f"{t['used_as']} — defined in "
                   f"{str(first['source']).split('/')[-1]}:{first['line']}")
        else:
            # An undefined word is a finding, not a blank: it is what the mirror and the
            # glossary's own undefined list exist to surface. Saying "used 638 times and
            # nothing says what it means" is more useful than omitting the row.
            why = f"{t['used_as']} — nothing in this program says what it means"
        out.append({
            "kind": "vocabulary",
            "label": t["term"],
            "why": why,
            "count": int(t["uses"]),
            "subject": _cohort("term", t["term"], t["term"]),
        })

    return out


# --------------------------------------------------------------------------- #
# The one way in
# --------------------------------------------------------------------------- #

def for_node(store: Store, node_id: str, *, module: str = "", root: str = "",
             name: str = "", naming: dict[str, Any] | None = None,
             glossary: dict[str, Any] | None = None) -> dict[str, Any]:
    """Every thread off one node, grouped by kind and ordered within each.

    Answers with an empty list rather than refusing when a node has no threads. A routine
    with nothing beside it is an ordinary fact about a program -- most private helpers are
    exactly that -- and "no threads here" and "threads have not been computed" are
    opposite claims that must never render the same way. The client says which; this says
    which is true.
    """
    threads = _governance(store, node_id) + _boundary(store, node_id)
    if module:
        threads += _outliers(store, node_id, module, root)
    if name:
        threads += _vocabulary(name, module, naming, glossary)

    by_kind: dict[str, list[dict[str, Any]]] = {k: [] for k in KIND_ORDER}
    for t in threads:
        by_kind[t["kind"]].append(t)

    return {"found": True, "id": node_id,
            "threads": [t for k in KIND_ORDER for t in by_kind[k]],
            "counts": {k: len(v) for k, v in by_kind.items()}}


def cohort(store: Store, kind: str, key: str) -> dict[str, Any]:
    """The nodes a cohort thread resolves to.

    Routed from a table, so a kind nobody wrote a query for is a **named error** rather
    than an empty answer that looks like a real one -- design rule 16, and the reason
    every unhandled case in this product now says its own name.
    """
    sql = {
        "governance": queries.GOVERNANCE_ROUTINES,
        # A word is not a node and neither is a definition, so following one selects the
        # code that *uses* the word -- the same reasoning tables were given, and the same
        # refusal to invent an id to make a row clickable.
        "term": queries.TERM_ROUTINES,
        # `key` is a glob and the query uses `GLOB`, not `LIKE`: it is the same string the
        # convention counted with, so the routines selected here are exactly the population
        # the claim beside it was measured over. Two derivations would be two populations.
        "convention": queries.CONVENTION_ROUTINES,
        # The same statement the navigator's table rows already use. One query, one
        # place: a second copy is a second thing to be wrong, and they would disagree
        # quietly rather than loudly.
        "table": queries.TABLE_ROUTINES,
        "net": queries.NET_ROUTINES,
    }.get(kind)
    if sql is None:
        return {"found": False, "kind": kind, "key": key, "nodes": [],
                "reason": f"no such thread kind: {kind!r}"}

    # One key, and however many parameters the query needs to spend it. A term needs six
    # globs because GLOB has no alternation, and building them here keeps `queries.py` what
    # it is -- SQL text, with nothing assembling it at the call site.
    if kind == "term":
        low = key.lower()
        args: dict[str, Any] = {
            "term": low,
            "n_pre": f"{low}_*", "n_suf": f"*_{low}", "n_mid": f"*_{low}_*",
            "m_pre": f"{low}.*", "m_suf": f"*.{low}", "m_mid": f"*.{low}.*",
        }
    else:
        args = {{"governance": "value", "table": "name", "net": "target",
                 "convention": "glob"}[kind]: key}
    nodes = [str(r["node"]) for r in _rows(store, sql, args) if r["node"]]
    # `found: True` with an empty list is a real answer -- a governance id cited only in
    # documentation has no code carrying it -- and is not the same as an unknown kind.
    return {"found": True, "kind": kind, "key": key, "nodes": nodes}
