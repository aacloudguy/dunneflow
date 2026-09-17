"""Bring a program directory's stored paths from absolute to relative, in place.

Every path in every store used to be absolute. That is wrong in four separate ways, and
three of them are about a program directory being a thing someone can *hand over*:

* it leaks one machine's directory layout to everyone the stores are given to;
* it breaks the moment a tree is moved, which people do to manage disk space;
* it breaks outright when a program directory is copied to another machine;
* and -- worst here -- two revisions read from two different trees give the same file two
  unrelated keys, so nothing can pair a file with itself across two points in time. On
  Mensores that read as **0 identical, 628 added, 625 removed** where the truth is 613
  identical, 12 modified, 3 added, 0 removed. The one question two revisions exist to ask
  could not be asked.

**In place, rather than by re-analysis.** Re-extracting is the sanctioned way to rebuild a
stale graph (rule 12), and it is the wrong instrument here for a reason that matters: a
sealed snapshot is kept precisely so it can be read after its source tree is gone, and
rebuilding would orphan exactly those. Nothing about what a call, a boundary or a constant
*is* has moved -- only the spelling of a column -- so this is rule 25's argument applied to
a derived store: no rule was applied to a path, so no rule change can make one wrong.

**Writable opens only.** A reader refuses an unmigrated store and names this command; it
may never repair one on the way past (rule 20). That is the same division `Store._is_stale`
already keeps between deciding and dropping.

## Re-stamping the extractor fingerprint, and why it is allowed exactly once

Making paths relative meant editing the extractors, which changes `rules_fingerprint()`,
which makes every existing store stale -- so a correctly migrated graph would be one nobody
could open. This module therefore re-stamps `meta.extractor` as well.

That is defensible **only because this migration performs exactly the transformation the
new fingerprint stands for**. To stop it becoming a general licence, it is gated on the
stored fingerprint being the specific value in force immediately before that edit. A store
carrying any other fingerprint is stale for reasons this module cannot speak to, and is
refused rather than re-stamped.

## Which columns hold a filesystem path

Named, and asserted complete -- not matched by name. `headings.path` in the document store
holds a *heading trail* ("Atheris fuzz crash"), and a migration that rewrote every column
called `path` would have been reading a name as a meaning, which is rule 5. Every column
named `file` or `path` in either store must appear below as either migrated or exempted;
`tests/test_migrate.py` derives both sets from the schema and fails on an unknown one, so
adding a table cannot silently leave a column absolute (rule 36).
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from . import revisions
from .schema import stored_path

# The marker. Present means "the paths in this store are relative to the tree it was read
# from"; absent means a store written before that was true. Deliberately **not** the
# schema version: bumping that discards the graph, which is the outcome this whole module
# exists to avoid.
META_PATHS = "paths"
PATHS_RELATIVE = "relative"

# The fingerprints every store carried immediately before paths became relative. A store
# holding one of these, and nothing else, is one this migration can honestly re-stamp --
# see the module docstring. Recorded as constants rather than computed, because the whole
# point is to name a *specific* prior state.
PREVIOUS_CODE_EXTRACTOR = "5:ec365db458b9d64e"
PREVIOUS_DOC_EXTRACTOR = "6:8db97e125e922bd0"

# The columns that hold a filesystem path, per store kind. `files.path` and every `file`
# column in the graph; `documents.path` in the document store; `paths.path` in the sidecar.
GRAPH_EXEMPT: dict[str, str] = {}
DOCS_EXEMPT = {
    "headings.path": "a trail of parent headings, not a filesystem path",
}
SOURCE_EXEMPT: dict[str, str] = {}


class MigrationRefused(Exception):
    """This store cannot be migrated, and the message says what to do instead."""


@dataclass
class StoreReport:
    """What one database's migration did, per column, so the total can be checked."""

    path: Path
    kind: str
    root: str = ""
    rewritten: dict[str, int] = field(default_factory=dict)
    # Paths that were *above* the analysed tree and are now `../something`. Kept apart
    # from `rewritten` so the count says what it counted (rule 32).
    above: dict[str, int] = field(default_factory=dict)
    already: bool = False

    @property
    def total(self) -> int:
        return sum(self.rewritten.values()) + sum(self.above.values())


@dataclass
class Report:
    stores: list[StoreReport] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(s.total for s in self.stores)

    @property
    def migrated(self) -> list[StoreReport]:
        return [s for s in self.stores if not s.already]


