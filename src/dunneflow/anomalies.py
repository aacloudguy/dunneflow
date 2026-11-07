"""Finding what is wrong, and being honest about what that means.

A program worth reading may well be broken. Ingest therefore never fails on a bad
program: a file that will not parse yields a recorded error rather than an exception,
colliding definitions keep separate identities rather than merging, and an edge lost to
ambiguity is recorded as lost rather than silently omitted.

Every anomaly carries a **blind spot**: the sentence describing what would make it a
false alarm. This is not decoration. In the first real run against a live codebase,
six confident findings in a row were defects in this tool rather than in the program
under study -- nested closures sharing a qualname, docstrings parsed as SQL, an upsert
clause read as a table, a `__main__` guard assumed to call `main`, an async context
manager read as an un-awaited call, and test-only helpers reported as dead because
tests were excluded from the scan. A finding without its blind spot is a guess wearing
a uniform.

Severity says what it means; confidence says how sure the tool is. They are different
questions and are never blurred.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from .detectors import load_rules
from .resolve.entrypoints import binding_note, supplied_why
from .schema import make_id
from .store import Store
from .words import are, plural

# What it means for the program.
BROKEN = "BROKEN"    # the program cannot be correct as written
SUSPECT = "SUSPECT"  # probably wrong, or a latent operational hazard
INFO = "INFO"        # worth knowing; not necessarily wrong

# How sure the tool is.
CERTAIN = "CERTAIN"
PROBABLE = "PROBABLE"
POSSIBLE = "POSSIBLE"

@dataclass(frozen=True, slots=True)
class _AsyncCost:
    """What it costs to drop an async call, in one language's terms.

    Three fields because the severity, the sentence and the blind spot are three separate
    claims and the old finding got all three wrong at once for TypeScript. Keyed by the
    `unawaited_async` a reader declares in its own rules file, so this table is the only
    place the two answers are spelled and `anomalies.py` still names no language.
    """

    severity: str
    title: str
    detail: str
    blind_spot: str


_ASYNC_COST = {
    # Python. `f()` on an `async def` builds a coroutine and returns it; nothing runs
    # until something awaits it. The work does not happen, which is BROKEN's own
    # definition -- the program cannot be correct as written.
    "inert": _AsyncCost(
        severity=BROKEN,
        title="never awaited",
        detail="The coroutine is created and never run.",
        blind_spot="The result may be awaited elsewhere, passed to `asyncio.gather`, or "
                   "scheduled as a task. Calls managed by `async with` are already "
                   "excluded.",
    ),
    # JavaScript and TypeScript. The request is made the moment the call is; what is lost
    # is the ordering, and without a `.catch` the failure. **Not BROKEN**, because the
    # work happens and because dropping it deliberately is an idiom with a name.
    "runs": _AsyncCost(
        severity=SUSPECT,
        title="started and not awaited",
        detail="The promise runs, so the work happens — but nothing waits for it, so its "
               "ordering against what follows is not guaranteed and a rejection is "
               "unobserved unless it is caught.",
        blind_spot="Fire-and-forget is deliberate here often enough to be an idiom, and "
                   "a `.catch()` on the end handles the rejection this would otherwise "
                   "warn about — neither is visible to this check, which sees only that "
                   "no `await` is on the call. A promise stored and awaited later, or "
                   "handed to `Promise.all`, reads the same way.",
    ),
}


_SEVERITY_ORDER = {BROKEN: 0, SUSPECT: 1, INFO: 2}
_CONFIDENCE_ORDER = {CERTAIN: 0, PROBABLE: 1, POSSIBLE: 2}

_STDLIB = frozenset(sys.stdlib_module_names)


@dataclass(slots=True)
class Occurrence:
    """One of the things a finding is about, and how to open it.

    **`nav` is the name of a *route*, not the kind of the thing.** `routine`, `t`, `file`,
    `ep` and `b` are entries in the shell's `NAV_ROUTES` and are what a navigator row
    already writes -- so an occurrence carries a subject the router acts on rather than a
    label with no way in (rule 30). Naming the kind instead would need a second table
    mapping kinds to routes at the far end, which is a second place to forget one (rule 51).

    `file` and `line` travel beside the id rather than instead of it: they are what makes a
    row worth reading before it is clicked, and for the two occurrence families with no
    selectable subject -- an index, a lost call site -- they *are* the way in.
    """

    nav: str
    id: str
    label: str
    file: str = ""
    line: int = 0


@dataclass(slots=True)
class Anomaly:
    """One finding, and what makes it *this* finding rather than another.

    `ident_parts` is what the detector says identifies its finding, and it has no
    default: a detector that does not answer the question cannot construct one. That is
    deliberate, and it is the half of this design that has to survive a second language.
    Detectors are query-driven over the store, so a Kotlin or C++ extractor's facts run
    through the ones here unchanged -- and will bring detectors of their own. A central
    rule that *inferred* identity from `subject` would have to go on being right about
    every one of them; a rule declared beside the detector makes adding one a
    self-contained job.

    Two constraints on the parts, and both were measured rather than reasoned:

    * **No position.** Not a line, and -- for a detector that groups -- not a file
      either. `file` on a grouped finding is `MIN(file)`, an arbitrary tiebreak that
      moves when an unrelated file changes: keyed with it, Mensores' pair loses three of
      its 106 pairings and reports them as removed-and-added. That is `make_id`'s own
      argument one level up, and `changes.py` makes it again for facts.
    * **The parts come from the fact contract**, never from a language's syntax. Every
      detector here already groups by store columns -- `qualname`, `callee_expr`, `tbl`,
      `module` -- which is exactly what `schema.py` guarantees any extractor emits.

    A finding that is about the *whole program* -- `DEAD_CODE`, `UNREACHABLE` -- declares
    `()`, and that empty tuple is a statement rather than an omission: there is one of
    these per program, so the kind alone identifies it. Before this it was an empty
    `subject` that fell out of a default argument, which reads identically and claims
    nothing.
    """

    kind: str
    severity: str
    confidence: str
    title: str
    detail: str
    blind_spot: str
    # What identifies this finding across two versions of one program. Required.
    ident_parts: tuple[str, ...]
    subject: str = ""
    file: str = ""
    line: int = 0
    count: int = 1
    # **The things this finding is about, as a population rather than as prose.**
    #
    # `detail` has always carried them as a semicolon-joined string of names, and that is
    # rule 41 exactly: a prose claim and a machine-readable population are two things, and
    # only one of them can be asked a question. The worklist's two jump buttons sat disabled
    # for want of this, saying so in their tooltips -- honest, and the weakest form of the
    # fix.
    #
    # Never a sample. Rule 8 bounds a diagram, not a reference list, and the whole point is
    # that the list was unreachable.
    occurrences: list[Occurrence] = field(default_factory=list)
    # Why this finding lists nothing, **when it lists nothing**. An empty list and *"this
    # kind cannot be enumerated"* are different answers (design rule 21), and flattening
    # them gives a button that silently does nothing on exactly the findings that most need
    # explaining. `detect` refuses a finding that answers neither.
    unenumerated: str = ""

    @property
    def ident(self) -> str:
        """The identity, derived -- never stored beside the parts it comes from.

        A second copy of an answer is a second thing to keep in step (rule 51), and the
        parts are kept because the pairing is a *claim*: two findings are said to be one,
        and the parts are how a reader or a guard sees why (design rule 13).

        `make_id` joins on `\\x00`, so no part can be spelled to look like a boundary
        between two -- the separator collision `diagram.py` has to assert its way around
        cannot arise here. The `"finding"` prefix is the same namespacing `make_id("ep",
        ...)` and `make_id("site", ...)` already use, so a finding's id can never collide
        with a routine's.
        """
        return make_id("finding", self.kind, *self.ident_parts)


@dataclass(slots=True)
class Report:
    items: list[Anomaly] = field(default_factory=list)
    _seen: dict[str, int] = field(default_factory=dict, repr=False)

    def add(self, a: Anomaly) -> None:
        """Keep the finding, disambiguating a genuine repeat rather than merging it.

        Nine of the detectors group, so their key is unique by construction. Four do not
        -- `PARSE_ERROR` reports one finding per error in a file, and two files can
        legitimately create indexes of the same name -- and for those a key can repeat.
        Left alone, two findings would share an id and the pairing would quietly speak
        about one of them twice.

        So an exact repeat takes an **ordinal among identical keys**, which is the same
        residue `_identity()` gives colliding qualnames and `call_site_id` gives two
        identical expressions in one routine. It is a position of last resort and it is
        stated here rather than hidden: it is stable only while the repeats keep their
        order, which for a stored, ordered query they do.

        Note what this does *not* do: it never invents the key, only breaks a tie in it.
        The detector still says what identifies its finding.
        """
        n = self._seen.get(a.ident, 0)
        self._seen[a.ident] = n + 1
        if n:
            a.ident_parts = (*a.ident_parts, f"#{n + 1}")
        self.items.append(a)

    def sorted(self) -> list[Anomaly]:
        return sorted(
            self.items,
            key=lambda a: (
                _SEVERITY_ORDER.get(a.severity, 9),
                _CONFIDENCE_ORDER.get(a.confidence, 9),
                -a.count,
                a.kind,
            ),
        )

    def counts(self) -> dict[str, int]:
        out = {BROKEN: 0, SUSPECT: 0, INFO: 0}
        for a in self.items:
            out[a.severity] = out.get(a.severity, 0) + 1
        return out

    @property
    def broken(self) -> int:
        return self.counts()[BROKEN]


# --------------------------------------------------------------------------- #
# Detectors. Each is query-driven, so they run against a stored graph without
# re-reading a line of source.
# --------------------------------------------------------------------------- #


def _routine_rows(store: Store, where: str,
                  args: tuple[object, ...] = (), *, scan: bool = False) -> list[Occurrence]:
    """The routines a finding is about, as occurrences the shell can already open.

    One helper rather than the same three lines in six detectors: what a routine occurrence
    *is* -- the `routine` route, the node id, the qualname to print -- is one answer, and
    six copies would drift the day a route is renamed (rule 51).

    `where` is interpolated because every caller passes a literal written in this file; the
    values that come from data are bound.

    `scan` reads the table in its own order for a population that is most of it -- an index
    walk is a random seek per row, which on a large map is the whole cost (BACKLOG 8). A
    selective `where` keeps the index, which is right for it.
    """
    return [
        Occurrence(nav="routine", id=str(x["id"]), label=str(x["qualname"]),
                   file=str(x["file"] or ""), line=int(x["line_start"] or 0))
        for x in store.query(
            f"SELECT id, qualname, file, line_start FROM routines"
            f"{' NOT INDEXED' if scan else ''} {where}"
            " ORDER BY file, line_start, qualname", args)
    ]


def _at_lines(members: list[Occurrence]) -> str:
    """The lines a finding is about, in the order the reader will meet them.

    **Not `GROUP_CONCAT`, which has no defined order.** Both detectors below built this
    string in SQL and then wrote a sentence *about* the order — *"only the last one exists
    at run time"*, *"the later definition shadows the earlier"* — so `(lines 23,18)` was
    not a list that came back rearranged but a **false statement about which definition
    wins**. Found by reversing the rows of a fixture with one name declared twice.

    Built from `members` so the sentence and the occurrences it opens are the same rows in
    the same order (rule 13), which is also why no `ORDER BY` is spelled here: it is
    `_routine_rows`' order, decided in one place.
    """
    return ",".join(str(m.line) for m in members)


def _parse_failures(store: Store, r: Report) -> None:
    for row in store.query("SELECT path, errors FROM files WHERE errors != '[]' ORDER BY path"):
        for err in json.loads(row["errors"]):
            r.add(Anomaly(
                kind="PARSE_ERROR", severity=BROKEN, confidence=CERTAIN,
                title=f"{row['path']} could not be parsed",
                detail=err,
                blind_spot="None. The file is not valid Python for the interpreter "
                           "running DunneFlow; if the program targets an older or "
                           "newer syntax, that is the difference.",
                # One finding per error, so the path alone would merge a file's two
                # failures into one. The message is what tells them apart, and it is
                # what the finding is *about*.
                ident_parts=(row["path"], err),
                subject=row["path"], file=row["path"],
                # A file, and `file` is the code browser's own route.
                occurrences=[Occurrence(nav="file", id=row["path"], label=row["path"],
                                        file=row["path"])],
            ))


# **What a second definition of one name means, asked of the language that wrote it.**
#
# `NAME_COLLISION` and `REDEFINITION` both say *the later definition shadows the earlier*,
# and both were right about every corpus this tool had read — all of which were Python or
# TypeScript, where they are. C++ overloads: a second definition with a different parameter
# list is a different routine, and the first run of the C++ reader turned Unreal's `Core`
# module into **3,875 BROKEN** out of the command a CI job exits non-zero on — `operator<<`
# defined 180 times, which is that language working exactly as intended.
#
# Rule 98 for the third time, and the remedy is `unawaited_async`'s: the language declares
# it, `anomalies.py` names no language, and **empty means the detector does not fire**.
# Asked off `files.lang` per row rather than of the map, because a mixed map holds both
# answers at once and one file's answer is not another's.
_SHADOWS = "shadows"


def _shadowing_langs(store: Store) -> list[str]:
    """The languages in this map where a second definition replaces the first.

    **Asked once and answered in SQL, not once per finding.** Written first as a lookup per
    collision group — `SELECT lang FROM files WHERE path = ?` against `MIN(file)` — which is
    wrong twice over. It is a query per group, and on a tree the size of Unreal's `Runtime`
    that is tens of thousands of them; and `MIN(file)` names *one* of the colliding
    definitions arbitrarily, so in a mixed map the language of one file decided the verdict
    for a group that may hold several.

    Filtering the population instead makes the grouping right as well as the speed: a
    collision is between definitions **in one language**, because that is the only scope in
    which *the later one shadows the earlier* means anything.
    """
    langs = [row["lang"] for row in
             store.query("SELECT DISTINCT lang FROM files WHERE lang != '' ORDER BY lang")]
    return [str(x) for x in langs if load_rules(str(x)).redefinition == _SHADOWS]


def _lang_clause(langs: list[str]) -> tuple[str, tuple[str, ...]]:
    """A `files.lang IN (…)` fragment, or one that matches nothing.

    An empty list has to mean **no rows**, never *no filter*: a map holding only languages
    that overload would otherwise have every one of its definitions judged by a rule none of
    them declared, which is the silent default rule 49 forbids.
    """
    if not langs:
        return "0", ()
    return "f.lang IN (" + ",".join("?" * len(langs)) + ")", tuple(langs)


def _any_called(store: Store, ids: list[str]) -> bool:
    """Whether any call names one of the definitions `ids` -- what *every call resolves to
    it* has to be true of before it is printed (rule 13).

    **Named, not resolved.** A call to a name defined twice is a lost edge: the resolver
    records `ambiguous` and binds nothing, so a test of `callee_id` would find no caller
    for every collision there is. A call in the same file by the bare name is the one the
    redefinition governs, and a resolved one is counted as well.
    """
    marks = ",".join("?" * len(ids))
    if store.query(f"SELECT 1 FROM calls WHERE callee_id IN ({marks}) LIMIT 1", tuple(ids)):
        return True
    # Two indexed lookups per definition rather than one correlated query: an `OR` across
    # `calls` is a scan of every call in the map, once per finding.
    for d in store.query(f"SELECT DISTINCT file, name FROM routines WHERE id IN ({marks})"
                         " ORDER BY file, name", tuple(ids)):
        if store.query("SELECT 1 FROM calls WHERE file = ? AND callee_expr = ? LIMIT 1",
                       (d["file"], d["name"])):
            return True
    return False


def _decision_arms(store: Store, routine_id: str) -> list[tuple[str, int, int, int]]:
    """Every arm of every decision or `try` in one routine, as `(point, arm, first, last)`.

    `control_arms` records an arm's *header* line only, so an arm's body is read as running
    from its header to the line before the next arm's, and the last arm to the end of the
    decision. A decision with no arm rows -- a lone `if` -- is one arm over its whole span.
    """
    out: list[tuple[str, int, int, int]] = []
    for d in store.query(
            "SELECT point_id, line_start, line_end FROM control"
            " WHERE routine_id = ? AND kind IN ('DECISION', 'HANDLER')"
            " ORDER BY line_start, point_id",
            (routine_id,)):
        heads = [int(a["line_start"]) for a in store.query(
            "SELECT line_start FROM control_arms WHERE point_id = ? ORDER BY idx",
            (d["point_id"],))] or [int(d["line_start"])]
        ends = [h - 1 for h in heads[1:]] + [int(d["line_end"])]
        out.extend((str(d["point_id"]), i, h, e)
                   for i, (h, e) in enumerate(zip(heads, ends, strict=True)))
    return out


def _decorated_by_itself(decorators: str, name: str) -> bool:
    """Whether a definition's decorator is written in the definition's own name.

    `@fov.setter` reads the `fov` already bound and hands back something holding both, so
    the earlier definition is used by the later one. It is the same for `@f.register`, and
    the test is the written name, not the word `setter`, so no language's vocabulary is
    needed to ask it.
    """
    return any(str(d).replace("(", ".").split(".", 1)[0] == name
               for d in json.loads(decorators or "[]"))


def _is_rebinding(store: Store, members: list[Occurrence]) -> bool:
    """Whether a group of definitions is one name *rebound*, not a collision.

    Unreal's `TraceLog/create_standalone.py` defines `predicate` inside `_main_trace`,
    passes it to `_collect_source`, and then -- under `if analysis:` -- defines a second
    `predicate` and passes that. It was the one BROKEN finding in all of `Runtime`, and
    the program has no defect. OpenUSD then gave 89 at BROKEN, of which 87 were false: 82
    a `@property` with its `@x.setter`, and 5 a function defined on each arm of a
    module-level `if`, where only one ever runs. Any of these makes *only the last one
    exists at run time* false, so each consecutive pair must show one of them:

    - **decorated by itself** -- the later definition's decorator is written in the name
      being defined, so the earlier one is what it is built from. Any scope;
    - **an arm apart** -- one definition sits in an arm of a decision or a `try` that the
      other does not, so they are alternatives. Any scope: a module's and a class body's
      decisions belong to the file's `<module>` routine; or
    - **used between** -- the name is called, or passed as an argument, by the enclosing
      routine on a line between the end of one definition and the start of the next.
      Nested definitions only: at module or class scope the later one really does replace
      the earlier for every caller, which is the finding.
    """
    if len(members) < 2:
        return False
    rows = store.query(
        "SELECT id, name, qualname, file, line_start, line_end, is_nested, decorators"
        f" FROM routines WHERE id IN ({','.join('?' * len(members))})"
        " ORDER BY line_start, id", tuple(m.id for m in members))
    if len({x["file"] for x in rows}) != 1:
        return False
    nested = all(x["is_nested"] for x in rows)
    if nested:
        enclosing = store.query(
            "SELECT id FROM routines WHERE file = ? AND qualname = ?"
            " AND line_start <= ? AND line_end >= ? ORDER BY line_start DESC, id LIMIT 1",
            (rows[0]["file"], str(rows[0]["qualname"]).rsplit(".", 1)[0],
             rows[0]["line_start"], rows[-1]["line_end"]))
    else:
        enclosing = store.query(
            "SELECT id FROM routines WHERE file = ? AND name = '<module>' LIMIT 1",
            (rows[0]["file"],))
    outer = str(enclosing[0]["id"]) if enclosing else ""
    arms = _decision_arms(store, outer) if outer else []
    name = str(rows[0]["name"])

    def where(line: int) -> frozenset[tuple[str, int]]:
        return frozenset((p, i) for p, i, first, last in arms if first <= line <= last)

    for a, b in zip(rows, rows[1:], strict=False):
        if _decorated_by_itself(str(b["decorators"]), name):
            continue
        if outer and where(int(a["line_start"])) != where(int(b["line_start"])):
            continue
        if nested and outer and store.query(
                "SELECT 1 FROM calls c LEFT JOIN call_args ca ON ca.site_id = c.site_id"
                " WHERE c.caller_id = ? AND c.line > ? AND c.line < ?"
                "   AND (c.callee_expr = ? OR ca.expr = ?) LIMIT 1",
                (outer, a["line_end"], b["line_start"], name, name)):
            continue
        return False
    return True


def _name_collisions(store: Store, r: Report) -> None:
    where, params = _lang_clause(_shadowing_langs(store))
    for row in store.query(
        "SELECT r.qualname AS qualname, f.lang AS lang, COUNT(*) n, MIN(r.file) f"
        "  FROM routines r JOIN files f ON r.file = f.path"
        f" WHERE r.name != '<module>' AND {where}"
        " GROUP BY f.lang, r.qualname HAVING n > 1 ORDER BY n DESC, f.lang, r.qualname",
        params,
    ):
        # **Every definition that collides, not the group.** The finding is that several
        # things share one name, so a single occurrence would name one arbitrarily -- the
        # same reason `MIN(file)` is kept out of the key just below.
        members = _routine_rows(
            store, "WHERE name != '<module>' AND qualname = ? AND lang = ?",
            (row["qualname"], row["lang"]))
        if _is_rebinding(store, members):
            continue
        called = _any_called(store, [m.id for m in members])
        detail = (f"`{row['qualname']}` is defined {row['n']} times "
                  f"(lines {_at_lines(members)}). Only the last one exists at run time")
        detail += ("; every call resolves to it and the others are unreachable." if called
                   else ", and the others are unreachable. No call in the map resolves to "
                        "any of them.")
        r.add(Anomaly(
            kind="NAME_COLLISION", severity=BROKEN, confidence=CERTAIN,
            title=f"`{row['qualname']}` is defined {row['n']} times",
            detail=detail,
            blind_spot="If these are nested functions in different enclosing scopes "
                       "they are distinct and this is a naming defect in DunneFlow, "
                       "not in the program. Check whether the definitions sit inside "
                       "different functions. A name rebound -- decorated in its own "
                       "name, defined on different arms of a decision or a `try`, or "
                       "nested and used before it is defined again -- is already left "
                       "out; one used only through something this map does not record as "
                       "a call or an argument is not.",
            # Grouped by language and qualname, so the pair is the key -- unique by
            # construction. `f` is MIN(file) and is deliberately not here: it names one of
            # the colliding definitions arbitrarily, and which one it names can move.
            ident_parts=(str(row["lang"]), row["qualname"]),
            subject=row["qualname"], file=row["f"], count=row["n"],
            occurrences=members,
        ))


def _redefinitions(store: Store, r: Report) -> None:
    where, params = _lang_clause(_shadowing_langs(store))
    for row in store.query(
        "SELECT r.module AS module, r.name AS name, f.lang AS lang, COUNT(*) n,"
        "       MIN(r.file) f"
        "  FROM routines r JOIN files f ON r.file = f.path"
        f" WHERE r.name != '<module>' AND r.is_nested = 0 AND r.is_method = 0 AND {where}"
        " GROUP BY f.lang, r.module, r.name HAVING n > 1"
        " ORDER BY n DESC, f.lang, r.module, r.name",
        params,
    ):
        members = _routine_rows(
            store,
            "WHERE name != '<module>' AND is_nested = 0 AND is_method = 0"
            "  AND module = ? AND name = ? AND lang = ?",
            (row["module"], row["name"], row["lang"]))
        if _is_rebinding(store, members):
            continue
        r.add(Anomaly(
            kind="REDEFINITION", severity=SUSPECT, confidence=CERTAIN,
            title=f"`{row['name']}` is defined {row['n']} times in one module",
            detail=f"`{row['name']}` is defined {row['n']} times in `{row['module']}` "
                   f"(lines {_at_lines(members)}). The later definition shadows the earlier.",
            blind_spot="Definitions on different arms of a decision or a `try` are "
                       "already left out. One made conditional some other way, such as "
                       "an early return or a loop, is not, and only one of them may ever "
                       "be live.",
            # The GROUP BY key, all three parts of it: the same name in two modules is
            # two findings, and joining them into one string would be a key that cannot
            # say which part is which.
            ident_parts=(str(row["lang"]), row["module"], row["name"]),
            subject=f"{row['module']}.{row['name']}", file=row["f"], count=row["n"],
            occurrences=members,
        ))


def _lost_edges(store: Store, r: Report) -> None:
    """Calls that meant something local but could not be pinned to one definition."""
    # **Two causes, one finding, two sentences** (Tom, 2026-11-02). A name several routines
    # share is Python's case and the sentence below was written for it. A call the reader
    # marked `dynamic` is dispatch: the checker resolved it, to a slot that several bodies
    # fill, which is the language working rather than a collision. The edge is still not
    # drawn, so the finding stands -- what changes is that it says which of the two it is,
    # off `calls.reason` and never off a language's name. The Java reader's first real tree
    # (traccar) gave 22 of these, every one dispatch, under the collision sentence.
    rows = store.query(
        "SELECT callee_expr, MAX(ambiguous) rivals, COUNT(*) n, MIN(file) f,"
        "       SUM(reason = 'dynamic') dispatched"
        "  FROM calls"
        " WHERE ambiguous > 1"
        "   AND (callee_expr NOT LIKE '%.%' OR callee_expr LIKE 'self.%'"
        "        OR callee_expr LIKE 'cls.%')"
        " GROUP BY callee_expr ORDER BY n DESC, callee_expr"
    )
    # **Every group's call sites in one read**, not one query per group. There is no index
    # on `callee_expr`, so the per-group query walked all of `calls` each time: on Unreal's
    # Runtime, 1,465 groups over 972,536 calls, 0.13-3.7 s apiece, which is most of the
    # 2,416 s the anomaly phase took there. One ordered scan, grouped here, in the order
    # each group was read in before -- file, then line -- with the caller as the tiebreak
    # that order never had (rule 66).
    sites: dict[str, list[sqlite3.Row]] = {}
    for x in store.query(
            "SELECT c.callee_expr, c.file, c.line, r.qualname AS caller FROM calls c"
            "  LEFT JOIN routines r ON r.id = c.caller_id"
            " WHERE c.ambiguous > 1"
            " ORDER BY c.callee_expr, c.file, c.line, r.qualname"):
        sites.setdefault(x["callee_expr"], []).append(x)
    for row in rows:
        dispatch = row["dispatched"] == row["n"]
        if dispatch:
            title = (f"`{row['callee_expr']}` is dispatched to one of "
                     f"{row['rivals']} implementations, and none is drawn")
            detail = (f"`{row['callee_expr']}` is called {plural(row['n'], 'time')}. The "
                      f"reader resolved it to a method that {row['rivals']} definitions in "
                      f"this tree can answer, and which one runs is decided by the object "
                      f"at run time. The call graph has no edge here, so anything "
                      f"downstream is missing from every flow that passes through it.")
            blind = ("Dispatch is ordinary: a template method calling its own abstract "
                     "step, or an interface with several implementations, is the design "
                     "working, and nothing is wrong with the program. The finding is what "
                     "the map cannot follow, not what the code does.")
        else:
            title = (f"`{row['callee_expr']}` could not be connected: "
                     f"{row['rivals']} definitions share the name")
            detail = (f"`{row['callee_expr']}` is called {plural(row['n'], 'time')}, and "
                      f"{row['rivals']} routines share that name. The call graph has no "
                      f"edge here, so anything downstream is missing from every flow "
                      f"that passes through it.")
            blind = ("If the receiver is a third-party object, or the method is "
                     "supplied by a mixin or set dynamically, no local definition "
                     "was ever intended and nothing is wrong.")
        r.add(Anomaly(
            kind="LOST_EDGE", severity=SUSPECT, confidence=PROBABLE,
            title=title,
            detail=detail,
            blind_spot=blind,
            # The expression that could not be pinned. **Not** the rivals and not the
            # callers: both are what the finding *reports*, and both move while the
            # finding stays the same one -- 93 of Mensores' 106 findings are this kind,
            # so keying on either would report most of the program as churn.
            ident_parts=(row["callee_expr"],),
            subject=row["callee_expr"], file=row["f"], count=row["n"],
            # **The call sites, never the rivals.** The callee not resolving *is* the
            # finding, so there is no callee node to open -- but every call is written
            # somewhere, and that is what a reader wants to look at. Opening a rival would
            # be the guess rule 5 forbids, dressed as a destination.
            occurrences=[
                Occurrence(nav="file", id=str(x["file"]),
                           label=f"{x['caller']} \u2192 {row['callee_expr']}",
                           file=str(x["file"]), line=int(x["line"] or 0))
                for x in sites.get(row["callee_expr"], [])
            ],
        ))


def _dead_code(store: Store, r: Report, include_tests: bool) -> None:
    # `NOT INDEXED`: every routine is read, so the table is read in its own order and sorted
    # in memory. Through the index each row was a random seek, and on a 262,879-routine map
    # on the external volume that is minutes rather than seconds (BACKLOG 8).
    rows = store.query(
        "SELECT id, qualname, file, line_start FROM routines NOT INDEXED"
        " WHERE name != '<module>' AND is_method = 0 AND is_nested = 0"
        "   AND body_by = ''"
        "   AND name NOT LIKE '\\_\\_%' ESCAPE '\\'"
        "   AND id NOT IN (SELECT callee_id FROM calls WHERE callee_id IS NOT NULL)"
        "   AND id NOT IN (SELECT routine_id FROM entrypoints"
        "                   WHERE routine_id IS NOT NULL)"
        # **A routine named as a value is used**, whoever calls it: tmux's callbacks are
        # handed to `event_set` and stored in command tables, and 714 of its routines read
        # as dead code until its reader could say so (`SuppliedUse`).
        "   AND NOT EXISTS (SELECT 1 FROM value_uses u WHERE u.file = routines.file"
        "                   AND u.line = routines.line_start AND u.name = routines.name)"
        " ORDER BY qualname, file, line_start"
    )
    # **A routine a macro's body wrote is out of this finding, and counted.** `RB_GENERATE`
    # writes every operation on a tree and tmux uses some: an unused one is what instantiating
    # that macro means, and nobody decided to leave it there. Rule 98: this detector was
    # written against routines somebody typed.
    written = store.query(
        "SELECT COUNT(*) n FROM routines NOT INDEXED WHERE body_by <> ''"
        " AND is_method = 0 AND is_nested = 0 AND name != '<module>'")[0]["n"]
    # **A call the reader could not type may be a call to this routine**, and the map has
    # no way to say it is not (Tom, 2026-11-02). A checker that is missing a dependency
    # cannot choose an overload once one argument's type is unknown, so traccar's
    # `BufferUtil.indexOf(…, buf)` -- `buf` a Netty `ByteBuf`, Netty not on the machine --
    # is `untyped`, and `indexOf` read as never called. So a routine whose name is the last
    # segment of any untyped call is left out: the finding loses a routine it could not
    # stand behind, and nothing gains an edge it was never given (rule 1, rule 49).
    untyped = {
        str(x["callee_expr"]).rsplit(".", 1)[-1]
        for x in store.query("SELECT DISTINCT callee_expr FROM calls WHERE reason = 'untyped'")
    }
    spared = 0
    if untyped:
        kept = [x for x in rows if str(x["qualname"]).rsplit(".", 1)[-1] not in untyped]
        spared = len(rows) - len(kept)
        rows = kept
    if not rows:
        return
    scope = (
        "Tests were included in this scan."
        if include_tests
        else "**Tests were excluded from this scan**, so a routine used only by tests "
             "appears here. Re-run with `--include-tests` to remove those."
    )
    r.add(Anomaly(
        kind="DEAD_CODE", severity=INFO, confidence=POSSIBLE,
        title=f"{plural(len(rows), 'routine')} {are(len(rows))} never called and "
              f"{'is' if len(rows) == 1 else 'are'} not a way in",
        detail="; ".join(x["qualname"] for x in rows),
        blind_spot=f"{scope} Routines reached by name (plugin registries, "
                   f"`getattr`, entry-point groups) also appear here, because no "
                   f"static analysis can see those calls. A routine passed or stored as "
                   f"a value is left out where its reader reports such uses; where it "
                   f"does not, a callback appears here too."
                   + (f" {plural(spared, 'routine')} {are(spared)} left out because a "
                      f"call the reader could not type uses the name, and may be a call "
                      f"to it." if spared else "")
                   + (f" {plural(written, 'routine')} a macro wrote {are(written)} left out: "
                      f"a macro writes what it writes whether or not all of it is used."
                      if written else ""),
        # One per program: this is a finding *about the program*, not about any of the
        # routines it lists. `file` and `line` point at the first of them so the row is
        # clickable, and neither may enter the key -- which routine sorts first is not
        # part of what this finding is.
        ident_parts=(),
        subject="", file=rows[0]["file"], line=rows[0]["line_start"], count=len(rows),
        # The rows the title counts and `detail` names in prose, as a population -- the
        # same query, so the number and the list cannot disagree (rule 13).
        occurrences=[
            Occurrence(nav="routine", id=str(x["id"]), label=str(x["qualname"]),
                       file=str(x["file"] or ""), line=int(x["line_start"] or 0))
            for x in rows
        ],
    ))


def _module_scopes(store: Store) -> set[str]:
    return {str(x["id"]) for x in store.query("SELECT id FROM routines WHERE name = '<module>'")}


def _unreachable(store: Store, r: Report) -> None:
    ways_in = [
        row["routine_id"]
        for row in store.query(
            "SELECT DISTINCT routine_id FROM entrypoints WHERE routine_id IS NOT NULL"
            " UNION SELECT routine_id FROM entrypoint_roots"
            " ORDER BY routine_id"
        )
    ]
    if not ways_in:
        return
    # Through macros too: whether a routine can run at all is not a question about flows, and
    # one only a macro calls runs. A routine a macro wrote is out of the count and said to be
    # (rule 32), for `_dead_code`'s reason.
    reached = store.reachable_through_macros(ways_in)
    total = store.query(
        "SELECT COUNT(*) n FROM routines WHERE name != '<module>' AND body_by = ''"
    )[0]["n"]
    written_ids = {
        str(x["id"]) for x in store.query(
            "SELECT id FROM routines NOT INDEXED WHERE name != '<module>' AND body_by <> ''")
    }
    stranded = total - len({str(r_) for r_ in reached} - written_ids - _module_scopes(store))
    if stranded <= 0:
        return
    # **The stranded routines themselves.** The count was a subtraction and nothing named
    # the rows it stood for, so the finding said *N of M* and a reader could reach none of
    # them. The complement of the reached set is the answer this already had in hand.
    # The reached set built **once**. It was a comprehension inside the filter, so every
    # routine rebuilt the whole set to ask one membership question: on Unreal's Runtime
    # part, 262,879 rebuilds, and 176 s of the cover's 660 (BACKLOG 8).
    reached_ids = {str(v) for v in reached}
    strand_rows = [
        Occurrence(nav="routine", id=str(x["id"]), label=str(x["qualname"]),
                   file=str(x["file"] or ""), line=int(x["line_start"] or 0))
        for x in store.query(
            "SELECT id, qualname, file, line_start FROM routines NOT INDEXED"
            " WHERE name != '<module>' AND body_by = '' ORDER BY file, line_start, qualname")
        if str(x["id"]) not in reached_ids
    ]
    r.add(Anomaly(
        kind="UNREACHABLE", severity=INFO, confidence=POSSIBLE,
        title=f"{stranded:,} of {plural(total, 'routine')} {are(stranded)} not reachable "
              f"from any way in",
        detail="These cannot run when the program is started by any entrypoint "
               "DunneFlow found."
               # Said where it is true, so a figure that crossed dispatch is never read as
               # one that stopped at it (rule 32; `resolve/dispatch.py`).
               + (" Reach followed every dispatched call into each body that may answer "
                  "it." if store.dispatch_of_map() else "")
               + (f" {plural(len(written_ids), 'routine')} a macro wrote {are(len(written_ids))}"
                  f" not counted either way." if written_ids else ""),
        blind_spot="An edge lost to ambiguity strands everything behind it, so "
                   "LOST_EDGE findings inflate this number. Library code meant to be "
                   "imported by other programs is also unreachable by design.",
        ident_parts=(),  # one per program
        count=stranded,
        occurrences=strand_rows,
    ))


def _schema_drift(store: Store, r: Report) -> None:
    for row in store.query(
        "SELECT name, COUNT(DISTINCT file || ':' || line) defs FROM db_tables"
        " GROUP BY name HAVING defs > 1 ORDER BY name"
    ):
        shapes = store.query(
            "SELECT file, COUNT(*) n FROM db_columns WHERE tbl = ? GROUP BY file",
            (row["name"],),
        )
        widths = sorted({s["n"] for s in shapes})
        if len(widths) <= 1:
            continue
        r.add(Anomaly(
            kind="SCHEMA_DRIFT", severity=SUSPECT, confidence=PROBABLE,
            title=f"`{row['name']}` is created with {len(widths)} different shapes",
            detail=f"`{row['name']}` has {row['defs']} CREATE statements with column "
                   f"counts {widths}. Which shape exists depends on which code path "
                   f"created the database.",
            blind_spot="Migrations legitimately create the same table at different "
                       "versions; check whether these statements belong to different "
                       "migration steps.",
            # Grouped by the table's name. The shapes and the statement count are
            # what the finding says about it, and both move while it stays one finding.
            ident_parts=(row["name"],),
            subject=row["name"], count=row["defs"],
            # The table first -- `t` is the route the whole shell uses for one -- then each
            # statement that creates it, because *which* shapes disagree is the question a
            # reader opens this to answer.
            occurrences=[
                Occurrence(nav="t", id=str(row["name"]), label=str(row["name"])),
                *[Occurrence(nav="file", id=str(x["file"]),
                             label=f"{row['name']} \u2014 {x['n']} columns here",
                             file=str(x["file"]))
                  for x in shapes],
            ],
        ))


def _one_way_tables(store: Store, r: Report) -> None:
    for row in store.query(
        "SELECT tbl, SUM(direction='READ') rd, SUM(direction='WRITE') wr"
        "  FROM sql_ops WHERE tbl != '' GROUP BY tbl"
        " HAVING (rd = 0 AND wr > 0) OR (wr = 0 AND rd > 0)"
        " ORDER BY (rd + wr) DESC, tbl"
    ):
        write_only = row["rd"] == 0
        r.add(Anomaly(
            kind="ONE_WAY_TABLE", severity=INFO, confidence=POSSIBLE,
            title=(f"`{row['tbl']}` is written but never read back" if write_only
                   else f"`{row['tbl']}` is read but never written"),
            detail=f"`{row['tbl']}`: {row['rd']} reads, {row['wr']} writes.",
            blind_spot="The other half may live in another program, in tests, in a "
                       "migration, or in SQL built by string interpolation that "
                       "DunneFlow could not attribute to a table.",
            # Grouped by the table. Note what is *not* in the key: which way it is
            # one-way. A table that gains its first read stops being this finding
            # rather than becoming a different one, and that is the honest reading --
            # the finding is about the table, and it went.
            ident_parts=(row["tbl"],),
            subject=row["tbl"], count=row["rd"] + row["wr"],
            # The table, then the routines that touch it -- which is what a reader is
            # really after: *who writes this and never reads it back*.
            occurrences=[
                Occurrence(nav="t", id=str(row["tbl"]), label=str(row["tbl"])),
                *[Occurrence(nav="routine", id=str(x["id"]), label=str(x["qualname"]),
                             file=str(x["file"] or ""), line=int(x["line_start"] or 0))
                  for x in store.query(
                      "SELECT DISTINCT r.id, r.qualname, r.file, r.line_start"
                      "  FROM sql_ops o JOIN routines r ON r.id = o.routine_id"
                      " WHERE o.tbl = ? ORDER BY r.file, r.line_start, r.qualname", (row["tbl"],))],
            ],
        ))


def _orphan_indexes(store: Store, r: Report) -> None:
    for row in store.query(
        "SELECT name, tbl, file, line FROM db_indexes"
        " WHERE tbl NOT IN (SELECT name FROM db_tables) ORDER BY tbl, name, file, line"
    ):
        r.add(Anomaly(
            kind="ORPHAN_INDEX", severity=SUSPECT, confidence=PROBABLE,
            title=f"`{row['name']}` indexes `{row['tbl']}`, which is never created here",
            detail=f"`{row['name']}` indexes `{row['tbl']}`, which has no CREATE "
                   f"TABLE anywhere in this program.",
            blind_spot="The table may be created by a migration tool, by another "
                       "program sharing the database, or by SQL loaded from a file.",
            # Not grouped, so the key is what names this index and the table it
            # claims. `file` stays out even here: an index moved between files is the
            # same orphan, and `line` is a position in any case. Two indexes of one
            # name over one table take the ordinal `Report.add` gives a genuine repeat.
            ident_parts=(row["name"], row["tbl"]),
            subject=row["name"], file=row["file"], line=row["line"],
            # An index is not a subject this shell selects, and inventing a route for one
            # would be a link to nothing. It has a definition site, and that is a real
            # place to be taken -- the file, at the line the CREATE INDEX is written.
            occurrences=[Occurrence(nav="file", id=str(row["file"]),
                                    label=f"CREATE INDEX {row['name']}",
                                    file=str(row["file"]), line=int(row["line"] or 0))],
        ))


def _remote_call_hazards(store: Store, r: Report) -> None:
    total = store.query("SELECT COUNT(*) n FROM net_calls")[0]["n"]
    if not total:
        return
    no_timeout = store.query(
        "SELECT r.id AS rid, r.qualname, n.expr, n.protocol, r.file, n.line"
        "  FROM net_calls n"
        " JOIN routines r ON n.routine_id = r.id WHERE n.timeout = ''"
        " ORDER BY r.file, n.line, r.qualname, n.expr"
    )
    if no_timeout:
        r.add(Anomaly(
            kind="NO_TIMEOUT", severity=SUSPECT, confidence=PROBABLE,
            title=f"{len(no_timeout)} of {total} remote calls set no timeout",
            detail="; ".join(f"{x['qualname']} ({x['protocol']})" for x in no_timeout),
            blind_spot="A timeout may be set on the client object rather than the "
                       "call, or globally by the library's configuration. Check the "
                       "client construction before treating any one of these as a bug.",
            ident_parts=(),  # one per program: it counts the calls, it is not one
            count=len(no_timeout),
            file=no_timeout[0]["file"], line=no_timeout[0]["line"],
            # The routines making the calls, which is what `detail` already names in prose
            # -- the same rows, so the count and the list cannot disagree.
            occurrences=[
                Occurrence(nav="routine", id=str(x["rid"]), label=str(x["qualname"]),
                           file=str(x["file"] or ""), line=int(x["line"] or 0))
                for x in no_timeout
            ],
        ))

    no_retry = store.query("SELECT COUNT(*) n FROM net_calls WHERE retries = ''")[0]["n"]
    if no_retry == total and total > 2:
        r.add(Anomaly(
            kind="NO_RETRY", severity=INFO, confidence=PROBABLE,
            title=f"None of the {total} remote calls declares a retry policy",
            detail="A single transient failure propagates to the caller.",
            blind_spot="Retries are often handled by a transport adapter, a service "
                       "mesh, or the caller rather than at the call site.",
            ident_parts=(),  # one per program
            count=total,
            # Every remote call, because the finding is that *none* of them retries -- the
            # population is the whole of `net_calls` and naming one would be arbitrary.
            occurrences=[
                Occurrence(nav="routine", id=str(x["rid"]), label=str(x["qualname"]),
                           file=str(x["file"] or ""), line=int(x["line"] or 0))
                for x in store.query(
                    "SELECT r.id AS rid, r.qualname, r.file, n.line FROM net_calls n"
                    "  JOIN routines r ON n.routine_id = r.id"
                    " ORDER BY r.file, n.line, r.qualname, n.protocol")
            ],
        ))

    # **The language decides what a discarded async call costs, and it is asked per row.**
    # This said *"The coroutine is created and never run"* at BROKEN of every language,
    # which is true of Python and false of JavaScript -- a promise runs whether or not
    # anybody holds it. Put to gstack it produced two BROKEN out of the command that gates
    # CI on BROKEN, one of them three lines under the comment *"No await; this is
    # fire-and-forget"* and ending in `.catch(() => {})`. Rule 98: a judgement unchanged
    # for a year, handed a population it had never been shown.
    #
    # `files.lang` rather than the map's languages, because this is a claim about one call
    # site in one file and a mixed map holds both answers at once. Nothing here names a
    # language: `unawaited_async` is declared in each reader's own rules file, so a third
    # language answers for itself on the day it is registered (rule 92).
    unawaited = store.query(
        "SELECT r.id AS rid, r.qualname, n.expr, r.file, n.line, f.lang AS lang"
        "  FROM net_calls n"
        " JOIN routines r ON n.routine_id = r.id"
        " JOIN files f ON n.file = f.path"
        " WHERE n.is_async = 1 AND n.awaited = 0"
        " ORDER BY r.file, n.line, r.qualname, n.expr"
    )
    for x in unawaited:
        # **Empty means the detector does not fire**, and that is refusing to guess rather
        # than an omission (rule 49). A severity is a claim about what dropping this call
        # costs; a language nobody has answered that question for gets no claim made on
        # its behalf, least of all in the one command a CI job trusts.
        said = _ASYNC_COST.get(load_rules(str(x["lang"])).unawaited_async)
        if said is None:
            continue
        r.add(Anomaly(
            kind="ASYNC_NOT_AWAITED", severity=said.severity, confidence=PROBABLE,
            title=f"`{x['expr']}` in `{x['qualname']}` is {said.title}",
            detail=f"`{x['qualname']}` calls `{x['expr']}` without awaiting it. "
                   + said.detail,
            blind_spot=said.blind_spot,
            # The routine and the expression it never awaits. Two identical
            # expressions in one routine are two of these, and they take the ordinal --
            # the same residue `call_site_id` carries, for the same reason.
            ident_parts=(x["qualname"], x["expr"]),
            subject=x["qualname"], file=x["file"], line=x["line"],
            # One call, one occurrence -- the routine that makes it.
            occurrences=[Occurrence(nav="routine", id=str(x["rid"]),
                                    label=str(x["qualname"]), file=str(x["file"] or ""),
                                    line=int(x["line"] or 0))],
        ))


# What "reaches out of the program" means for a loop. Database, queue and network -- the
# things whose cost is per call rather than per instruction. `FILE`, `STDIO`, `ENV` and
# `PROCESS` are deliberately out: a loop that writes a line per row is what writing a file
# *is*, and reporting it would put most of the program on a worklist.
_REACHES_OUT = ("DATABASE", "QUEUE", "NETWORK")

# Every loop that reaches one of those on **every pass**, with what its bound looks like.
#
# **Three tables unioned to places, not one table asked.** `boundaries` alone misses two of
# Society's 74 -- `for col in _SPEC_COLUMNS: ... ALTER TABLE Spec` is a `sql_ops` row that
# the boundary detector did not also record -- and a finding whose title counts database
# work has to count all of it (rule 13). The `UNION` deduplicates the line, which is
# exactly what `resolve/shape.places` does, so an `INSERT` recorded as a `DATABASE` row
# *and* a `SQL` row on one line is one act here as it is everywhere else (rule 40).
#
# `control.once_start`/`once_end` are the lines the loop evaluates once, so the iterable of
# `for row in conn.execute(q).fetchall():` is excluded here exactly as it is in
# `resolve/shape.py` -- 9 of those 74 are that shape, and reporting them would be
# reporting one query as a query per row.
#
# `k.name` is the loop's header matched against a constant **declared in the same module**.
# Not a bare name match across the program (rule 5): a module-scoped name is exact, and
# what it buys is the difference between a bound nobody can read and `for stmt in INDEXES:`.
_LOOPED_OUT = """
WITH reaches AS (
    SELECT routine_id, line FROM boundaries
     WHERE kind IN (?, ?, ?) AND routine_id IS NOT NULL AND line IS NOT NULL
    UNION
    SELECT routine_id, line FROM sql_ops
     WHERE routine_id IS NOT NULL AND line IS NOT NULL
    UNION
    SELECT routine_id, line FROM net_calls
     WHERE routine_id IS NOT NULL AND line IS NOT NULL)
