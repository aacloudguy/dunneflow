"""`source.db` -- the bytes that were actually measured, kept beside the map.

A third store, parallel to `graph.db` and `docs.db` and never inside either, for the same
reason `docstore.py` gives: the join is one `ATTACH DATABASE` away, and keeping them apart
means a map can be handed over with or without the code it was read from. `--no-source`
becomes a file not written, and mailing a map without the source becomes a file not
attached -- a per-recipient decision rather than a per-analysis one.

**Content-addressed**, keyed by the `content_hash` already in `files`. Each unique file
body is stored once no matter how many paths or revisions point at it, so the sidecar
grows only by what genuinely changed. That is what makes temporal layers storable at
Mensores' rate of six hundred commits a month, and it is why this is the store the layer
work builds on rather than a new one.

Two rules from `CLAUDE.md` apply here in an unusual way, and both are load-bearing:

* **Rule 16 -- never open a database as the wrong kind.** Stamped `source`, and it refuses
  a graph or a document store before anything is allowed to touch it.

* **Rule 12 in reverse -- this store is *not* invalidated by the extractor.** Every other
  cache here is derived from the detector rules, so changing a rule must discard it. These
  are the file bodies themselves: no rule was applied to them, so no rule change can make
  them wrong. Discarding this store on a fingerprint change would throw away exactly the
  history the temporal layers exist to hold -- the one artefact in the project that cannot
  be rebuilt from a stale source tree, because the source tree has moved on. A tool
  upgrade must leave it alone.

Bodies are stored compressed, because a mailable sidecar is the point and source text
compresses about four to one. Nothing is truncated on the way in -- rule 8.
"""

from __future__ import annotations

import sqlite3
import zlib
from collections.abc import Iterator
from pathlib import Path

SOURCE_SCHEMA_VERSION = 1

# The working tree as analysed, as opposed to a named revision. Empty rather than a word
# like "HEAD", because this store is deliberately version-control agnostic: it never asks
# where the bytes came from, which is what lets git, Perforce, Lore and a nightly cron all
# be the same problem.
WORKING = ""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- One row per unique file body, ever. The hash is the graph's `files.content_hash`,
-- so a node's file can be found without storing a second copy of anything.
CREATE TABLE IF NOT EXISTS blobs (
    hash  TEXT PRIMARY KEY,
    bytes INTEGER NOT NULL,          -- uncompressed size, for reporting the real cost
    lines INTEGER NOT NULL,
    body  BLOB NOT NULL              -- zlib-compressed UTF-8, whole and untruncated
);