# --------------------------------------------------------------------------- #
# Reading the state of a store
# --------------------------------------------------------------------------- #


def paths_are_relative(conn: sqlite3.Connection) -> bool:
    """Does this store hold relative paths? Answered from the marker, not from the data.

    A store with no rows in it has no absolute path to find, and guessing "relative"
    from that would call an empty legacy store migrated. The marker is a statement
    somebody made; the absence of evidence is not one.
    """
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = ?", (META_PATHS,)
        ).fetchone()
    except sqlite3.Error:
        return False
    return row is not None and str(row[0]) == PATHS_RELATIVE


def _meta(conn: sqlite3.Connection, key: str) -> str:
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    except sqlite3.Error:
        return ""
    return "" if row is None else str(row[0])


def migration_speaks_for(conn: sqlite3.Connection, previous: str) -> bool:
    """Would this migration actually rewrite this store, or refuse it?

    **The question a refusal has to ask before naming this command.** `_refuse_if_stale`
    branched on `paths_are_relative` alone and told every unmigrated store to run
    `dunneflow migrate`, which is only true for a store carrying the *one* fingerprint
    `_require_previous` can honestly re-stamp. Everything older gets a sentence naming a
    command that refuses it in turn -- rule 49's shape in prose, a plausible remedy
    standing where the real one should be, and it cost nothing until somebody kept an old
    map. Three of the four program directories in this project's own `output/` were in
    exactly that state on 2026-09-08: `beads` (extractor unrecorded, schema 1),
    `dunneflow` and `mensores@2026-08-29T19-43-39Z` (both `5:...`, neither the gated
    value). Every one of them was told to migrate; every one of them, run, was refused.

    **The fingerprint and not the root.** `_migrate_one` has a second refusal -- a store
    that records no tree has nothing to be made relative *to* -- and this deliberately
    does not test for it. That root is read per revision in `recorded_roots`, from a graph
    that may not be the store being refused, so answering it here would mean rebuilding
    the migration's own bookkeeping inside a read path to word a sentence. It is also
    reachable only *past* this gate, so a store this returns `True` for and migration then
    refuses is told the truth twice, one refusal after the other, which is the honest
    failure rather than the plausible one.
    """
    return not paths_are_relative(conn) and _meta(conn, "extractor") == previous


