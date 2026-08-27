"""The document store.

A second SQLite database, `docs.db`, beside the code graph rather than inside it. Three
reasons, and the third is the one that settled it:

* A documentation rescan never touches `graph.db`, so code-only analysis stays cheap and
  a prose rule change cannot invalidate a code fact.
* Documentation is often absent. A program with no documents produces an empty document
  store and a complete code map, which is the normal case rather than a degraded one.
* The doc corpus becomes a separately handable artifact -- the same logic as the source
  sidecar. Many organisations will hand over a charter and never a line of source.

The join is one `ATTACH DATABASE` away, so keeping them apart costs nothing.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .detectors.prose import doc_rules_fingerprint
from .schema import DOC_SCHEMA_VERSION, DocFacts

DOC_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = -65536;
PRAGMA mmap_size = 536870912;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    path         TEXT PRIMARY KEY,
    fmt          TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    mtime_ns     INTEGER NOT NULL DEFAULT 0,
    title        TEXT NOT NULL DEFAULT '',
    doc_class    TEXT NOT NULL DEFAULT 'OTHER',
    size         INTEGER NOT NULL DEFAULT 0,
    words        INTEGER NOT NULL DEFAULT 0,
    frontmatter  TEXT NOT NULL DEFAULT '{}',
    duplicate_of TEXT NOT NULL DEFAULT '',
    errors       TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS headings (
    doc   TEXT NOT NULL,
    level INTEGER NOT NULL,
    text  TEXT NOT NULL,
    line  INTEGER NOT NULL,
    path  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS definitions (
    doc         TEXT NOT NULL,
    term        TEXT NOT NULL,
    definition  TEXT NOT NULL,
    line        INTEGER NOT NULL,
    form        TEXT NOT NULL,
    heading     TEXT NOT NULL DEFAULT '',
    source_line TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS doc_rules (
    doc       TEXT NOT NULL,
    text      TEXT NOT NULL,
    line      INTEGER NOT NULL,
    lane      TEXT NOT NULL,
    scope     TEXT NOT NULL DEFAULT '',
    pattern   TEXT NOT NULL DEFAULT '',
    heading   TEXT NOT NULL DEFAULT '',
    checkable INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS doc_refs (
    doc   TEXT NOT NULL,
    kind  TEXT NOT NULL,
    value TEXT NOT NULL,
    line  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS doc_tables (
    doc     TEXT NOT NULL,
    idx     INTEGER NOT NULL,
    line    INTEGER NOT NULL,
    heading TEXT NOT NULL DEFAULT '',
    header  TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (doc, idx)
);

CREATE TABLE IF NOT EXISTS doc_table_rows (
    doc   TEXT NOT NULL,
    idx   INTEGER NOT NULL,
    row   INTEGER NOT NULL,
    cells TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS doc_annotations (
    doc   TEXT NOT NULL,
    kind  TEXT NOT NULL,
    value TEXT NOT NULL,
    line  INTEGER NOT NULL,
    text  TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS ix_headings_doc   ON headings(doc);
CREATE INDEX IF NOT EXISTS ix_defs_doc       ON definitions(doc);
CREATE INDEX IF NOT EXISTS ix_defs_term      ON definitions(term);
CREATE INDEX IF NOT EXISTS ix_docrules_doc   ON doc_rules(doc);
CREATE INDEX IF NOT EXISTS ix_docrules_lane  ON doc_rules(lane);
CREATE INDEX IF NOT EXISTS ix_docrefs_doc    ON doc_refs(doc);
CREATE INDEX IF NOT EXISTS ix_docrefs_value  ON doc_refs(value);
CREATE INDEX IF NOT EXISTS ix_doctables_doc  ON doc_tables(doc);
CREATE INDEX IF NOT EXISTS ix_doctrows_doc   ON doc_table_rows(doc, idx);
CREATE INDEX IF NOT EXISTS ix_docannot_doc   ON doc_annotations(doc);
CREATE INDEX IF NOT EXISTS ix_docannot_value ON doc_annotations(value);
CREATE INDEX IF NOT EXISTS ix_documents_class ON documents(doc_class);
CREATE INDEX IF NOT EXISTS ix_documents_hash  ON documents(content_hash);
CREATE INDEX IF NOT EXISTS ix_documents_dup   ON documents(duplicate_of);
"""


