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
import json
import multiprocessing
import sqlite3
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from . import revisions
from .anomalies import BROKEN, INFO, SUSPECT, detect
from .docstore import DocStore
from .migrate import MigrationRefused, migrate_program
from .render.index import legacy_map_files, render_index
from .render.markdown import render_all
from .render.snapshot import mapless, render_maps
from .resolve import version as program_version
from .resolve.calls import resolve_calls
from .resolve.cli import resolve_cli
from .resolve.entrypoints import entrypoints_from_packaging
from .resolve.flows import entry_reach
from .resolve.glossary import bind
from .resolve.mirror import BANDS as MIRROR_BANDS
from .resolve.mirror import measure as measure_mirror
from .resolve.naming import measure
from .runtime import default_output_root, tool_version
from .sourcedb import STATE_FOR_COMPARISON, DocSourceStore, SourceStore
from .sourcedb import capture as capture_source
from .standards import STANDARDS_DB, standards_refusal
from .store import StaleGraphError, Store, UnfinishedMapError, unfinished_sentence
from .walk import analyze_docs_tree, analyze_tree


def _default_paths(target: Path, name: str | None, out_root: Path) -> tuple[str, Path]:
    program = name or target.resolve().name
    return program, out_root / program


def _emit(msg: str) -> None:
    print(msg, file=sys.stderr)


def _out_root(args: argparse.Namespace) -> Path:
    """Where this run's maps go, and **said out loud when nobody chose it.**

    `--output` used to default to the literal `output`, relative to whatever working
    directory the command was run from. That is right for a checkout and meaningless for a
    double-clicked application, which has no working directory worth the name -- so the
    default now comes from `runtime.default_output_root()`, which answers differently in
    the two worlds.

    Two answers to one question is a thing this project distrusts on sight, so the fallback
    **names the directory it chose**. A default that quietly moves between a terminal run
    and an application is exactly the sort of silence that costs a session hunting for a map
    that was written somewhere else.
    """
    if args.output:
        return Path(args.output)
    root = default_output_root()
    _emit(f"no --output given; maps go to {root}")
    return root


def _args_said(args: argparse.Namespace) -> str:
    """What this run was told, as a short readable phrase.

    Only what **removes** something. A map with no documents and a map analysed
    `--no-docs` look identical from the inside, and only one of them is a program that has
    no documentation -- design rule 1 again, one store over.
    """
    said = []
    if args.include_tests:
        said.append("tests included")
    if args.no_docs:
        said.append("documentation not read")
    elif args.docs:
        said.append(f"documentation from {Path(args.docs).name}")
    if args.no_source:
        said.append("source bodies not kept")
    if args.no_doc_source:
        said.append("document bodies not kept")
    if args.no_render:
        said.append("map not written")
    return "; ".join(said)


# -- what an analysis is doing, for whoever is watching it ------------------ #
#
# The dashboard runs `analyze` as a subprocess and draws a bar against these. The labels
# and the count both come from here and are **printed as sent** all the way to the screen,
# so there is one answer to "what does an analysis involve" and no copy of it downstream to
# fall behind (rule 51). `serve.py`'s `BUILD_STEPS` is the same shape one subject over.

STEP_EXTRACT = "reading the source tree"
STEP_DOCS = "reading the documents"
STEP_DOC_BODIES = "capturing the document bodies"
STEP_STANDARDS = "reading the standards"
STEP_RESOLVE = "resolving calls and command trees"
STEP_BODIES = "capturing the source bodies"
STEP_RENDER = "writing the map"
STEP_ANOMALIES = "looking for anomalies"

# Every label that exists, so a step advanced under a name nobody declared is caught here
# rather than becoming a bar that silently never moves.
ALL_STEPS = frozenset({
    STEP_EXTRACT, STEP_DOCS, STEP_DOC_BODIES, STEP_STANDARDS, STEP_RESOLVE,
    STEP_BODIES, STEP_RENDER, STEP_ANOMALIES,
})


