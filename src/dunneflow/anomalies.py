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
import sys
from dataclasses import dataclass, field

from .store import Store

# What it means for the program.
BROKEN = "BROKEN"    # the program cannot be correct as written
SUSPECT = "SUSPECT"  # probably wrong, or a latent operational hazard
INFO = "INFO"        # worth knowing; not necessarily wrong

# How sure the tool is.
CERTAIN = "CERTAIN"
PROBABLE = "PROBABLE"
POSSIBLE = "POSSIBLE"

_SEVERITY_ORDER = {BROKEN: 0, SUSPECT: 1, INFO: 2}
_CONFIDENCE_ORDER = {CERTAIN: 0, PROBABLE: 1, POSSIBLE: 2}

_STDLIB = frozenset(sys.stdlib_module_names)


@dataclass(slots=True)
class Anomaly:
    kind: str
    severity: str
    confidence: str
    title: str
    detail: str
    blind_spot: str
    subject: str = ""
    file: str = ""
    line: int = 0
    count: int = 1


@dataclass(slots=True)
class Report:
    items: list[Anomaly] = field(default_factory=list)

    def add(self, a: Anomaly) -> None:
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


def _parse_failures(store: Store, r: Report) -> None:
    for row in store.query("SELECT path, errors FROM files WHERE errors != '[]'"):
        for err in json.loads(row["errors"]):
            r.add(Anomaly(
                kind="PARSE_ERROR", severity=BROKEN, confidence=CERTAIN,
                title=f"{row['path']} could not be parsed",
                detail=err,
                blind_spot="None. The file is not valid Python for the interpreter "
                           "running DunneFlow; if the program targets an older or "
                           "newer syntax, that is the difference.",
                subject=row["path"], file=row["path"],
            ))


def _name_collisions(store: Store, r: Report) -> None:
    for row in store.query(
        "SELECT qualname, COUNT(*) n, GROUP_CONCAT(line_start) lines, MIN(file) f"
        "  FROM routines WHERE name != '<module>'"
        " GROUP BY qualname HAVING n > 1 ORDER BY n DESC"
    ):
        r.add(Anomaly(
            kind="NAME_COLLISION", severity=BROKEN, confidence=CERTAIN,
            title=f"`{row['qualname']}` is defined {row['n']} times",
            detail=f"`{row['qualname']}` is defined {row['n']} times "
                   f"(lines {row['lines']}). Only the last one exists at run time; "
                   f"every call resolves to it and the others are unreachable.",
            blind_spot="If these are nested functions in different enclosing scopes "
                       "they are distinct and this is a naming defect in DunneFlow, "
                       "not in the program. Check whether the definitions sit inside "
                       "different functions.",
            subject=row["qualname"], file=row["f"], count=row["n"],
        ))


def _redefinitions(store: Store, r: Report) -> None:
    for row in store.query(
        "SELECT module, name, COUNT(*) n, GROUP_CONCAT(line_start) lines, MIN(file) f"
        "  FROM routines WHERE name != '<module>' AND is_nested = 0 AND is_method = 0"
        " GROUP BY module, name HAVING n > 1 ORDER BY n DESC"
    ):
        r.add(Anomaly(
            kind="REDEFINITION", severity=SUSPECT, confidence=CERTAIN,
            title=f"`{row['name']}` is defined {row['n']} times in one module",
            detail=f"`{row['name']}` is defined {row['n']} times in `{row['module']}` "
                   f"(lines {row['lines']}). The later definition shadows the earlier.",
            blind_spot="Conditional definitions (`if TYPE_CHECKING:`, platform "
                       "branches, try/except ImportError) legitimately define a name "
                       "more than once and only one is ever live.",
            subject=f"{row['module']}.{row['name']}", file=row["f"], count=row["n"],
        ))


def _lost_edges(store: Store, r: Report) -> None:
    """Calls that meant something local but could not be pinned to one definition."""
    rows = store.query(
        "SELECT callee_expr, MAX(ambiguous) rivals, COUNT(*) n, MIN(file) f"
        "  FROM calls"
        " WHERE ambiguous > 1"
        "   AND (callee_expr NOT LIKE '%.%' OR callee_expr LIKE 'self.%'"
        "        OR callee_expr LIKE 'cls.%')"
        " GROUP BY callee_expr ORDER BY n DESC"
    )
    for row in rows:
        r.add(Anomaly(
            kind="LOST_EDGE", severity=SUSPECT, confidence=PROBABLE,
            title=f"`{row['callee_expr']}` could not be connected: "
                  f"{row['rivals']} definitions share the name",
            detail=f"`{row['callee_expr']}` is called {row['n']} times, and "
                   f"{row['rivals']} routines share that name. The call graph has no "
                   f"edge here, so anything downstream is missing from every flow "
                   f"that passes through it.",
            blind_spot="If the receiver is a third-party object, or the method is "
                       "supplied by a mixin or set dynamically, no local definition "
                       "was ever intended and nothing is wrong.",
            subject=row["callee_expr"], file=row["f"], count=row["n"],
        ))


