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

from datetime import UTC, datetime
from pathlib import Path

GRAPH = "graph"
DOCS = "docs"
SEP = "@"


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


def revision_of(path: Path) -> str | None:
    """The revision a filename claims, or None for a legacy bare name.

    A *claim*, and only that: the authority is `meta.revision` inside the file. This
    exists so a listing can be built without opening several hundred megabytes.
    """
    stem = path.stem
    if SEP not in stem:
        return None
    named = stem.split(SEP, 1)[1]
    if not named:
        return None
    # Only the *time* separators were replaced; the date's own dashes are part of it.
    date, sep, clock = named.partition("T")
    return f"{date}T{clock.replace('-', ':')}" if sep else named