def path_columns(conn: sqlite3.Connection, exempt: dict[str, str]) -> list[tuple[str, str]]:
    """Every (table, column) in this store that holds a filesystem path.

    Read from the schema so a table added later is included without anyone remembering,
    and filtered by an **exemption list that names its reasons** -- an unknown column
    called `path` is a question, not a default (rule 36, and rule 5 for why a name is not
    a meaning).
    """
    found: list[tuple[str, str]] = []
    tables = [
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    for tbl in tables:
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{tbl}")')]
        for col in cols:
            if col not in ("file", "path"):
                continue
            if f"{tbl}.{col}" in exempt:
                continue
            found.append((tbl, col))
    return found


# --------------------------------------------------------------------------- #
# The rewrite
# --------------------------------------------------------------------------- #


def _strip(conn: sqlite3.Connection, tbl: str, col: str, root: str) -> tuple[int, int]:
    """Rewrite every absolute path in one column against `root`. Returns (under, above).

    Two transforms, because a stored path is not always *under* the tree that was analysed.
    Packaging metadata is the case that proves it: for a `src/` layout `pyproject.toml`
    sits one directory above the code, so `entrypoints.file` legitimately becomes
    `../pyproject.toml` and a prefix strip cannot reach it. A first version did only the
    strip and left those four rows absolute in every graph -- correct-looking, since the
    other 54,746 moved, and wrong in the one place the ground truth lives.

    So: `substr` for what is under the root, and `os.path.relpath` for what is above it,
    which is exactly what `entrypoints_from_packaging` now does when writing -- through
    `stored_path`, as it does, because a `..` computed on Windows comes back spelled with a
    backslash and the two have to agree on the spelling as well as on the path. The two
    agree by construction rather than by memory. They are **counted separately** because a
    `..` path is worth an operator knowing about, and a total that hid it would be rule 32's
    defect -- a number that does not say what it counted.

    A path that is already relative is left untouched: this migration runs once, and a
    second pass must not treat `mensores/cli.py` as something to make relative again.

    The **absolute** test is `LIKE '/%'` and stays that way. Every store this migration is
    allowed to speak for was written by one named build, on macOS, and holds POSIX absolute
    paths; a drive-letter test here would be a branch for a store that cannot exist
    (rule 62 -- this speaks for exactly one prior state, and that state is that one).
    """
    prefix = root.rstrip("/") + "/"
    under = conn.execute(
        f'UPDATE "{tbl}" SET "{col}" = substr("{col}", :n) WHERE "{col}" LIKE :like',
        {"n": len(prefix) + 1, "like": prefix.replace("%", r"\%") + "%"},
    ).rowcount or 0

    # Whatever is still absolute is outside the tree, and `relpath` is the only spelling
    # that can say so. Done value by value rather than in SQL, because there is no SQL for
    # it and because there are four of them.
    above = 0
    outside = [r[0] for r in conn.execute(
        f'SELECT DISTINCT "{col}" FROM "{tbl}" WHERE "{col}" LIKE ?', ("/%",))]
    for value in outside:
        above += conn.execute(
            f'UPDATE "{tbl}" SET "{col}" = ? WHERE "{col}" = ?',
            (stored_path(os.path.relpath(str(value), prefix.rstrip("/"))), value),
        ).rowcount or 0
    return int(under), int(above)


def _require_previous(conn: sqlite3.Connection, path: Path, want: str) -> None:
    """Refuse anything but the one prior state this migration can speak for."""
    have = _meta(conn, "extractor")
    if have == want:
        return
    raise MigrationRefused(
        f"{path.name} was written by extractor {have or '(unrecorded)'}, and this "
        f"migration can only speak for {want} — it re-stamps the fingerprint on the "
        f"claim that making paths relative is the only thing that changed, which it "
        f"cannot claim about any other version. Re-run `dunneflow analyze` instead."
    )


def _migrate_one(path: Path, kind: str, root: str, root_key: str,
                 previous: str, new_extractor: str,
                 exempt: dict[str, str]) -> StoreReport:
    """Migrate one database, or leave it exactly as it was.

    Everything happens in one transaction: a store half-rewritten is worse than one not
    rewritten at all, because nothing downstream could tell which half it was reading.
    """
    rep = StoreReport(path=path, kind=kind, root=root)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        if paths_are_relative(conn):
            rep.already = True
            return rep
        _require_previous(conn, path, previous)
        if not root:
            raise MigrationRefused(
                f"{path.name} does not record the tree it was read from, so there is "
                f"nothing to make its paths relative to"
            )
        conn.execute("BEGIN")
        for tbl, col in path_columns(conn, exempt):
            under, above = _strip(conn, tbl, col, root)
            if under:
                rep.rewritten[f"{tbl}.{col}"] = under
            # Stated apart from the rest. `../pyproject.toml` is a real and correct answer,
            # and it is also the kind of row somebody should look at once.
            if above:
                rep.above[f"{tbl}.{col}"] = above
        # The root goes with the paths. Keeping it would leave the leak this migration
        # exists to close, one meta key instead of fifty thousand rows.
        conn.execute("DELETE FROM meta WHERE key = ?", (root_key,))
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
                     (META_PATHS, PATHS_RELATIVE))
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
                     ("extractor", new_extractor))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return rep


def _migrate_source(path: Path, roots: dict[str, str]) -> StoreReport:
    """Migrate the sidecar, whose paths are relative to a *different root per revision*.

    The sidecar records no root of its own -- the one fact saying where a revision's code
    came from lived only in the graph beside it, which is the wrong way round for the one
    store that is never discarded. `roots` is read out of the graphs before any of them is
    touched, because migrating a graph deletes the very key this needs.

    A revision with no graph beside it is **refused and named**, never guessed. A longest
    common prefix would be a plausible root and plausibly wrong, and rule 20 says a store
    may be refused but never repaired on a guess.
    """
    rep = StoreReport(path=path, kind="source")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        if paths_are_relative(conn):
            rep.already = True
            return rep
        present = [
            str(r[0]) for r in conn.execute(
                "SELECT DISTINCT revision FROM paths ORDER BY revision"
            )
        ]
        missing = [r for r in present if not roots.get(r)]
        if missing:
            raise MigrationRefused(
                f"{path.name} holds bodies for {', '.join(missing)} and there is no "
                f"graph beside it recording which tree they were read from, so their "
                f"paths cannot be made relative to anything. Analyse that tree again, "
                f"or remove the revision with `dunneflow revisions`."
            )
        conn.execute("BEGIN")
        for rev in present:
            prefix = roots[rev].rstrip("/") + "/"
            cur = conn.execute(
                "UPDATE paths SET path = substr(path, :n) "
                "WHERE revision = :rev AND path LIKE :like",
                {"n": len(prefix) + 1, "rev": rev,
                 "like": prefix.replace("%", r"\%") + "%"},
            )
            if cur.rowcount:
                rep.rewritten[f"paths.path@{rev}"] = int(cur.rowcount)
        conn.execute("DELETE FROM meta WHERE key = 'source_root'")
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
                     (META_PATHS, PATHS_RELATIVE))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return rep