def analysis_steps(args: argparse.Namespace) -> tuple[str, ...]:
    """The steps *this* run will take, in order.

    **Computed for the run, never a constant**, and that is rule 32 rather than
    fastidiousness: four flags remove work. `--no-docs` drops two of these, `--no-source`
    and `--no-render` one each. A fixed tuple would put a total on the bar that a
    `--no-docs` run can never reach -- and a progress bar that stops at five of seven is
    indistinguishable from a run that died at step five.
    """
    steps = [STEP_EXTRACT]
    if not args.no_docs:
        steps.append(STEP_DOCS)
        if not args.no_doc_source:
            steps.append(STEP_DOC_BODIES)
    # A step the reader *adds* rather than one a flag removes, which is the same argument
    # from the other side: a run given no standard must not show a step it will never take.
    if getattr(args, "standards", None):
        steps.append(STEP_STANDARDS)
    steps.append(STEP_RESOLVE)
    if not args.no_source:
        steps.append(STEP_BODIES)
    if not args.no_render:
        steps.append(STEP_RENDER)
    steps.append(STEP_ANOMALIES)
    return tuple(steps)


class _Progress:
    """`--progress-json`: one JSON object per line on **stdout**, or nothing at all.

    Two channels, and keeping them apart is the whole point. stdout is the machine
    channel; stderr keeps the prose it has always printed and stays governed by
    `--quiet`, which is where a failure's reason comes from. Scraping the prose instead
    would make a sentence written for a human into a contract (rule 30).

    Flushed every line. A buffered pipe reports nothing for ninety seconds and then
    everything at once, which is a progress report that is only correct after it stops
    being needed.

    **The step label is asserted against the list**, because a step advanced under a name
    `analysis_steps` did not produce is a bar that silently never moves -- the shape of
    rule 44, arriving from the other end.
    """

    def __init__(self, steps: tuple[str, ...], on: bool) -> None:
        self.steps = steps
        self.on = on
        self.i = 0
        self.label = steps[0] if steps else ""
        # Where a step is also **recorded**, so a map that never finished can name where it
        # stopped. Wired to the store once there is one -- the reporter is built before the
        # graph is opened, because it has to be able to report the opening.
        #
        # `None` until then, and nothing here fills it in: a `_Progress` with no store has
        # nothing to record into, and a fallback that wrote somewhere plausible instead
        # would hide exactly the run this exists for (rule 49).
        self.mark: Callable[[str, str], None] | None = None

    def _say(self, **fields: object) -> None:
        if not self.on:
            return
        print(json.dumps(fields), flush=True)

    def step(self, label: str) -> None:
        """Advance to a named step. A step this run is not taking is not an error here."""
        assert label in ALL_STEPS, f"unknown analysis step {label!r}"
        if label not in self.steps:
            return
        self.i = self.steps.index(label)
        self.label = label
        # Committed as it goes, so a killed run leaves a map that can say *"stopped while
        # reading the documents"* rather than only *"stopped"*. Seven commits over a
        # ninety-second run.
        if self.mark is not None:
            self.mark("step", label)
        self._say(state="working", step=label, done_steps=self.i,
                  steps=len(self.steps), detail="")

    def detail(self, done: int, total: int) -> None:
        """Restate the current step with a count. The step is unchanged; only the inside."""
        self._say(state="working", step=self.label, done_steps=self.i,
                  steps=len(self.steps), detail=f"{done:,}/{total:,}")

    def done(self, **fields: object) -> None:
        self._say(state="done", step="", done_steps=len(self.steps),
                  steps=len(self.steps), **fields)


