"""Command line.

    dunneflow analyze <path> --name mensores    extract, resolve, and write the map
    dunneflow touches <path> --routine save     what does this reach?
    dunneflow impact <path> --routine save      what breaks if I change it?
    dunneflow query <path> --sql "..."          ask the graph directly

`analyze` is incremental: run it again after editing and only the changed files are
re-read.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .anomalies import BROKEN, INFO, SUSPECT, detect
from .docstore import DocStore
from .render.markdown import render_all
from .resolve.calls import resolve_calls
from .resolve.cli import resolve_cli
from .resolve.entrypoints import entrypoints_from_packaging
from .resolve.flows import entry_reach
from .resolve.glossary import bind
from .resolve.mirror import BANDS as MIRROR_BANDS
from .resolve.mirror import measure as measure_mirror
from .resolve.naming import measure
from .store import Store
from .walk import analyze_docs_tree, analyze_tree

DEFAULT_OUTPUT = Path("output")


def _default_paths(target: Path, name: str | None, out_root: Path) -> tuple[str, Path]:
    program = name or target.resolve().name
    return program, out_root / program


def _emit(msg: str) -> None:
    print(msg, file=sys.stderr)


def cmd_analyze(args: argparse.Namespace) -> int:
    target = Path(args.path).resolve()
    if not target.exists():
        _emit(f"error: {target} does not exist")
        return 2

    source_root = target
    program, out_dir = _default_paths(target, args.name, Path(args.output))
    db_path = Path(args.db) if args.db else out_dir / "graph.db"

    t0 = time.perf_counter()
    store = Store(db_path)
    store.set_meta("program", program)
    store.set_meta("source_root", str(source_root))

    def progress(path: str, i: int, total: int) -> None:
        if args.quiet:
            return
        if i % 50 == 0 or i == total:
            _emit(f"  extracting {i}/{total}")

    stats = analyze_tree(
        source_root, store, include_tests=args.include_tests,
        jobs=args.jobs, progress=progress,
    )
    t_extract = time.perf_counter() - t0

    # The package root is where pyproject.toml lives, which may be above src/.
    pkg_root = source_root
    for candidate in (source_root, *source_root.parents):
        if (candidate / "pyproject.toml").exists():
            pkg_root = candidate
            break
    entrypoints_from_packaging(pkg_root, store)

    # Documentation is a parallel input, read from the package root because that is
    # where prose lives relative to `src/`. It is never a prerequisite: a program with
    # no documents yields an empty document store and a complete code map.
    doc_stats = None
    doc_store: DocStore | None = None
    docs_root: Path | None = None
    if not args.no_docs:
        docs_root = Path(args.docs).resolve() if args.docs else pkg_root
        doc_store = DocStore(out_dir / "docs.db")
        doc_store.set_meta("program", program)
        doc_store.set_meta("docs_root", str(docs_root))
        doc_stats = analyze_docs_tree(docs_root, doc_store, jobs=args.jobs,
                                      recheck=args.recheck_docs)
        duplicates = doc_store.mark_duplicates()
        dc = doc_store.counts()
        if not args.quiet:
            if getattr(doc_store, "rebuilt", False):
                _emit("document store written by older prose rules — discarded and re-read")
            _emit(
                f"documents {doc_stats.found} (read {doc_stats.parsed}, "
                f"cached {doc_stats.cached}, removed {doc_stats.removed}, "
                f"failed {doc_stats.failed}): {dc['definitions']:,} definitions, "
                f"{dc['doc_rules']:,} stated rules, {dc['doc_annotations']:,} governance ids"
                + (f"; {duplicates:,} are copies of another document"
                   if duplicates else "")
            )
        doc_store.optimize()

    t1 = time.perf_counter()
    rstats = resolve_calls(store)
    clistats = resolve_cli(store)
    store.optimize()
    t_resolve = time.perf_counter() - t1

    if not args.quiet:
        if getattr(store, "rebuilt", False):
            # Say it out loud. A silent rebuild looks like a slow run; an unsaid
            # one looks like a fast run that quietly told you last week's truth.
            _emit("graph written by an older DunneFlow — discarded and re-extracted")
        _emit(
            f"files {stats.found} (parsed {stats.parsed}, cached {stats.cached}, "
            f"removed {stats.removed}, failed {stats.failed}) in {t_extract:.1f}s"
        )
        _emit(
            f"calls {rstats.total:,}: {rstats.certain:,} certain, "
            f"{rstats.inferred:,} inferred, {rstats.external:,} external "
            f"({rstats.rate():.0f}% internal) in {t_resolve:.1f}s"
        )
        _emit(
            f"cli: {clistats.apps} apps, {clistats.commands_attached} commands, "
            f"{clistats.mounts_resolved}/{clistats.mounts_total} mounts"
        )

    if not args.no_render:
        t2 = time.perf_counter()
        store.warm()
        files = render_all(store, out_dir, source_root, program,
                           include_tests=args.include_tests,
                           docs=doc_store, docs_root=docs_root)
        if not args.quiet:
            _emit(f"wrote {len(files)} documents to {out_dir} in "
                  f"{time.perf_counter() - t2:.1f}s")

    store.warm()
    rep = detect(store, include_tests=args.include_tests)
    ac = rep.counts()
    if not args.quiet and any(ac.values()):
        _emit(
            f"anomalies: {ac.get(BROKEN, 0)} broken, {ac.get(SUSPECT, 0)} suspect, "
            f"{ac.get(INFO, 0)} informational"
        )

    c = store.counts()
    print(
        f"{program}: {c['routines']:,} routines · {c['resolved_calls']:,} internal calls · "
        f"{c['boundaries']:,} boundary touches · {c['structures']:,} structures · "
        f"{c['entrypoints']:,} ways in"
    )
    print(f"graph: {db_path}")
    if doc_stats is not None:
        print(f"docs:  {out_dir}/docs.db")
    if not args.no_render:
        print(f"map:   {out_dir}/README.md")
    if doc_store is not None:
        doc_store.close()
    store.close()
    return 0


def _find_routine(store: Store, needle: str) -> list[dict]:
    rows = store.query(
        "SELECT id, name, qualname, module, file, line_start FROM routines"
        " WHERE qualname = ? OR name = ? ORDER BY qualname LIMIT 25",
        (needle, needle),
    )
    if not rows:
        rows = store.query(
            "SELECT id, name, qualname, module, file, line_start FROM routines"
            " WHERE qualname LIKE ? ORDER BY qualname LIMIT 25",
            (f"%{needle}%",),
        )
    return [dict(r) for r in rows]


def _open_store(args: argparse.Namespace) -> tuple[Store, Path] | None:
    target = Path(args.path).resolve()
    program, out_dir = _default_paths(target, args.name, Path(args.output))
    db_path = Path(args.db) if args.db else out_dir / "graph.db"
    if not db_path.exists():
        _emit(f"error: no graph at {db_path} — run `dunneflow analyze` first")
        return None
    return Store(db_path), db_path


def cmd_touches(args: argparse.Namespace) -> int:
    opened = _open_store(args)
    if not opened:
        return 2
    store, _ = opened
    matches = _find_routine(store, args.routine)
    if not matches:
        _emit(f"no routine matching {args.routine!r}")
        return 1
    for m in matches[: args.limit]:
        reach, kinds = entry_reach(store, m["id"])
        print(f"\n{m['qualname']}  ({m['file']}:{m['line_start']})")
        print(f"  reaches {reach:,} routines")
        bounds = store.boundaries_reached(m["id"])
        if not bounds:
            print("  touches nothing outside itself")
            continue
        by_kind: dict[str, set[str]] = {}
        for b in bounds:
            by_kind.setdefault(b.kind.value, set()).add(b.target or b.evidence)
        for kind in sorted(by_kind):
            targets = sorted(t for t in by_kind[kind] if t)[:8]
            print(f"  {kind:10s} {', '.join(targets) if targets else '(dynamic)'}")
    store.close()
    return 0


def cmd_impact(args: argparse.Namespace) -> int:
    opened = _open_store(args)
    if not opened:
        return 2
    store, _ = opened
    matches = _find_routine(store, args.routine)
    if not matches:
        _emit(f"no routine matching {args.routine!r}")
        return 1
    for m in matches[: args.limit]:
        callers = store.callers_of(m["id"])
        print(f"\n{m['qualname']}  ({m['file']}:{m['line_start']})")
        print(f"  {len(callers):,} routines depend on this, directly or transitively")
        if callers:
            ph = ",".join("?" * len(callers))
            eps = store.query(
                f"SELECT DISTINCT name, kind FROM entrypoints WHERE routine_id IN ({ph})"
                " ORDER BY name",
                tuple(callers),
            )
            if eps:
                print(f"  ways in affected ({len(eps)}):")
                for e in eps[:20]:
                    print(f"    - {e['name']} [{e['kind']}]")
            plans = store.query(
                f"SELECT DISTINCT value FROM annotations WHERE owner_id IN ({ph})"
                " AND kind IN ('PLAN','DECISION','AUDIT_LOCK') ORDER BY value",
                tuple(callers),
            )
            if plans:
                vals = ", ".join(p["value"] for p in plans[:25])
                print(f"  governance implicated: {vals}")
    store.close()
    return 0


def _open_docs(args: argparse.Namespace) -> DocStore | None:
    target = Path(args.path).resolve()
    _program, out_dir = _default_paths(target, args.name, Path(args.output))
    path = out_dir / "docs.db"
    return DocStore(path) if path.exists() else None


def cmd_glossary(args: argparse.Namespace) -> int:
    """What this program's words mean, and who says so."""
    opened = _open_store(args)
    if not opened:
        return 2
    store, _ = opened
    docs = _open_docs(args)
    report = bind(store, docs)
    defined, total = report.coverage()
    print(f"{defined:,} of {total:,} terms are defined somewhere "
          f"({defined / total:.0%})" if total else "no terms found")
    for term in [t for t in report.terms if t.defined][: args.limit]:
        sense = term.senses[0]
        print(f"\n{term.term}  ({term.uses:,} uses)")
        print(f"  {sense.definition[:160]}")
        print(f"  [{sense.provenance.value}] {sense.source}:{sense.line}")
    if report.undefined:
        print(f"\nnothing defines these {len(report.undefined):,}:")
        print("  " + ", ".join(t.term for t in report.undefined[: args.limit * 3]))
        if len(report.undefined) > args.limit * 3:
            print(f"  ... see 10-glossary.md for all {len(report.undefined):,}")
    if docs is not None:
        docs.close()
    store.close()
    return 0


