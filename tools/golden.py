"""Take the golden, or compare a graph against it.

`output/GOLDEN-v1.txt` is the gate every ingest change is measured against: row counts,
distributions, and seven identity digests over a graph of Comitia read by v1. `make_id` is
derived from names and never from positions, so while `extractors/python/` is unchanged
every one of those digests must stay byte-identical -- not "the counts should match", which
a swap of contents can satisfy while the total holds.

**The script that took it was never recorded.** The development record pointed at its own
v2 entries and there were none, so until this file existed the gate could be
read and not run. This is that script, recovered against the recorded values rather than
written from memory: five of the seven digests reproduce exactly, which is what says the
serialisation below is the original's and not a second convention that happens to be
self-consistent.

**Two do not, and that is stated rather than smoothed.** `routines.body` and
`calls.resolved` are recorded as `3ad85059509e714b` and `fc254ebafacd4775`; the statement
that produced either was not recorded, and neither was recovered by a **bounded** sweep --
column permutations up to three wide over ten candidate columns, six orderings, ten
field-and-row separators, three renderings of NULL. Bounded and not exhaustive: the space
is bigger than that and the search was abandoned rather than finished. *We did not find it*
is not *it is not there*, and writing the first as the second is how a residue becomes a
claim (rule 24). So they are **redefined here**, explicitly, and their
values against the preserved v1 graph are printed by `--adopt`. That costs nothing the gate
needs: the artifact is `output/lictores-v1/`, the v1 graph itself, and a digest is only ever
compared between two graphs computed by one script. A recorded number whose definition is
lost is a label, not an identity (rule 30) -- the remedy is to state the definition, not to
keep the number.

    uv run python tools/golden.py output/lictores-v1/graph@*.db
    uv run python tools/golden.py <new.db> --against output/GOLDEN-v1.txt
    uv run python tools/golden.py <v1.db> <v2.db>
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
import sys
from pathlib import Path

from dunneflow.store import read_only_uri

# Each digest names the statement that produces it, because a digest whose statement is not
# written down is exactly the position this file was written to get out of. The first five
# reproduce `output/GOLDEN-v1.txt` exactly; the last two are this file's own definitions.
DIGESTS: tuple[tuple[str, str], ...] = (
    ("routines.id", "SELECT id FROM routines ORDER BY id"),
    ("structures.id", "SELECT id FROM structures ORDER BY id"),
    ("entrypoints.id", "SELECT id FROM entrypoints ORDER BY id"),
    ("calls.site_id", "SELECT site_id FROM calls ORDER BY site_id"),
    ("control.point_id", "SELECT point_id FROM control ORDER BY point_id"),
    ("routines.body", "SELECT id, body_hash FROM routines ORDER BY id"),
    ("calls.resolved",
     "SELECT site_id, callee_id, confidence, external, ambiguous FROM calls "
     "ORDER BY site_id, callee_id"),
)

# The digests whose recorded v1 value this script reproduces. Named rather than counted, so
# that a sixth one being recovered later is a line added here and not a number edited.
#
# **All five moved on 2026-09-19 and none of them will reproduce again.** Rule 106 put the
# file into a definition's identity, so every id in every map is a different hash of the
# same facts. This set is kept because it is what the *v1 report* can be compared for, and
# `GOLDEN-v1.txt` is a dated record rather than a live baseline: a fresh graph compared
# against it now reports five MOVED, correctly and for ever. `GOLDEN-v2.txt` is the live
# baseline, it carries `TAKEN_HERE` below, and every one of its seven digests is comparable
# because this script wrote both sides of that comparison.
REPRODUCES = frozenset({
    "routines.id", "structures.id", "entrypoints.id", "calls.site_id", "control.point_id",
})

# The line a report written by this script carries, and the thing `--against` asks of a
# report before deciding how much of it to trust. Not a version and not a date: the only
# question is *did the statements below come from this file*, because two of the seven are
# this file's own definitions and a report that predates it cannot answer for them.
TAKEN_HERE = "# digests: all seven are this script's own statements"

# What a map says when its keys are taken out of it — the check the rule 106 change was
# made under, and the only one that can tell *re-keyed* from *changed*. Every column here
# is a fact about the program; not one of them is an id, so two graphs of one tree agree
# on all four across a change that moves every id, and disagree the moment extraction
# does something different. A digest cannot do this job: it is keyed on the thing that
# moved.
REKEYED: tuple[tuple[str, str], ...] = (
    ("routines", "SELECT qualname, name, module, file, line_start, line_end, lang,"
                 "       body_hash FROM routines ORDER BY 1,2,3,4,5,6,7,8"),
    ("structures", "SELECT name, kind, module, file, line, lang FROM structures"
                   " ORDER BY 1,2,3,4,5,6"),
    ("calls", "SELECT file, callee_expr, line, confidence, external, ambiguous, at_boundary"
              "  FROM calls ORDER BY 1,2,3,4,5,6,7"),
    ("boundaries", "SELECT file, kind, direction, target, line FROM boundaries"
                   " ORDER BY 1,2,3,4,5"),
    ("control", "SELECT file, kind, line_start, line_end, header, arms FROM control"
                " ORDER BY 1,2,3,4,5,6"),
    ("entrypoints", "SELECT kind, name, module, file, evidence FROM entrypoints"
                    " ORDER BY 1,2,3,4,5"),
)

DISTRIBUTIONS: tuple[tuple[str, str], ...] = (
    ("boundaries kind/dir",
     "SELECT kind || ' ' || direction AS k, count(*) FROM boundaries GROUP BY k ORDER BY k"),
    ("entrypoints kind", "SELECT kind, count(*) FROM entrypoints GROUP BY kind ORDER BY kind"),
    ("control kind", "SELECT kind, count(*) FROM control GROUP BY kind ORDER BY kind"),
    # Resolved calls only, and the predicate is `callee_id IS NOT NULL` rather than
    # `external = 0`, which returns the same two numbers on this graph. Confidence is
    # recorded on every row including the 24,103 that resolved to nothing, so the
    # unfiltered lane reads INFERRED 24,891 -- a count that does not say what it counts
    # (rule 32). Naming the predicate for the thing itself is what keeps the two from
    # drifting apart on a graph where they stop agreeing.
    ("calls confidence",
     "SELECT confidence, count(*) FROM calls WHERE callee_id IS NOT NULL "
     "GROUP BY confidence ORDER BY confidence"),
    ("files lang", "SELECT lang, count(*) FROM files GROUP BY lang ORDER BY lang"),
)


def _open(path: Path) -> sqlite3.Connection:
    """Read-only, because a gate that can write to the thing it measures is not a gate.

    Through `store.read_only_uri` rather than pasting the path into a URI here. This file
    wrote it by hand first and was the fifth site doing so; a golden whose own path handling
    is a sixth spelling of a rule the tool states once is not the example to set (rule 51).
    """
    if not path.is_file():
        raise SystemExit(f"error: {path} is not a file")
    return sqlite3.connect(read_only_uri(path), uri=True)


def digest(conn: sqlite3.Connection, sql: str) -> tuple[str, int]:
    """sha256 of every field, NUL-terminated, in the order the statement returns them.

    NUL-*terminated* and not NUL-separated: the difference is one trailing byte and it is
    the difference between reproducing the recorded digests and not.
    """
    h = hashlib.sha256()
    rows = 0
    for row in conn.execute(sql):
        rows += 1
        for value in row:
            h.update(("" if value is None else str(value)).encode())
            h.update(b"\x00")
    return h.hexdigest()[:16], rows


def tables(conn: sqlite3.Connection) -> list[str]:
    """Every table the graph holds, asked of the graph rather than kept in a list here.

    A hand-kept list drifts the moment somebody adds a table, and a golden that silently
    omits one is the gate failing in the direction nobody looks.
    """
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name")]


def take(path: Path, header: str = "") -> str:
    """The whole report for one graph, in `GOLDEN-v1.txt`'s own layout."""
    conn = _open(path)
    try:
        out: list[str] = []
        if header:
            out.append(f"# {header}")
        out.append(f"# graph: {path.name}")
        out.append(TAKEN_HERE)
        out.append("")
        out.append("## row counts")
        for table in tables(conn):
            # Interpolated rather than bound, because a table name is an identifier and
            # SQLite binds values only. The names come from `sqlite_master` on the line
            # above, so the only thing that can reach this string is a table the graph
            # already holds.
            n = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            out.append(f"{table:<18}{n:>7,}")
        out.append("")
        out.append("## identity digests (sorted ids, sha256[:16])")
        for label, sql in DIGESTS:
            value, rows = digest(conn, sql)
            out.append(f"{label:<19}{value}  ({rows:,} rows)")
        out.append("")
        out.append("## distributions")
        for label, sql in DISTRIBUTIONS:
            out.append("")
            out.append(f"[{label}]")
            for key, n in conn.execute(sql):
                out.append(f"  {key:<27}{n:>5,}")
        return "\n".join(out) + "\n"
    finally:
        conn.close()