def cmd_analyze(args: argparse.Namespace) -> int:
    target = Path(args.path).resolve()
    if not target.exists():
        _emit(f"error: {target} does not exist")
        return 2

    source_root = target
    out_root = _out_root(args)
    program, out_dir = _default_paths(target, args.name, out_root)
    # What this run will do, decided before it starts doing it: the dashboard draws a bar
    # against this list and it has to be right from the first line.
    prog = _Progress(analysis_steps(args), on=args.progress_json)

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

    # **Every standards root is judged before anything is opened**, and a single refusal
    # stops the run. Checking them here rather than beside the scan is deliberate: by the
    # time the corpus is being read there is a graph, a source snapshot and a document
    # store on disk, and refusing then would either abandon a half-written map or -- worse
    # -- carry on with the offending root dropped, reporting part of a standard as the
    # whole of one. Rule 20: a read may refuse, but it may never repair.
    standards_roots: list[Path] = []
    if getattr(args, "standards", None):
        would_read_docs = None if args.no_docs else (
            Path(args.docs).resolve() if args.docs else pkg_root)
        standards_out_root = out_root.resolve()
        refused = False
        for given in args.standards:
            root = Path(given).resolve()
            why = standards_refusal(root, tree=target,
                                    out_root=standards_out_root,
                                    docs_root=would_read_docs)
            if why:
                _emit(f"error: --standards {given} refused — {why}")
                refused = True
            else:
                standards_roots.append(root)
        if refused:
            return 2

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
    # **Unfinished until proven otherwise, and committed now.** Rule 80. A killed `analyze` leaves a
    # graph that opens perfectly and reports a program that calls nothing -- see
    # `UnfinishedMapError`. This is the only thing that can speak for a run that does not
    # reach its own last line, so it is written before any work starts and committed on the
    # spot: an uncommitted marker is lost by exactly the `kill -9` it exists for.
    store.set_meta_now("complete", "")
    prog.mark = store.set_meta_now

    # -- what read this map, and whether anything was guessed ---------------- #
    #
    # **A standing guarantee, not a placeholder waiting for a model.** Nothing on this path
    # calls a model or touches a network: the extractors are stdlib `ast` and `tokenize`,
    # the document scanner is hand-written, and `Provenance`'s two paid tiers (CITED,
    # INFERRED) are declared and unbuilt. So `inference` says `none` because that is the
    # fact, and design rule 21 says a thing worth knowing is stated rather than left absent.
    #
    # `model` is written **empty** rather than omitted, and the difference is the whole
    # reason it is here: a key that is missing means *this map predates the question* and a
    # key that is blank means *nothing read it but the code* -- two different facts that a
    # reader would otherwise have to tell apart by the absence of a row (rule 30). When a
    # reader ever turns inference on, voluntarily, this is where the answer goes.
    store.set_meta("tool_version", tool_version())
    store.set_meta("inference", "none")
    store.set_meta("model", "")
    # What the run was told, so a thin map can say it was asked to be thin rather than
    # leaving a reader to wonder why a program has no documents (design rule 1).
    store.set_meta("analysis_args", _args_said(args))

    def progress(path: str, i: int, total: int) -> None:
        if i % 50 == 0 or i == total:
            prog.detail(i, total)
        if args.quiet:
            return
        if i % 50 == 0 or i == total:
            _emit(f"  extracting {i}/{total}")

    prog.step(STEP_EXTRACT)
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
        # **Every map under the output root, kept out of this run's corpus.** Not just this
        # program's directory: `output/mensores` is where this map goes and `output/` is
        # where every *other* map goes, and reading a report about some other program as
        # documentation about this one is the same mistake one directory up. Analysing
        # DunneFlow itself read 46 of 54 documents that way.
        #
        # Directories holding a graph, never the *name* `output` -- so a folder of
        # hand-written prose sitting beside two program directories is still read.
        # `analyze_docs_tree` has taken a `progress` callback since it was written and was
        # never given one, so on a 2,064-document corpus the bar sat still through most of
        # a minute. The terminal never noticed -- there was nothing drawing a bar.
        def doc_progress(path: str, i: int, total: int) -> None:
            if i % 50 == 0 or i == total:
                prog.detail(i, total)

        prog.step(STEP_DOCS)
        doc_stats = analyze_docs_tree(
            docs_root, doc_store, jobs=args.jobs, recheck=args.recheck_docs,
            progress=doc_progress,
            exclude=frozenset({out_dir}) | revisions.program_dirs(out_dir.parent))
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
            prog.step(STEP_DOC_BODIES)
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

    # **The standard, read into a store of its own.** Everything above describes what this
    # program says about itself; this is what somebody else says every program must do, and
    # the two are never mixed -- see `standards.py` for why that is a file and not a column.
    #
    # The same walk, deliberately: `discover_docs` already refuses a nested checkout on the
    # `.git`-file marker (rule 57), and a standards directory is exactly as likely to have
    # a worktree under it as a project is. Writing a second scanner would be a second answer
    # to "what is a document" (rule 51).
    standards_store: DocStore | None = None
    if standards_roots:
        prog.step(STEP_STANDARDS)
        standards_store = DocStore(out_dir / STANDARDS_DB)
        standards_store.set_meta("revision", revision)
        standards_store.set_meta("program", program)
        # What was read, so the store can say whose standard it holds rather than only
        # what it says. A reader looking at a rule has to be able to ask where it came from.
        standards_store.set_meta("roots", "\n".join(str(r) for r in standards_roots))
        std_found = std_read = 0
        for root in standards_roots:
            st = analyze_docs_tree(
                root, standards_store, jobs=args.jobs, recheck=args.recheck_docs,
                exclude=frozenset({out_dir}) | revisions.program_dirs(out_dir.parent))
            std_found += st.found
            std_read += st.parsed
            # Design rule 1 again, and it matters more here than for the corpus: a reader
            # who named this directory is owed the news that part of it was skipped.
            for d in st.nested:
                where = Path(d)
                shown = where.relative_to(root) if where.is_relative_to(root) else where
                _emit(f"  skipped {shown} — a checkout of its own, not a standard")
        standards_store.mark_duplicates()
        sc = standards_store.counts()
        if not args.quiet:
            _emit(
                f"standards {std_found} documents from "
                f"{len(standards_roots)} director{'y' if len(standards_roots) == 1 else 'ies'} "
                f"(read {std_read}): {sc['doc_rules']:,} stated rules"
            )
        standards_store.optimize()
        # Left **open** until the map is written: `11-naming.md` reports the comparison, and
        # a store closed here would make the report the one surface that could not see the
        # standard it was given. Closed beside `doc_store` below, where the other corpus is.

    prog.step(STEP_RESOLVE)
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
    # What the index will say about every snapshot here, taken from the handle already
    # open. A second read-only handle to a database this process is holding is 36x slower
    # (rule 58), and it would also have to be opened after the close below to be correct --
    # two reasons to ask now and one answer.
    rev_rows: tuple[dict[str, object], ...] = ()
    if source is not None:
        prog.step(STEP_BODIES)
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
        rev_rows = tuple(source.revisions())
        source.close()

    if not args.no_render:
        prog.step(STEP_RENDER)
        t2 = time.perf_counter()
        store.warm()
        # **Into a directory named for this revision**, so a second analysis writes a
        # second map rather than over the first one's. The databases have been
        # revision-named since the spine went in; the written map was not, and a sealed
        # snapshot -- which exists to be readable after its source tree is gone -- kept its
        # graph and lost the documents a reader actually reads.
        #
        # Decided here rather than inside `render_all`, which writes the map into the
        # directory it is handed and should go on knowing nothing about revisions: *which*
        # directory is a question about time, and this is the caller that knows the answer.
        map_out = revisions.map_dir(out_dir, revision)
        files = render_all(store, map_out, program,
                           include_tests=args.include_tests,
                           docs=doc_store, standards=standards_store)
        # And the listing that says which map is which. Written every time, because a
        # revision's *state* changes underneath it -- sealing one makes every earlier
        # listing wrong about which snapshot is the working one.
        index = render_index(out_dir, program, rows=rev_rows)
        if not args.quiet:
            _emit(f"wrote {len(files)} documents to {map_out} in "
                  f"{time.perf_counter() - t2:.1f}s")
            stale = legacy_map_files(out_dir)
            if stale:
                # Named rather than removed, and named rather than left silent: these are
                # a real map of a revision nothing records, and the reader decides.
                _emit(f"        {index.name} lists this directory's maps; {len(stale)} "
                      f"documents from before maps were named are still beside it")

    prog.step(STEP_ANOMALIES)
    store.warm()
    rep = detect(store, include_tests=args.include_tests)
    ac = rep.counts()
    if not args.quiet and any(ac.values()):
        _emit(
            f"anomalies: {ac.get(BROKEN, 0)} broken, {ac.get(SUSPECT, 0)} suspect, "
            f"{ac.get(INFO, 0)} informational"
        )

    c = store.counts()
    # **stdout is one channel or the other, never both.** With `--progress-json` it is the
    # machine channel and these four lines would arrive in the middle of it; without it,
    # they are the summary the terminal has always printed. The counts are the same either
    # way -- one is the sentence and one is the object (rule 13).
    if prog.on:
        prog.done(program=program, revision=revision, graph=str(db_path),
                  routines=c["routines"], calls=c["resolved_calls"],
                  boundaries=c["boundaries"], structures=c["structures"],
                  entrypoints=c["entrypoints"],
                  files=stats.found, documents=doc_stats.found if doc_stats else 0)
    else:
        print(
            f"{program}: {c['routines']:,} routines · {c['resolved_calls']:,} internal "
            f"calls · {c['boundaries']:,} boundary touches · {c['structures']:,} "
            f"structures · {c['entrypoints']:,} ways in"
        )
        print(f"graph: {db_path}")
        if doc_stats is not None:
            print(f"docs:  {revisions.db_path(out_dir, revisions.DOCS, revision)}")
        if not args.no_render:
            # The map this run wrote, not the directory's index. Both are `README.md` and
            # they answer different questions -- one is the overview of *this* revision, the
            # other the list of every revision here -- so the line that says "start reading
            # here" has to name the one inside the map (rule 30, and the reason the index
            # says what it is in its own first heading).
            print(f"map:   {revisions.map_dir(out_dir, revision)}/README.md")
            print(f"index: {out_dir}/README.md")
    if doc_store is not None:
        doc_store.close()
    if standards_store is not None:
        standards_store.close()
    # The last act before the store is closed, and committed like its opposite above. Every
    # reader that presents this map as finished asks for this one value.
    store.set_meta_now("complete", "yes")
    store.close()
    return 0


