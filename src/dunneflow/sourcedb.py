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

**A snapshot has a name and an instant.** `WORKING` is a *state* -- the one snapshot the
next capture writes into -- and a revision's identity is when it was captured. Before that
distinction existed the id and the state were the same empty string, so re-analysing
replaced the only snapshot there was: the bodies survived, because blobs are never pruned,
and nothing was left that could name them. `seal()` is the whole of the preparation for
temporal layers, and it is deliberately small -- the working revision already has an
identity and a timestamp, so keeping it is a change of state and nothing else. No path row
moves and no body is touched.

Nothing here reads a second revision yet. This is the spine, so that a time selector is
added to a working view rather than invented alongside one.
"""

from __future__ import annotations

import sqlite3
import zlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .migrate import META_PATHS, PATHS_RELATIVE

SOURCE_SCHEMA_VERSION = 3

# A revision is identified by **when it was captured**, and by nothing else. Not "HEAD",
# not a commit, not a tag: this store is deliberately version-control agnostic and never
# asks where the bytes came from, which is what lets git, Perforce, Lore, a nightly cron
# and a release tag all be the same problem. An instant is the one identity every one of
# them has.
#
# WORKING is a **state**, not an id. It used to be both -- the id was the empty string, and
# there was nowhere to record when the snapshot had been taken -- so a re-analysis silently
# replaced the only snapshot there was. The bodies survived it, because `prune_missing`
# leaves blobs alone on purpose, but nothing was left that could name them. Exactly one
# revision is WORKING at a time: the one the next capture writes into.
STATE_WORKING = "WORKING"
STATE_FOR_COMPARISON = "FOR_COMPARISON"
STATES = (STATE_WORKING, STATE_FOR_COMPARISON)

# How much inflated source this store will keep in memory, and it is a **stated ceiling
# rather than a pretence**.
#
# `store.py` says nothing holds the whole program in memory, and that rule is about the
# graph: reachability is recursive SQL because a call graph does not fit and does not need
# to. Text is the one thing here you cannot answer a question about without reading it --
# searching 184,722 lines means inflating 184,722 lines -- so the honest answer is a bound
# that says what it is, not a claim to be holding nothing. Mensores is 7.8 MB and fits
# whole; a corpus larger than this re-inflates the overflow on every search, and the search
# reports how many bodies it had to inflate so a reader can see that happening rather than
# only feel it.
#
# Eviction is oldest-first. For a scan larger than the budget that is the worst case for
# any policy -- it evicts exactly what the next scan asks for first -- and pretending
# otherwise with an LRU would buy nothing. The bound is what matters; the order is not.
INFLATE_BUDGET_BYTES = 64 * 1024 * 1024

# What every sidecar written before revisions were recorded holds its paths under. It reads
# as the working revision and is stamped on the next *writable* open -- never on a read.
# Rule 20: a read may refuse, but it may never repair, and this is the one store that must
# survive everything.
LEGACY_REVISION = ""

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

-- Covering, and that is the whole point of it. `lines` sits in a row that also holds a
-- compressed body, so reading it off the table drags several kilobytes of blob through the
-- page cache per file -- 1,370 ms cold on 626 files, to learn something already written
-- down. With hash and lines in the index the body is never touched.
CREATE INDEX IF NOT EXISTS ix_blobs_lines ON blobs(hash, lines);

-- One row per snapshot. Additive: an older sidecar gains this table and loses nothing.
--
-- Two columns that look like one. `revision` is the identity and is always known -- the
-- instant the row was made. `captured_at` is a claim about the *source*: when those bodies
-- were measured. For an ordinary capture they are the same instant. For a sidecar migrated
-- from before revisions existed they are not, because nothing here knows when its bodies
-- were read, and `captured_at` is left empty rather than filled with a plausible lie.
CREATE TABLE IF NOT EXISTS revisions (
    revision    TEXT PRIMARY KEY,   -- ISO 8601 UTC, to the second
    state       TEXT NOT NULL,      -- one of STATES
    captured_at TEXT NOT NULL,      -- the same instant, or empty when it is not known
    label       TEXT NOT NULL DEFAULT '',
    note        TEXT NOT NULL DEFAULT '',
    -- The **leaf** of the directory this version was read from, and only the leaf:
    -- `society-2026-08-26`, never the path that led to it. Two versions of one program
    -- are two directories, so this is what a reader recognises them by -- an instant
    -- says when we read the bytes and nothing about which tree they came from.
    --
    -- A leaf and a path are not the same disclosure. The path is one machine's layout
    -- and is deliberately not recorded anywhere (rule 60); the leaf is a name somebody
    -- chose for the source, travels with the map, and survives a move. It is written
    -- down in `README.md` as something a handed-over program directory contains,
    -- because a reader is entitled to know what they are passing on.
    --
    -- Distinct from `label`, which is what a person called a snapshot at `seal` time.
    -- One meaning per column: `seal --label` must not overwrite where the code came
    -- from, and a directory name must not masquerade as a considered description.
    tree        TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_revisions_state ON revisions(state);
"""