def _dead_code(store: Store, r: Report, include_tests: bool) -> None:
    rows = store.query(
        "SELECT qualname, file, line_start FROM routines"
        " WHERE name != '<module>' AND is_method = 0 AND is_nested = 0"
        "   AND name NOT LIKE '\\_\\_%' ESCAPE '\\'"
        "   AND id NOT IN (SELECT callee_id FROM calls WHERE callee_id IS NOT NULL)"
        "   AND id NOT IN (SELECT routine_id FROM entrypoints"
        "                   WHERE routine_id IS NOT NULL)"
        " ORDER BY qualname"
    )
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
        title=f"{len(rows)} routines are never called and are not a way in",
        detail="; ".join(x["qualname"] for x in rows),
        blind_spot=f"{scope} Routines reached by name (plugin registries, "
                   f"`getattr`, entry-point groups) also appear here, because no "
                   f"static analysis can see those calls.",
        subject="", file=rows[0]["file"], line=rows[0]["line_start"], count=len(rows),
    ))


def _unreachable(store: Store, r: Report) -> None:
    ways_in = [
        row["routine_id"]
        for row in store.query(
            "SELECT DISTINCT routine_id FROM entrypoints WHERE routine_id IS NOT NULL"
        )
    ]
    if not ways_in:
        return
    reached = store.reachable_from_many(ways_in)
    total = store.query(
        "SELECT COUNT(*) n FROM routines WHERE name != '<module>'"
    )[0]["n"]
    stranded = total - len({r_ for r_ in reached})
    if stranded <= 0:
        return
    r.add(Anomaly(
        kind="UNREACHABLE", severity=INFO, confidence=POSSIBLE,
        title=f"{stranded:,} of {total:,} routines are not reachable from any way in",
        detail="These cannot run when the program is started by any entrypoint "
               "DunneFlow found.",
        blind_spot="An edge lost to ambiguity strands everything behind it, so "
                   "LOST_EDGE findings inflate this number. Library code meant to be "
                   "imported by other programs is also unreachable by design.",
        count=stranded,
    ))


def _schema_drift(store: Store, r: Report) -> None:
    for row in store.query(
        "SELECT name, COUNT(DISTINCT file || ':' || line) defs FROM db_tables"
        " GROUP BY name HAVING defs > 1"
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
            subject=row["name"], count=row["defs"],
        ))


def _one_way_tables(store: Store, r: Report) -> None:
    for row in store.query(
        "SELECT tbl, SUM(direction='READ') rd, SUM(direction='WRITE') wr"
        "  FROM sql_ops WHERE tbl != '' GROUP BY tbl"
        " HAVING (rd = 0 AND wr > 0) OR (wr = 0 AND rd > 0)"
        " ORDER BY (rd + wr) DESC"
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
            subject=row["tbl"], count=row["rd"] + row["wr"],
        ))


def _orphan_indexes(store: Store, r: Report) -> None:
    for row in store.query(
        "SELECT name, tbl, file, line FROM db_indexes"
        " WHERE tbl NOT IN (SELECT name FROM db_tables)"
    ):
        r.add(Anomaly(
            kind="ORPHAN_INDEX", severity=SUSPECT, confidence=PROBABLE,
            title=f"`{row['name']}` indexes `{row['tbl']}`, which is never created here",
            detail=f"`{row['name']}` indexes `{row['tbl']}`, which has no CREATE "
                   f"TABLE anywhere in this program.",
            blind_spot="The table may be created by a migration tool, by another "
                       "program sharing the database, or by SQL loaded from a file.",
            subject=row["name"], file=row["file"], line=row["line"],
        ))