_ROUTINE_COLUMNS = "id, name, qualname, module, file, line_start"


@dataclass(frozen=True, slots=True)
class Found:
    """What a routine search found, and **how it found it**.

    The rows alone were the defect. `_find_routine` matched a qualname or a name exactly
    and, on no hit, fell back to a substring search -- silently -- so
    `touches --routine mensores.cli.app` answered about **`mensores.cli.apply.apply`** and
    reported a reach of 1. `app` is a Typer object rather than a routine, so nothing could
    match it and the fallback returned something plausible instead: rule 49's shape (a
    fallback that yields a plausible value has hidden the failure it was written for)
    inside rule 5's (never match on a bare common name), in the one command a reader would
    use to check an executable's reach.

    The fallback is kept, because a half-remembered name is a real way to arrive. What it
    may not do is wear an exact match's clothes, so `exact` travels with the rows and the
    caller says which it is holding.

    `total` is how many the search really matched, before the query's own cap and before
    `--limit` -- a count must say what it counts (rule 32), and *showing 1* over a search
    that matched forty is the same silence one level down.

    `module` is the true answer to the case that bit. A needle shaped `<module>.<tail>`
    whose head **is** a module in this map is not a misspelling; it is a name that belongs
    to something the map does not hold as a routine, and saying so is worth more than any
    number of near-misses. Read from `routines.module`, never guessed.
    """

    matches: list[dict]
    exact: bool
    total: int
    module: str
    module_file: str
    module_routines: int