-- Which path held which body, at which revision. Many rows may share one hash: an
-- unchanged file across fifty revisions is fifty rows here and one blob over there.
CREATE TABLE IF NOT EXISTS paths (
    revision TEXT NOT NULL,
    path     TEXT NOT NULL,
    hash     TEXT NOT NULL,
    lang     TEXT,
    PRIMARY KEY (revision, path)
);
CREATE INDEX IF NOT EXISTS ix_paths_hash ON paths(hash);
"""


class WrongStoreKind(ValueError):
    """Raised when a file is opened as a kind of store it is not."""


class SourceStore:
    """The source bodies for one analysed program."""

    def __init__(self, path: Path | str, *, writable: bool = True,
                 shared: bool = False) -> None:
        self.path = Path(path)
        self.writable = writable
        if writable:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        # See `Store.__init__`: shared means many threads, and a lock owed by the caller.
        self.conn = sqlite3.connect(self.path, check_same_thread=not shared)
        self.conn.row_factory = sqlite3.Row
        self._refuse_wrong_kind()
        if not writable:
            return
        self.conn.executescript(SCHEMA_SQL)
        self.set_meta("kind", "source")
        self.set_meta("schema_version", str(SOURCE_SCHEMA_VERSION))

    # ------------------------------------------------------------------ kind --- #

    def _refuse_wrong_kind(self) -> None:
        """Refuse anything that is not a source sidecar.

        Rule 16. Pointing `--db` at the wrong file once dropped every table in a document
        store, so the kind is checked before this class is allowed to run its schema.
        """
        try:
            row = self.conn.execute("SELECT value FROM meta WHERE key = 'kind'").fetchone()
        except sqlite3.Error:
            return                              # no meta table yet: a fresh database
        if row is not None and str(row[0]) != "source":
            raise WrongStoreKind(
                f"{self.path} is a {row[0]} database, not a source sidecar -- refusing "
                f"to open it as one, because doing so would discard its contents"
            )

    # ------------------------------------------------------------------ meta --- #

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def get_meta(self, key: str) -> str | None:
        try:
            row = self.conn.execute(
                "SELECT value FROM meta WHERE key = ?", (key,)
            ).fetchone()
        except sqlite3.Error:
            return None
        return None if row is None else str(row[0])

    # --------------------------------------------------------------- writing --- #

    def has_blob(self, content_hash: str) -> bool:
        """Is this body already held? The whole point of content addressing.

        Callers use it to avoid reading a file at all: on a re-analysis where nothing
        changed, every hash is already present and not one byte is read from disk.
        """
        row = self.conn.execute(
            "SELECT 1 FROM blobs WHERE hash = ?", (content_hash,)
        ).fetchone()
        return row is not None

    def add_blob(self, text: str, content_hash: str) -> bool:
        """Store one body under its hash. Returns True if it was new.

        Deliberately separate from `map_path`. They were one call taking both a path and
        a body, which forced every caller that already held the blob to pass a body it
        did not have -- and the only thing standing between `""` and a corrupt blob
        stored under a real hash was an internal freshness check. Content addressing
        means a wrong body is trusted forever, so the call that can write one is the call
        you must be holding a real body to make.
        """
        if self.has_blob(content_hash):
            return False
        raw = text.encode("utf-8")
        self.conn.execute(
            "INSERT INTO blobs(hash, bytes, lines, body) VALUES(?, ?, ?, ?)",
            (content_hash, len(raw), text.count("\n") + 1, zlib.compress(raw, 6)),
        )
        return True

    def map_path(self, path: str, content_hash: str, *,
                 lang: str | None = None, revision: str = WORKING) -> None:
        """Record that `path` held this body at this revision.

        Written whether or not the blob was new: two paths with identical contents are
        two facts about the program and one blob.
        """
        self.conn.execute(
            "INSERT INTO paths(revision, path, hash, lang) VALUES(?, ?, ?, ?) "
            "ON CONFLICT(revision, path) DO UPDATE SET hash = excluded.hash, "
            "lang = excluded.lang",
            (revision, path, content_hash, lang),
        )

    def prune_missing(self, live_paths: list[str], *, revision: str = WORKING) -> int:
        """Forget paths that no longer exist at this revision.

        The *blobs* are deliberately left alone. A body that no path currently points at
        is still the body some earlier revision was analysed from, and this store exists
        to keep exactly that. Only the path mapping is current-state.
        """
        keep = set(live_paths)
        gone = [
            r["path"] for r in self.conn.execute(
                "SELECT path FROM paths WHERE revision = ?", (revision,)
            ) if r["path"] not in keep
        ]
        if gone:
            self.conn.executemany(
                "DELETE FROM paths WHERE revision = ? AND path = ?",
                [(revision, p) for p in gone],
            )
        return len(gone)

    def commit(self) -> None:
        self.conn.commit()

    # --------------------------------------------------------------- reading --- #

    def text(self, path: str, *, revision: str = WORKING) -> str | None:
        """The whole body of one file, or None if this sidecar does not hold it.

        None is an honest answer and the caller must show it as one: a map analysed with
        `--no-source`, or handed over without its sidecar, has no source to open, and
        that is different from a file that is empty.
        """
        row = self.conn.execute(
            "SELECT b.body FROM paths p JOIN blobs b ON b.hash = p.hash "
            "WHERE p.revision = ? AND p.path = ?",
            (revision, path),
        ).fetchone()
        if row is None:
            return None
        return zlib.decompress(row["body"]).decode("utf-8", errors="replace")

    def lines(self, path: str, first: int, last: int, *,
              revision: str = WORKING) -> list[tuple[int, str]]:
        """A numbered span of one file, clamped to what the file actually has.

        Numbering is one-based to match every line number the graph records, and the
        numbers travel with the text so a span shown out of context still says where it
        came from.
        """
        body = self.text(path, revision=revision)
        if body is None:
            return []
        rows = body.split("\n")
        lo = max(1, first)
        hi = min(len(rows), max(lo, last))
        return [(i, rows[i - 1]) for i in range(lo, hi + 1)]

    def counts(self) -> dict[str, int]:
        """What this sidecar holds, for the line `analyze` prints."""
        blobs, raw = self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(bytes), 0) FROM blobs"
        ).fetchone()
        stored = self.conn.execute(
            "SELECT COALESCE(SUM(LENGTH(body)), 0) FROM blobs"
        ).fetchone()[0]
        paths = self.conn.execute("SELECT COUNT(*) FROM paths").fetchone()[0]
        return {"blobs": int(blobs), "paths": int(paths),
                "bytes": int(raw), "stored": int(stored)}

    def close(self) -> None:
        self.conn.close()


def capture(store_hashes: dict[str, str], source: SourceStore, *,
            langs: dict[str, str] | None = None,
            revision: str = WORKING) -> dict[str, int]:
    """Store every body the graph measured that this sidecar does not already hold.

    Driven by `Store.known_hashes()` -- path to content hash for every live file -- rather
    than by walking the tree again, which gives the property that matters: a file whose
    hash is already present is never opened. A re-analysis with nothing changed reads
    zero bytes of source, and a cold one reads each file exactly once more.

    A file that has since been deleted or become unreadable is counted as missing rather
    than raising. Ingest must never fail on a broken program, and a sidecar that is one
    file short is worth far more than no sidecar at all -- but the count is returned so
    the caller can say so, because a silent shortfall is the failure this project keeps
    paying for.
    """
    langs = langs or {}
    stats = {"stored": 0, "cached": 0, "missing": 0}
    for path, content_hash in sorted(store_hashes.items()):
        if source.has_blob(content_hash):
            # The body is known; this path at this revision pointing at it may not be.
            source.map_path(path, content_hash, lang=langs.get(path), revision=revision)
            stats["cached"] += 1
            continue
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            stats["missing"] += 1
            continue
        source.add_blob(text, content_hash)
        source.map_path(path, content_hash, lang=langs.get(path), revision=revision)
        stats["stored"] += 1
    source.prune_missing(list(store_hashes), revision=revision)
    source.commit()
    return stats


def iter_paths(source: SourceStore, *, revision: str = WORKING) -> Iterator[str]:
    """Every path this sidecar can serve, in order."""
    for row in source.conn.execute(
        "SELECT path FROM paths WHERE revision = ? ORDER BY path", (revision,)
    ):
        yield str(row["path"])
