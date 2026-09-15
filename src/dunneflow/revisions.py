"""Where a revision's databases live, and how to find the newest.

A program directory holds one `source.db` -- the spine, never discarded (rule 25) --
and a graph and a document store **per revision**:

    output/mensores/
        source.db                       the revision index, and the bodies
        graph@2026-08-26T09-14-02Z.db
        docs@2026-08-26T09-14-02Z.db
        graph@2026-08-29T23-11-46Z.db
        docs@2026-08-29T23-11-46Z.db

Two points in time are then one `ATTACH` apart, which is the same join `docs.db` has
always used, and neither snapshot has to be moved, renamed or copied to be compared.

**The filename is a convenience; the identity is inside.** Every graph records its own
`meta.revision`, because a name is not an identity (rule 30) and a file someone renamed
must still be able to say what it is. The name is derived from the id by replacing the
colons, which are legal on this filesystem and a portability trap on others -- and the
replacement is order-preserving, so an ISO-8601 stamp still sorts lexically into
chronological order.

A directory written before this layout existed holds a bare `graph.db`. It is **read**
as the one revision it is, and never rewritten into the new shape: rule 20 says a read
may refuse but may never repair, and the same argument that stopped `Store.__init__`
discarding a stale graph stops this from quietly renaming someone's files. The next
`analyze` writes the new layout beside it.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path

GRAPH = "graph"
DOCS = "docs"
MAP = "map"
SEP = "@"

# What a map is recognised by, in one place. The pattern matches `graph.db` -- the legacy
# bare name -- as well as `graph@<revision>.db`.
GRAPH_DB = f"{GRAPH}*.db"


def names_a_map(names: Iterable[str]) -> bool:
    """Does this listing hold a map's spine?

    **The graph, and never a directory called `output`.** Blacklisting the name was the
    obvious test and is the wrong one: `output/` is a fine name for a directory of
    hand-written documents, and nothing should silently drop one because a tool the author
    has never heard of writes there (rule 30). What identifies a map is the one file it
    cannot be a map without.

    Taking *names* rather than a path is what lets `discover_docs` ask at no cost: `os.walk`
    has already listed the directory, so the answer is in `filenames` and needs no `stat` --
    which is the same bargain rule 57's checkout marker strikes one test over.

    Two residues, both older than this function and neither changed by it. A stray 0-byte
    `graph.db` -- which `sqlite3.connect` will leave behind -- makes an empty directory look
    like a program, and `store.refuse_missing` is the other side of that. And a map
    directory whose `graph*.db` has been deleted by hand is **not** recognised, which is
    reachable through `CLAUDE.md`'s recipe for dropping a superseded sealed snapshot; its
    `map@<revision>/` would then be read as prose. Recognising a map by anything else means
    recognising it by a name, and that is what was rejected.
    """
    return any(fnmatch(n, GRAPH_DB) for n in names)


def holds_a_map(where: Path) -> bool:
    """`names_a_map` for a caller holding a path rather than a listing.

    The same question and the same answer; `glob` is the listing, taken here rather than
    handed in. Kept beside it so the two forms cannot drift into two answers (rule 51) --
    they were three separate spellings of `glob("graph*.db")` before this existed, two in
    `program_dirs` and one re-implemented in `serve.where`, whose own docstring called it
    "the same question `analyze` asks".
    """
    return any(where.glob(GRAPH_DB))


def stamp() -> str:
    """A revision id: when the source was captured, to the second."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def as_filename(revision: str) -> str:
    """`2026-08-29T23:11:46Z` -> `2026-08-29T23-11-46Z`.

    Order-preserving, so filenames still sort into chronological order: `:` is 0x3A and
    `-` is 0x2D, and both are replaced everywhere they occur.
    """
    return revision.replace(":", "-")


def db_path(out_dir: Path, stem: str, revision: str) -> Path:
    return out_dir / f"{stem}{SEP}{as_filename(revision)}.db"


def map_dir(out_dir: Path, revision: str) -> Path:
    """Where the written map for one revision goes.

    A **directory** rather than fifteen `01-entrypoints@<revision>.md`, and the reason is
    the links: the map's own README points at its fourteen siblings by bare name, and every
    one of those would have to be rewritten per revision to say the same thing. Inside a
    directory of its own they are already right, and the program directory stays something
    a person can look at.

    The same `@` idiom as the databases beside it, so a listing of the program directory
    reads as one layout rather than two, and the same order-preserving replacement of the
    colons -- see `as_filename`.
    """
    return out_dir / f"{MAP}{SEP}{as_filename(revision)}"


