"""Does the map depend on the order the rows happen to be in?

It did, for a year, and nobody noticed — including every session that diffed two maps by
hand. **Two analyses of Society by the same build, minutes apart, differ**: 1,488 lines in
`06-governance.md`, 656 in `12-traceability.md`, and every difference is *order* and never
content. `analyze_tree` collects facts through `as_completed`, so which file is written
first varies per run and so does every rowid; a query with no `ORDER BY`, or one ordering
on a column with ties, then returns rows in whatever order the pool happened to finish in.
Rule 66: an order the tool cannot defend is not an order, and these are undefended ties
rather than wrong answers.

**This probes it by reversing the rows rather than by analysing twice**, and that is the
whole reason it is a usable gate. Two real runs shuffle *some* of the order and catch
*some* of the ties, differently each time — `07-database.md` came out stable in one pair
and unstable in the next, which is what a coin looks like. Reversing every table is the
worst case and is the same every time, so a map that survives it survives any order at all,
and a run that reports nothing has actually checked something (rule 37).

**Reversing is safe, and that was established rather than assumed.** Nothing in either
store declares an `INTEGER PRIMARY KEY`, so no rowid is anybody's key: every identity here
is a `make_id` string, deliberately (`resolve/contract.py` says why). The one place a rowid
is held at all is `resolve/cli.py`, which reads and updates inside a single pass. So the
content after a reversal is identical by construction and only the physical order moves.

**Why reversal rather than a stable pool** — which is the fix somebody reaches for first.
Sorting the pool's output would keep the parallelism, since the results are accumulated
before they are written. It still would not be a fix: analysis is **incremental**, so a
re-analysed file's rows are deleted and appended at the end, and rowid order tracks the
edit history of the tree rather than anything about the program. Only a total order on
every rendered list is stable under that, which is what rule 66 asks for anyway.

    uv run python tools/ordering.py output/mensores
    uv run python tools/ordering.py output/mensores --show 06-governance.md
"""

from __future__ import annotations

import argparse
import difflib
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path

from dunneflow import revisions
from dunneflow.runtime import self_argv

# The one line that is *meant* to differ between two renders of one snapshot. The snapshot
# instant and the source-read instant are facts about the analysis and are identical in
# both copies; only *when these documents were written* is a fact about the render, and the
# cover states three instants on purpose (see `render/`). Normalised rather than dropped, so
# a document that differs **only** here still reads as a document that differed nowhere.
WRITTEN = re.compile(r"written \d{4}-\d\d-\d\d \d\d:\d\d UTC")


def reverse_rows(db: Path) -> int:
    """Flip the physical order of every table, keeping every row exactly as it was.

    `meta` is left alone: it is the map's identity — the schema version, the two
    fingerprints, whether the analysis finished — read by key and never by order, and
    rewriting it would be the one edit here that could change what the store *means*.
    """
    conn = sqlite3.connect(db)
    try:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        moved = 0
        for t in names:
            if t == "meta":
                continue
            conn.execute(f'CREATE TEMP TABLE _flip AS SELECT * FROM "{t}" ORDER BY rowid DESC')
            conn.execute(f'DELETE FROM "{t}"')
            conn.execute(f'INSERT INTO "{t}" SELECT * FROM _flip')
            conn.execute("DROP TABLE _flip")
            moved += 1
        conn.commit()
        return moved
    finally:
        conn.close()


def render(program: Path) -> Path:
    """Write this program's map from the graph it already has, and return the map dir."""
    for old in program.glob("map@*"):
        shutil.rmtree(old)
    done = subprocess.run([*self_argv(), "render", str(program)],
                          capture_output=True, text=True)
    if done.returncode != 0:
        said = (done.stderr or done.stdout or "").strip().splitlines()
        raise SystemExit(f"could not render {program}:\n  "
                         + (said[-1] if said else "it said nothing"))
    made = sorted(program.glob("map@*"))
    if not made:
        raise SystemExit(f"{program} rendered nothing, so there is nothing to compare")
    return made[0]


def _lines(path: Path) -> list[str]:
    return [WRITTEN.sub("written <when>", line)
            for line in path.read_text(encoding="utf-8").splitlines()]


def compare(a: Path, b: Path) -> dict[str, list[str]]:
    """Per document, the unified diff of the two renders, or nothing at all."""
    out: dict[str, list[str]] = {}
    names = sorted({p.name for p in a.glob("*.md")} | {p.name for p in b.glob("*.md")})
    for name in names:
        left = _lines(a / name) if (a / name).exists() else []
        right = _lines(b / name) if (b / name).exists() else []
        d = [ln for ln in difflib.unified_diff(left, right, lineterm="", n=1)
             if ln[:1] in "+-" and ln[:3] not in ("---", "+++")]
        if d:
            out[name] = d
    return out


def probe(program: Path, keep: Path | None = None) -> dict[str, list[str]]:
    """Render this program twice — as it is, and with every row reversed.

    Both copies are rendered, rather than one being compared against the map `analyze`
    already wrote. The map on disk was written by a different command at a different
    instant, and comparing against it would fold *did the renderer change* into *does the
    order matter* — two questions, one answer, and no way to tell which one moved.
    """
    with tempfile.TemporaryDirectory(prefix="dunneflow-order-") as tmp:
        where = Path(keep) if keep else Path(tmp)
        where.mkdir(parents=True, exist_ok=True)
        straight, flipped = where / "straight", where / "flipped"
        for d in (straight, flipped):
            if d.exists():
                shutil.rmtree(d)
            shutil.copytree(program, d)
        # **One glob, and it has to be one.** This was three — `*.db`, then `graph@*.db`,
        # then `docs@*.db` — and the first already matches the other two, so every graph
        # was reversed and then reversed back. The probe ran, rendered twice, diffed, and
        # reported *every document is byte-identical* over a store it had not changed:
        # rule 37 in the instrument, which is the one place it costs most (rule 38).
        for db in sorted(flipped.glob("*.db")):
            reverse_rows(db)
        return compare(render(straight), render(flipped))


def _programs(where: Path) -> Iterable[Path]:
    """Every analysed program under `where`, or `where` itself if it is one."""
    if revisions.holds_a_map(where):
        return [where]
    return sorted(p for p in revisions.program_dirs(where) if p != where)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="ordering",
        description="Does this program's map depend on the order its rows are stored in?")
    p.add_argument("program", type=Path, help="an analysed program directory, or a maps root")
    p.add_argument("--show", default="", metavar="DOC",
                   help="print the actual differing lines for one document")
    p.add_argument("--lines", type=int, default=20,
                   help="how many differing lines to print with --show (default 20)")
    p.add_argument("--keep", type=Path, default=None,
                   help="keep both renders here instead of in a temporary directory")
    args = p.parse_args(argv)

    where = args.program.resolve()
    if not where.is_dir():
        print(f"!! {where} is not a directory", file=sys.stderr)
        return 1

    bad = 0
    for program in _programs(where):
        found = probe(program, keep=args.keep)
        print(f"\n== {program.name}")
        if not found:
            print("   every document is byte-identical under a full row reversal")
            continue
        bad += 1
        for name, d in found.items():
            print(f"   {name:<24} {len(d):>6} differing lines")
        if args.show:
            for name, d in found.items():
                if name == args.show:
                    print(f"\n-- {name}")
                    for line in d[:args.lines]:
                        print(f"   {line}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
