"""Finding source files and documents, and extracting them without doing work twice.

Two properties matter here and both are about growth rather than correctness:

* Extraction runs in parallel across files, because parsing is CPU-bound and
  embarrassingly parallel.
* A file whose content hash matches what is already stored is not re-parsed at all.
  Re-analysing after editing three files costs three files, which is what turns
  analysis from an event into a habit.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from .docstore import DocStore
from .extractors.docs import DOC_SUFFIXES, extract_doc
from .extractors.python.extract import extract_file
from .schema import DocFacts, FileFacts, hash_source
from .store import Store

# Directories that never contain the program under study.
SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    "node_modules", ".venv", "venv", "env", ".env", "site-packages", ".tox", ".nox",
    "build", "dist", ".eggs", ".idea", ".vscode", "htmlcov", ".DS_Store", "site",
    ".groma", ".claude",
})

# Documentation is discovered under a different rule, and the difference is the point.
# Vendored trees are still out -- nobody is documenting this program in `node_modules`.
# But `.groma` and `.claude` are deliberately kept IN, because that is where a project
# files its charter, its decisions and its naming standard. Skipping every dotted
# directory is right for code and hides the vocabulary.
DOC_SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    "node_modules", ".venv", "venv", "env", "site-packages", ".tox", ".nox", ".uv-cache",
    "build", "dist", "dist-isolation", ".eggs", ".idea", ".vscode", "htmlcov", "site",
    "vendor", "target", ".next", ".astro", "coverage", "test-results", ".hypothesis",
    ".benchmarks", ".git-crypt", "_build",
})

# A directory *below* the root carrying its own version-control marker is a checkout
# of something, and not this program's documentation. `.claude` and `.groma` are kept in
# deliberately -- that is where a project files its charter, its decisions and its naming
# standard -- and admitting a directory for its documents must not admit a **copy of the
# program** underneath it. Two stale agent worktrees under `.claude/worktrees/` put 335
# May-era duplicates of Mensores' own governance documents into the corpus. The copy
# detector caught 303 and every consumer filters `duplicate_of`, so most numbers were
# protected; the 32 that had since drifted from their originals were no longer identical
# and escaped it, putting ten definitions -- `mensor`, `mensores` and `Society of
# Mensores` among them -- into the glossary from a directory that is not the project.
#
# The marker is read off the disk and is never a question asked of a VCS: a worktree
# carries a `.git` *file*, a clone a `.git` *directory*, and `.hg` and `.svn` are the
# same claim in another dialect. Version control must stay pluggable, and recognising a
# directory by what is in it does not talk to one.
#
# The root's own marker is never consulted, because the corpus is itself a checkout and
# that is the point. `discover` needs none of this: it already drops every dotted
# directory, so a nested checkout was only ever reachable through the document walk.
VCS_MARKERS = frozenset({".git", ".hg", ".svn"})

# Matched at an edge of the filename, never as a substring -- see `is_test_path`.
TEST_MARKERS = ("test_", "_test", "conftest")

@dataclass(slots=True)
class WalkStats:
    found: int = 0
    parsed: int = 0
    cached: int = 0
    removed: int = 0
    failed: int = 0
    # Nested checkouts pruned by `discover_docs`. A count of documents *not* read is
    # not derivable from `found`, and a corpus quietly 14% smaller than the tree is
    # exactly the kind of silent filter design rule 1 exists to forbid.
    nested: list[str] = field(default_factory=list)


def is_test_path(path: Path) -> bool:
    """Is this a test, as opposed to a module that has something to do with testing?

    The marker must be at an edge of the name, because a substring match is rule 5 in
    a new place: `_test_stage.py` is the real Test stage of the Groma pipeline (Plan
    30-02), `_test_extras_schemas.py` declares schemas, and all three were dropped from
    the map entirely -- routines, boundaries, comments and all -- for containing the
    word. `test_x` and `x_test` are the pytest conventions and are what a test is
    actually called.
    """
    if any(p in {"tests", "test", "testing"} for p in path.parts):
        return True
    stem = path.stem
    return (
        stem == "conftest"
        or stem.startswith("test_")
        or stem.endswith("_test")
    )


def discover(root: Path, include_tests: bool = False,
             suffixes: frozenset[str] = frozenset({".py"})) -> Iterator[Path]:
    """Every source file under `root` that is plausibly part of the program."""
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        here = Path(dirpath)
        for fn in filenames:
            p = here / fn
            if p.suffix not in suffixes:
                continue
            if not include_tests and is_test_path(p.relative_to(root)):
                continue
            yield p


def discover_docs(root: Path, suffixes: frozenset[str] = DOC_SUFFIXES,
                  nested: list[str] | None = None,
                  exclude: frozenset[Path] = frozenset()) -> Iterator[Path]:
    """Every document under `root` that is plausibly about the program.

    Nested checkouts are pruned and, when `nested` is given, named -- see `VCS_MARKERS`.
    The test costs nothing: `os.walk` has already listed this directory, so the marker
    is in `dirnames` (a clone) or in `filenames` (a worktree) and needs no `stat`.

    **`exclude` is how a program's own output stays out of its own corpus**, and it is a
    path rather than a name on purpose. Pointing DunneFlow at itself read 46 of 54
    documents out of `output/` -- its own generated reports, including 369,684 words of
    `06-governance.md` *about a different program* -- and every one of the 942 rules it
    then claimed to have found came from them. That is rule 57 with the tool's own output
    in place of a stale worktree, and worse, because the output is about somebody else.

    Blacklisting the *name* `output` was the obvious fix and is the wrong one: it is a
    perfectly good name for a directory of hand-written documents, and no scanner should
    silently drop one because a tool it has never heard of writes there. What is actually
    known is a **path** -- `analyze` is writing to it in this very run -- so that is what is
    passed. A project whose generated docs live somewhere else is unaffected either way,
    which is honest: DunneFlow can only exclude what it can know.
    """
    root = root.resolve()
    skip = {p.resolve() for p in exclude}
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        if here != root and (VCS_MARKERS & (set(dirnames) | set(filenames))):
            dirnames[:] = []
            if nested is not None:
                nested.append(str(here))
            continue
        dirnames[:] = [d for d in dirnames
                       if d not in DOC_SKIP_DIRS and (here / d).resolve() not in skip]
        for fn in filenames:
            p = here / fn
            if p.suffix.lower() in suffixes:
                yield p


def _extract_doc_one(args: tuple[str, str]) -> DocFacts:
    """Worker entry point for documents. Must be module-level and picklable."""
    path_s, root_s = args
    return extract_doc(Path(path_s), Path(root_s))


def analyze_docs_tree(
    root: Path,
    store: DocStore,
    jobs: int | None = None,
    progress: Callable[[str, int, int], None] | None = None,
    recheck: bool = False,
    exclude: frozenset[Path] = frozenset(),
) -> WalkStats:
    """Read every changed document under `root` into `store`.

    The same two properties as the code walk, for the same reasons: parallel because
    scanning is CPU-bound, and skipped entirely when the content hash is unchanged.
    """
    root = root.resolve()
    stats = WalkStats()

    docs = sorted(discover_docs(root, nested=stats.nested, exclude=exclude))
    stats.found = len(docs)

    known = store.known_hashes()
    stamps = {} if recheck else store.known_stamps()
    todo: list[Path] = []
    live: list[str] = []
    for p in docs:
        # Relative for the key, absolute for the read -- see `analyze_tree`.
        key = str(p.relative_to(root))
        live.append(key)
        try:
            st = p.stat()
        except OSError:
            stats.failed += 1
            continue
        # Cheap gate first. Reading 44 MB to decide that nothing changed costs more
        # than every other stage of analysis put together.
        if stamps.get(key) == (st.st_mtime_ns, st.st_size):
            stats.cached += 1
            continue
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            stats.failed += 1
            continue
        if known.get(key) == hash_source(src):
            stats.cached += 1
            store.touch(key, st.st_mtime_ns, st.st_size)
        else:
            todo.append(p)

    stats.removed = store.prune_missing(live)

    if not todo:
        store.conn.commit()
        return stats

    jobs = jobs or min(os.cpu_count() or 4, 16)
    payload = [(str(p), str(root)) for p in todo]
    results: list[DocFacts] = []

    if jobs > 1 and len(todo) > 8:
        try:
            with ProcessPoolExecutor(max_workers=jobs) as pool:
                futures = {pool.submit(_extract_doc_one, a): a[0] for a in payload}
                for i, fut in enumerate(as_completed(futures), 1):
                    try:
                        results.append(fut.result())
                    except Exception:
                        stats.failed += 1
                    if progress:
                        progress(futures[fut], i, len(todo))
        except Exception:
            results = []  # fall through to serial

    if not results:
        for i, a in enumerate(payload, 1):
            try:
                results.append(_extract_doc_one(a))
            except Exception:
                stats.failed += 1
            if progress:
                progress(a[0], i, len(todo))

    with store.batch():
        for df in results:
            try:
                # `df.path` is the key, relative to `root`. Joined back onto the root to
                # touch the disk, because the warm gate is `(mtime, size)` and a stat of
                # a relative path resolves against the working directory instead.
                mtime_ns = (root / df.path).stat().st_mtime_ns
            except OSError:
                mtime_ns = 0
            store.write_doc_facts(df, mtime_ns)
            stats.parsed += 1
            if df.errors:
                stats.failed += 1
    return stats


def _extract_one(args: tuple[str, str]) -> FileFacts:
    """Worker entry point. Must be module-level and picklable."""
    path_s, root_s = args
    return extract_file(Path(path_s), Path(root_s))


def analyze_tree(
    root: Path,
    store: Store,
    include_tests: bool = False,
    jobs: int | None = None,
    progress: Callable[[str, int, int], None] | None = None,
) -> WalkStats:
    """Extract every changed file under `root` into `store`."""
    root = root.resolve()
    stats = WalkStats()

    files = sorted(discover(root, include_tests=include_tests))
    stats.found = len(files)

    known = store.known_hashes()
    todo: list[Path] = []
    live: list[str] = []
    for p in files:
        # Two spellings, and they are not interchangeable. The **key** is relative to the
        # analysed root, because that is what the store holds and what pairs a file with
        # itself across two revisions read from two different trees. The **path** stays
        # absolute, because that is what opens the file. Keying on the absolute form is
        # what made moving a tree a full re-parse and a churned graph rather than a no-op.
        key = str(p.relative_to(root))
        live.append(key)
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            stats.failed += 1
            continue
        if known.get(key) == hash_source(src):
            stats.cached += 1
        else:
            todo.append(p)

    stats.removed = store.prune_missing(live)

    if not todo:
        store.conn.commit()
        return stats

    jobs = jobs or min(os.cpu_count() or 4, 16)
    payload = [(str(p), str(root)) for p in todo]
    results: list[FileFacts] = []

    if jobs > 1 and len(todo) > 8:
        try:
            with ProcessPoolExecutor(max_workers=jobs) as pool:
                futures = {pool.submit(_extract_one, a): a[0] for a in payload}
                for i, fut in enumerate(as_completed(futures), 1):
                    try:
                        results.append(fut.result())
                    except Exception:
                        stats.failed += 1
                    if progress:
                        progress(futures[fut], i, len(todo))
        except Exception:
            results = []  # fall through to serial

    if not results:
        for i, a in enumerate(payload, 1):
            try:
                results.append(_extract_one(a))
            except Exception:
                stats.failed += 1
            if progress:
                progress(a[0], i, len(todo))

    # One transaction for the whole burst; per-file commits dominate otherwise.
    with store.batch():
        for ff in results:
            store.write_file_facts(ff)
            stats.parsed += 1
            if ff.errors:
                stats.failed += 1
    return stats