# --------------------------------------------------------------------------- #
# The whole program directory
# --------------------------------------------------------------------------- #


def recorded_roots(out_dir: Path) -> dict[str, str]:
    """Every revision's source tree, read from the graph that recorded it.

    Read-only, and taken **before** anything is migrated: `_migrate_one` deletes the key
    this reads, so asking afterwards would answer nothing for every store that succeeded.
    """
    roots: dict[str, str] = {}
    for g in revisions.known(out_dir, revisions.GRAPH):
        rev = revisions.revision_of(g)
        conn = sqlite3.connect(f"file:{g}?mode=ro", uri=True)
        try:
            root = _meta(conn, "source_root")
        finally:
            conn.close()
        if rev and root:
            roots[rev] = root
    legacy = out_dir / f"{revisions.GRAPH}.db"
    if legacy.exists():
        conn = sqlite3.connect(f"file:{legacy}?mode=ro", uri=True)
        try:
            rev, root = _meta(conn, "revision"), _meta(conn, "source_root")
        finally:
            conn.close()
        if rev and root:
            roots.setdefault(rev, root)
    return roots


def migrate_program(out_dir: Path) -> Report:
    """Make every stored path in one program directory relative, in place.

    Order is load-bearing. The graphs' recorded roots are read first, because the sidecar
    has no root of its own and migrating a graph deletes the key that supplies it.
    """
    from .detectors import rules_fingerprint
    from .detectors.prose import doc_rules_fingerprint
    from .schema import DOC_SCHEMA_VERSION, SCHEMA_VERSION

    report = Report()
    roots = recorded_roots(out_dir)

    source_db = out_dir / "source.db"
    if source_db.exists():
        report.stores.append(_migrate_source(source_db, roots))

    graphs = list(revisions.known(out_dir, revisions.GRAPH))
    legacy_graph = out_dir / f"{revisions.GRAPH}.db"
    if legacy_graph.exists():
        graphs.append(legacy_graph)
    for g in graphs:
        report.stores.append(_migrate_one(
            g, "graph", roots.get(revisions.revision_of(g) or "", ""), "source_root",
            PREVIOUS_CODE_EXTRACTOR, f"{SCHEMA_VERSION}:{rules_fingerprint()}",
            GRAPH_EXEMPT,
        ))

    docs = list(revisions.known(out_dir, revisions.DOCS))
    legacy_docs = out_dir / f"{revisions.DOCS}.db"
    if legacy_docs.exists():
        docs.append(legacy_docs)
    for d in docs:
        conn = sqlite3.connect(f"file:{d}?mode=ro", uri=True)
        try:
            docs_root = _meta(conn, "docs_root")
        finally:
            conn.close()
        report.stores.append(_migrate_one(
            d, "docs", docs_root, "docs_root",
            PREVIOUS_DOC_EXTRACTOR, f"{DOC_SCHEMA_VERSION}:{doc_rules_fingerprint()}",
            DOCS_EXEMPT,
        ))

    return report


__all__ = [
    "DOCS_EXEMPT",
    "GRAPH_EXEMPT",
    "META_PATHS",
    "PATHS_RELATIVE",
    "PREVIOUS_CODE_EXTRACTOR",
    "PREVIOUS_DOC_EXTRACTOR",
    "SOURCE_EXEMPT",
    "MigrationRefused",
    "Report",
    "StoreReport",
    "migrate_program",
    "migration_speaks_for",
    "path_columns",
    "paths_are_relative",
    "recorded_roots",
]
