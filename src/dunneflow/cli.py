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
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from . import revisions
from .anomalies import BROKEN, INFO, SUSPECT, detect
from .docstore import DocStore
from .migrate import MigrationRefused, migrate_program
from .render.markdown import render_all
from .resolve import version as program_version
from .resolve.calls import resolve_calls
from .resolve.cli import resolve_cli
from .resolve.entrypoints import entrypoints_from_packaging
from .resolve.flows import entry_reach
from .resolve.glossary import bind
from .resolve.mirror import BANDS as MIRROR_BANDS
from .resolve.mirror import measure as measure_mirror
from .resolve.naming import measure
from .sourcedb import STATE_FOR_COMPARISON, DocSourceStore, SourceStore
from .sourcedb import capture as capture_source
from .store import StaleGraphError, Store
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

    # Which snapshot this analysis writes, decided before anything is opened because it
    # names the files. The sidecar is the authority: `open_working` reuses the revision
    # that is already open, so analysing twice without sealing rewrites one snapshot
    # rather than leaving two half-filled ones -- and a sealed sidecar hands back a new
    # id, which is how a second point in time comes to exist beside the first.
    #
    # `--no-source` leaves nothing to ask, so the clock answers instead. The layout is
    # the same either way; what is missing is the state (WORKING / FOR_COMPARISON),
    # which only the sidecar records.
    # Where `pyproject.toml` lives, which may be above `src/`. Found once, here, because
    # three things want it: the entrypoint reader, the version reader, and the name of the
    # tree recorded below.
    pkg_root = target
    for candidate in (target, *target.parents):
        if (candidate / "pyproject.toml").exists():
            pkg_root = candidate
            break

    # The leaf that **identifies this tree**, and only the leaf: `target` is an absolute
    # path, and recording it would put one machine's directory layout into a map built to
    # be handed over (rule 60).
    #
    # The *package* root's leaf, not the analysed directory's. Analysing a `src/` layout
    # means `target` is `.../society-2026-08-26/src`, whose leaf is `src` -- which names
    # every src-layout program ever analysed and so identifies none of them. Measured on
    # the real corpus, which is the only place it shows: the toy fixtures have no `src/`
    # and recorded the right answer by having nowhere else to go.
    tree_leaf = pkg_root.name
    out_dir.mkdir(parents=True, exist_ok=True)
    source: SourceStore | None = None
    if not args.no_source:
        source = SourceStore(out_dir / "source.db")
        source.set_meta("program", program)
        revision = source.open_working(tree=tree_leaf)
    else:
        revision = revisions.stamp()

    db_path = (Path(args.db) if args.db
               else revisions.db_path(out_dir, revisions.GRAPH, revision))

    t0 = time.perf_counter()
    store = Store(db_path)
    # The identity, inside the file. The name is derived from this and not the other way
    # round, so a graph someone renamed can still say which snapshot it is (rule 30).
    store.set_meta("revision", revision)
    store.set_meta("program", program)
    #
    # `source_root` is **not** recorded here, and its absence is the decision. It is one
    # machine's directory layout: it leaks that layout to whoever the map is handed to, it
    # is wrong the moment the tree is moved, and it is wrong on every machine a copy
    # reaches. Every path in this graph is relative to it, and nothing at read time needs
    # it back -- bodies come from `source.db` by content hash, never by opening a path.
    # The one step that touches the disk is this one, and it is holding the root already.
    # See `migrate.py`.
    #
    # When this map was made. The cover says it out loud, because a map is a reading of
    # a program at a moment and a reader who cannot see the moment cannot judge the map.
    store.set_meta("analysed_at",
                   datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"))

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

    # Relative to the analysed tree, like every other stored path -- which for a
    # `src/` layout means `../pyproject.toml`, because packaging metadata sits
    # above the code. See the note there.
    entrypoints_from_packaging(pkg_root, store, relative_to=source_root)

    # What the program says its own version is, with the tier it was learned at. Recorded
    # even when it is nothing: two versions of a program are two directories, and a reader
    # holding both is entitled to whatever each one claims about itself -- or to being told
    # plainly that it claims nothing. Never asked of a VCS; see `resolve/version.py`.
    found = program_version.detect(source_root, package_root=pkg_root, leaf=tree_leaf)
    if found is not None:
        store.set_meta("program_version", found.value)
        store.set_meta("program_version_tier", str(found.provenance))
        store.set_meta("program_version_where", found.where)

    # Documentation is a parallel input, read from the package root because that is
    # where prose lives relative to `src/`. It is never a prerequisite: a program with
    # no documents yields an empty document store and a complete code map.
    doc_stats = None
    doc_store: DocStore | None = None
    docs_root: Path | None = None
    if not args.no_docs:
        docs_root = Path(args.docs).resolve() if args.docs else pkg_root
        doc_store = DocStore(revisions.db_path(out_dir, revisions.DOCS, revision))
        doc_store.set_meta("revision", revision)
        doc_store.set_meta("program", program)
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
            # Design rule 1: no filter is ever silent. A nested checkout can be most
            # of a corpus -- two stale worktrees were 335 of Mensores' 2,381 documents
            # -- and a reader comparing two points in time would otherwise read their
            # absence as the project having deleted them.
            for d in doc_stats.nested:
                where = Path(d)
                shown = (where.relative_to(docs_root)
                         if where.is_relative_to(docs_root) else where)
                _emit(f"  skipped {shown} — a checkout of its own, not this program")
        doc_store.optimize()

        # The **document** sidecar, the exact mirror of the source one below and driven the
        # same way: by the hashes the scan just recorded rather than by a second walk, so a
        # document whose body is already held is never opened again.
        #
        # `docs.db` records what a document *says* -- its headings, definitions, stated rules
        # and tables. Nothing anywhere held what it **is**, so 2,064 documents were mined and
        # unreadable: the glossary could quote a definition's line and then say, in as many
        # words, that it could not open the document it came from. Design rule 11 calls
        # documentation and source *equal inputs*, and source had a sidecar and a browser
        # while documentation had neither.
        #
        # Its own file rather than a lane in `source.db`, because design rule 14 turns on the
        # two being separately handable -- *"many will send documentation and never source"*.
        if not args.no_doc_source:
            docsource = DocSourceStore(out_dir / "docsource.db")
            docsource.set_meta("program", program)
            # Under the id `source.db` already chose, never one of its own: two sidecars
            # describing one analysis must name the same snapshot (see `adopt_revision`).
            docsource.adopt_revision(revision, tree=tree_leaf)
            doc_src_stats = capture_source(doc_store.known_hashes(), docsource,
                                           root=docs_root, revision=revision)
            dsc = docsource.counts()
            if not args.quiet:
                _emit(
                    f"documents: {dsc['blobs']:,} bodies for {dsc['paths']:,} paths "
                    f"({dsc['stored'] / 1e6:.1f} MB stored, {dsc['bytes'] / 1e6:.1f} MB of "
                    f"prose) — {doc_src_stats['stored']:,} read, "
                    f"{doc_src_stats['cached']:,} already held"
                    + (f", {doc_src_stats['missing']:,} unreadable"
                       if doc_src_stats["missing"] else "")
                )
            docsource.close()

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
            f"cli: {clistats.apps} apps, {clistats.commands_found} commands "
            f"({clistats.commands_attached} in a tree), "
            f"{clistats.mounts_resolved}/{clistats.mounts_total} mounts"
        )

    # The source sidecar. Driven by the hashes the graph just recorded rather than by a
    # second walk of the tree, so a file whose body is already held is never opened: a
    # re-analysis with nothing changed reads no source at all. Content-addressed, so this
    # is also the store the temporal layers will be built on.
    src_stats = None
    if source is not None:
        src_stats = capture_source(store.known_hashes(), source, root=source_root,
                                   langs=store.known_langs(), revision=revision)
        sc = source.counts()
        rev = revision
        if not args.quiet:
            _emit(
                f"source: {sc['blobs']:,} bodies for {sc['paths']:,} paths "
                f"({sc['stored'] / 1e6:.1f} MB stored, {sc['bytes'] / 1e6:.1f} MB of "
                f"source) — {src_stats['stored']:,} read, {src_stats['cached']:,} "
                f"already held"
                + (f", {src_stats['missing']:,} unreadable" if src_stats["missing"] else "")
            )
            # Which snapshot this went into, and how many there are. A sidecar quietly
            # holding one revision and a sidecar quietly replacing the only one it had
            # look identical from here, and they were the same thing until now.
            _emit(
                f"        revision {rev} of {sc['revisions']:,}"
                + (f", {sc['mapped']:,} path-revision rows in all"
                   if sc["revisions"] > 1 else "")
            )
        source.close()

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
        print(f"docs:  {revisions.db_path(out_dir, revisions.DOCS, revision)}")
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
    db_path = (Path(args.db) if args.db
               else revisions.newest(out_dir, revisions.GRAPH))
    if db_path is None:
        _emit(f"error: no graph in {out_dir} — run `dunneflow analyze` first")
        return None
    if not db_path.exists():
        _emit(f"error: no graph at {db_path} — run `dunneflow analyze` first")
        return None
    try:
        # Read-only: an orientation command must never drop the map it came to read.
        return Store(db_path, writable=False), db_path
    except StaleGraphError as exc:
        _emit(f"error: {exc}")
        return None


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
    path = revisions.newest(out_dir, revisions.DOCS)
    if path is None or not path.exists():
        return None
    try:
        return DocStore(path, writable=False)
    except StaleGraphError as exc:
        _emit(f"error: {exc}")
        return None


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
    """The naming standard **as found**: derived from the code, quoted from the documents.

    Neither lane is a requirement and neither is a comparison. Form is counted off the
    graph; Vocabulary is quoted out of whatever the project happens to have written down.
    Checking either against a standard a team supplies is not built -- see `BRIEFING.md`.
    """
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