SELECT c.point_id, c.word, c.header, c.file, c.line_start,
       r.id AS rid, r.qualname, r.module,
       COUNT(DISTINCT x.line) AS places,
       COALESCE(k.value, '') AS bound
  FROM control c
  JOIN routines r ON r.id = c.routine_id
  JOIN reaches x ON x.routine_id = c.routine_id
                AND x.line BETWEEN c.line_start AND c.line_end
                AND NOT (c.once_start > 0
                         AND x.line BETWEEN c.once_start AND c.once_end)
  LEFT JOIN constants k ON k.module = r.module AND k.name = c.header
 WHERE c.kind IN ('LOOP', 'COMPREHENSION')
 GROUP BY c.point_id
 ORDER BY c.file, c.line_start, c.point_id
"""


def _bounded(row: sqlite3.Row) -> str:
    """Why this loop's bound is readable, or "" where nothing static can count it.

    Three shapes, and the point of naming them is that they are the ones a reader can
    already answer for themselves. A `while` is a poll or a retry and is that shape on
    purpose; a literal written at the loop and a collection the module declares both say
    how many passes there are, on the line above.

    What is left is the population this finding is about: an argument, a query's rows, a
    directory listing -- a number that exists only at run time.
    """
    if row["word"] == "while":
        return "a while loop, which is a poll or a retry and is this shape on purpose"
    header = str(row["header"] or "").lstrip()
    if header[:1] in ("(", "[", "{"):
        return "a collection written at the loop, so its size is on the line"
    if str(row["bound"] or "").lstrip()[:1] in ("(", "[", "{"):
        return "a collection this program declares, so its size can be read"
    return ""


def _looped_boundaries(store: Store, r: Report) -> None:
    """A database, queue or network call written inside a loop.

    **The measurement chose the shape of this, and it is worth saying how.** Read as
    `net_calls` alone it fires twice on Society, and both are `wait_until_serving` --
    `while True:` poll loops with a deadline, which is the second blind spot below. Two of
    two findings would have been false alarms, which is what `CLAUDE.md` means by
    verifying a detector's findings against real source before shipping it.

    Widened to the database it is real: 74 loops, of which 39 have a bound a reader can
    read off the page. Those 39 are **named and not reported** (design rule 1) -- it is
    the 39 that make the 35 credible, exactly as the 1,222 still loops make the 261 rates.

    One finding for the program, on `NO_TIMEOUT`'s model: this is one thing to think about
    and 35 places to look at it, and the count comes off the same list the occurrences do
    so the two cannot disagree (rule 13).
    """
    rows = store.query(_LOOPED_OUT, _REACHES_OUT)
    if not rows:
        return
    reported = [x for x in rows if not _bounded(x)]
    if not reported:
        return

    named: dict[str, int] = {}
    for x in rows:
        why = _bounded(x)
        if why:
            named[why] = named.get(why, 0) + 1
    aside = "; ".join(f"{n} over {why}" for why, n in sorted(named.items()))

    r.add(Anomaly(
        kind="LOOPED_BOUNDARY", severity=INFO, confidence=PROBABLE,
        # **Loops and places are different numbers, and both are said** (rule 32). The
        # loops answer *how many times could this run in a pass*; the places answer *how
        # many acts are in there*, and one figure would be whichever the reader assumed.
        # `places` is the query's own `COUNT(DISTINCT line)`, which is
        # `resolve/shape.places` in SQL for the reason that function exists.
        title=f"{plural(len(reported), 'loop')} "
              f"{'reaches' if len(reported) == 1 else 'reach'} a database, a queue or the "
              f"network on every pass — "
              f"{plural(sum(int(x['places']) for x in reported), 'place')} in all",
        detail=(
            "; ".join(f"{x['qualname']} ({x['file']}:{x['line_start']})"
                      for x in reported)
            + (f". Not counted here: {aside} — the loop says how many passes it makes."
               if aside else "")
        ),
        blind_spot=(
            "The thing being looped over may hold one item, and nothing static can "
            "count it — that is why a loop whose bound is written down is named "
            "above rather than reported. A retry or poll loop is this shape on "
            "purpose and is excluded on its `while`. And a local database file is "
            "not a network: DunneFlow reads the call, not what is at the other end "
            "of it, so a SQLite store and a remote one look identical here."
        ),
        # One per program: it counts the loops, it is not one of them. The same
        # positionless key `NO_TIMEOUT` and `NO_RETRY` declare.
        ident_parts=(),
        count=len(reported),
        file=str(reported[0]["file"]), line=int(reported[0]["line_start"] or 0),
        # **The routine, not the span.** There is no `NAV_ROUTES` entry for a control
        # point, and `web/shape.py:_row` answers the same question the same way: a span
        # is not a node in the graph, and minting an id to make a row clickable would be
        # a link to nothing. The line is the loop's, so the reader lands on it.
        occurrences=[
            Occurrence(nav="routine", id=str(x["rid"]), label=str(x["qualname"]),
                       file=str(x["file"] or ""), line=int(x["line_start"] or 0))
            for x in reported
        ],
    ))


def _messaging_hazards(store: Store, r: Report) -> None:
    producers = store.query(
        "SELECT COUNT(*) n FROM boundaries WHERE kind = 'QUEUE' AND direction = 'OUT'"
    )[0]["n"]
    consumers = store.query(
        "SELECT COUNT(*) n FROM boundaries WHERE kind = 'QUEUE' AND direction = 'IN'"
    )[0]["n"]
    if producers and not consumers:
        r.add(Anomaly(
            kind="PRODUCERS_WITHOUT_CONSUMERS", severity=INFO, confidence=POSSIBLE,
            title=f"{producers} queue producers and no consumer in this program",
            detail="Messages are published but nothing here reads them.",
            blind_spot="The consumer is very often a separate program or service, "
                       "which is the normal shape for messaging.",
            ident_parts=(),  # one per program
            count=producers,
            # The publishing sites. A queue producer's identity is its target and its file,
            # so the honest way in is the code that publishes.
            occurrences=[
                Occurrence(nav="file", id=str(x["file"]),
                           label=f"publishes to {x['target'] or 'a queue'}",
                           file=str(x["file"]), line=int(x["line"] or 0))
                for x in store.query(
                    "SELECT target, file, line FROM boundaries"
                    " WHERE kind = 'QUEUE' AND direction = 'OUT' ORDER BY file, line, target")
            ],
        ))


def _entrypoint_problems(store: Store, r: Report) -> None:
    for row in store.query(
        "SELECT id, kind, name, module, evidence, file, declared FROM entrypoints"
        " WHERE routine_id IS NULL AND parent_id IS NULL ORDER BY name, module, id"
    ):
        # **A known limit is not a suspicion.** A manifest may declare a way in whose
        # target this build has no reader for at all -- DunneNote's three Rust binaries,
        # uigen's generated `index.js` -- and every one of them is a real way into that
        # application. Reporting them SUSPECT would be chunk 11's 83 false BROKENs one
        # surface over: a finding about DunneFlow's reach, filed against somebody else's
        # program. What the map says instead is *declared and not bound*, with the
        # reason, wherever a way in is drawn.
        #
        # The **condition** is asked, never the sentence. `binding_note` returns the
        # wording and the judgement together so the two cannot disagree (rule 13), and
        # a guard that matched the wording would be rule 30 in the guard.
        #
        # A reader's own reason counts the same way: a way in it marked and said has no body
        # here -- generated, or implemented only by overriders -- is not leading nowhere.
        if ((row["declared"] or supplied_why(store, str(row["id"])))
                and binding_note(store, str(row["id"])).known_limit):
            continue
        r.add(Anomaly(
            kind="ENTRYPOINT_NO_TARGET", severity=SUSPECT, confidence=PROBABLE,
            title=f"Way in `{row['name']}` leads nowhere",
            detail=f"`{row['name']}` ({row['kind']}) was detected from "
                   f"{row['evidence']}, but no routine could be found for it.",
            blind_spot="The target may be built dynamically, or supplied by a "
                       "dependency rather than defined in this program.",
            # A way in is named within a module, and both halves are needed: two
            # modules may each declare a `main` that leads nowhere.
            ident_parts=(row["module"], row["name"]),
            subject=row["name"], file=row["file"],
            # `ep` is the way-in route the cover's rows already take. The finding is that
            # this way in leads nowhere, and opening it is how a reader sees that.
            occurrences=[Occurrence(nav="ep", id=str(row["name"]),
                                    label=str(row["name"]), file=str(row["file"] or ""))],
        ))
    for row in store.query(
        "SELECT parent_var, child_expr, file, line FROM cli_mounts WHERE child_id IS NULL"
        " ORDER BY file, line, parent_var, child_expr"
    ):
        r.add(Anomaly(
            kind="UNRESOLVED_MOUNT", severity=SUSPECT, confidence=PROBABLE,
            title=f"Mounted sub-application `{row['child_expr']}` could not be found",
            detail=f"`{row['parent_var']}` mounts `{row['child_expr']}`, which "
                   f"resolves to no application object. Its commands are missing "
                   f"from the command tree.",
            blind_spot="The sub-application may come from an installed package "
                       "rather than from this source tree.",
            # Which application mounts which sub-application. `file` stays out: the
            # mount moved to another module is the same unresolved mount.
            ident_parts=(row["parent_var"], row["child_expr"]),
            subject=row["child_expr"], file=row["file"], line=row["line"],
            # The mount resolves to nothing -- that is the finding -- so the way in is the
            # line where it is written, never a guess at what it meant.
            occurrences=[Occurrence(nav="file", id=str(row["file"]),
                                    label=f"{row['parent_var']} mounts {row['child_expr']}",
                                    file=str(row["file"]), line=int(row["line"] or 0))],
        ))


def _type_gaps(store: Store, r: Report) -> None:
    total = store.query(
        "SELECT COUNT(*) n FROM routines WHERE name != '<module>'"
    )[0]["n"]
    if not total:
        return
    # `NOT INDEXED`: every routine is read, so the table is read in its own order and sorted
    # in memory. Through the index each row was a random seek, and on a 262,879-routine map
    # on the external volume that is minutes rather than seconds (BACKLOG 8).
    missing = store.query(
        "SELECT id, qualname, file, line_start FROM routines NOT INDEXED"
        " WHERE name != '<module>' AND returns IS NULL ORDER BY qualname, file, line_start"
    )
    untyped = store.query(
        "SELECT COUNT(DISTINCT routine_id) n FROM params NOT INDEXED"
        " WHERE type IS NULL AND name NOT IN ('self', 'cls')"
    )[0]["n"]
    if missing:
        r.add(Anomaly(
            kind="MISSING_RETURN_TYPE", severity=INFO, confidence=CERTAIN,
            title=f"{len(missing)} of {total:,} routines declare no return type",
            detail="; ".join(x["qualname"] for x in missing),
            blind_spot="None as a fact; whether it matters depends on whether the "
                       "project requires annotations.",
            ident_parts=(),  # one per program
            count=len(missing), file=missing[0]["file"], line=missing[0]["line_start"],
            occurrences=[
                Occurrence(nav="routine", id=str(x["id"]), label=str(x["qualname"]),
                           file=str(x["file"] or ""), line=int(x["line_start"] or 0))
                for x in missing
            ],
        ))
    if untyped:
        r.add(Anomaly(
            kind="UNTYPED_PARAMETER", severity=INFO, confidence=CERTAIN,
            title=f"{untyped:,} routines have at least one parameter with no type",
            detail="What moves in is undeclared, so the map cannot say what these "
                   "routines accept.",
            blind_spot="None as a fact.",
            ident_parts=(),  # one per program
            count=untyped,
            # The routines the count is over. `DISTINCT` there and here, so the number and
            # the list are one population asked twice rather than two answers.
            occurrences=_routine_rows(
                store,
                "WHERE name != '<module>' AND id IN ("
                "  SELECT DISTINCT routine_id FROM params NOT INDEXED"
                "   WHERE type IS NULL AND name NOT IN ('self', 'cls'))", scan=True),
        ))


def _ipc_commands(store: Store, r: Report) -> None:
    """A command nothing can call, and a name sent that nothing answers.

    The two halves of `resolve/ipc.py`'s link, each reported where it fails. Neither names
    a language: the command is an `IPC_COMMAND` way in, the registration is a fact, and the
    send is a row in `ipc_links`, whichever readers produced them.

    **Both SUSPECT.** An unregistered command is certainly unregistered *by every registrar
    this map read*, and the name that answers nothing is matched by string: a CI job that
    exits on BROKEN should not exit on a registrar this reader cannot see.
    """
    unregistered = store.query(
        "SELECT e.name, e.file, e.routine_id, r.qualname, r.line_start"
        "  FROM entrypoints e LEFT JOIN routines r ON r.id = e.routine_id"
        " WHERE e.kind = 'IPC_COMMAND'"
        "   AND e.name NOT IN (SELECT name FROM ipc_registrations)"
        " ORDER BY e.name, e.file, e.id"
    )
    for x in unregistered:
        r.add(Anomaly(
            kind="UNREGISTERED_COMMAND", severity=SUSPECT, confidence=CERTAIN,
            title=f"`{x['name']}` is a command no registrar names, so no client can call it",
            detail=f"It is declared a command at {x['file']}:{x['line_start'] or 0}, and "
                   f"no registrar this map read hands `{x['name']}` to the dispatch. "
                   f"A client that sends it gets an error rather than an answer.",
            blind_spot="A registrar this reader does not read -- a macro that wraps the "
                       "declared one, a plugin builder, a second crate outside this tree -- "
                       "registers it unseen. A command kept for a client that is gone is "
                       "dead code rather than a defect.",
            ident_parts=(str(x["name"]), str(x["qualname"] or "")),
            subject=str(x["name"]), file=str(x["file"]), line=int(x["line_start"] or 0),
            occurrences=[Occurrence(nav="routine", id=str(x["routine_id"] or ""),
                                    label=str(x["qualname"] or x["name"]),
                                    file=str(x["file"]), line=int(x["line_start"] or 0))],
        ))

    # A send is unknown only where this map holds the other side at all. A front end read
    # without its back end would otherwise report every command it sends (rule 98).
    if not store.query("SELECT 1 FROM ipc_registrations LIMIT 1"):
        return
    # Grouped by the name, as `LOST_EDGE` groups by the expression: the name is what the
    # finding is about, and the sites that send it are what it reports.
    for row in store.query(
        "SELECT command, COUNT(*) n, MIN(file) f, MIN(line) l FROM ipc_links"
        " WHERE status = 'unknown' GROUP BY command ORDER BY command"
    ):
        name = str(row["command"])
        r.add(Anomaly(
            kind="UNKNOWN_COMMAND", severity=SUSPECT, confidence=PROBABLE,
            title=f"`{name}` is sent as a command and no command of this program answers it",
            detail=f"Sent from {plural(row['n'], 'site')}; no declared command in this map "
                   f"is named `{name}`. Called, it fails at run time.",
            blind_spot="Matched by name. A command defined in a crate this tree does not "
                       "hold, or registered by a plugin whose prefix the rules file does "
                       "not declare, answers it unseen; so does one whose name a macro "
                       "builds.",
            ident_parts=(str(row["command"]),),
            subject=name, file=str(row["f"]), line=int(row["l"]), count=row["n"],
            occurrences=[
                Occurrence(nav="routine", id=str(x["caller_id"]),
                           label=str(x["qualname"] or x["caller_id"]),
                           file=str(x["file"]), line=int(x["line"]))
                for x in store.query(
                    "SELECT l.file, l.line, l.caller_id, r.qualname"
                    "  FROM ipc_links l LEFT JOIN routines r ON r.id = l.caller_id"
                    " WHERE l.status = 'unknown' AND l.command = ?"
                    " ORDER BY l.file, l.line, l.caller_id", (name,))
            ],
        ))



def _macro_hidden_boundaries(store: Store, r: Report) -> None:
    """**A macro whose expansion leaves the program, at a line that does not say so.**

    One finding per definition, because a name is not an identity: a second `check` that
    runs `system` is not the first. SUSPECT, and worded about what happens and never about
    why, because most of these are somebody's ordinary wrapper and the map cannot tell.

    Left out, each for a reason a reader could check:

    * a definition this tree did not write: a library's macro is the library's business, and
      `FD_SET` is not a tactic. Only what this program, or its build, chose.
    * a low-salience boundary, which is a log line.
    * a callee that starts with the macro's name: `open` becoming `open64` and
      `CreateProcess` becoming `CreateProcessW` are a platform's spelling of the written name.
    * any language whose reader does not expand: declared, never named here (rule 98).
    """
    expanding = {
        str(x["lang"]) for x in store.query("SELECT DISTINCT lang FROM files")
        if load_rules(str(x["lang"])).macro_expansion == "read"
    }
    if not expanding:
        return
    rows = store.query(
        "SELECT d.id AS def_id, d.name AS macro, d.file AS def_file, d.line AS def_line,"
        "       d.origin, b.kind, b.direction, b.evidence, b.target, b.file, b.line,"
        "       b.routine_id, r.qualname, f.lang"
        "  FROM boundaries b"
        "  JOIN macro_defs d ON d.id = b.through_macro"
        "  JOIN files f ON f.path = b.file"
        "  JOIN routines r ON r.id = b.routine_id"
        " WHERE b.through_macro <> '' AND b.salience <> 'low'"
        "   AND d.origin IN ('tree', 'command_line')"
        " ORDER BY d.name, d.file, d.line, b.file, b.line, b.evidence"
    )
    groups: dict[str, list[sqlite3.Row]] = {}
    for x in rows:
        last = str(x["evidence"]).rsplit(".", 1)[-1]
        if str(x["lang"]) in expanding and not last.startswith(str(x["macro"])):
            groups.setdefault(str(x["def_id"]), []).append(x)
    for def_id, hits in groups.items():
        first = hits[0]
        places = len(hits)
        kinds = sorted({str(h["kind"]) for h in hits})
        callees = sorted({str(h["evidence"]) for h in hits})
        # What a rule cannot see: the other ways its uses leave, which no list of names covers.
        other = store.query(
            "SELECT COUNT(DISTINCT CASE WHEN target_file = '' AND candidates = 0 AND indirect = 0"
            "       THEN callee END) AS leaving,"
            "       COALESCE(SUM(CASE WHEN indirect = 1 THEN count END), 0) AS indirect"
            "  FROM macro_callees WHERE def_id = ?", (def_id,))[0]
        where = (f"defined at {first['def_file']}:{first['def_line']}" if first["def_file"]
                 else "defined on the build's command line")
        r.add(Anomaly(
            kind="MACRO_HIDDEN_BOUNDARY", severity=SUSPECT, confidence=CERTAIN,
            title=f"`{first['macro']}` reaches {', '.join(kinds)} through its expansion, "
                  f"at {plural(places, 'place')} that {'does' if places == 1 else 'do'} "
                  f"not name it",
            detail=f"`{first['macro']}` ({where}) expands to {', '.join(callees)}, and the "
                   f"code using it writes only the macro's name. Its uses reach "
                   f"{plural(int(other['leaving']), 'function')} outside this tree in all"
                   + (f", and make {plural(int(other['indirect']), 'call')} through a value"
                      if other["indirect"] else "") + ".",
            blind_spot="Most macros like this are an ordinary wrapper, and this says what the "
                       "expansion does and nothing about why. It sees only names the boundary "
                       "rules list, only the configuration read (an arm not taken is not here), "
                       "and one hop: a macro inside a macro's body is credited to the one written "
                       "at the line.",
            # The definition, without its line: it is what the finding is about, and a macro
            # that gains another kind of boundary is the same finding, grown.
            ident_parts=(str(first["macro"]), str(first["def_file"])),
            subject=str(first["macro"]),
            file=str(first["file"]), line=int(first["line"] or 0), count=places,
            occurrences=[
                Occurrence(nav="routine", id=str(h["routine_id"]),
                           label=f"{h['qualname']}: {h['evidence']}",
                           file=str(h["file"]), line=int(h["line"] or 0))
                for h in hits
            ],
        ))


DETECTORS = (
    _parse_failures,
    _name_collisions,
    _redefinitions,
    _lost_edges,
    _macro_hidden_boundaries,
    _unreachable,
    _schema_drift,
    _one_way_tables,
    _orphan_indexes,
    _remote_call_hazards,
    _looped_boundaries,
    _messaging_hazards,
    _entrypoint_problems,
    _type_gaps,
    _ipc_commands,
)


def detect(store: Store, include_tests: bool = False,
           tick: Callable[[int, int, str], None] | None = None) -> Report:
    """Run every detector against a stored graph.

    `tick(done, total, what)` is called before each detector and once at the end, so a run
    that spends forty minutes here -- Unreal's `Runtime`, 223,614 routines -- says which of
    fifteen it is on rather than nothing at all.
    """
    report = Report()
    total = len(DETECTORS) + 1
    for i, fn in enumerate(DETECTORS):
        if tick is not None:
            tick(i, total, "detector")
        fn(store, report)
    if tick is not None:
        tick(total - 1, total, "detector")
    _dead_code(store, report, include_tests)
    if tick is not None:
        tick(total, total, "detector")
    # **Every finding says what it is about, or why it cannot.** Asserted here rather than
    # in `Report.add`, and the difference is what the rule is *about*: this is a contract on
    # **detectors**, not on the `Anomaly` type -- `add` is also called by tests building a
    # finding by hand to check how an identity takes an ordinal, and holding those to a rule
    # about enumeration would be the guard drifting from its own subject.
    #
    # A detector that answers neither produces a control that looks live and does nothing --
    # design rule 16 arriving from the data rather than from the markup, where no amount of
    # reading the shell would ever find it.
    for a in report.items:
        assert a.occurrences or a.unenumerated, (
            f"{a.kind}: a finding must list what it is about, or say why it cannot"
        )
    return report
