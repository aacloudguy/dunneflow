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

import json
import os
import stat
from collections.abc import Callable, Iterator, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from . import ingest, revisions
from .docstore import DocStore
from .extractors.docs import DOC_SUFFIXES, extract_doc
from .ingest import literals
from .ingest.acts import one_act
from .ingest.contract import DiscoveryRules, ToolchainMissing

# **The one import this module makes into `resolve/`, and it is a name rather than a
# behaviour.** Which filenames declare something is a *discovery* fact -- `PLAN-v2.md`
# §1h calls its section "Discovery and manifests" -- and the providers own the list
# because they are what makes a name mean anything (rule 51: a second copy beside the
# walk would drift the day somebody adds a seventh). Nothing here reads a manifest;
# `resolve/manifests` does that, after extraction, with the paths this walk hands it.
from .resolve.manifests import MANIFEST_FILES
from .schema import DocFacts, FileFacts, hash_source, stored_path
from .store import Store
from .words import plural

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
# Measured before adding any of them: Comitia's `src` holds no directory of any of those
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
# May-era duplicates of Lictores' own governance documents into the corpus. The copy
# detector caught 303 and every consumer filters `duplicate_of`, so most numbers were
# protected; the 32 that had since drifted from their originals were no longer identical
# and escaped it, putting ten definitions -- `lictor`, `lictores` and `Comitia of
# Lictores` among them -- into the glossary from a directory that is not the project.
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
    # Why -> how many: names in the tree that a reader would have claimed and that are not
    # files of this tree (`not_a_tree_file`). Said, like everything else left out.
    not_files: dict[str, int] = field(default_factory=dict)
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
    # Every manifest this walk passed -- `package.json`, `Cargo.toml`, `pyproject.toml`
    # and the rest -- for `resolve/manifests` to read. Collected **here** rather than by a
    # second walk of its own, because the only question is *which directories are part of
    # this program*, and this loop has already answered it: `SKIP_DIRS`, every dotted
    # directory and every directory holding a map are gone by the time a filename is
    # looked at. A second traversal would be a second answer, and the two would disagree
    # the first time somebody extended one of the three (rule 92, and rule 51's shape).
    #
    # A manifest is **not** source and no reader claims one, so it still counts towards
    # `unclaimed` where its suffix is unread. Both are true at once: `Package.swift` is a
    # manifest this tool reads and Swift source it does not.
    manifests: list[Path] = field(default_factory=list)
    # Language -> strings the reader did not send, because they fall outside
    # `ingest.literals`' bound. A filter **inside** a file rather than a file left out,
    # and it is listed beside them because it is the same claim: this one runs in a
    # process the host cannot look inside, so the count is the only way it can be seen at
    # all. It is per language because the bound is applied by each reader in turn.
    literals_dropped: dict[str, int] = field(default_factory=dict)
    # Language -> test items a reader left out **inside** files it read: Rust's
    # `#[cfg(test)] mod tests` and `#[test] fn`. `tests_excluded`'s claim one level down,
    # and listed beside it, because a tree that keeps its tests inline would otherwise read
    # as one with none (design rule 1). Counted as `literals_dropped` is -- off the files
    # this run read -- so a warm run that read none of them says nothing.
    tests_dropped: dict[str, int] = field(default_factory=dict)
    # Language -> files this build can read and was told not to. **Its own counter and
    # never `unclaimed`'s**, because they are two different facts that look identical in a
    # map (design rule 21): *no reader here claims `.go`* is answered by a build that has
    # one, and *you declined typescript* is answered by not declining it. Flattening them
    # would tell a reader who declined a language that the tool cannot read it.
    declined: dict[str, int] = field(default_factory=dict)
    # Language -> files this build has a reader for and **this machine cannot run**, with
    # the probe's own sentence beside it in `no_toolchain_said`. A third fact beside
    # `unclaimed` and `declined`, and never folded into either (design rule 21): *no reader
    # claims `.go`* is answered by a build that has one, *you declined go* by not declining
    # it, and *go is not installed* by installing it. PLAN-v2 drew this as *swift declined
    # (no toolchain)* and nothing ever filled it: until 2026-11-01 `probe_toolchain` was
    # called by tests alone, so a missing `node` reached a reader as an uncaught refusal from
    # the worker that could not start, and took the whole analysis down with it.
    no_toolchain: dict[str, int] = field(default_factory=dict)
    no_toolchain_said: dict[str, str] = field(default_factory=dict)
    # Languages whose reader declares `reports_literals: false`. A real answer and not an
    # empty one -- that language contributes no SQL and no named files, on purpose -- and
    # it has to be said, because a map with neither is indistinguishable from a program
    # that touches no database and names no files.
    no_literals: list[str] = field(default_factory=list)
    # Language -> edges its reader handed over, where its toolchain resolved the far end
    # of a call itself. Beside the extraction counts rather than inside them because it is
    # a different pass over a different question: `parsed` is files read, this is calls
    # whose target somebody already knew (rule 32).
    supplied_edges: dict[str, int] = field(default_factory=dict)
    # Language -> call sites its reader walked and could **not** name a far end for, in
    # two dictionaries because they are two facts (design rule 21). `edges_outside` is a
    # call whose far end the reader named and this map does not hold, which is an external
    # call and correct; `edges_unknown` is one the reader could not resolve at all, which
    # is its limit. Only the reader can count either: the host sees what arrived and never
    # what did not.
    # What each reader said when it opened its session: how it divided the file set into
    # compilations, and how long that took. Not residue -- these files **are** in the map
    # -- so it is said beside `read:` rather than among the things left out.
    reader_notes: list[str] = field(default_factory=list)
    edges_outside: dict[str, int] = field(default_factory=dict)
    # Language -> what its reader read beyond this tree to name the frontier, and what it
    # looked for and did not find (`IngestPlugin.edges_read_beyond`).
    read_beyond: dict[str, list[str]] = field(default_factory=dict)
    not_present: dict[str, list[str]] = field(default_factory=dict)
    # Language -> files left out as test code that only the reader's whole-program pass
    # can name: a file a `#[cfg(test)] mod x;` declares. Said on **every** run that leaves
    # them out, warm or cold, because the set is held in the store and not re-derived from
    # what this run happened to read -- unlike `tests_dropped`, which counts items inside
    # the files a run parsed.
    test_modules: dict[str, int] = field(default_factory=dict)
    edges_unknown: dict[str, int] = field(default_factory=dict)
    # Fields an edge carried that this build does not read. Survivable -- a plugin built
    # against a later schema knows about fields this one does not -- and never silent: an
    # edge has no `errors` list of its own to carry them in, so they come out here.
    edge_notes: list[str] = field(default_factory=list)


