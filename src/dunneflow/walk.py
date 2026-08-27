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
from dataclasses import dataclass
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

TEST_MARKERS = ("test_", "_test", "conftest")

LANG_SUFFIX = {".py": "python", ".pyi": "python"}


@dataclass(slots=True)
class WalkStats:
    found: int = 0
    parsed: int = 0
    cached: int = 0
    removed: int = 0
    failed: int = 0


def is_test_path(path: Path) -> bool:
    if any(p in {"tests", "test", "testing"} for p in path.parts):
        return True
    return any(m in path.stem for m in TEST_MARKERS)


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


def discover_docs(root: Path, suffixes: frozenset[str] = DOC_SUFFIXES) -> Iterator[Path]:
    """Every document under `root` that is plausibly about the program."""
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DOC_SKIP_DIRS]
        here = Path(dirpath)
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
) -> WalkStats:
    """Read every changed document under `root` into `store`.

    The same two properties as the code walk, for the same reasons: parallel because
    scanning is CPU-bound, and skipped entirely when the content hash is unchanged.
    """
    root = root.resolve()
    stats = WalkStats()

    docs = sorted(discover_docs(root))
    stats.found = len(docs)

    known = store.known_hashes()
    stamps = {} if recheck else store.known_stamps()
    todo: list[Path] = []
    live: list[str] = []
    for p in docs:
        key = str(p)
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
                mtime_ns = Path(df.path).stat().st_mtime_ns
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
        key = str(p)
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