def cmd_revisions(args: argparse.Namespace) -> int:
    """What snapshots this sidecar holds, and how to keep the current one.

    Listing opens the store **read-only**, which is not a detail: a writable open stamps a
    sidecar written before revisions were recorded, and that is a migration. Rule 20 says a
    read may refuse but may never repair, so asking what is there must not change what is
    there. `--seal` is the writable path, and it says what it did.
    """
    out_dir = Path(args.out_dir)
    db = out_dir / "source.db"
    if not db.exists():
        _emit(f"no source sidecar at {db} — analysed with --no-source, or handed over "
              f"without it")
        return 1

    if args.seal:
        # The instant those bodies were measured is not in this store, and inventing one
        # would be provenance nobody can check (rule 13). The graph beside it recorded
        # `analysed_at` when it read them, so state that rather than today's date.
        at = args.at or _analysed_at(revisions.newest(out_dir, revisions.GRAPH))
        source = SourceStore(db)
        try:
            rev = source.seal(label=args.label or "", at=at)
        except ValueError as exc:
            # "already sealed" and "nothing here" are different answers and the store
            # keeps them apart; printing one message for both would lose that.
            _emit(f"nothing to seal: {exc}")
            source.close()
            return 1
        source.commit()
        if rev is None:
            _emit("nothing to seal: this sidecar holds no paths")
            source.close()
            return 1
        _emit(f"sealed {rev} as {STATE_FOR_COMPARISON}"
              + (f" — “{args.label}”" if args.label else "")
              + ("" if at else "\n  its capture instant is unknown and stays unknown; "
                               "state one with --at"))
        _emit("the next `analyze` opens a fresh working revision beside it")
        source.close()
        return 0

    source = SourceStore(db, writable=False)
    rows = source.revisions()
    if not rows:
        _emit(f"{db} holds no revisions and no paths")
        source.close()
        return 1
    print(f"{'revision':22} {'state':16} {'captured':22} {'files':>6}  label")
    for r in rows:
        rev = r["revision"] or "(un-stamped)"
        cap = r["captured_at"] or "—"
        print(f"{rev:22} {r['state']:16} {cap:22} {r['files']:>6,}  {r['label']}")
        if r["note"]:
            print(f"  {r['note']}")
    if any(not r["stamped"] for r in rows):
        # The table goes to stdout and the advice to stderr, which two buffers will
        # otherwise interleave backwards -- advice about a listing, printed above it.
        sys.stdout.flush()
        _emit("\nrun `dunneflow revisions <dir> --seal` to give the current snapshot a "
              "name before it is replaced")
    source.close()
    return 0


