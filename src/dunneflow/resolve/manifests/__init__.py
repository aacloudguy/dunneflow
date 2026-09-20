"""What a program **declares** about itself, read from the files that declare it.

A manifest is the one place a program states its contract with whoever installs it:
`[project.scripts]` is not a heuristic, and neither is a `package.json` `bin`. Anything
found here outranks a decorator or a naming convention, and the field that says so is
`Entrypoint.declared` -- a **field**, because `flows.py` used to decide it with
`"[project.scripts]" in e.evidence`, a substring test against a sentence
`web/waysin.py:120` renders verbatim (rule 30).

**One provider per filename, and the evidence is the provider's own.** A `package.json`
entry claiming to come from `pyproject.toml` would be a visible falsehood in the one string
a reader is shown unparsed. That is also why this is six small modules rather than one
reader with six branches: the sentence and the rule that produced it live together.

**Two manifests at one level is the ordinary polyglot repository, not an error.** DunneNote
carries a `package.json` and a `Cargo.toml` side by side and both declare `0.9.0`; Society
carries a `package.json` beside its `pyproject.toml` and the JavaScript one declares
nothing at all. Both are read, both are recorded, and **nothing is picked** when they
disagree -- two declared versions is the honest answer and also a signal, because a tree
stating two may be two programs.

**Entrypoints and version are independent columns.** `go.mod` declares a module path and no
version of the program; `Package.swift` declares executables and no version at all. Saying
so beats inventing one.

**Discovery is the whole tree, not a walk up it.** Tom's criterion, 2026-09-17: *any module
that has inputs and/or outputs is included, because that is flow -- it must include the
entire application.* A `bin` is a way in, and a way in is where flow starts, so a manifest
is read wherever the code walk reaches one. The walk decides *where* -- `walk.discover`,
off the listing it already took, which already prunes `SKIP_DIRS`, every dotted directory
and every directory holding a map (rule 92's shape) -- and the providers decide *what*. The
package root is read as well, because a `src/` layout puts it above the analysed tree.

**The package root's manifests answer the program's version; a nested one does not.** A
member's version is a fact about the member, kept in its own reading and named in the
report. Promoting it would make the program's version depend on how deep somebody looked.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from ...schema import stored_path
from . import cargo, gomod, gradle, packagejson, pyproject, swiftpm
from .records import ManifestEntry, ManifestReading, Provider, TargetKind

__all__ = [
    "MANIFEST_FILES", "PROVIDERS", "ManifestEntry", "ManifestReading", "ManifestStats",
    "Provider", "TargetKind", "disagree", "find_package_root", "names_a_manifest",
    "read", "read_all", "residue", "summary", "versions",
]

# The providers, in the order a version is trusted when several root manifests declare one.
#
# **Stated rather than emergent** (rule 66). This is not a claim that a `pyproject.toml` is
# more truthful than a `package.json`; it is a claim that when two disagree the tool must
# answer the same way twice, and a written-down order is the only one a reader can look up.
# Both declarations are recorded either way -- `versions()` returns all of them -- so what
# this decides is which one the single-valued `program_version` key carries, never which
# one is true.
PROVIDERS: tuple[Provider, ...] = (
    pyproject.PROVIDER,
    packagejson.PROVIDER,
    cargo.PROVIDER,
    gomod.PROVIDER,
    swiftpm.PROVIDER,
    gradle.PROVIDER,
)

# Every filename that declares something. Derived from the providers rather than written
# out beside them, because a hand-kept second list drifts the moment somebody adds a
# provider -- the same defence `core_extraction_inputs` names, and rule 51's shape.
MANIFEST_FILES: frozenset[str] = frozenset(p.filename for p in PROVIDERS)

_BY_NAME: dict[str, Provider] = {p.filename: p for p in PROVIDERS}


@dataclass(slots=True)
class ManifestStats:
    """What this run read, for the sentence it prints and the table it writes."""

    readings: list[ManifestReading] = field(default_factory=list)
    bound: int = 0
    unbound: int = 0


def names_a_manifest(filenames: Iterable[str]) -> bool:
    """Does this directory listing hold a manifest?

    Asked of the listing `os.walk` already took, never by globbing the directory again --
    `revisions.names_a_map` sets the precedent and rule 92 is why it matters.
    """
    return any(fn in MANIFEST_FILES for fn in filenames)


def find_package_root(target: Path, ceiling: Path | None = None) -> tuple[Path, list[Path]]:
    """The nearest ancestor holding **any** manifest, and every manifest at that level.

    This generalises the `pyproject.toml` walk-up that stood in `cli.py:283` -- the whole
    truth while Python was the only language, and an answer of *no* for every TypeScript,
    Rust, Go and Swift tree there is.

    Returns `target` itself when nothing above declares anything, which is the state a bare
    directory of source is in and is not an error.

    **Every manifest at that level, not the first.** Two at one level is DunneNote, and
    stopping at the first would make the answer depend on which filename sorts earlier.

    **`ceiling` is where the climb stops, and the climb had none.** This walk decides two
    things a reader will never trace back to it -- the **documentation root** (`cli.py`
    passes `pkg_root` to `analyze_docs_tree`) and the leaf that **identifies the tree**
    (rule 64) -- and it climbed to the filesystem root looking for any of six filenames.
    Measured on 2026-09-20, analysing a part of Unreal: the climb went four levels past
    the tree into the *Developer directory itself*, which holds a stray `package.json`,
    and the document walk then read **every project on this machine**. Each of the 85
    Unreal maps holds the same 15,497 documents, **2,607 of them from programs that are
    not Unreal** -- and a document is evidence (design rule 11), so their glossaries,
    naming standards, mirrors and traceability were all measured partly over somebody
    else's vocabulary. It cost about 205 s a part, which over 85 parts is most of a
    327-minute run.

    `None` keeps the unbounded climb, which is what a whole-program analysis wants and
    what rule 64 was minted on: `.../society-2026-08-26/src` really does belong to the
    `pyproject.toml` one level up. **`analyze --part-of <tree>` supplies the ceiling**,
    because a part of a tree cannot belong to a package above that tree -- that is what
    being a part means. The general case, an `analyze` of a bare subdirectory with no
    `--part-of`, still climbs without one and is stated in `BACKLOG.md`: nothing in the
    arguments says where to stop, and guessing at a stopping condition would be a rule
    with no evidence behind it.
    """
    for candidate in (target, *target.parents):
        found = sorted(candidate / n for n in MANIFEST_FILES if (candidate / n).is_file())
        if found:
            return candidate, found
        if ceiling is not None and candidate == ceiling:
            # The tree itself declares nothing, so the part is its own package root. Not
            # a failure and not a fallback: it is the same answer an unbounded climb gives
            # for a bare directory of source, arrived at honestly rather than by carrying
            # on until something unrelated matched (rule 49).
            break
    return target, []


def read(path: Path, *, relative_to: Path, at_root: bool = False) -> ManifestReading | None:
    """Read one manifest through the provider that claims its name.

    `relative_to` is the **analysed** tree, so a package root above a `src/` layout is
    honestly written `../pyproject.toml`. `os.path.relpath` rather than
    `Path.relative_to`, which cannot express `..` and would raise on most real layouts;
    through `stored_path` because this lands in the same column as a routine's file and
    must be spelled the same way whichever platform wrote it (rules 60 and 93).

    A file that cannot be read at all yields `None`. A file that can be read and cannot be
    *parsed* yields a reading whose note says so, because those are different facts and
    only one of them is about this program.
    """
    provider = _BY_NAME.get(path.name)
    if provider is None:
        return None
    where = stored_path(os.path.relpath(path.resolve(), Path(relative_to).resolve()))
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    got = provider.read(text, path, where)
    return None if got is None else replace(got, at_root=at_root)


def read_all(roots: Sequence[Path], nested: Sequence[Path], *,
             relative_to: Path) -> list[ManifestReading]:
    """Every manifest, root ones first, deduplicated by the file each one actually is.

    A package root that **is** the analysed tree appears in both lists, and reading it
    twice would declare its ways in twice -- which `INSERT OR REPLACE` would hide and the
    version list would not.
    """
    seen: set[Path] = set()
    out: list[ManifestReading] = []
    for path, at_root in [*((p, True) for p in roots), *((p, False) for p in nested)]:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        got = read(path, relative_to=relative_to, at_root=at_root)
        if got is not None:
            out.append(got)
    return out


def versions(readings: Sequence[ManifestReading]) -> list[ManifestReading]:
    """The **root** manifests that declare a version, in `PROVIDERS` order.

    All of them, because nothing is picked. The caller records every one and the cover
    says so when they differ.
    """
    order = {p.filename: i for i, p in enumerate(PROVIDERS)}
    stated = [r for r in readings if r.at_root and r.version is not None]
    return sorted(stated, key=lambda r: (order.get(r.filename, len(order)), r.where))


def disagree(readings: Sequence[ManifestReading]) -> bool:
    """Do the root manifests state more than one version between them?"""
    return len({r.version.value for r in versions(readings) if r.version}) > 1


def residue(readings: Sequence[ManifestReading]) -> list[str]:
    """What the providers declined, in their own words, or nothing at all.

    **One line per kind of refusal, never one per manifest**, which is `walk_residue`'s
    rule and was paid for here before it was copied: DunneNote's twenty manifests produce
    twenty-one notes and eleven of them are the same sentence about
    `version.workspace = true`. A report nobody reads to the end is design rule 1's letter
    without its point.

    A note that fired once keeps the file it came from, because one path is the useful
    half of a single finding. A note that fired more than once states how many and where
    the first was, because the name and the count is what anybody acts on.
    """
    order: list[str] = []
    where: dict[str, list[str]] = {}
    for r in readings:
        for note in r.notes:
            if note not in where:
                order.append(note)
                where[note] = []
            where[note].append(r.where)
    out = []
    for note in order:
        seen = where[note]
        out.append(f"{seen[0]}: {note}" if len(seen) == 1
                   else f"{seen[0]} and {len(seen) - 1:,} other"
                        f"{'' if len(seen) == 2 else 's'}: {note}")
    return out


def summary(readings: Sequence[ManifestReading]) -> str:
    """*manifests 7: package.json 0.9.0 · Cargo.toml 0.9.0 · 3 ways in declared*.

    The versions are the **root** ones, because that is what the program claims about
    itself; the count of ways in is every manifest's, because that is what reached the
    map. Two numbers over two populations, said apart (rule 32).
    """
    if not readings:
        return "manifests 0: nothing here declares a way in or a version"
    parts = [f"{r.filename} {r.version.value}" for r in versions(readings) if r.version]
    declared = sum(len(r.entries) for r in readings)
    parts.append(f"{declared} way{'' if declared == 1 else 's'} in declared")
    return f"manifests {len(readings)}: " + " · ".join(parts)