def _recorded(report: str) -> dict[str, str]:
    """The digests a written report states, read back out of it."""
    found: dict[str, str] = {}
    for line in report.splitlines():
        m = re.match(r"^(\S+\.\S+)\s+([0-9a-f]{16})\b", line)
        if m:
            found[m.group(1)] = m.group(2)
    return found


def compare(left: dict[str, str], right: dict[str, str], left_name: str, right_name: str,
            only: frozenset[str] | None = None) -> int:
    """Name every digest that moved, and say plainly when none did.

    `only` bounds the comparison to the digests the left-hand side can be trusted for.
    Against the *written* report that is `REPRODUCES` and not all seven: the other two
    record a value whose statement is lost, so comparing them would report a difference
    every single run -- and a check that cries wolf has already failed (rule 43).
    """
    wanted = [label for label, _ in DIGESTS if only is None or label in only]
    shared = [label for label in wanted if label in left and label in right]
    missing = [label for label in wanted if label not in left or label not in right]
    held = [label for label, _ in DIGESTS if label not in wanted]
    moved = [label for label in shared if left[label] != right[label]]
    for label in moved:
        print(f"MOVED  {label:<19}{left_name}={left[label]}  {right_name}={right[label]}")
    for label in missing:
        print(f"absent {label:<19}not stated on both sides, so not compared")
    for label in held:
        print(f"held   {label:<19}redefined here; compare it graph to graph, not against "
              f"a report")
    if moved:
        print(f"\n{len(moved)} of {len(shared)} digests moved. "
              f"Every difference is explained, not absorbed.")
        return 1
    print(f"{len(shared)} of {len(DIGESTS)} digests identical"
          + (f"; {len(missing)} not stated" if missing else "")
          + (f"; {len(held)} held back" if held else "")
          + ".")
    return 0