_TEST_MODULES = "test_modules:"
# How many of a reader's `edges_done.notes` the summary prints before it says how many more.
_EDGES_SAID_SHOWN = 12
# `whole` or `rest`, committed before a reader is asked for anything and cleared after its
# edge pass. See `_why_whole`.
_READING = "reading:"
_INPUTS = "inputs:"


def _test_modules(store: Store) -> dict[str, dict[str, str]]:
    """Language -> the test-only module files its reader last named, each with its hash."""
    out: dict[str, dict[str, str]] = {}
    for r in store.conn.execute(
        "SELECT key, value FROM meta WHERE key LIKE ? ORDER BY key", (f"{_TEST_MODULES}%",)
    ):
        out[str(r["key"])[len(_TEST_MODULES):]] = dict(json.loads(r["value"]))
    return out


def _leave_out_test_modules(store: Store, paths: Sequence[str]) -> None:
    """Drop a test module's facts, and every edge a reader supplied into it.

    `forget_file` keeps `supplied_edges` by design -- an edge into a file belongs to a
    caller elsewhere -- but an edge into test code from production code is one this pass
    is dropping the far end of, and an edge left pointing at a file with no facts is a
    target nothing can open.
    """
    for p in paths:
        store.forget_file(p)
        store.conn.execute("DELETE FROM supplied_edges WHERE file = ?", (p,))


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
    if stats.declined:
        listed = ", ".join(f"{n:,} {lang}" for lang, n in sorted(stats.declined.items()))
        out.append(f"declined by you: {listed} — this build has a reader for "
                   + ("that language" if len(stats.declined) == 1 else "those languages")
                   + "; drop --without to read them")
    for lang, n in sorted(stats.no_toolchain.items()):
        # One line per language rather than one joined line, because each carries its own
        # command and its own way forward, and a sentence that names two toolchains is
        # one nobody can act on in a single step (rule 89).
        out.append(f"not read, no toolchain: {plural(n, 'file')} of {lang} — "
                   + stats.no_toolchain_said.get(lang, "its reader could not be started"))
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
    for lang, n in sorted(stats.test_modules.items()):
        out.append(f"left out as tests: {plural(n, 'file')} of {lang} that a test-only "
                   f"module declaration names — analyse again with --include-tests to "
                   f"read them")
    if stats.tests_dropped:
        listed = ", ".join(f"{n:,} {lang}"
                           for lang, n in sorted(stats.tests_dropped.items()))
        out.append(f"test code inside source files left out: {listed} — items the reader "
                   f"marks as tests; --include-tests reads test files, not these")
    if stats.not_files:
        listed = ", ".join(f"{n:,} {why}" for why, n in sorted(stats.not_files.items()))
        out.append(f"not read, not a file of this tree: {listed} — a link is followed "
                   f"only to a file inside the tree, and a pipe, a socket or a device is "
                   f"never opened")
    if stats.lang_skipped:
        listed = ", ".join(f"{n:,} {lang}"
                           for lang, n in sorted(stats.lang_skipped.items()))
        out.append(f"skipped by the reader's own rule: {listed} — a directory or a "
                   f"filename that reader does not count as program source")
    if stats.no_literals:
        out.append(f"no strings reported by: {', '.join(sorted(stats.no_literals))} — "
                   f"that language contributes no SQL and no named files to this map")
    if stats.literals_dropped:
        listed = ", ".join(f"{n:,} {lang}"
                           for lang, n in sorted(stats.literals_dropped.items()))
        out.append(f"strings not judged: {listed} — outside the "
                   f"{literals.LITERAL_MIN}–{literals.LITERAL_MAX:,} character bound a "
                   f"reader applies before sending")
    if stats.edges_outside:
        listed = ", ".join(f"{n:,} {lang}"
                           for lang, n in sorted(stats.edges_outside.items()))
        out.append(f"calls resolved to somewhere outside this map: {listed} — a library, "
                   f"a type declaration or a file no reader claimed; external, and right")
    if stats.edges_unknown:
        listed = ", ".join(f"{n:,} {lang}"
                           for lang, n in sorted(stats.edges_unknown.items()))
        out.append(f"calls whose far end the reader could not name at all: {listed} — "
                   f"left external rather than guessed by name")
    for lang, read in sorted(stats.read_beyond.items()):
        shown = ", ".join(read[:12]) + (f" and {len(read) - 12} more" if len(read) > 12 else "")
        out.append(f"{lang} frontier read from this machine, never fetched: "
                   f"{plural(len(read), 'dependency', 'dependencies')} — {shown}")
    for lang, missing in sorted(stats.not_present.items()):
        shown = ", ".join(missing[:8]) + (
            f" and {len(missing) - 8} more" if len(missing) > 8 else "")
        out.append(f"{lang} frontier spelt, not confirmed: "
                   f"{plural(len(missing), 'dependency', 'dependencies')} not read — {shown}")
    if stats.edge_notes:
        out.append("edges carried fields this build does not read: "
                   + "; ".join(stats.edge_notes))
    if stats.maps:
        out.append(f"pruned {len(stats.maps):,} "
                   + ("directory" if len(stats.maps) == 1 else "directories")
                   + " holding a map — a program's map is not its source")
    if stats.pruned:
        worst = sorted(stats.pruned.items(), key=lambda kv: (-kv[1], kv[0]))
        listed = ", ".join(f"{name} ×{n}" if n > 1 else name for name, n in worst)
        # `plural`, because one pruned directory read "pruned 1 directories: vendor" on
        # every map of a tree with a single `vendor/` (found retaking the guide, 2026-10-02).
        out.append(f"pruned {plural(sum(stats.pruned.values()), 'directory', 'directories')}"
                   f": {listed}")
    return out