def _find_routine(store: Store, needle: str) -> Found:
    rows = store.query(
        f"SELECT {_ROUTINE_COLUMNS} FROM routines"
        " WHERE qualname = ? OR name = ? ORDER BY qualname LIMIT 25",
        (needle, needle),
    )
    if rows:
        # Counted, not `len(rows)`, for the same reason as the name search below: the
        # LIMIT has already decided that number. `touches --routine resolve --limit 2`
        # over four routines called `resolve` showed two and said nothing (rule 32).
        exact_total = store.query(
            "SELECT COUNT(*) AS n FROM routines WHERE qualname = ? OR name = ?",
            (needle, needle),
        )[0]["n"]
        return Found([dict(r) for r in rows], exact=True, total=exact_total,
                     module="", module_file="", module_routines=0)

    rows = store.query(
        f"SELECT {_ROUTINE_COLUMNS} FROM routines"
        " WHERE qualname LIKE ? ORDER BY qualname LIMIT 25",
        (f"%{needle}%",),
    )
    # Counted rather than inferred from `len(rows)`, which the LIMIT above has already
    # decided (rule 32). The two are equal until they are not, and that is the point.
    total = store.query(
        "SELECT COUNT(*) AS n FROM routines WHERE qualname LIKE ?", (f"%{needle}%",),
    )[0]["n"]

    module, module_file, module_routines = "", "", 0
    if "." in needle:
        head = needle.rsplit(".", 1)[0]
        # **`files`, not `routines`** -- and that is the whole of why this fires. A package
        # module declares no routines of its own, so asking `routines.module` says "not a
        # module here" about `mensores.cli`, which is a file this analysis read. `files`
        # is where a module is recorded as having been read at all; how many routines it
        # holds is the *next* question and often the answer (rule 32).
        seen = store.query("SELECT path FROM files WHERE module = ? LIMIT 1", (head,))
        if seen:
            module, module_file = head, str(seen[0]["path"])
            # `<module>` is excluded, and that is not tidiness. It is the module's own
            # top-level code wearing a routine's shape -- nobody declared it -- so
            # counting it would answer *"declares 1 routine"* about a package `__init__`
            # holding a docstring and two assignments, which is the opposite of the
            # sentence's job. `<module>` is answered as what it is everywhere else.
            module_routines = store.query(
                "SELECT COUNT(*) AS n FROM routines WHERE module = ? AND name != ?",
                (head, "<module>"),
            )[0]["n"]

    return Found([dict(r) for r in rows], exact=False, total=total,
                 module=module, module_file=module_file,
                 module_routines=module_routines)