def cmd_naming(args: argparse.Namespace) -> int:
    """The naming standard: stated in documentation, measured against the code."""
    opened = _open_store(args)
    if not opened:
        return 2
    store, _ = opened
    docs = _open_docs(args)

    stated = docs.query(
        "SELECT r.text, r.lane, r.doc, r.line FROM doc_rules r"
        " JOIN documents d ON d.path = r.doc WHERE d.duplicate_of = ''"
        " ORDER BY r.lane, r.line"
    ) if docs is not None else []
    if stated:
        print("STATED — quoted from documentation")
        for r in stated:
            print(f"  [{r['lane']:10s}] {' '.join(str(r['text']).split())[:96]}")
            print(f"               {r['doc']}:{r['line']}")
    else:
        print("STATED — nothing in this program's documentation states a naming rule")

    m = measure(store)
    print("\nMEASURED — counted against the code")
    for c in m.conventions[: args.limit]:
        exc = (f"  ({len(c.exceptions)} exception"
               f"{'s' if len(c.exceptions) != 1 else ''})") if c.exceptions else ""
        print(f"  [{c.rating()}] {c.holds:,}/{c.total:,}  {c.claim}{exc}")
    if len(m.conventions) > args.limit:
        print(f"  ... {len(m.conventions) - args.limit} more; all of them in 11-naming.md")
    for g in m.gaps:
        spread = ", ".join(f"{k} {v}" for k, v in g.spread)
        print(f"  GAP  {g.population}: {g.total:,} counted — {spread}")
    if docs is not None:
        docs.close()
    store.close()
    return 0