def _remote_call_hazards(store: Store, r: Report) -> None:
    total = store.query("SELECT COUNT(*) n FROM net_calls")[0]["n"]
    if not total:
        return
    no_timeout = store.query(
        "SELECT r.qualname, n.expr, n.protocol, r.file, n.line FROM net_calls n"
        " JOIN routines r ON n.routine_id = r.id WHERE n.timeout = ''"
    )
    if no_timeout:
        r.add(Anomaly(
            kind="NO_TIMEOUT", severity=SUSPECT, confidence=PROBABLE,
            title=f"{len(no_timeout)} of {total} remote calls set no timeout",
            detail="; ".join(f"{x['qualname']} ({x['protocol']})" for x in no_timeout),
            blind_spot="A timeout may be set on the client object rather than the "
                       "call, or globally by the library's configuration. Check the "
                       "client construction before treating any one of these as a bug.",
            count=len(no_timeout),
            file=no_timeout[0]["file"], line=no_timeout[0]["line"],
        ))

    no_retry = store.query("SELECT COUNT(*) n FROM net_calls WHERE retries = ''")[0]["n"]
    if no_retry == total and total > 2:
        r.add(Anomaly(
            kind="NO_RETRY", severity=INFO, confidence=PROBABLE,
            title=f"None of the {total} remote calls declares a retry policy",
            detail="A single transient failure propagates to the caller.",
            blind_spot="Retries are often handled by a transport adapter, a service "
                       "mesh, or the caller rather than at the call site.",
            count=total,
        ))

    unawaited = store.query(
        "SELECT r.qualname, n.expr, r.file, n.line FROM net_calls n"
        " JOIN routines r ON n.routine_id = r.id"
        " WHERE n.is_async = 1 AND n.awaited = 0"
    )
    for x in unawaited:
        r.add(Anomaly(
            kind="ASYNC_NOT_AWAITED", severity=BROKEN, confidence=PROBABLE,
            title=f"`{x['expr']}` in `{x['qualname']}` is never awaited",
            detail=f"`{x['qualname']}` calls `{x['expr']}` without awaiting it. The "
                   f"coroutine is created and never run.",
            blind_spot="The result may be awaited elsewhere, passed to "
                       "`asyncio.gather`, or scheduled as a task. Calls managed by "
                       "`async with` are already excluded.",
            subject=x["qualname"], file=x["file"], line=x["line"],
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
            count=producers,
        ))


def _entrypoint_problems(store: Store, r: Report) -> None:
    for row in store.query(
        "SELECT kind, name, module, evidence, file FROM entrypoints"
        " WHERE routine_id IS NULL AND parent_id IS NULL"
    ):
        r.add(Anomaly(
            kind="ENTRYPOINT_NO_TARGET", severity=SUSPECT, confidence=PROBABLE,
            title=f"Way in `{row['name']}` leads nowhere",
            detail=f"`{row['name']}` ({row['kind']}) was detected from "
                   f"{row['evidence']}, but no routine could be found for it.",
            blind_spot="The target may be built dynamically, or supplied by a "
                       "dependency rather than defined in this program.",
            subject=row["name"], file=row["file"],
        ))
    for row in store.query(
        "SELECT parent_var, child_expr, file, line FROM cli_mounts WHERE child_id IS NULL"
    ):
        r.add(Anomaly(
            kind="UNRESOLVED_MOUNT", severity=SUSPECT, confidence=PROBABLE,
            title=f"Mounted sub-application `{row['child_expr']}` could not be found",
            detail=f"`{row['parent_var']}` mounts `{row['child_expr']}`, which "
                   f"resolves to no application object. Its commands are missing "
                   f"from the command tree.",
            blind_spot="The sub-application may come from an installed package "
                       "rather than from this source tree.",
            subject=row["child_expr"], file=row["file"], line=row["line"],
        ))


def _type_gaps(store: Store, r: Report) -> None:
    total = store.query(
        "SELECT COUNT(*) n FROM routines WHERE name != '<module>'"
    )[0]["n"]
    if not total:
        return
    missing = store.query(
        "SELECT qualname, file, line_start FROM routines"
        " WHERE name != '<module>' AND returns IS NULL ORDER BY qualname"
    )
    untyped = store.query(
        "SELECT COUNT(DISTINCT routine_id) n FROM params"
        " WHERE type IS NULL AND name NOT IN ('self', 'cls')"
    )[0]["n"]
    if missing:
        r.add(Anomaly(
            kind="MISSING_RETURN_TYPE", severity=INFO, confidence=CERTAIN,
            title=f"{len(missing)} of {total:,} routines declare no return type",
            detail="; ".join(x["qualname"] for x in missing),
            blind_spot="None as a fact; whether it matters depends on whether the "
                       "project requires annotations.",
            count=len(missing), file=missing[0]["file"], line=missing[0]["line_start"],
        ))
    if untyped:
        r.add(Anomaly(
            kind="UNTYPED_PARAMETER", severity=INFO, confidence=CERTAIN,
            title=f"{untyped:,} routines have at least one parameter with no type",
            detail="What moves in is undeclared, so the map cannot say what these "
                   "routines accept.",
            blind_spot="None as a fact.",
            count=untyped,
        ))


DETECTORS = (
    _parse_failures,
    _name_collisions,
    _redefinitions,
    _lost_edges,
    _unreachable,
    _schema_drift,
    _one_way_tables,
    _orphan_indexes,
    _remote_call_hazards,
    _messaging_hazards,
    _entrypoint_problems,
    _type_gaps,
)


def detect(store: Store, include_tests: bool = False) -> Report:
    """Run every detector against a stored graph."""
    report = Report()
    for fn in DETECTORS:
        fn(store, report)
    _dead_code(store, report, include_tests)
    return report