def _search_said(needle: str, found: Found, shown: int) -> list[str]:
    """What to say above rows that are not what was asked for. Empty for an exact match.

    One place, because `touches` and `impact` share `_find_routine` and shared exactly
    this defect (rule 51). Printed to **stdout** with the answer rather than to stderr:
    a reader who pipes the answer to a file must not lose the sentence saying it is a
    name search.
    """
    if found.exact:
        # An exact match needs no caveat -- but a *bounded* one does. Two answers where
        # the reader asked about a name four routines share is not four answers.
        if shown < found.total:
            return [f"{found.total:,} routines are named {needle!r}; showing {shown:,}."]
        return []
    said = [f"no routine is named {needle!r}."]
    if found.module:
        # The measured statement, and the reason this is worth a line of its own: the
        # needle names a real module and something in it that is not a routine -- a Typer
        # app, a class attribute, a module-level object. That is an answer; the
        # near-misses below are not.
        tail = needle.rsplit(".", 1)[1]
        holds = (f"declares {found.module_routines:,} routine"
                 f"{'' if found.module_routines == 1 else 's'}"
                 if found.module_routines else "declares no routines at all")
        said.append(f"  {found.module} is a module here — {found.module_file} — and "
                    f"{holds}; nothing in it is named {tail!r}.")
    if found.matches:
        more = f", showing {shown:,}" if shown < found.total else ""
        said.append(f"  {found.total:,} routine name"
                    f"{' contains' if found.total == 1 else 's contain'} it{more} — "
                    f"a name search, not the routine you asked for:")
    return said


def _open_store(args: argparse.Namespace, *,
                finished_only: bool = True) -> tuple[Store, Path] | None:
    """The read path every orientation command shares.

    **`finished_only` defaults to refusing**, because every command that comes through here
    presents its answer as a fact about a program: `touches`, `impact`, `glossary`,
    `naming`, `mirror` and `check` all do. An unfinished map answers all six confidently
    and wrongly -- `check` most expensively, since it is the one that gates CI and would
    report a half-read program as `0 broken`.

    `query` is the one caller that passes `False`, and it **says so out loud** rather than
    reading in silence: its whole contract is that you get the rows that are there.
    """
    target = Path(args.path).resolve()
    program, out_dir = _default_paths(target, args.name, _out_root(args))
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
        store = Store(db_path, writable=False)
    except StaleGraphError as exc:
        _emit(f"error: {exc}")
        return None
    if store.finished() == "":
        # The step is read **before** anything is closed. It was read after, once, and
        # `check` died on a closed connection while trying to explain why it was refusing.
        said = unfinished_sentence(program, store.get_meta("step") or "")
        if finished_only:
            store.close()
            _emit(f"error: {said}")
            return None
        # Read anyway, and say what is being read. An escape hatch that quietly hands over
        # a half-written map is not an escape hatch, it is a trap.
        _emit(f"warning: {said}")
    return store, db_path