def _tally(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def not_a_tree_file(p: Path, root: Path) -> str:
    """Why this name is not read, or `""` when it is an ordinary file of the tree.

    **A tree being read is somebody else's, and a name in it is not a promise about what is
    behind the name.** Two things were tried on 2026-11-12 and both happened. `leak.py`, a
    symbolic link to a file outside the tree, was read like any other: its constants were in
    the rendered map, so analysing a checkout could copy `~/.netrc` or a key into a map
    somebody then shares. And `pipe.py`, a named pipe, was opened for reading and the
    analysis waited on it for ever, with nothing on the screen to say why.

    `os.walk` already declines to follow a link to a *directory*; this is the same refusal
    for files, asked in the one place both walks admit a name (rule 51). A link to a file
    **inside** the tree is still read, because that is an ordinary way to lay a tree out and
    nothing outside it is disclosed. `root` must already be resolved.
    """
    try:
        mode = os.lstat(p).st_mode
    except OSError:
        return "that could not be examined"
    if stat.S_ISREG(mode):
        return ""
    if not stat.S_ISLNK(mode):
        return "that are a pipe, a socket or a device"
    try:
        target = p.resolve(strict=True)
        if not stat.S_ISREG(target.stat().st_mode):
            return "links to something that is not a file"
        target.relative_to(root)
    except ValueError:
        return "links to a file outside the tree"
    except OSError:
        return "links to nothing"
    return ""


def discover(root: Path, include_tests: bool = False,
             rules: Sequence[DiscoveryRules] | None = None,
             stats: WalkStats | None = None,
             declined: frozenset[str] = frozenset(),
             judge_root: Path | None = None) -> Iterator[Path]:
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

    **`declined` filters last, and that placement is the whole of what it reports.** Taken
    off `rules` instead, a declined language's suffixes would leave `owner` and its files
    would land in `unclaimed` — *no reader here claims `.ts`* said by a build that has one,
    which is the flattening design rule 21 is about and a false sentence besides. Asked
    after the skip rules and the test rule, `declined` counts **exactly the files that
    would otherwise have been read**, so the number answers the only question a reader has
    about it: what did I lose. The test and skip lines still appear and are still true;
    the three sets are disjoint and the arithmetic closes.

    **`judge_root` is where the path-shaped rules are measured from, and `root` is still
    the program.** Every such rule -- a plugin's `skip_dirs`, and `is_test`'s `test_dirs` --
    is matched against `rel.parts`, so the same file is judged differently depending on
    where the walk started: the component that hid it is no longer in any relative path.
    `Engine/Source/ThirdParty` is 620 files seen from the top of Unreal and **57,373**
    walked as its own root, and `Engine/Binaries` is 3,146 against **3,619** -- the second
    of which went onto disk reporting success. Given the tree a part belongs to, this walk
    judges as the tree would while `root` stays the part, so module names, stored paths and
    the store key are untouched. `None` means the two are the same, which is every analysis
    of a whole program and the only behaviour there has ever been.

    A prefix that crosses none of those names gives the same answer either way, which is
    why the flag is a no-op on all but a handful of parts: the extra components it adds to
    `rel` are exactly the ones that match nothing.
    """
    root = root.resolve()
    judged_from = root if judge_root is None else judge_root.resolve()
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
            # Measured from the tree when there is one, so a part is judged as the piece
            # of a program it is rather than as a program of its own. `root` is unchanged
            # and is still what every key below is relative to.
            rel = p.relative_to(judged_from)
            # Declarations follow the corpus. This is not a filter on what is yielded --
            # a manifest is never source -- it is the walk answering the one question
            # `resolve/manifests` cannot answer for itself: which directories in this
            # tree are the program's.
            if (lang is not None or fn in MANIFEST_FILES) and (
                    why := not_a_tree_file(p, root)):
                if stats is not None:
                    _tally(stats.not_files, why)
                continue
            if stats is not None and fn in MANIFEST_FILES:
                stats.manifests.append(p)
            if lang is None:
                # A document is read by `analyze_docs_tree`, so naming it unread here
                # would be a false claim rather than a missing one (rule 13).
                if stats is not None and suffix and suffix not in DOC_SUFFIXES:
                    _tally(stats.unclaimed, suffix)
                continue
            rule = by_lang[lang]
            if any(part in rule.skip_dirs for part in rel.parts[:-1]) or (
                rule.skip_names and rel.name.endswith(rule.skip_names)
            ):
                if stats is not None:
                    _tally(stats.lang_skipped, lang)
                continue
            if not include_tests and rule.is_test(rel):
                if stats is not None:
                    _tally(stats.tests_excluded, lang)
                continue
            if lang in declined:
                if stats is not None:
                    _tally(stats.declined, lang)
                continue
            if stats is not None:
                _tally(stats.by_lang, lang)
            yield p


# **How many files this tool is known to read in one go.** Not a guess and not a round
# number chosen for looking like one: `Engine/Source/Runtime` of `UnrealEngine-release` is
# **18,191** files and is the largest tree ever read end to end — 8 m 54 s, on record. The
# whole of that tree is 88,356, which is 4.9x it, and that run degraded to 0.1% CPU and was
# stopped after 1 h 45 m (`store.WAL_CAP_BYTES` carries the mechanism, and the bound there
# is what makes a tree this size finishable at all).
#
# So the guard is set at the **edge of measured experience** rather than at a limit, and the
# refusal says which number it is and where it came from. A reader who has a tree between
# 18,191 and 20,000 files is inside what has been done; one with 88,356 is being told that
# nobody has, and handed the parts.
TOO_BIG = 20_000


@dataclass(slots=True)
class Breakdown:
    """A tree cut into pieces an `analyze` command can each read whole.

    `uncovered` is the honest half and is why this is a record rather than a list. **A part
    has to read what the breakdown says it reads** (rule 13), and one thing makes a
    directory fail that: **it had to be split.** `analyze` reads a directory *and everything
    under it*, so a directory whose children are already parts cannot also be one — the
    command for it would re-read them and would itself be the oversized analysis this
    mechanism exists to refuse. Its own files then belong to no part.

    **There were two, and the second is now a flag rather than a refusal.** A plugin's
    `skip_dirs` is matched against the path *relative to the analysed root*, so the same
    directory yields different files depending on where the walk started:
    `Engine/Source/ThirdParty` is 620 files seen from the top of Unreal and **57,373**
    walked as its own root, because the word `ThirdParty` — which the C++ reader skips — is
    no longer in any relative path. Found the hard way, and both directions were observed:
    the breakdown proposed `Engine/Binaries` and analysing it read **473 files nobody asked
    for** while reporting success, and it proposed `Engine/Source/ThirdParty`, which the
    guard then refused for being over the bound — the system catching its own advice. Two
    parts of Unreal's 86, 3,766 files of 88,356.

    Refusing to propose them was the interim answer and it covered less of the tree than the
    tree has. `analyze --part-of <tree>` judges every path-shaped rule from the tree while
    the root stays the part (`discover`), so such a directory can be a part again and reads
    what the breakdown claims. **The flag is what makes that safe, so every command this
    breakdown is printed as carries it** — one spelling, in `cli.part_argv`, rather than a
    rule kept at the call sites that would have to be right in each of them (rule 51).
    """

    total: int
    parts: list[tuple[Path, int]]
    uncovered: list[tuple[Path, int]]
    #: The same files by the reader that owns them -- what `estimate` prices a run from,
    #: counted off the one walk rather than a second (the docstring's "one walk" bargain).
    by_lang: dict[str, int] = field(default_factory=dict)

    @property
    def whole(self) -> bool:
        """Is the tree already one part? Then there is nothing to break down."""
        return not self.parts


def parts_under(root: Path, bound: int = TOO_BIG,
                rules: Sequence[DiscoveryRules] | None = None,
                judge_root: Path | None = None) -> Breakdown:
    """The tree cut into parts no larger than `bound`, or `[]` if it already is one.

    **The cut is adaptive, and that is what makes it worth printing.** Choosing a depth
    gives a reader 109 parts of wildly different sizes, most of them a handful of files;
    descending only into what is oversized gives the fewest parts that satisfy the bound,
    and for Unreal the largest of them comes out as `Engine/Source/Runtime` — 18,191 files,
    which is precisely the corpus the recorded run used. That is a good sign rather than a
    coincidence: the tree's own structure is what both the bound and the corpus came from.

    A directory that has to be split may also hold files of its own, and those are a part
    named for the directory itself. Without that they would belong to no part and the
    breakdown would silently cover less than the tree — design rule 1, in an instruction
    somebody is going to paste into a shell.

    **One walk, not one per candidate.** `discover` is a 52-second answer on a tree this
    size and asking it per directory would be quadratic; it is asked once and the paths are
    bucketed here. That also makes the parts exactly what an analysis would read — the same
    function, the same exclusions — rather than a second opinion about the tree (rule 51).

    **The count comes back either way** so that the one walk answers both questions: it is
    52 seconds on a tree this size, and asking a second time merely to say how big something
    is would be the more expensive half of the guard.

    **`judge_root` is `discover`'s and is passed through for the same reason the walk takes
    it** (rule 51): a breakdown of a part already being read as a piece of its tree has to
    cut the files that part actually reads, or the guard refuses the command the guard
    printed. It is asked here and nowhere else in this function -- the bucketing below is
    over paths relative to `root`, because those are what name a part.
    """
    found = list(discover(root, rules=rules, judge_root=judge_root))
    by_lang: dict[str, int] = {}
    for p in found:
        lang = ingest.language_of(p) or p.suffix
        by_lang[lang] = by_lang.get(lang, 0) + 1
    files = [p.relative_to(root) for p in found]
    if len(files) <= bound:
        return Breakdown(len(files), [], [], by_lang)

    # **A directory under a name a reader skips is a part again**, and the counts here are
    # already the right ones: `members` came out of the single `discover(root)` above, so
    # `Engine/Source/ThirdParty` is bucketed with the 620 files the tree admits and never
    # the 57,373 it holds. What used to be missing was a command that would read those 620,
    # and `--part-of` is it — so this function proposes the directory and `cli.part_argv`
    # writes the flag that makes the proposal true. `Breakdown` carries why.
    left: list[tuple[Path, int]] = []

    def cut(prefix: tuple[str, ...], members: list[tuple[str, ...]]) -> list[tuple[Path, int]]:
        if len(members) <= bound:
            return [(root.joinpath(*prefix) if prefix else root, len(members))]
        # `()` is a file sitting directly in this directory rather than under a child of it.
        groups: dict[tuple[str, ...], list[tuple[str, ...]]] = {}
        for rel in members:
            groups.setdefault(rel[:1] if len(rel) > 1 else (), []).append(rel[1:])
        own = groups.pop((), None)
        out: list[tuple[Path, int]] = []
        if not groups:
            # Nowhere left to descend: every file sits in this one directory and it is over
            # the bound. Reported as the oversized part it is rather than pretended about --
            # the reader can see the number and decide.
            return [(root.joinpath(*prefix) if prefix else root, len(members))]
        for head, rest in groups.items():
            out.extend(cut(prefix + head, rest))
        if own:
            # **Not a part**, because the command for this directory would read the children
            # above as well. See `Breakdown.uncovered`.
            left.append((root.joinpath(*prefix) if prefix else root, len(own)))
        return out

    parts = cut((), [p.parts for p in files])
    return Breakdown(
        len(files),
        sorted(parts, key=lambda kv: (-kv[1], str(kv[0]))),
        sorted(left, key=lambda kv: (-kv[1], str(kv[0]))),
        by_lang,
    )


def discover_docs(root: Path, suffixes: frozenset[str] = DOC_SUFFIXES,
                  nested: list[str] | None = None,
                  exclude: frozenset[Path] = frozenset(),
                  maps: list[str] | None = None,
                  not_files: dict[str, int] | None = None) -> Iterator[Path]:
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
                if (why := not_a_tree_file(p, root)):
                    if not_files is not None:
                        _tally(not_files, why)
                    continue
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
                                maps=stats.maps, not_files=stats.not_files))
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


def _runnable(files: list[Path], stats: WalkStats) -> list[Path]:
    """The discovered files, minus every language this machine cannot run a reader for.

    **Asked once per language that has files, before any cache key is read or any worker
    is started** — `probe_toolchain`'s own docstring said *before any store is opened*,
    and nothing asked it at all. A language with no files is never probed: a Python tree
    has no business failing for want of `go`.

    **Removed from `files` rather than skipped later, and that is `declined`'s placement
    for `declined`'s reason.** The files leave the walk before `live` is built, so they
    leave the store with it — the same as a language declined by name — and a map
    cannot carry last week's facts for a language this run did not read as though it
    had. The count leaves `by_lang` too, so the arithmetic of the residue still closes.

    `ToolchainMissing` and nothing broader: a `PluginRefused` is a build defect and still
    stops the run (rule 49). The sentence it raised is kept whole — it names the command,
    the versions and both ways forward — and the count is added here, because the count is
    the one part the probe cannot know.
    """
    owned = _by_language(files)
    gone: set[str] = set()
    for lang in sorted(owned):
        try:
            ingest.PLUGINS[lang].probe()
        except ToolchainMissing as exc:
            gone.add(lang)
            n = len(owned[lang])
            stats.no_toolchain[lang] = n
            stats.no_toolchain_said[lang] = str(exc)
            left = stats.by_lang.get(lang, 0) - n
            if left > 0:
                stats.by_lang[lang] = left
            else:
                stats.by_lang.pop(lang, None)
    if not gone:
        return files
    return [p for p in files if ingest.language_of(p) not in gone]


def _input_stat(path: str) -> list[int]:
    """What an input is compared by. `[-1, -1]` is a real answer: a file looked for and not
    found, which starts to matter the moment it exists (`compile_commands.json`)."""
    try:
        st = os.stat(path)
    except OSError:
        return [-1, -1]
    return [st.st_mtime_ns, st.st_size]


def _named(paths: Sequence[str], what: str) -> str:
    more = f" and {len(paths) - 1:,} more" if len(paths) > 1 else ""
    return f"`{paths[0]}`{more} {what}"


def _why_whole(lang: str, store: Store, owned: set[str], hashes: Mapping[str, str],
               known: Mapping[str, str], languages: Mapping[str, str]) -> str:
    """Why every file of a `facts_span_files` reader must be read, or `""` if none need be.

    **The reader parses all of them whenever it is opened**, because its edge pass answers
    about the whole compilation. So what this decides is whether their fresh facts are kept
    or dropped, and not whether they are parsed. Dropping them is what wrote fresh edges
    against stale facts (rule 81).

    **The marker is what a killed run leaves, and it says which kind of run that was** (rule
    80). `whole`: every hash may now match with half the facts old, so nothing else here could
    notice, and the whole read starts again. `rest`: a cold read, whose missing files are not
    additions to anything finished, so they do not re-read what it did finish. No marker and
    no row means this language has never been read, and everything is unread anyway.
    """
    marker = store.get_meta(_READING + lang) or ""
    if marker == "whole":
        return "a read of all of them was interrupted"
    changed = sorted(k for k in owned if k in known and hashes.get(k, known[k]) != known[k])
    if changed:
        return _named(changed, "changed")
    removed = sorted(k for k, owner in languages.items() if owner == lang and k not in owned)
    if removed:
        return _named(removed, "was removed")
    if not marker and any(owner == lang for owner in languages.values()):
        added = sorted(k for k in owned if k not in known and k in hashes)
        if added:
            return _named(added, "was added")
    held = json.loads(store.get_meta(_INPUTS + lang) or "{}")
    moved = sorted(p for p, stat in held.items() if _input_stat(p) != stat)
    if moved:
        return _named(moved, "changed")
    return ""


def analyze_tree(
    root: Path,
    store: Store,
    include_tests: bool = False,
    jobs: int | None = None,
    progress: Callable[[str, int, int], None] | None = None,
    declined: frozenset[str] = frozenset(),
    part_of: Path | None = None,
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

    **`part_of` reaches `discover` and nothing else.** It decides which files are *judged*
    in; every key written below is still relative to `root`, which is what keeps a part's
    stored paths and module names its own -- so two parts of one tree cannot collide, and a
    part re-read with the flag is the same map minus whatever the tree was hiding.
    """
    root = root.resolve()
    stats = WalkStats()

    files = sorted(discover(root, include_tests=include_tests, stats=stats,
                            declined=declined, judge_root=part_of))
    files = _runnable(files, stats)
    stats.found = len(files)

    known = store.known_hashes()
    held = _test_modules(store)
    # Under --include-tests the set is ignored, so its files are read as any other.
    left_out = {} if include_tests else {p: h for d in held.values() for p, h in d.items()}
    hashes: dict[str, str] = {}
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
        hashes[key] = hash_source(src)
        if known.get(key) == hashes[key]:
            stats.cached += 1
        elif left_out.get(key) == hashes[key]:
            # A test module, unchanged since the pass that named it: nothing to read, and
            # nothing in the store to keep. Its declaration lives in another file, and a
            # change to that file is what re-opens the question (see below).
            stats.cached += 1
        else:
            todo.append(p)

    # Before the prune, which forgets the only thing a removed file can still say.
    languages = store.known_langs()
    whole: dict[str, str] = {}
    owned = _by_language(files)
    keys = {lang: {stored_path(p.relative_to(root)) for p in paths}
            for lang, paths in owned.items()}
    for lang in owned:
        if ingest.PLUGINS[lang].manifest.facts_span_files:
            why = _why_whole(lang, store, keys[lang], hashes, known, languages)
            if why:
                whole[lang] = why
    if whole:
        wanted_now = set(todo)
        again = {p for lang in whole for p in owned[lang]
                 if stored_path(p.relative_to(root)) in hashes}
        stats.cached -= len(again - wanted_now)
        todo = [p for p in files if p in wanted_now or p in again]
        stats.reader_notes.extend(
            f"{lang} all {len(owned[lang]):,} files were read, because {why}"
            for lang, why in sorted(whole.items()))

    stats.removed = store.prune_missing(live)
    if not include_tests:
        # A run with --include-tests kept these files' facts; this one does not want them.
        # Applied here, before the early return, because nothing may have changed at all.
        _leave_out_test_modules(store, [p for p in left_out if p in known])
        for lang, d in held.items():
            if d:
                stats.test_modules[lang] = len(d)

    work = _by_language(todo)
    # **A reader killed before its edge pass** still owes it, with every file written and so
    # nothing above that looks like work. Asked for with no files.
    for lang in owned:
        if lang not in work and store.get_meta(_READING + lang):
            work[lang] = []

    if not work:
        store.conn.commit()
        return stats

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
        if plugin.manifest.supplies_edges:
            store.set_meta_now(_READING + lang, "whole" if lang in whole else "rest")
        plugin.open(root, owned.get(lang, []))
        stats.reader_notes.extend(f"{lang} {n}" for n in plugin.opened_notes)
        try:
            # One transaction per reader; per-file commits dominate otherwise — **and it
            # ends early when the log outgrows the page cache** (`settle_if_large`). The
            # two are not in tension: this still commits per burst rather than per file, and
            # what the bound removes is the case the sentence above never had to cover,
            # which is a burst so long that SQLite can never checkpoint the log it is
            # writing. Unreal's 84,159 C++ files in one transaction is that case.
            def write(ffs: Iterator[FileFacts], _lang: str = lang,
                      _plugin: ingest.IngestPlugin = plugin) -> None:
                for ff in ffs:
                    _verify_lang(ff, _lang)
                    # What a string *means* is decided here, for every language at once,
                    # and never by the reader that found it (rule 51). This is the one
                    # place both kinds of reader pass through, which is why it is here
                    # and not in each of the two wrappers.
                    literals.judge(ff, _plugin.manifest.reports_literals)
                    one_act(ff)
                    if ff.literals_dropped:
                        stats.literals_dropped[_lang] = (
                            stats.literals_dropped.get(_lang, 0) + ff.literals_dropped
                        )
                    if ff.tests_dropped:
                        stats.tests_dropped[_lang] = (
                            stats.tests_dropped.get(_lang, 0) + ff.tests_dropped
                        )
                    store.write_file_facts(ff)
                    store.settle_if_large()
                    stats.parsed += 1
                    if ff.errors:
                        stats.failed += 1

            with store.batch():
                write(plugin.extract(wanted, root, relay, jobs))
            # **Asked after the files and before `close`, and asked whether or not this
            # run read anything of this language.** A checker answers about the whole
            # compilation, so its answer is not a function of what changed -- and the set
            # is replaced whole for exactly that reason (see `SuppliedEdge`). Inside the
            # `try` because a reader that dies here must still be closed; outside the
            # `batch` because the edges are not this file's facts and share no
            # transaction with them.
            if plugin.manifest.supplies_edges:
                n = store.replace_supplied_edges(lang, plugin.edges())
                stats.supplied_edges[lang] = n
                # After the stream, which is what fills them; cleared for a reader that
                # sends none, so a binding never outlives the reader saying it.
                store.replace_supplied_bindings(
                    lang, plugin.edge_bindings if plugin.manifest.supplies_bindings else [])
                store.replace_value_uses(
                    lang, plugin.edge_uses if plugin.manifest.supplies_uses else [])
                store.replace_macro_callees(
                    lang, plugin.edge_macros if plugin.manifest.supplies_macro_callees else [])
                # After the edges, whose rows these replace for their sites (rule 2), and
                # cleared for a reader that sends none. How many there were is the reader's
                # to say, in its notes, which are relayed below.
                store.replace_supplied_touches(
                    lang, plugin.edge_touches if plugin.manifest.supplies_touches else [])
                store.replace_supplied_ways_in(
                    lang, plugin.edge_ways_in if plugin.manifest.supplies_ways_in else [])
                if plugin.edges_outside:
                    stats.edges_outside[lang] = plugin.edges_outside
                if plugin.edges_unknown:
                    stats.edges_unknown[lang] = plugin.edges_unknown
                if plugin.edges_read_beyond:
                    stats.read_beyond[lang] = list(plugin.edges_read_beyond)
                if plugin.edges_not_present:
                    stats.not_present[lang] = list(plugin.edges_not_present)
                stats.edge_notes.extend(f"{lang}: {n}" for n in plugin.edge_notes)
                # Beside what it said on opening, and bounded: a reader's account of its
                # pass is evidence, and a histogram of nine thousand missing packages is
                # not a summary (rule 91).
                said = plugin.edges_said
                stats.reader_notes.extend(f"{lang} {n}" for n in said[:_EDGES_SAID_SHOWN])
                if len(said) > _EDGES_SAID_SHOWN:
                    stats.reader_notes.append(
                        f"{lang} … and {len(said) - _EDGES_SAID_SHOWN} more lines about "
                        f"its edge pass")
                named = [p for p in plugin.edges_test_only if p in hashes]
                store.set_meta(f"{_TEST_MODULES}{lang}",
                               json.dumps({p: hashes[p] for p in named}, sort_keys=True))
                if not include_tests:
                    _leave_out_test_modules(store, named)
                    if named:
                        stats.test_modules[lang] = len(named)
                    else:
                        stats.test_modules.pop(lang, None)
                    # **A file the last pass left out and this one does not** -- its
                    # parent's `#[cfg(test)]` was removed. It was skipped above as a test
                    # module, so it has no facts; read it now, while the reader is open.
                    back = sorted(set(held.get(lang, {})) - set(named))
                    back = [p for p in back if p in hashes]
                    if back:
                        with store.batch():
                            write(plugin.extract([root / p for p in back], root, None, jobs))
                if plugin.manifest.facts_span_files:
                    store.set_meta(_INPUTS + lang, json.dumps(
                        {p: _input_stat(p) for p in plugin.edges_inputs}, sort_keys=True))
                store.conn.commit()
                store.set_meta_now(_READING + lang, "")
        finally:
            plugin.close()
        # A file whose reader died never arrives at all, so the reader is the only thing
        # that can say it existed -- see `IngestPlugin.lost`.
        stats.failed += plugin.lost
        done += len(wanted)
    return stats