def known_maps(out_dir: Path) -> dict[str, Path]:
    """Every written map in a program directory, by the revision its name claims.

    A *claim*, like `revision_of`'s: the authority for what a map describes is the
    `analysed_at` and the counts inside it, and nothing renames one on the reader's behalf.
    Directories only -- a file called `map@…` is not a map and is left where it is rather
    than reported as one.
    """
    found: dict[str, Path] = {}
    if not out_dir.is_dir():
        return found
    for child in sorted(out_dir.glob(f"{MAP}{SEP}*")):
        if not child.is_dir():
            continue
        rev = revision_of(child)
        if rev:
            found[rev] = child
    return found


def known(out_dir: Path, stem: str) -> list[Path]:
    """Every revision-named database for `stem`, newest first."""
    return sorted(out_dir.glob(f"{stem}{SEP}*.db"), key=lambda p: p.name, reverse=True)


def newest(out_dir: Path, stem: str) -> Path | None:
    """The database a reader should open when nobody has said which revision.

    Revision-named files first, newest by name; then the bare legacy file. Returns None
    when there is nothing to read at all, which the caller must report rather than
    silently answering out of an empty store -- `(no rows)` and "no such program" are
    different answers (rule 20).
    """
    for p in known(out_dir, stem):
        return p
    legacy = out_dir / f"{stem}.db"
    return legacy if legacy.exists() else None


def resolve(out_dir: Path, stem: str, revision: str | None = None) -> Path | None:
    """The database for one named revision, or the newest when none is named."""
    if revision is None:
        return newest(out_dir, stem)
    p = db_path(out_dir, stem, revision)
    return p if p.exists() else None


def program_dirs(out_root: Path) -> frozenset[Path]:
    """Every directory under `out_root` that holds a DunneFlow map, `out_root` included.

    Written for one job: keeping a program's own output out of its own document corpus.
    Analysing DunneFlow itself read 46 of 54 documents out of `output/` -- its own generated
    reports, including 369,684 words about a *different* program -- and every rule it then
    claimed came from them. That is rule 57 with the tool's own output in place of a stale
    worktree.

    **A directory holding a graph, never a directory called `output`** -- see
    `names_a_map`, which is where that test and its residues now live.

    One level down and no deeper, and that bound is honest here while the sentence which
    used to defend it was not. It read: *a recursive search of a documentation root for
    databases would cost every project a walk to protect against a layout nobody uses.*
    **That layout is what an installed application does.** Frozen, the output root is
    `~/Library/Application Support/DunneFlow`, so it is nowhere near the tree being read
    and this function has nothing of that tree to enumerate -- and a checkout's own
    `output/` full of maps went into the corpus of every analysis the packaged build made.
    Measured on DunneFlow's own map, 2026-09-10: **122 of 147 documents** came out of
    `output/`, and **all 122** of the naming rules it then stated were about a different
    program. Rule 92.

    The walk it declined to pay for was one `discover_docs` was already making, so that is
    where the question is asked of the tree now. What is left here is the job this can do
    that a walk cannot: answer for the **output root**, cheaply and before any walk starts,
    which is what `serve` and `roots` ask it for.
    """
    if not out_root.is_dir():
        return frozenset()
    found = {out_root} if holds_a_map(out_root) else set()
    for child in out_root.iterdir():
        # `is_dir()` rather than a `try`: an unreadable entry is not a program directory,
        # and an analysis must not fail because something odd sits beside its output.
        if child.is_dir() and holds_a_map(child):
            found.add(child)
    return frozenset(found)


def revision_of(path: Path) -> str | None:
    """The revision a filename claims, or None for a legacy bare name.

    A *claim*, and only that: the authority is `meta.revision` inside the file. This
    exists so a listing can be built without opening several hundred megabytes.
    """
    # `Path.stem` on a directory is its whole name, which is what `known_maps` wants: a
    # map directory has no suffix to strip and a database has one that must go.
    stem = path.stem
    if SEP not in stem:
        return None
    named = stem.split(SEP, 1)[1]
    if not named:
        return None
    # Only the *time* separators were replaced; the date's own dashes are part of it.
    date, sep, clock = named.partition("T")
    return f"{date}T{clock.replace('-', ':')}" if sep else named