def _analysed_at(graph_db: Path | None) -> str:
    """When the graph beside this sidecar says it read the source, or "" if it cannot say.

    A separate store, opened here and nowhere else: `sourcedb` must not reach into
    `graph.db`, and the CLI is the one caller that legitimately holds both paths.

    `None` -- no graph in the directory at all -- is the same answer as an unreadable
    one and gets the same empty string, because `seal` may only ever *fill* an empty
    `captured_at` and never overwrite a recorded instant. Stating today's date for a
    snapshot measured on some other day is the invented provenance rule 13 forbids.
    """
    if graph_db is None or not graph_db.exists():
        return ""
    try:
        conn = sqlite3.connect(f"file:{graph_db}?mode=ro", uri=True)
        row = conn.execute("SELECT value FROM meta WHERE key = 'analysed_at'").fetchone()
        conn.close()
    except sqlite3.Error:
        return ""
    return "" if row is None else str(row[0])


def cmd_query(args: argparse.Namespace) -> int:
    opened = _open_store(args)
    if not opened:
        return 2
    store, db_path = opened
    # A claim this tool prints from both stores has to be re-runnable from both
    # stores, or rule 13 is satisfied only on paper.
    if getattr(args, "docs", False):
        docs_path = (Path(args.docs_db) if args.docs_db
                     else revisions.newest(db_path.parent, revisions.DOCS))
        if docs_path is None or not docs_path.exists():
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
    a.add_argument("--no-source", action="store_true",
                   help="do not keep a copy of the source beside the map")
    # Its own switch rather than a second meaning for `--no-source`, and design rule 14 is
    # the reason: the two corpora are handed over separately, and "send the documentation
    # but not the code" is the posture that rule names as common. One switch governing both
    # would make that posture unreachable at the point the bodies are written.
    a.add_argument("--no-doc-source", action="store_true",
                   help="do not keep a copy of the documents beside the map")
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

    nm = sub.add_parser("naming",
                        help="the naming standard as found: derived, and quoted")
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

    rv = sub.add_parser(
        "revisions", help="what snapshots the source sidecar holds, and keep the current one")
    rv.add_argument("out_dir", help="an analysed program's output directory")
    rv.add_argument("--seal", action="store_true",
                    help="keep the current snapshot under its own name, so the next "
                         "analysis is a second one rather than a replacement")
    rv.add_argument("--label", help="a name for the sealed snapshot")
    rv.add_argument("--at", help="when its bodies were measured, if the graph cannot say")
    rv.set_defaults(func=cmd_revisions)

    mg = sub.add_parser(
        "migrate", help="rewrite a program directory's stored paths as relative, in place")
    mg.add_argument("out_dir", help="an analysed program's output directory")
    mg.set_defaults(func=cmd_migrate)

    sv = sub.add_parser("serve", help="open the interactive map in a browser")
    sv.add_argument("out_dir", help="an analysed program's output directory")
    sv.add_argument("--port", type=int, default=8787)
    sv.add_argument("--no-open", action="store_true", help="do not open a browser")
    sv.add_argument("--revision", default=None,
                    help="which point in time to open as the base (default: the newest). "
                         "The reader can switch it from the page; this is how a chosen "
                         "base survives a restart of the server.")
    sv.set_defaults(func=cmd_serve)
    return p