def _now() -> str:
    """The identity a new revision gets. UTC, to the second, sortable as a string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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
        # Inflated bodies, keyed by content hash -- so an identical file at fifty paths is
        # inflated once, which is the property content addressing was chosen for. Bounded
        # by `INFLATE_BUDGET_BYTES`; see the note there for why a bound rather than none.
        self._inflated: dict[str, list[str]] = {}
        self._inflated_bytes = 0
        self._refuse_wrong_kind()
        if not writable:
            return
        self.conn.executescript(SCHEMA_SQL)
        self._add_missing_columns()
        self.set_meta("kind", "source")
        self.set_meta("schema_version", str(SOURCE_SCHEMA_VERSION))
        # Paths here are relative to the tree each revision was read from, and that tree
        # is not recorded anywhere -- see `migrate.py`. Marked rather than inferred: an
        # empty sidecar holds no absolute path to find, and "nothing to see" is not the
        # same claim as "already relative".
        self.set_meta(META_PATHS, PATHS_RELATIVE)
        self._stamp_legacy_paths()

    # -------------------------------------------------------------- additive --- #

    # Columns added to an existing table after the fact. `CREATE TABLE IF NOT EXISTS`
    # does nothing to a table that already exists, so a sidecar written before a column
    # existed never gains it -- and this is the one store that is never rebuilt (rule
    # 25), so there is no re-analysis that would fix it.
    #
    # **Add only.** Nothing here drops, renames or rewrites a column, and the test that
    # this module contains no `DROP` covers it. A column that is no longer wanted is left
    # alone: unused space in a file nobody can regenerate is the cheapest thing here.
    _ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
        ("revisions", "tree", "TEXT NOT NULL DEFAULT ''"),
    )

    def _add_missing_columns(self) -> None:
        for table, column, decl in self._ADDED_COLUMNS:
            have = {str(r[1]) for r in
                    self.conn.execute(f"PRAGMA table_info({table})")}
            if not have:
                continue                        # no such table yet; the schema owns it
            if column not in have:
                self.conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

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

    # ------------------------------------------------------------- revisions --- #

    def _require_writable(self, what: str) -> None:
        """Rule 20, stated where it can be enforced rather than remembered."""
        if not self.writable:
            raise PermissionError(
                f"this sidecar was opened read-only; refusing to {what}. A read may "
                f"refuse, but it may never repair."
            )

    def _free_revision_id(self, stamp: str) -> str:
        """`stamp`, or `stamp#2` if that instant is already taken.

        Two captures inside one second is unlikely and not impossible, and a primary-key
        collision here would silently merge two snapshots into one.
        """
        rev, n = stamp, 1
        while self.conn.execute(
            "SELECT 1 FROM revisions WHERE revision = ?", (rev,)
        ).fetchone() is not None:
            n += 1
            rev = f"{stamp}#{n}"
        return rev

    def _stamp_legacy_paths(self) -> str | None:
        """Give an un-stamped sidecar's paths a revision that has a name.

        Writable opens only, which in practice means `analyze` and `dunneflow revisions`.
        A reader gets the legacy revision exactly as it stands and reports it as
        un-stamped, because rule 20 says a read may refuse but may never repair -- and of
        every store here this is the one that must survive a tool upgrade untouched.

        The instant recorded as the *identity* is this migration. `captured_at` is left
        empty, because nothing in this file knows when those bodies were measured and a
        plausible timestamp is worse than an absent one. `graph.db` records `analysed_at`
        beside this file, and the CLI -- which legitimately holds both -- can state it.
        """
        # Loudly rather than quietly. `__init__` is the only caller and it returns before
        # reaching here on a read-only open, so this can never fire today -- but a guard
        # that silently returns None is one a future caller could trip without noticing,
        # and this method writes. Rule 42: check that the guard catches, not that it
        # mentions.
        self._require_writable("stamp an un-stamped sidecar")
        working = self.conn.execute(
            "SELECT 1 FROM revisions WHERE state = ? LIMIT 1", (STATE_WORKING,)
        ).fetchone()
        if working is not None:
            return None                         # already stamped; nothing to migrate
        legacy = self.conn.execute(
            "SELECT 1 FROM paths WHERE revision = ? LIMIT 1", (LEGACY_REVISION,)
        ).fetchone()
        if legacy is None:
            return None                         # a fresh sidecar, or one already moved
        rev = self._free_revision_id(_now())
        self.conn.execute(
            "INSERT INTO revisions(revision, state, captured_at, note) VALUES(?, ?, '', ?)",
            (rev, STATE_WORKING,
             "captured before revisions were recorded, so the instant these bodies were "
             "measured is not known here"),
        )
        self.conn.execute(
            "UPDATE paths SET revision = ? WHERE revision = ?", (rev, LEGACY_REVISION)
        )
        self.conn.commit()
        return rev

    def current_revision(self) -> str | None:
        """The revision every read defaults to. `None` means this sidecar holds nothing.

        The working revision if there is one, and **otherwise the newest** -- which is not
        a nicety. `seal()` leaves no working revision behind, on purpose: the next capture
        opens a fresh one. Between those two moments a sidecar that resolved reads only to
        WORKING would answer "no source" for every file it holds, so sealing a snapshot
        would blind the dashboard until the next analysis. Falling back to the newest is
        the honest reading of "what is in this file"; opening a revision to *write* is a
        different question and `open_working()` answers it.

        `None` is a different answer from an empty file, and the caller must show it as one.
        """
        try:
            row = self.conn.execute(
                "SELECT revision FROM revisions "
                "ORDER BY state = ? DESC, revision DESC LIMIT 1", (STATE_WORKING,),
            ).fetchone()
        except sqlite3.Error:
            row = None                          # a sidecar older than this table
        if row is not None:
            return str(row["revision"])
        legacy = self.conn.execute(
            "SELECT 1 FROM paths WHERE revision = ? LIMIT 1", (LEGACY_REVISION,)
        ).fetchone()
        return LEGACY_REVISION if legacy is not None else None

    def working_revision(self) -> str | None:
        """The revision a capture would write into, or None if none is open.

        Deliberately not `current_revision()`. "What do I read" and "what do I write" are
        different questions, and answering both with one call is how the state and the id
        were one string in the first place.
        """
        try:
            row = self.conn.execute(
                "SELECT revision FROM revisions WHERE state = ? "
                "ORDER BY revision DESC LIMIT 1", (STATE_WORKING,),
            ).fetchone()
        except sqlite3.Error:
            return None
        return None if row is None else str(row["revision"])

    def resolve_revision(self, revision: str | None) -> str:
        """Reading: `None` means the current revision; anything else is taken at its word.

        Public because callers outside this module legitimately need to name the revision
        they are reading -- the code browser lists what the current one holds. A private
        resolver reached from another file is a boundary that exists only in its name.
        """
        if revision is not None:
            return revision
        current = self.current_revision()
        return LEGACY_REVISION if current is None else current

    def _resolve_for_write(self, revision: str | None) -> str:
        """Writing: `None` means the working revision, **opened if there is none**.

        Deliberately not `_resolve`. Reading a store that holds nothing must answer
        nothing; writing into a store that holds nothing must create somewhere to put it,
        or the row lands in the legacy revision -- a path belonging to no named snapshot,
        which is the exact state this table exists to remove. `capture()` resolves once and
        passes the id down; this catches every other caller, and there were three.
        """
        if revision is not None:
            return revision
        return self.open_working()

    def open_working(self, *, at: str | None = None, tree: str = "") -> str:
        """The revision new bodies are mapped into, created and stamped if there is none.

        Reused rather than recreated, so analysing twice in one day does not leave two
        half-filled snapshots behind: a capture replaces the working revision's path map,
        which is what `prune_missing` has always done.

        `tree` is the **leaf** of the directory the source was read from -- the name a
        reader recognises this version by, since two versions of one program are two
        directories. It is filled on a revision that has none rather than overwritten on
        every open: re-analysing the same working revision from the same tree writes the
        same value, and the one case where they differ -- re-analysing a working revision
        from a *different* tree -- is the reader replacing what the snapshot is of, so the
        newer answer is the true one.
        """
        self._require_writable("open a revision")
        open_already = self.working_revision()
        if open_already is not None:
            if tree:
                self.conn.execute(
                    "UPDATE revisions SET tree = ? WHERE revision = ?",
                    (tree, open_already))
            return open_already
        stamp = at or _now()
        rev = self._free_revision_id(stamp)
        self.conn.execute(
            "INSERT INTO revisions(revision, state, captured_at, tree) VALUES(?, ?, ?, ?)",
            (rev, STATE_WORKING, stamp, tree),
        )
        return rev

    def seal(self, *, state: str = STATE_FOR_COMPARISON, label: str = "",
             note: str = "", at: str | None = None) -> str | None:
        """Keep the current snapshot under its own name, so the next capture is a second one.

        This is the whole of the temporal preparation, and it is deliberately small: the
        working revision already **has** an identity and a timestamp, so sealing it is a
        change of state and nothing else. No path rows move, no body is touched, and the
        next `capture()` opens a fresh working revision beside it.

        `at` fills in a `captured_at` that migration could not know. It is only ever
        allowed to fill an empty one -- overwriting a recorded instant with a stated one
        would be inventing provenance, which is what rule 13 exists to prevent.

        Returns the sealed revision's id, or None if there was nothing to seal.
        """
        self._require_writable("seal a revision")
        if state not in STATES:
            raise ValueError(
                f"{state!r} is not a revision state; expected one of {STATES}"
            )
        rev = self.working_revision()
        if rev is None:
            # Nothing open to seal. Either this sidecar is empty, or its snapshot is
            # already sealed -- and those are different answers, so say which.
            if self.current_revision() is None:
                return None
            raise ValueError(
                "the newest snapshot is already sealed; the next `analyze` opens a "
                "working revision beside it, and that is the one to seal next"
            )
        self.conn.execute(
            "UPDATE revisions SET state = ?, label = ?, note = ?, "
            "captured_at = CASE WHEN captured_at = '' THEN ? ELSE captured_at END "
            "WHERE revision = ?",
            (state, label, note, at or "", rev),
        )
        self.conn.commit()
        return rev

    def revisions(self) -> list[dict[str, Any]]:
        """Every snapshot this sidecar holds, newest first, with how many paths it maps.

        An un-stamped sidecar is *reported* as the one working revision it is, marked
        `stamped: False`. Reporting is not repairing: nothing is written, and the row says
        plainly that it has no identity yet rather than being given one behind the reader.
        """
        # Which columns this sidecar actually has, rather than which ones this version of
        # the code knows about. **A read may refuse but may never repair** (rule 20), so a
        # read-only open never runs the additive migration -- and a sidecar written before
        # `tree` existed is opened read-only every time the dashboard starts.
        #
        # Naming the column unconditionally cost exactly what that rule warns about: the
        # SELECT raised, the blanket `except` below turned it into `rows = []`, and the
        # server reported a two-revision program as holding **no revisions at all** --
        # state, label, capture instant and file counts all blank. A plausible answer, no
        # error anywhere, and it consumed the evidence on its way past (rule 49). Found by
        # reading the served JSON, which no test does.
        have = {str(r[1]) for r in self.conn.execute("PRAGMA table_info(revisions)")}
        if not have:
            rows = []                       # no such table: a sidecar older than revisions
        else:
            optional = [c for c in ("label", "note", "tree") if c in have]
            cols = ", ".join(f"r.{c}" for c in ["revision", "state", "captured_at"] + optional)
            rows = self.conn.execute(
                f"SELECT {cols}, "
                "       (SELECT COUNT(*) FROM paths p WHERE p.revision = r.revision) files "
                "FROM revisions r ORDER BY r.revision DESC"
            ).fetchall()
        out: list[dict[str, Any]] = [
            {"revision": str(r["revision"]), "state": str(r["state"]),
             "captured_at": str(r["captured_at"]),
             # A column this sidecar does not have is empty, and empty is the honest
             # answer: it was captured before we recorded this, not "we recorded nothing".
             "label": str(r["label"]) if "label" in have else "",
             "note": str(r["note"]) if "note" in have else "",
             "tree": str(r["tree"]) if "tree" in have else "",
             "files": int(r["files"]), "stamped": True}
            for r in rows
        ]
        legacy = self.conn.execute(
            "SELECT COUNT(*) FROM paths WHERE revision = ?", (LEGACY_REVISION,)
        ).fetchone()
        if legacy is not None and int(legacy[0]):
            out.append({
                "revision": LEGACY_REVISION, "state": STATE_WORKING, "captured_at": "",
                "label": "", "tree": "", "files": int(legacy[0]), "stamped": False,
                "note": "captured before revisions were recorded; open this sidecar for "
                        "writing, or run `dunneflow revisions --seal`, to give it a name",
            })
        return out

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
                 lang: str | None = None, revision: str | None = None) -> None:
        """Record that `path` held this body at this revision.

        Written whether or not the blob was new: two paths with identical contents are
        two facts about the program and one blob. `revision` defaults to the current one;
        `capture()` resolves it once and passes it, rather than asking per file.
        """
        revision = self._resolve_for_write(revision)
        self.conn.execute(
            "INSERT INTO paths(revision, path, hash, lang) VALUES(?, ?, ?, ?) "
            "ON CONFLICT(revision, path) DO UPDATE SET hash = excluded.hash, "
            "lang = excluded.lang",
            (revision, path, content_hash, lang),
        )

    def prune_missing(self, live_paths: list[str], *,
                      revision: str | None = None) -> int:
        """Forget paths that no longer exist at this revision.

        The *blobs* are deliberately left alone. A body that no path currently points at
        is still the body some earlier revision was analysed from, and this store exists
        to keep exactly that. Only the path mapping is current-state.
        """
        revision = self._resolve_for_write(revision)
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

    def hash_of(self, path: str, *, revision: str | None = None) -> str | None:
        """Which body this path held at this revision. One indexed lookup, no blob."""
        row = self.conn.execute(
            "SELECT hash FROM paths WHERE revision = ? AND path = ?",
            (self.resolve_revision(revision), path),
        ).fetchone()
        return None if row is None else str(row["hash"])

    def path_lines(self, path: str, *,
                   revision: str | None = None) -> list[str] | None:
        """One file's body as a list of lines, through the cache.

        The shape every caller here actually wanted. `text()` returned a single string and
        every one of its callers immediately split it -- so opening a file, then a span of
        it, then searching it, materialised the same megabyte three times over. Going
        through `body_lines` means all three share one inflation.

        The returned list is the cached one; see `body_lines` on not mutating it.
        """
        content_hash = self.hash_of(path, revision=revision)
        if content_hash is None:
            return None
        return self.body_lines(content_hash)

    def text(self, path: str, *, revision: str | None = None) -> str | None:
        """The whole body of one file, or None if this sidecar does not hold it.

        None is an honest answer and the caller must show it as one: a map analysed with
        `--no-source`, or handed over without its sidecar, has no source to open, and
        that is different from a file that is empty.
        """
        rows = self.path_lines(path, revision=revision)
        return None if rows is None else "\n".join(rows)

    def lines(self, path: str, first: int, last: int, *,
              revision: str | None = None) -> list[tuple[int, str]]:
        """A numbered span of one file, clamped to what the file actually has.

        Numbering is one-based to match every line number the graph records, and the
        numbers travel with the text so a span shown out of context still says where it
        came from.
        """
        rows = self.path_lines(path, revision=revision)
        if rows is None:
            return []
        lo = max(1, first)
        hi = min(len(rows), max(lo, last))
        return [(i, rows[i - 1]) for i in range(lo, hi + 1)]

    def body_lines(self, content_hash: str) -> list[str] | None:
        """One body, inflated and split, or None if this sidecar does not hold it.

        Keyed by hash rather than by path, because that is what makes the cache correct:
        two paths holding the same bytes are one entry, and the same body at a second
        revision is not inflated twice.

        The returned list is the cached one and callers must not mutate it. Copying it per
        call would defeat the cache -- the whole cost being avoided is materialising the
        text -- so the contract is stated here instead. Everything in this codebase that
        reads it only slices.
        """
        hit = self._inflated.get(content_hash)
        if hit is not None:
            return hit
        row = self.conn.execute(
            "SELECT body FROM blobs WHERE hash = ?", (content_hash,)
        ).fetchone()
        if row is None:
            return None
        lines = zlib.decompress(row["body"]).decode("utf-8", errors="replace").split("\n")
        self._remember(content_hash, lines)
        return lines

    def _remember(self, content_hash: str, lines: list[str]) -> None:
        """Keep an inflated body, evicting oldest-first to stay inside the budget."""
        cost = sum(len(ln) for ln in lines) + len(lines)
        if cost > INFLATE_BUDGET_BYTES:
            return                              # one file larger than the whole budget
        while self._inflated and self._inflated_bytes + cost > INFLATE_BUDGET_BYTES:
            oldest = next(iter(self._inflated))
            gone = self._inflated.pop(oldest)
            self._inflated_bytes -= sum(len(ln) for ln in gone) + len(gone)
        self._inflated[content_hash] = lines
        self._inflated_bytes += cost

    def bodies(self, *, revision: str | None = None
               ) -> Iterator[tuple[str, str, list[str]]]:
        """Every path this revision holds, with its body as a list of lines.

        Yields `(path, content_hash, lines)` in path order. The hash travels with the path
        because the caller may legitimately want to know that two paths are one body --
        a search reports how many *bodies* it read, not only how many files it answered
        about, and those are different numbers on a program with a vendored copy in it.

        Distinct bodies are inflated in one pass before anything is yielded, so a hash
        shared by fifty paths costs one `zlib.decompress` rather than fifty cache probes
        interleaved with fifty queries.
        """
        rows = [
            (str(r["path"]), str(r["hash"])) for r in self.conn.execute(
                "SELECT path, hash FROM paths WHERE revision = ? ORDER BY path",
                (self.resolve_revision(revision),),
            )
        ]
        for content_hash in dict.fromkeys(h for _, h in rows):
            self.body_lines(content_hash)
        for path, content_hash in rows:
            lines = self.body_lines(content_hash)
            if lines is None:
                # A path row whose blob is gone. `prune_missing` never deletes blobs, so
                # this cannot happen to a sidecar this code wrote -- but a truncated or
                # hand-edited one is not this code's to trust, and skipping is the only
                # answer that does not invent a body.
                continue
            yield path, content_hash, lines

    def held_paths(self) -> dict[str, int]:
        """Every path this revision holds, with how many lines its body has.

        One query rather than a path list and then a `text()` per file: the line count is
        already recorded on the blob, and decompressing 626 bodies to count newlines in
        them would be seven megabytes of work to learn something the store wrote down.
        """
        return {
            str(r["path"]): int(r["lines"]) for r in self.conn.execute(
                "SELECT p.path AS path, b.lines AS lines FROM paths p "
                "JOIN blobs b ON b.hash = p.hash WHERE p.revision = ?",
                (self.resolve_revision(None),),
            )
        }

    def counts(self) -> dict[str, int]:
        """What this sidecar holds, for the line `analyze` prints."""
        blobs, raw = self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(bytes), 0) FROM blobs"
        ).fetchone()
        stored = self.conn.execute(
            "SELECT COALESCE(SUM(LENGTH(body)), 0) FROM blobs"
        ).fetchone()[0]
        # Per revision, not global. Once a second snapshot exists a global path count
        # answers no question anybody asks -- "how many files does this program have" and
        # "how many path-revision rows are stored" are different numbers, and the line
        # `analyze` prints wants the first. Rule 32: a count must say what it counts.
        paths = self.conn.execute(
            "SELECT COUNT(*) FROM paths WHERE revision = ?", (self.resolve_revision(None),)
        ).fetchone()[0]
        mapped = self.conn.execute("SELECT COUNT(*) FROM paths").fetchone()[0]
        revs = self.conn.execute("SELECT COUNT(*) FROM revisions").fetchone()[0]
        return {"blobs": int(blobs), "paths": int(paths), "mapped": int(mapped),
                "revisions": int(revs), "bytes": int(raw), "stored": int(stored)}

    def close(self) -> None:
        self.conn.close()


def capture(store_hashes: dict[str, str], source: SourceStore, *,
            root: Path | str,
            langs: dict[str, str] | None = None,
            revision: str | None = None) -> dict[str, int]:
    """Store every body the graph measured that this sidecar does not already hold.

    `root` is the tree the graph was read from. It is **used and not recorded**: the keys
    in `store_hashes` are relative, which is what this sidecar stores so that a file can
    be paired with itself across two revisions read from two different trees, and the root
    exists here only to find the bytes on disk one last time. Nothing at read time needs
    it back -- a body is fetched by content hash, never by opening a path.

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
    base = Path(root)
    # Resolved once. The working revision is created here if this is a first capture, so
    # that every path row below lands in a snapshot that has a name and an instant.
    revision = revision if revision is not None else source.open_working()
    stats = {"stored": 0, "cached": 0, "missing": 0}
    for path, content_hash in sorted(store_hashes.items()):
        if source.has_blob(content_hash):
            # The body is known; this path at this revision pointing at it may not be.
            source.map_path(path, content_hash, lang=langs.get(path), revision=revision)
            stats["cached"] += 1
            continue
        try:
            text = (base / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            stats["missing"] += 1
            continue
        source.add_blob(text, content_hash)
        source.map_path(path, content_hash, lang=langs.get(path), revision=revision)
        stats["stored"] += 1
    source.prune_missing(list(store_hashes), revision=revision)
    source.commit()
    # Statistics, or `ix_blobs_lines` is never chosen and the file list reads a compressed
    # body per file to learn a line count that is already indexed beside it. An index
    # SQLite has no reason to prefer is an index that does nothing -- which looks exactly
    # like an index that works. `store.py` warms the graph for the same reason.
    source.conn.execute("ANALYZE")
    source.commit()
    return stats


def iter_paths(source: SourceStore, *,
               revision: str | None = None) -> Iterator[str]:
    """Every path this sidecar can serve, in order."""
    for row in source.conn.execute(
        "SELECT path FROM paths WHERE revision = ? ORDER BY path",
        (source.resolve_revision(revision),),
    ):
        yield str(row["path"])