def cmd_touches(args: argparse.Namespace) -> int:
    opened = _open_store(args)
    if not opened:
        return 2
    store, _ = opened
    found = _find_routine(store, args.routine)
    if not found.matches and not found.module:
        _emit(f"no routine matching {args.routine!r}")
        return 1
    shown = found.matches[: args.limit]
    for line in _search_said(args.routine, found, len(shown)):
        print(line)
    if not shown:
        # The module sentence *is* the answer here, and there is nothing to list under it.
        store.close()
        return 1
    for m in shown:
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
    found = _find_routine(store, args.routine)
    if not found.matches and not found.module:
        _emit(f"no routine matching {args.routine!r}")
        return 1
    shown = found.matches[: args.limit]
    for line in _search_said(args.routine, found, len(shown)):
        print(line)
    if not shown:
        # The module sentence *is* the answer here, and there is nothing to list under it.
        store.close()
        return 1
    for m in shown:
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
    _program, out_dir = _default_paths(target, args.name, _out_root(args))
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
    # Never a silent filter (design rule 1). The count travels with the list it was taken
    # out of, and it names the one place a reader can read the words themselves.
    if report.set_aside:
        print(f"\n{len(report.set_aside):,} more were held back as fragments of compound "
              f"constant names — see 10-glossary.md, 'Words held back'")
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
    # The one reader that will open an unfinished map, because its whole contract is that
    # you get the rows that are there. It warns rather than refusing, and rather than
    # reading in silence -- see `_open_store`.
    opened = _open_store(args, finished_only=False)
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
        sp.add_argument("--output", default=None,
                        help="output root (default: ./output, or "
                             "~/Library/Application Support/DunneFlow "
                             "in a packaged application)")
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
    # Repeatable, because an organisation files its standards in more than one place and
    # naming one root the union of several would make the reader build a directory that
    # exists only to satisfy this tool.
    a.add_argument("--standards", action="append", metavar="DIR",
                   help="a directory of naming standards to measure this program against "
                        "(repeatable); read into standards.db, never into the corpus")
    a.add_argument("--no-source", action="store_true",
                   help="do not keep a copy of the source beside the map")
    # Its own switch rather than a second meaning for `--no-source`, and design rule 14 is
    # the reason: the two corpora are handed over separately, and "send the documentation
    # but not the code" is the posture that rule names as common. One switch governing both
    # would make that posture unreachable at the point the bodies are written.
    a.add_argument("--no-doc-source", action="store_true",
                   help="do not keep a copy of the documents beside the map")
    a.add_argument("--quiet", action="store_true")
    # The machine channel, for `dunneflow serve`, which runs this as a subprocess and draws
    # a bar against what it says. On stdout, because stderr is where the prose goes and a
    # failure's reason has to survive somewhere a parser is not reading (see `_Progress`).
    a.add_argument("--progress-json", action="store_true",
                   help="report progress as one JSON object per line on stdout")
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

    rn = sub.add_parser(
        "render", help="write the map of a revision whose graph is already here")
    rn.add_argument("out_dir", help="an analysed program's output directory")
    rn.add_argument("--revision", default=None,
                    help="which snapshot to write the map of (default: every revision "
                         "here that has a graph and no map). Naming one that already has "
                         "a map rewrites it.")
    rn.add_argument("--include-tests", action="store_true",
                    help="report anomalies in test code too, as `analyze` does")
    rn.set_defaults(func=cmd_render)

    mg = sub.add_parser(
        "migrate", help="rewrite a program directory's stored paths as relative, in place")
    mg.add_argument("out_dir", help="an analysed program's output directory")
    mg.set_defaults(func=cmd_migrate)

    sv = sub.add_parser("serve", help="open the interactive map in a browser")
    sv.add_argument("out_dir", nargs="?", default=None,
                    help="an analysed program's directory, or the output root holding "
                         "several (default: the output root)")
    sv.add_argument("--port", type=int, default=8787)
    sv.add_argument("--no-open", action="store_true", help="do not open a browser")
    sv.add_argument("--revision", default=None,
                    help="which point in time to open as the base (default: the newest). "
                         "The reader can switch it from the page; this is how a chosen "
                         "base survives a restart of the server.")
    sv.set_defaults(func=cmd_serve)
    return p


