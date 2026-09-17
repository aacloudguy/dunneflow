"""Finding source files and documents, and extracting them without doing work twice.

Three properties matter here. Two are about growth rather than correctness:

* Extraction runs in parallel across files, because parsing is CPU-bound and
  embarrassingly parallel. **Who owns that parallelism is the reader's business**, so the
  pool lives in the plugin now rather than here — this module asks for facts and counts
  what came back.
* A file whose content hash matches what is already stored is not re-parsed at all.
  Re-analysing after editing three files costs three files, which is what turns
  analysis from an event into a habit.

The third is new, and it is the whole of this module's share of v2: **which reader owns a
file is a question somebody asks**. `discover()` took `frozenset({".py"})` as a default
argument its only caller never overrode and `analyze_tree` imported one extractor by name,
so the language of a file was decided by an import rather than by a table. Both now come
from `ingest`, and nothing here names a language.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from . import ingest, revisions
from .docstore import DocStore
from .extractors.docs import DOC_SUFFIXES, extract_doc
from .ingest import literals
from .ingest.contract import DiscoveryRules
from .schema import DocFacts, FileFacts, hash_source, stored_path
from .store import Store

# Directories that never contain the program under study, **whatever language it is written
# in** -- and that qualifier is the rule rather than a remark. A plugin's own skip list is
# applied at the *file* level, after the suffix has said which language owns the file,
# because a TypeScript reader adding `out` to a set this walk prunes on would take `out/`
# out of the **Python** corpus too. A plugin may contribute a filter; it may not impose
# one on somebody else's map. The cost is a descent that finds nothing.
#
# The five names added for v2 -- `target`, `vendor`, `obj`, `Pods` and `DerivedData` --
# are the build output of languages this tool cannot read yet, and `DOC_SKIP_DIRS` has
# had `vendor` and `target` all along: this walk was the only one of the two that could still
# descend into somebody else's build tree. `.gradle`, `.build` and `.turbo` are
# deliberately **not** listed, because every name below a dot is already pruned and a
# second answer to a question this file already answers is how the two come to disagree.
# Measured before adding any of them: Society's `src` holds no directory of any of those
# names, so the golden cannot move.
SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    "node_modules", ".venv", "venv", "env", ".env", "site-packages", ".tox", ".nox",
    "build", "dist", ".eggs", ".idea", ".vscode", "htmlcov", ".DS_Store", "site",
    ".groma", ".claude",
    "target", "vendor", "obj", "Pods", "DerivedData",
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

@dataclass(slots=True)
class WalkStats:
    found: int = 0
    parsed: int = 0
    cached: int = 0
    removed: int = 0
    failed: int = 0
    # What the code walk left out, and design rule 1 is why every one of these exists: a
    # filter nobody can see is a map that is quietly smaller than the directory it claims
    # to describe. Point this tool at a Go repository today and the map is empty; with
    # `unclaimed` it says *4,120 `.go` files -- no reader claims `.go`*, which is a
    # sentence somebody can act on (rule 89).
    #
    # `pruned` is keyed by the directory **name** that matched and counts directories, not
    # files, and the paths are deliberately not kept: four hundred `__pycache__` paths are
    # not a report, and the name with its count is the whole of what a reader does
    # anything with.
    pruned: dict[str, int] = field(default_factory=dict)
    # Suffix -> how many files carry it and nobody reads them. Documentation suffixes are
    # **not** counted here: those files are read, by the other walk in this module, and
    # calling them unread would be a false claim rather than a silent one.
    unclaimed: dict[str, int] = field(default_factory=dict)
    # Language -> files left out for being tests. Per language because a test is spelled
    # per language, and 322 of DunneNote's 767 `.ts` files are tests -- a number that must
    # never be the difference between two runs that nobody can see.
    tests_excluded: dict[str, int] = field(default_factory=dict)
    # Language -> files dropped by **that language's own** skip list, after the suffix
    # said who owns them. Python's list is wholly covered by `SKIP_DIRS` today, so this
    # cannot fire yet; it is the counter for the half of the asymmetry above that can.
    lang_skipped: dict[str, int] = field(default_factory=dict)
    # Language -> files admitted. Not derivable from `found`, which is one number for
    # every reader at once: *628 files* says nothing about whether the TypeScript half of
    # a tree was read at all, and a count must say what it counts (rule 32).
    by_lang: dict[str, int] = field(default_factory=dict)
    # Nested checkouts pruned by `discover_docs`. A count of documents *not* read is
    # not derivable from `found`, and a corpus quietly 14% smaller than the tree is
    # exactly the kind of silent filter design rule 1 exists to forbid.
    nested: list[str] = field(default_factory=list)
    # Maps pruned by `discover_docs`, and the same argument one subject over -- with the
    # number larger rather than smaller. DunneFlow's own tree read through the packaged
    # application was **122 of 147 documents** somebody else's map, so the corpus a silent
    # prune would shrink here is 83% of what the reader can see in the directory.
    maps: list[str] = field(default_factory=list)
    # Language -> strings the reader did not send, because they fall outside
    # `ingest.literals`' bound. A filter **inside** a file rather than a file left out,
    # and it is listed beside them because it is the same claim: this one runs in a
    # process the host cannot look inside, so the count is the only way it can be seen at
    # all. It is per language because the bound is applied by each reader in turn.
    literals_dropped: dict[str, int] = field(default_factory=dict)
    # Languages whose reader declares `reports_literals: false`. A real answer and not an
    # empty one -- that language contributes no SQL and no named files, on purpose -- and
    # it has to be said, because a map with neither is indistinguishable from a program
    # that touches no database and names no files.
    no_literals: list[str] = field(default_factory=list)


def walk_languages(stats: WalkStats) -> str:
    """What was read, per language: *python 628 · typescript 412*.

    Beside `walk_residue`'s *what was left out* and never inside it, because these are
    files that **are** in the map. One number for every reader at once cannot say whether
    a language was read at all -- a tree half TypeScript whose plugin refused would report
    the same `files 628` as one that had no TypeScript in it (rule 32).
    """
    return " · ".join(f"{lang} {n:,}" for lang, n in sorted(stats.by_lang.items()))


def walk_residue(stats: WalkStats) -> list[str]:
    """What the code walk left out, in sentences, or nothing at all when it left nothing.

    Design rule 1 in the one place a reader will actually be standing: the end of an
    analysis. Point this tool at a Go repository and the map is empty; what is wanted is
    not an empty map but *2,410 `.go` files — no reader here claims `.go`*, which names
    the thing that happened and implies what would fix it (rule 89).

    **One line per kind and never one per file.** A run that pruned four hundred
    `__pycache__` directories has one fact to report and four hundred paths to report it
    with; the name and the count is the whole of what anybody does anything about, and a
    report nobody reads to the end is design rule 1's letter without its point.
    """
    out: list[str] = []
    if stats.unclaimed:
        worst = sorted(stats.unclaimed.items(), key=lambda kv: (-kv[1], kv[0]))
        listed = ", ".join(f"{n:,} {suffix}" for suffix, n in worst)
        out.append(f"unread: {listed} — no reader here claims "
                   + ("that suffix" if len(worst) == 1 else "those suffixes"))
    if stats.tests_excluded:
        listed = ", ".join(f"{n:,} {lang}"
                           for lang, n in sorted(stats.tests_excluded.items()))
        out.append(f"left out as tests: {listed} — analyse again with --include-tests "
                   f"to read them")
    if stats.lang_skipped:
        listed = ", ".join(f"{n:,} {lang}"
                           for lang, n in sorted(stats.lang_skipped.items()))
        out.append(f"skipped by the reader's own rule: {listed}")
    if stats.no_literals:
        out.append(f"no strings reported by: {', '.join(sorted(stats.no_literals))} — "
                   f"that language contributes no SQL and no named files to this map")
    if stats.literals_dropped:
        listed = ", ".join(f"{n:,} {lang}"
                           for lang, n in sorted(stats.literals_dropped.items()))
        out.append(f"strings not judged: {listed} — outside the "
                   f"{literals.LITERAL_MIN}–{literals.LITERAL_MAX:,} character bound a "
                   f"reader applies before sending")
    if stats.maps:
        out.append(f"pruned {len(stats.maps):,} "
                   + ("directory" if len(stats.maps) == 1 else "directories")
                   + " holding a map — a program's map is not its source")
    if stats.pruned:
        worst = sorted(stats.pruned.items(), key=lambda kv: (-kv[1], kv[0]))
        listed = ", ".join(f"{name} ×{n}" if n > 1 else name for name, n in worst)
        out.append(f"pruned {sum(stats.pruned.values()):,} directories: {listed}")
    return out


def _tally(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def discover(root: Path, include_tests: bool = False,
             rules: Sequence[DiscoveryRules] | None = None,
             stats: WalkStats | None = None) -> Iterator[Path]:
    """Every source file under `root` that is plausibly part of the program.

    **`is_test_path` lived here and is gone**, and its replacement is
    `DiscoveryRules.is_test` per language. Its rule-5 precision is carried over whole --
    a marker matches at an **edge** of the name and never as a substring, because
    `_test_stage.py` is the Test stage of a pipeline and was once dropped from a map
    entire for containing the word -- and what it could not do is spell a test any other
    way than Python's. `Path("client.test.ts").stem` is `"client.test"`, which starts with
    neither `test_` nor ends with `_test`, so **322 of DunneNote's 767 `.ts` files** would
    have been admitted as program code, inflating routines, conventions and every dead-code
    number in the map.

    `rules` defaults to every plugin this build ships. It is a parameter rather than a
    lookup so that a caller can ask this walk about readers it does not have yet, which is
    the only way the multi-language behaviour above can be pressed while one language is
    wired.

    Which suffix belongs to whom is `ingest.suffix_owners`, the same function the registry
    itself is built from (rule 51): a walk that answered `.js` differently from the
    registry would route a file to a reader the fingerprint says never read it.
    """
    root = root.resolve()
    rules = tuple(ingest.discovery()) if rules is None else tuple(rules)
    owner = ingest.suffix_owners(rules)
    by_lang = {r.lang: r for r in rules}
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        # A map is not source, and it is pruned on the free test the listing already
        # took -- `discover_docs`' rule, applied to the other walk at last. It never
        # mattered while only Python was read, because a program directory holds no `.py`
        # and the code walk had no way to say what it had passed over; the moment this
        # walk started counting what nobody reads, a reader analysing a tree with an
        # `output/` in it was told about twelve unread `.db` files that are this tool's
        # own writing.
        #
        # **The root is exempt, and here that asymmetry runs the opposite way to the
        # document walk's.** There, `--docs` pointed at a program directory is the failure
        # rather than the ordinary case. Here the root is the tree somebody named, and a
        # graph written *beside* the source it was taken from is an ordinary arrangement
        # -- `--output .` is one, and every test in this suite that keeps its store in the
        # tree it analyses is another. Pruning at the root would answer that with an empty
        # map and a line about a directory, which is precisely the shape of failure rule
        # 49 is about. Below the root, a directory holding a map is somebody else's
        # program and never this one's source.
        if here != root and revisions.names_a_map(filenames):
            dirnames[:] = []
            if stats is not None:
                stats.maps.append(str(here))
            continue
        keep = []
        for d in dirnames:
            if d in SKIP_DIRS or d.startswith("."):
                if stats is not None:
                    _tally(stats.pruned, d)
            else:
                keep.append(d)
        dirnames[:] = keep
        for fn in filenames:
            p = here / fn
            suffix = p.suffix.lower()
            lang = owner.get(suffix)
            rel = p.relative_to(root)
            if lang is None:
                # A document is read by `analyze_docs_tree`, so naming it unread here
                # would be a false claim rather than a missing one (rule 13).
                if stats is not None and suffix and suffix not in DOC_SUFFIXES:
                    _tally(stats.unclaimed, suffix)
                continue
            rule = by_lang[lang]
            if any(part in rule.skip_dirs for part in rel.parts[:-1]):
                if stats is not None:
                    _tally(stats.lang_skipped, lang)
                continue
            if not include_tests and rule.is_test(rel):
                if stats is not None:
                    _tally(stats.tests_excluded, lang)
                continue
            if stats is not None:
                _tally(stats.by_lang, lang)
            yield p


def discover_docs(root: Path, suffixes: frozenset[str] = DOC_SUFFIXES,
                  nested: list[str] | None = None,
                  exclude: frozenset[Path] = frozenset(),
                  maps: list[str] | None = None) -> Iterator[Path]:
    """Every document under `root` that is plausibly about the program.

    Nested checkouts are pruned and, when `nested` is given, named -- see `VCS_MARKERS`.
    The test costs nothing: `os.walk` has already listed this directory, so the marker
    is in `dirnames` (a clone) or in `filenames` (a worktree) and needs no `stat`.

    **A map is pruned wherever it sits**, on that same free test and named in `maps` --
    `revisions.names_a_map` reads the listing `os.walk` has already taken. Pointing
    DunneFlow at itself read 46 of 54 documents out of `output/` -- its own generated
    reports, including 369,684 words of `06-governance.md` *about a different program* --
    and every one of the 942 rules it then claimed to have found came from them. That is
    rule 57 with the tool's own output in place of a stale worktree, and worse, because
    the output is about somebody else.

    **It is asked of this tree rather than computed from where the run writes, and that
    distinction is rule 92.** The first fix passed `exclude` a set built by
    `revisions.program_dirs(out_root)`, which is correct and was measured -- from a
    checkout, where the output root is `./output` and therefore inside the tree being
    read. Frozen it is `~/Library/Application Support/DunneFlow`, so the set enumerates a
    directory nowhere near this walk and a checkout's own maps went back into the corpus.
    Retaken on DunneFlow's map as the packaged application built it, 2026-09-10: **122 of
    147 documents** out of `output/`, **122 of 122** stated naming rules, 655 of 680
    definitions, and a document store of **289 MB**.

    Pruning is by `dirnames`, so a program directory takes its `map@<revision>/`
    subdirectories with it. **Unlike the checkout marker this one is applied at `root`
    too**, and the asymmetry is the point: a corpus is itself a checkout and that is why
    the root is exempt there, but a corpus is never itself a map, so a `--docs` pointed
    into a program directory is the failure rather than the ordinary case. It cannot fire
    by accident on the default path, where the docs root is the nearest ancestor holding a
    `pyproject.toml` and a program directory holds none.

    **`exclude` stays, and it is not the same mechanism.** It is a path known for certain
    rather than a marker read off the disk, which is what answers for this run's own
    `out_dir`: that directory is created before the documents are scanned and holds no
    graph until after, so nothing on the walk can recognise it. Blacklisting the *name*
    `output` was the obvious fix for both and is the wrong one -- it is a perfectly good
    name for a directory of hand-written documents, and no scanner should silently drop
    one because a tool it has never heard of writes there.
    """
    root = root.resolve()
    skip = {p.resolve() for p in exclude}
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        if revisions.names_a_map(filenames):
            dirnames[:] = []
            if maps is not None:
                maps.append(str(here))
            continue
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

    docs = sorted(discover_docs(root, nested=stats.nested, exclude=exclude,
                                maps=stats.maps))
    stats.found = len(docs)

    known = store.known_hashes()
    stamps = {} if recheck else store.known_stamps()
    todo: list[Path] = []
    live: list[str] = []
    for p in docs:
        # Relative for the key, absolute for the read -- see `analyze_tree`.
        key = stored_path(p.relative_to(root))
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


def _verify_lang(ff: FileFacts, expected: str) -> None:
    """What the reader says it read, against what it was handed (rule 30).

    A manifest is a label and a running reader is the identity, so the claim is checked
    rather than trusted -- and it is checked here because this is the seam a reader on the
    far side of a pipe will arrive through. It is refused rather than counted as a failed
    file: a reader answering about a language it was not given is a defect in the build,
    and every other fact that came back with it is now worth exactly as much as this one.
    """
    if ff.lang != expected:
        raise ingest.PluginRefused(
            f"the {expected} reader answered about {ff.path} claiming the language "
            f"{ff.lang!r}. A reader is handed the files its own suffixes claimed, so this "
            f"is the reader and the registry disagreeing about what was read, and not a "
            f"file this tree got wrong."
        )


def _by_language(paths: Sequence[Path]) -> dict[str, list[Path]]:
    """Group discovered files by the reader that owns them.

    **Refuses rather than skipping**, and the refusal is rule 49 rather than caution:
    every path here came out of `discover`, which admitted it *because* a plugin claimed
    its suffix, so a file with no language at this point means the walk and the registry
    are reading two different tables. Dropping it would leave a map short of a file with
    no symptom anywhere -- the reader would see a smaller number and nothing else.
    """
    out: dict[str, list[Path]] = {}
    for p in paths:
        lang = ingest.language_of(p)
        if lang is None:
            raise ingest.PluginRefused(
                f"{p} was discovered as source and no reader claims {p.suffix!r}. The "
                f"walk and the plugin registry have stopped agreeing about which suffix "
                f"belongs to whom, which is a build defect rather than something this "
                f"tree can be blamed for."
            )
        out.setdefault(lang, []).append(p)
    return out


def analyze_tree(
    root: Path,
    store: Store,
    include_tests: bool = False,
    jobs: int | None = None,
    progress: Callable[[str, int, int], None] | None = None,
) -> WalkStats:
    """Extract every changed file under `root` into `store`.

    **Grouped by language and dispatched, never extracted here.** The `from
    .extractors.python.extract import extract_file` this function used to open with was
    the one line that made DunneFlow a Python tool rather than a tool that happens to
    ship a Python reader; what is left is a cache, a transaction and a count.

    The order of the two loops is the contract rather than housekeeping. A reader is
    `open`ed with **every** file of its language, including the ones the content hash
    says have not changed, because a reader that resolves symbols over a subset of the
    compilation answers wrongly rather than partially; `extract` is then given only what
    missed the cache. Python's reader needs neither, and says so in `InProcessPlugin.open`.
    """
    root = root.resolve()
    stats = WalkStats()

    files = sorted(discover(root, include_tests=include_tests, stats=stats))
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
        # `stored_path` rather than `str` because the key has to be the one the store
        # holds, and a store written on another platform spells it with forward slashes.
        key = stored_path(p.relative_to(root))
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

    owned = _by_language(files)
    work = _by_language(todo)

    # The progress contract is the caller's and is unchanged: `i` counts from 1 to the
    # whole run's total, whichever reader is speaking. A plugin counts its own payload,
    # because it cannot know what else is being read -- so the offset is held here, which
    # is the one thing the host knows and the readers do not.
    done = 0
    total = len(todo)

    for lang, wanted in work.items():
        plugin = ingest.PLUGINS[lang]
        offset = done

        def relay(path: str, i: int, _n: int, _offset: int = offset) -> None:
            if progress:
                progress(path, _offset + i, total)

        if not plugin.manifest.reports_literals:
            stats.no_literals.append(lang)
        plugin.open(root, owned.get(lang, []))
        try:
            # One transaction per reader; per-file commits dominate otherwise.
            with store.batch():
                for ff in plugin.extract(wanted, root, relay, jobs):
                    _verify_lang(ff, lang)
                    # What a string *means* is decided here, for every language at once,
                    # and never by the reader that found it (rule 51). This is the one
                    # place both kinds of reader pass through, which is why it is here
                    # and not in each of the two wrappers.
                    literals.judge(ff, plugin.manifest.reports_literals)
                    if ff.literals_dropped:
                        stats.literals_dropped[lang] = (
                            stats.literals_dropped.get(lang, 0) + ff.literals_dropped
                        )
                    store.write_file_facts(ff)
                    stats.parsed += 1
                    if ff.errors:
                        stats.failed += 1
        finally:
            plugin.close()
        # A file whose reader died never arrives at all, so the reader is the only thing
        # that can say it existed -- see `IngestPlugin.lost`.
        stats.failed += plugin.lost
        done += len(wanted)
    return stats