def rekeyed(left: Path, right: Path) -> int:
    """Are these two graphs the same program under different keys?

    **The question `--against` cannot ask.** Every digest in this file is taken over ids, so
    a change to how an id is derived moves all of them and says nothing whatever about
    whether extraction still reads the same program. That is exactly the position rule 106
    put this gate in on 2026-09-19: five of five digests moved by construction, and the only
    thing that could distinguish *we re-keyed the map* from *we broke the reader* was a
    comparison with the keys taken out.

    So `REKEYED` projects each table onto its facts and none of its ids, and the two graphs
    are compared column for column. Against `output/lictores-v1/` -- v1's own graph, read by
    v1 -- all six agree, which is the statement the change was taken on.

    It is not a replacement for the digests and does not want to be: two routines that swap
    identities are invisible here and loud there. The pair is the gate.
    """
    a, b = _open(left), _open(right)
    try:
        moved = []
        for label, sql in REKEYED:
            da, _ = digest(a, sql)
            db, rows = digest(b, sql)
            if da == db:
                print(f"same   {label:<12}{da}  ({rows:,} rows)")
            else:
                moved.append(label)
                print(f"MOVED  {label:<12}{left.name}={da}  {right.name}={db}")
        if moved:
            print(f"\n{len(moved)} of {len(REKEYED)} projections differ, so these two graphs "
                  f"are not one program under two keys — something extraction reads changed.")
            return 1
        print(f"\nall {len(REKEYED)} projections identical: the same facts, differently "
              f"keyed.")
        return 0
    finally:
        a.close()
        b.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="golden", description="Take the golden for a graph, or compare two.")
    p.add_argument("graph", type=Path, help="the graph database to measure")
    p.add_argument("other", type=Path, nargs="?",
                   help="a second graph; the two are compared instead of printed")
    p.add_argument("--against", type=Path, default=None,
                   help="a written report (output/GOLDEN-v2.txt) to compare against")
    p.add_argument("--rekeyed", type=Path, default=None,
                   help="a second graph: compare the two with every id taken out, which is"
                        " what tells a re-keying from a change of facts")
    p.add_argument("--header", default="", help="the first line of a freshly taken report")
    p.add_argument("--adopt", action="store_true",
                   help="say which recorded digests this script reproduces, and which it redefines")
    args = p.parse_args(argv)

    if args.other:
        left = _recorded(take(args.graph))
        right = _recorded(take(args.other))
        return compare(left, right, args.graph.name, args.other.name)

    if args.rekeyed:
        return rekeyed(args.graph, args.rekeyed)

    if args.against:
        report = args.against.read_text(encoding="utf-8")
        # **How much of the report to trust is the report's own claim**, not a flag and not
        # a filename. A report this script wrote answers for all seven; `GOLDEN-v1.txt`
        # predates it and answers for five, and since rule 106 those five all moved -- so
        # comparing against it is a historical question and says so rather than failing
        # silently at a different scope.
        only = None if TAKEN_HERE in report else REPRODUCES
        taken = _recorded(take(args.graph))
        return compare(_recorded(report), taken, "recorded", "taken", only=only)

    if args.adopt:
        conn = _open(args.graph)
        try:
            for label, sql in DIGESTS:
                value, rows = digest(conn, sql)
                note = ("reproduces the recorded value" if label in REPRODUCES
                        else "redefined by this script -- the v1 statement was never recorded")
                print(f"{label:<19}{value}  ({rows:,} rows)  {note}")
        finally:
            conn.close()
        return 0

    sys.stdout.write(take(args.graph, args.header))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