def cmd_migrate(args: argparse.Namespace) -> int:
    """Make every stored path in one program directory relative to its own tree.

    In place, rather than by re-analysis, and that is the point rather than a shortcut: a
    sealed snapshot is kept so it can be read after its source tree is gone, and rebuilding
    would orphan exactly those. Nothing about what a fact *is* changes -- only the spelling
    of a path column -- so this is rule 25's argument applied to a derived store.

    Says what it did per store, because a migration that reports only "done" is one nobody
    can check, and this one rewrites tens of thousands of rows in a file the reader cannot
    rebuild.
    """
    out_dir = Path(args.out_dir)
    if not out_dir.is_dir():
        _emit(f"error: {out_dir} is not a directory")
        return 2
    try:
        report = migrate_program(out_dir)
    except MigrationRefused as exc:
        _emit(f"refused: {exc}")
        return 2

    if not report.stores:
        _emit(f"no stores in {out_dir} — nothing to migrate")
        return 1
    for st in report.stores:
        if st.already:
            _emit(f"  {st.path.name}: already relative")
            continue
        _emit(f"  {st.path.name}: {st.total:,} paths rewritten "
              f"across {len(st.rewritten)} columns")
        for col, n in sorted(st.rewritten.items(), key=lambda kv: -kv[1]):
            _emit(f"      {n:>8,}  {col}")
        for col, n in sorted(st.above.items(), key=lambda kv: -kv[1]):
            _emit(f"      {n:>8,}  {col} — above the analysed tree, now `../…`")
    done = report.migrated
    if done:
        _emit(f"\n{report.total:,} paths are now relative to the tree each store was read "
              f"from, across {len(done)} stores. The tree itself is no longer recorded "
              f"anywhere — nothing at read time needs it.")
    else:
        _emit("\nnothing to do: every store here already holds relative paths")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Open the map. Read-only throughout -- serving can never damage what it shows."""
    from .web.serve import serve
    try:
        serve(Path(args.out_dir), port=args.port,
              open_browser=not args.no_open, revision=args.revision, emit=_emit)
    except (FileNotFoundError, StaleGraphError) as exc:
        _emit(f"error: {exc}")
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
