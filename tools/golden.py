"""Take the golden, or compare a graph against it.

`output/GOLDEN-v1.txt` is the gate every ingest change is measured against: row counts,
distributions, and seven identity digests over a graph of Society read by v1. `make_id` is
derived from names and never from positions, so while `extractors/python/` is unchanged
every one of those digests must stay byte-identical -- not "the counts should match", which
a swap of contents can satisfy while the total holds.

**The script that took it was never recorded.** `V2-START-HERE.md` points at
`HANDOFF.md`'s v2 entries and there are none, so until this file existed the gate could be
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
needs: the artifact is `output/mensores-v1/`, the v1 graph itself, and a digest is only ever
compared between two graphs computed by one script. A recorded number whose definition is
lost is a label, not an identity (rule 30) -- the remedy is to state the definition, not to
keep the number.

    uv run python tools/golden.py output/mensores-v1/graph@*.db
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
REPRODUCES = frozenset({
    "routines.id", "structures.id", "entrypoints.id", "calls.site_id", "control.point_id",
})

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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="golden", description="Take the golden for a graph, or compare two.")
    p.add_argument("graph", type=Path, help="the graph database to measure")
    p.add_argument("other", type=Path, nargs="?",
                   help="a second graph; the two are compared instead of printed")
    p.add_argument("--against", type=Path, default=None,
                   help="a written report (output/GOLDEN-v1.txt) to compare against")
    p.add_argument("--header", default="", help="the first line of a freshly taken report")
    p.add_argument("--adopt", action="store_true",
                   help="say which recorded digests this script reproduces, and which it redefines")
    args = p.parse_args(argv)

    if args.other:
        left = _recorded(take(args.graph))
        right = _recorded(take(args.other))
        return compare(left, right, args.graph.name, args.other.name)

    if args.against:
        recorded = _recorded(args.against.read_text(encoding="utf-8"))
        taken = _recorded(take(args.graph))
        return compare(recorded, taken, "recorded", "taken", only=REPRODUCES)

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