def cmd_mirror(args: argparse.Namespace) -> int:
    """Vocabulary the documentation defines, and what the code does with it.

    The traceability report's mirror. Prints the spectrum, then the band that is
    actually a finding -- the words nothing in the program answers to -- because a
    reader opening this is looking for drift, not for confirmation that `groma` is
    a package name.
    """
    opened = _open_store(args)
    if not opened:
        return 2
    store, _ = opened
    docs = _open_docs(args)
    report = measure_mirror(store, docs)

    if not report.had_docs:
        print("no documentation was read, so there is nothing to mirror.")
        print("point analyze at a documentation root: --docs <path>")
        store.close()
        return 0

    groups = report.by_band()
    print(f"{report.definitions_seen:,} definitions read, "
          f"{report.excluded_total:,} set aside as not a word, "
          f"{len(report.terms):,} terms carried forward")
    for band in MIRROR_BANDS:
        print(f"  {band.label:8} {len(groups[band.key]):4}   {band.meaning}")

    absent = groups["ABSENT"]
    if absent:
        print(f"\ndefined in documentation, nowhere in the code ({len(absent):,}):")
        for term in absent[: args.limit]:
            source = term.definitions[0]
            print(f"\n  {term.term}")
            print(f"    {source.definition[:160]}")
            print(f"    {source.doc}:{source.line}")
        if len(absent) > args.limit:
            print(f"\n  ... see 13-mirror.md for all {len(absent):,}, "
                  "each with its definition and the line it came from")
    print("\nonly Python is extracted: absent from this graph is not absent from "
          "the product.")

    if docs is not None:
        docs.close()
    store.close()
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Anomalies only. Exits non-zero when something is BROKEN, so CI can gate on it."""
    opened = _open_store(args)
    if not opened:
        return 2
    store, _ = opened
    store.warm()
    report = detect(store, include_tests=args.include_tests)
    wanted = {BROKEN, SUSPECT, INFO} if args.all else (
        {BROKEN} if args.broken_only else {BROKEN, SUSPECT}
    )
    shown = [a for a in report.sorted() if a.severity in wanted]

    for a in shown[: args.limit]:
        where = f"  {a.file}:{a.line}" if a.file and a.line else (
            f"  {a.file}" if a.file else "")
        print(f"[{a.severity}/{a.confidence}] {a.kind}: {a.title}{where}")
        if args.verbose:
            print(f"    {a.detail}")
            print(f"    blind spot: {a.blind_spot}")
    if len(shown) > args.limit:
        print(f"... {len(shown) - args.limit} more (raise --limit to see them)")

    counts = report.counts()
    print(
        f"\n{counts.get(BROKEN, 0)} broken, {counts.get(SUSPECT, 0)} suspect, "
        f"{counts.get(INFO, 0)} informational"
    )
    store.close()
    return 1 if counts.get(BROKEN, 0) else 0


def cmd_query(args: argparse.Namespace) -> int:
    opened = _open_store(args)
    if not opened:
        return 2
    store, db_path = opened
    # A claim this tool prints from both stores has to be re-runnable from both
    # stores, or rule 13 is satisfied only on paper.
    if getattr(args, "docs", False):
        docs_path = Path(args.docs_db) if args.docs_db else db_path.parent / "docs.db"
        if not docs_path.exists():
            _emit(f"error: no document store at {docs_path}")
            store.close()
            return 2
        store.conn.execute("ATTACH DATABASE ? AS docs", (str(docs_path),))
    try:
        rows = store.query(args.sql)
    except Exception as exc:
        _emit(f"query failed: {exc}")
        store.close()
        return 1
    if not rows:
        print("(no rows)")
    else:
        keys = rows[0].keys()
        print(" | ".join(keys))
        for r in rows[: args.limit]:
            print(" | ".join(str(r[k]) for k in keys))
        if len(rows) > args.limit:
            print(f"... {len(rows) - args.limit} more rows")
    store.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dunneflow",
        description="Map what moves through a program: entrypoints, flows, and boundaries.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("path", help="the source tree to analyse")
        sp.add_argument("--name", help="program name (defaults to the directory name)")
        sp.add_argument("--output", default=str(DEFAULT_OUTPUT), help="output root")
        sp.add_argument("--db", help="graph database path")

    a = sub.add_parser("analyze", help="extract, resolve, and write the map")
    common(a)
    a.add_argument("--include-tests", action="store_true", help="include test files")
    a.add_argument("--jobs", type=int, default=None, help="parallel workers")
    a.add_argument("--no-render", action="store_true", help="build the graph only")
    a.add_argument("--docs", help="documentation root (defaults to the package root)")
    a.add_argument("--no-docs", action="store_true", help="skip documentation entirely")
    a.add_argument("--recheck-docs", action="store_true",
                   help="hash every document rather than trusting its modification time")
    a.add_argument("--quiet", action="store_true")
    a.set_defaults(func=cmd_analyze)

    t = sub.add_parser("touches", help="what does this routine reach?")
    common(t)
    t.add_argument("--routine", required=True, help="name or qualified name")
    t.add_argument("--limit", type=int, default=5)
    t.set_defaults(func=cmd_touches)

    i = sub.add_parser("impact", help="what breaks if I change this routine?")
    common(i)
    i.add_argument("--routine", required=True, help="name or qualified name")
    i.add_argument("--limit", type=int, default=5)
    i.set_defaults(func=cmd_impact)

    ck = sub.add_parser("check", help="report anomalies; non-zero exit if any are BROKEN")
    common(ck)
    ck.add_argument("--all", action="store_true", help="include informational findings")
    ck.add_argument("--broken-only", action="store_true", help="only BROKEN findings")
    ck.add_argument("--include-tests", action="store_true",
                    help="the graph included tests (changes dead-code reporting)")
    ck.add_argument("--verbose", action="store_true", help="show detail and blind spot")
    ck.add_argument("--limit", type=int, default=40)
    ck.set_defaults(func=cmd_check)

    g = sub.add_parser("glossary", help="what this program's words mean, and who says so")
    common(g)
    g.add_argument("--limit", type=int, default=20)
    g.set_defaults(func=cmd_glossary)

    nm = sub.add_parser("naming", help="the naming standard: stated, and measured")
    common(nm)
    nm.add_argument("--limit", type=int, default=15)
    nm.set_defaults(func=cmd_naming)

    mr = sub.add_parser(
        "mirror", help="words the documentation defines that the code does not use")
    common(mr)
    mr.add_argument("--limit", type=int, default=15)
    mr.set_defaults(func=cmd_mirror)

    q = sub.add_parser("query", help="ask the graph directly with SQL")
    q.add_argument("--docs", action="store_true",
                   help="attach the document store as `docs` for cross-store joins")
    q.add_argument("--docs-db", help="document database path (defaults beside the graph)")
    common(q)
    q.add_argument("--sql", required=True)
    q.add_argument("--limit", type=int, default=40)
    q.set_defaults(func=cmd_query)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