def cmd_render(args: argparse.Namespace) -> int:
    """Write the map of a revision this directory already holds a graph for.

    **Not analysis.** No source is read, no fingerprint is re-stamped and every store this
    opens is opened read-only, so rules 25 and 62 -- which forbid re-analysing a sealed
    snapshot in place -- are untouched and rule 20 is satisfied by construction.

    With no `--revision` it renders **every revision that has a graph and no map**, which is
    the job it was built for: a program directory whose maps were overwritten before they
    had names, given back what it lost. Naming one renders that one and rewrites its map if
    it has one, so a re-render is always something the reader asked for by name.

    The listing is rebuilt from the sidecar, whose rows carry the state and label a
    filename cannot (`revisions.revision_of` returns a *claim*, and the authority is inside
    the file).
    """
    out_dir = Path(args.out_dir)
    if not out_dir.is_dir():
        _emit(f"error: {out_dir} is not a directory")
        return 2

    wanted: list[str] | None = None
    if args.revision:
        wanted = [args.revision]
        if not revisions.db_path(out_dir, revisions.GRAPH, args.revision).exists():
            # Named and absent is worth listing what *is* here: a mistyped instant and a
            # snapshot whose stores were dropped look identical from the command line, and
            # rule 89 says a refusal has to name something that can act on it.
            here = mapless(out_dir) or [
                r for p in revisions.known(out_dir, revisions.GRAPH)
                if (r := revisions.revision_of(p))
            ]
            _emit(f"error: no graph for {args.revision} in {out_dir}")
            if here:
                _emit("this directory holds: " + ", ".join(here))
            return 2

    rows: list[dict] = []
    db = out_dir / "source.db"
    if db.exists():
        source = SourceStore(db, writable=False)
        try:
            rows = [dict(r) for r in source.revisions()]
        finally:
            source.close()

    done = render_maps(out_dir, wanted, include_tests=args.include_tests,
                       rows=rows, emit=_emit)
    # Non-zero on a refusal, so this can be scripted: a run that wrote nothing it was asked
    # for must not report success (rule 13's shape at the exit code).
    return 1 if any(r.refusal for r in done) else 0


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
    # The root when nobody said, on `_out_root`'s argument one command over: a
    # double-clicked application has no working directory for a relative default to mean
    # anything against. `serve` itself decides whether what it is handed is a program or
    # a root -- by whether it holds a map, never by what it is called.
    given = Path(args.out_dir) if args.out_dir else default_output_root()
    if not args.out_dir:
        _emit(f"no directory given; reading {given}")
    try:
        serve(given, port=args.port,
              open_browser=not args.no_open, revision=args.revision, emit=_emit)
    except (FileNotFoundError, StaleGraphError, UnfinishedMapError) as exc:
        _emit(f"error: {exc}")
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    """The entry point, and `freeze_support()` is its first statement for a reason.

    `walk.py` runs a `ProcessPoolExecutor` and macOS **spawns** rather than forks, so every
    worker starts by re-executing this program. In a checkout that re-executes the
    interpreter and `multiprocessing` sorts itself out; in a frozen application it
    re-executes *the application* -- which, for `serve`, means up to sixteen more servers
    each opening a browser, and for `analyze` sixteen more analyses. Not an exception the
    serial fallback in `walk.py` can catch, because nothing in the parent raises: the
    parent is fine, and the children are the program.

    `freeze_support()` is what makes a spawned child recognise itself as a worker and hand
    over. It is a no-op in every other case, which is why calling it here **and** in the
    packaged entry script is right rather than redundant -- whichever one is the real entry
    point of a given build, the first statement executed has made the call.
    """
    multiprocessing.freeze_support()
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