class DocStore:
    """A connection to one program's documentation corpus."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._refuse_wrong_kind()
        self.rebuilt = self._discard_if_stale()
        self.conn.executescript(DOC_SCHEMA_SQL)
        self.set_meta("kind", "docs")
        self.set_meta("doc_schema_version", str(DOC_SCHEMA_VERSION))
        self.set_meta("extractor", self._want())

    @staticmethod
    def _want() -> str:
        return f"{DOC_SCHEMA_VERSION}:{doc_rules_fingerprint()}"

    def _refuse_wrong_kind(self) -> None:
        """Refuse to open a code graph as a document store. See `Store` for the scar."""
        try:
            row = self.conn.execute("SELECT value FROM meta WHERE key = 'kind'").fetchone()
        except sqlite3.Error:
            return
        if row is not None and str(row[0]) != "docs":
            raise ValueError(
                f"{self.path} is a {row[0]} database, not a document store -- refusing "
                f"to open it as one, because doing so would discard its contents"
            )

    def _discard_if_stale(self) -> bool:
        """Rule 12, applied to prose.

        A cached fact is valid only if the source *and* the rule that read it are both
        unchanged. `detectors/docs/*.yaml` is the thing most often edited, and the file
        cache keys on document content, so a rule change would otherwise leave every
        stored fact answering the previous rule with nothing to reveal it.
        """
        try:
            row = self.conn.execute(
                "SELECT value FROM meta WHERE key = 'extractor'"
            ).fetchone()
        except sqlite3.Error:
            return False
        if row is None:
            try:
                n = self.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            except sqlite3.Error:
                return False
            if not n:
                return False
        elif str(row[0]) == self._want():
            return False
        names = [
            r[0] for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
                " AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for name in names:
            self.conn.execute(f'DROP TABLE IF EXISTS "{name}"')
        self.conn.commit()
        return True

    # -- lifecycle ---------------------------------------------------------- #

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()

    def __enter__(self) -> DocStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def batch(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # -- meta --------------------------------------------------------------- #

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    # -- incremental gate --------------------------------------------------- #

    def known_hashes(self) -> dict[str, str]:
        return {
            r["path"]: r["content_hash"]
            for r in self.conn.execute("SELECT path, content_hash FROM documents")
        }

    def known_stamps(self) -> dict[str, tuple[int, int]]:
        """Every document already read, with the (mtime, size) it was read at.

        The corpus is 44 MB across 2,381 files on an external volume, where hashing
        every one of them costs eighteen seconds whether anything changed or not --
        which turns re-analysis back into an event rather than a habit. A `stat` is
        free, so an unchanged stamp skips the read entirely and a changed one falls
        through to the content hash, which stays the thing that actually decides.

        Blind spot: a document rewritten to exactly its old length while its
        modification time is preserved is not noticed. `--recheck-docs` hashes
        everything and is the answer when that matters.
        """
        return {
            r["path"]: (int(r["mtime_ns"]), int(r["size"]))
            for r in self.conn.execute("SELECT path, mtime_ns, size FROM documents")
        }

    def forget_doc(self, path: str) -> None:
        for table in ("headings", "definitions", "doc_rules", "doc_refs", "doc_tables",
                      "doc_table_rows", "doc_annotations"):
            self.conn.execute(f"DELETE FROM {table} WHERE doc = ?", (path,))
        self.conn.execute("DELETE FROM documents WHERE path = ?", (path,))

    def prune_missing(self, live_paths: Iterable[str]) -> int:
        live = set(live_paths)
        gone = [p for p in self.known_hashes() if p not in live]
        for p in gone:
            self.forget_doc(p)
        return len(gone)

    def touch(self, path: str, mtime_ns: int, size: int) -> None:
        """Record a new stamp for a document whose content turned out to be unchanged.

        Without this, a document that was touched but not edited is re-hashed on every
        run for ever, and the fast path never takes hold.
        """
        self.conn.execute(
            "UPDATE documents SET mtime_ns = ?, size = ? WHERE path = ?",
            (mtime_ns, size, path),
        )

    # -- writes ------------------------------------------------------------- #

    def write_doc_facts(self, df: DocFacts, mtime_ns: int = 0) -> None:
        """Replace all facts for one document. Wrap bursts in `batch()`."""
        c = self.conn
        self.forget_doc(df.path)
        c.execute(
            "INSERT INTO documents(path,fmt,content_hash,mtime_ns,title,doc_class,size,"
            "words,frontmatter,errors) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (df.path, df.fmt.value, df.content_hash, mtime_ns, df.title,
             df.doc_class.value, df.size, df.words, json.dumps(df.frontmatter),
             json.dumps(df.errors)),
        )
        c.executemany(
            "INSERT INTO headings(doc,level,text,line,path) VALUES(?,?,?,?,?)",
            [(df.path, h.level, h.text, h.line, h.path) for h in df.headings],
        )
        c.executemany(
            "INSERT INTO definitions(doc,term,definition,line,form,heading,source_line)"
            " VALUES(?,?,?,?,?,?,?)",
            [(df.path, d.term, d.definition, d.line, d.form.value, d.heading, d.source_line)
             for d in df.definitions],
        )
        c.executemany(
            "INSERT INTO doc_rules(doc,text,line,lane,scope,pattern,heading,checkable)"
            " VALUES(?,?,?,?,?,?,?,?)",
            [(df.path, r.text, r.line, r.lane.value, r.scope, r.pattern, r.heading,
              int(r.checkable)) for r in df.rules],
        )
        c.executemany(
            "INSERT INTO doc_refs(doc,kind,value,line) VALUES(?,?,?,?)",
            [(df.path, r.kind.value, r.value, r.line) for r in df.refs],
        )
        for i, t in enumerate(df.tables):
            c.execute(
                "INSERT INTO doc_tables(doc,idx,line,heading,header) VALUES(?,?,?,?,?)",
                (df.path, i, t.line, t.heading, json.dumps(t.header)),
            )
            c.executemany(
                "INSERT INTO doc_table_rows(doc,idx,row,cells) VALUES(?,?,?,?)",
                [(df.path, i, r, json.dumps(cells)) for r, cells in enumerate(t.rows)],
            )
        c.executemany(
            "INSERT INTO doc_annotations(doc,kind,value,line,text) VALUES(?,?,?,?,?)",
            [(df.path, a.kind, a.value, a.line, a.text) for a in df.annotations],
        )

    # -- reads -------------------------------------------------------------- #

    def query(self, sql: str, args: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return list(self.conn.execute(sql, args))

    def counts(self) -> dict[str, int]:
        """Totals, and the same totals over canonical documents only.

        Both are reported because both are true: the corpus really does contain 2,381
        files, and it really only says 2,070 distinct things. Showing one without the
        other is how a count starts lying.
        """
        out: dict[str, int] = {}
        for table in ("documents", "definitions", "doc_rules", "doc_refs",
                      "doc_tables", "doc_annotations"):
            out[table] = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        out["duplicates"] = self.conn.execute(
            "SELECT COUNT(*) FROM documents WHERE duplicate_of <> ''"
        ).fetchone()[0]
        for table, col in (("definitions", "doc"), ("doc_rules", "doc"),
                           ("doc_annotations", "doc")):
            out[f"{table}_canonical"] = self.conn.execute(
                f"SELECT COUNT(*) FROM {table} t JOIN documents d ON d.path = t.{col}"
                " WHERE d.duplicate_of = ''"
            ).fetchone()[0]
        return out

    def mark_duplicates(self) -> int:
        """Point every copy of a document at the one canonical path.

        A corpus is rarely a set of distinct documents. Mensores keeps 335 documents
        inside agent worktrees -- copies of the project's own research and plans -- and
        counting them twice would double a definition, a governance id, and any measure
        built on either. Content-addressing settles it without a heuristic: identical
        bytes are the same document, whatever the path says.

        Nothing is deleted and nothing is hidden. The copies stay in the store with a
        pointer to the canonical path, so a reader can see exactly what was set aside
        and why -- the same discipline as `LOST_EDGE`.

        Canonical is the shallowest path, then the shortest, then alphabetical: a
        document at `docs/glossary.md` outranks the copy of it four directories deep
        inside a worktree.
        """
        groups: dict[str, list[str]] = {}
        for r in self.conn.execute(
            "SELECT path, content_hash FROM documents ORDER BY path"
        ):
            groups.setdefault(r["content_hash"], []).append(r["path"])

        marked = 0
        self.conn.execute("UPDATE documents SET duplicate_of = ''")
        for paths in groups.values():
            if len(paths) < 2:
                continue
            canonical = min(paths, key=lambda p: (p.count("/"), len(p), p))
            for p in paths:
                if p != canonical:
                    self.conn.execute(
                        "UPDATE documents SET duplicate_of = ? WHERE path = ?",
                        (canonical, p),
                    )
                    marked += 1
        self.conn.commit()
        return marked

    def duplicates(self) -> list[tuple[str, str]]:
        """Every copy and the document it duplicates. Never abbreviated."""
        return [
            (r["path"], r["duplicate_of"])
            for r in self.conn.execute(
                "SELECT path, duplicate_of FROM documents WHERE duplicate_of <> ''"
                " ORDER BY duplicate_of, path"
            )
        ]

    def attach_graph(self, graph_path: Path | str, alias: str = "code") -> None:
        """Join the two corpora. The whole cost of keeping them apart, paid here."""
        self.conn.execute(f"ATTACH DATABASE ? AS {alias}", (str(graph_path),))

    def optimize(self) -> None:
        self.conn.commit()
        self.conn.execute("PRAGMA optimize")
