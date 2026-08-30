"""The graph store.

SQLite is the spine of this tool, not an export format. Facts are written here as they
are extracted and queried from here by every later stage. Nothing ever holds the whole
program in memory, which is the single reason this keeps working as the target grows.

Two consequences worth knowing:

* Re-analysis is per-file. A file whose content hash is unchanged is not re-parsed, so
  editing 3 files out of 626 costs three files' worth of work.
* Reachability -- "what does this touch", "what breaks if I change this" -- is answered
  by recursive SQL against indexed edges, not by walking an in-memory graph. That is
  what keeps orientation queries fast at any size.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .detectors import rules_fingerprint
from .migrate import META_PATHS, PATHS_RELATIVE, paths_are_relative
from .schema import (
    SCHEMA_VERSION,
    Annotation,
    BoundaryHit,
    BoundaryKind,
    Comment,
    Confidence,
    DataStructure,
    Direction,
    Entrypoint,
    EntrypointKind,
    Field_,
    FileFacts,
    Param,
    Routine,
    StructureKind,
)

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
-- The graph often lives on an external volume, where a cold page read costs
-- hundreds of times what a warm one does. Memory-mapping it and giving SQLite a
-- large page cache turns repeat orientation queries from disk-bound into free.
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = -65536;
PRAGMA mmap_size = 536870912;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    path         TEXT PRIMARY KEY,
    lang         TEXT NOT NULL,
    module       TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    doc          TEXT NOT NULL DEFAULT '',
    errors       TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS routines (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    qualname   TEXT NOT NULL,
    module     TEXT NOT NULL,
    file       TEXT NOT NULL,
    line_start INTEGER NOT NULL,
    line_end   INTEGER NOT NULL,
    lang       TEXT NOT NULL,
    returns    TEXT,
    docstring  TEXT,
    decorators TEXT NOT NULL DEFAULT '[]',
    is_async   INTEGER NOT NULL DEFAULT 0,
    is_method  INTEGER NOT NULL DEFAULT 0,
    class_name TEXT,
    is_nested  INTEGER NOT NULL DEFAULT 0,
    visibility TEXT NOT NULL DEFAULT 'public',
    body_hash  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS params (
    routine_id TEXT NOT NULL,
    idx        INTEGER NOT NULL,
    name       TEXT NOT NULL,
    type       TEXT,
    dflt       TEXT,
    kind       TEXT NOT NULL,
    PRIMARY KEY (routine_id, idx)
);

CREATE TABLE IF NOT EXISTS comments (
    routine_id TEXT NOT NULL,
    line       INTEGER NOT NULL,
    text       TEXT NOT NULL,
    leading    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS annotations (
    owner_id   TEXT NOT NULL,
    owner_kind TEXT NOT NULL,
    kind       TEXT NOT NULL,
    value      TEXT NOT NULL,
    line       INTEGER NOT NULL,
    text       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS calls (
    file        TEXT NOT NULL,
    caller_id   TEXT NOT NULL,
    callee_expr TEXT NOT NULL,
    line        INTEGER NOT NULL,
    callee_id   TEXT,
    confidence  TEXT NOT NULL,
    external    INTEGER NOT NULL DEFAULT 0,
    at_boundary INTEGER NOT NULL DEFAULT 0,
    ambiguous   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS boundaries (
    file       TEXT NOT NULL,
    routine_id TEXT NOT NULL,
    kind       TEXT NOT NULL,
    direction  TEXT NOT NULL,
    target     TEXT NOT NULL,
    line       INTEGER NOT NULL,
    evidence   TEXT NOT NULL DEFAULT '',
    salience   TEXT NOT NULL DEFAULT 'normal'
);

CREATE TABLE IF NOT EXISTS structures (
    id        TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    kind      TEXT NOT NULL,
    module    TEXT NOT NULL,
    file      TEXT NOT NULL,
    line      INTEGER NOT NULL,
    lang      TEXT NOT NULL,
    docstring TEXT,
    bases     TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS fields (
    structure_id TEXT NOT NULL,
    idx          INTEGER NOT NULL,
    name         TEXT NOT NULL,
    type         TEXT,
    dflt         TEXT,
    comment      TEXT,
    PRIMARY KEY (structure_id, idx)
);

CREATE TABLE IF NOT EXISTS entrypoints (
    id         TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    name       TEXT NOT NULL,
    routine_id TEXT,
    module     TEXT NOT NULL DEFAULT '',
    file       TEXT NOT NULL DEFAULT '',
    evidence   TEXT NOT NULL DEFAULT '',
    grp        TEXT NOT NULL DEFAULT '',
    parent_id  TEXT,
    target_expr TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS classes (
    name     TEXT NOT NULL,
    qualname TEXT NOT NULL,
    module   TEXT NOT NULL,
    file     TEXT NOT NULL,
    line     INTEGER NOT NULL,
    bases    TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS net_calls (
    file            TEXT NOT NULL,
    routine_id      TEXT NOT NULL,
    expr            TEXT NOT NULL,
    protocol        TEXT NOT NULL,
    verb            TEXT NOT NULL DEFAULT '',
    destination     TEXT NOT NULL DEFAULT '',
    port            TEXT NOT NULL DEFAULT '',
    is_async        INTEGER NOT NULL DEFAULT 0,
    awaited         INTEGER NOT NULL DEFAULT 0,
    in_async_routine INTEGER NOT NULL DEFAULT 0,
    timeout         TEXT NOT NULL DEFAULT '',
    retries         TEXT NOT NULL DEFAULT '',
    tls             TEXT NOT NULL DEFAULT '',
    payload         TEXT NOT NULL DEFAULT '',
    headers         TEXT NOT NULL DEFAULT '',
    topic           TEXT NOT NULL DEFAULT '',
    ack             TEXT NOT NULL DEFAULT '',
    line            INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sql_ops (
    file       TEXT NOT NULL,
    routine_id TEXT NOT NULL,
    operation  TEXT NOT NULL,
    direction  TEXT NOT NULL,
    tbl        TEXT NOT NULL DEFAULT '',
    sql        TEXT NOT NULL,
    line       INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS db_tables (
    name      TEXT NOT NULL,
    file      TEXT NOT NULL,
    line      INTEGER NOT NULL,
    temporary INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (name, file, line)
);

CREATE TABLE IF NOT EXISTS db_columns (
    tbl         TEXT NOT NULL,
    file        TEXT NOT NULL,
    idx         INTEGER NOT NULL,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT '',
    constraints TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS db_indexes (
    name    TEXT NOT NULL,
    tbl     TEXT NOT NULL,
    columns TEXT NOT NULL,
    file    TEXT NOT NULL,
    line    INTEGER NOT NULL,
    uniq    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cli_apps (
    id      TEXT PRIMARY KEY,
    var     TEXT NOT NULL,
    module  TEXT NOT NULL,
    file    TEXT NOT NULL,
    line    INTEGER NOT NULL,
    title   TEXT NOT NULL DEFAULT '',
    factory TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS cli_mounts (
    file          TEXT NOT NULL,
    parent_var    TEXT NOT NULL,
    parent_module TEXT NOT NULL,
    parent_id     TEXT,
    child_expr    TEXT NOT NULL,
    child_id      TEXT,
    line          INTEGER NOT NULL,
    name          TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS imports (
    file    TEXT NOT NULL,
    module  TEXT NOT NULL,
    name    TEXT NOT NULL,
    alias   TEXT NOT NULL,
    is_from INTEGER NOT NULL,
    line    INTEGER NOT NULL
);

-- Files the program names in its own source: `tabularium.db`, `groma.json`,
-- `STATUSQUO.md`. One row per reference site, never deduplicated at ingest, so
-- "how often is this named, and by whom" is answerable.
-- Values the program names at module level: model names, token ceilings, directory
-- names, retry limits. A constant is a name a person chose, and it carries the WHY
-- in the comment beside it.
CREATE TABLE IF NOT EXISTS constants (
    file     TEXT NOT NULL,
    module   TEXT NOT NULL,
    name     TEXT NOT NULL,
    value    TEXT NOT NULL,
    type     TEXT NOT NULL DEFAULT '',
    is_final INTEGER NOT NULL DEFAULT 0,
    comment  TEXT NOT NULL DEFAULT '',
    private  INTEGER NOT NULL DEFAULT 0,
    line     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS artefacts (
    file       TEXT NOT NULL,
    routine_id TEXT NOT NULL,
    name       TEXT NOT NULL,
    stem       TEXT NOT NULL,
    ext        TEXT NOT NULL,
    kind       TEXT NOT NULL,
    line       INTEGER NOT NULL,
    literal    TEXT NOT NULL,
    is_pattern INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_routines_file    ON routines(file);
CREATE INDEX IF NOT EXISTS ix_routines_modname ON routines(module, name);
CREATE INDEX IF NOT EXISTS ix_routines_name    ON routines(name);
CREATE INDEX IF NOT EXISTS ix_routines_qual    ON routines(qualname);
CREATE INDEX IF NOT EXISTS ix_calls_caller     ON calls(caller_id);
CREATE INDEX IF NOT EXISTS ix_calls_callee     ON calls(callee_id);
CREATE INDEX IF NOT EXISTS ix_calls_file       ON calls(file);
CREATE INDEX IF NOT EXISTS ix_bound_routine    ON boundaries(routine_id);
CREATE INDEX IF NOT EXISTS ix_bound_kind       ON boundaries(kind);
CREATE INDEX IF NOT EXISTS ix_bound_sal        ON boundaries(salience);
CREATE INDEX IF NOT EXISTS ix_bound_file       ON boundaries(file);
CREATE INDEX IF NOT EXISTS ix_struct_file      ON structures(file);
CREATE INDEX IF NOT EXISTS ix_struct_name      ON structures(name);
CREATE INDEX IF NOT EXISTS ix_annot_owner      ON annotations(owner_id);
CREATE INDEX IF NOT EXISTS ix_annot_value      ON annotations(value);
CREATE INDEX IF NOT EXISTS ix_comments_routine ON comments(routine_id);
CREATE INDEX IF NOT EXISTS ix_params_routine   ON params(routine_id);
CREATE INDEX IF NOT EXISTS ix_imports_file     ON imports(file);
CREATE INDEX IF NOT EXISTS ix_ep_routine       ON entrypoints(routine_id);
CREATE INDEX IF NOT EXISTS ix_ep_parent        ON entrypoints(parent_id);
CREATE INDEX IF NOT EXISTS ix_cliapp_modvar    ON cli_apps(module, var);
CREATE INDEX IF NOT EXISTS ix_cliapp_file      ON cli_apps(file);
CREATE INDEX IF NOT EXISTS ix_climount_file    ON cli_mounts(file);
CREATE INDEX IF NOT EXISTS ix_climount_parent  ON cli_mounts(parent_id);
CREATE INDEX IF NOT EXISTS ix_sqlops_routine   ON sql_ops(routine_id);
CREATE INDEX IF NOT EXISTS ix_netcalls_routine ON net_calls(routine_id);
CREATE INDEX IF NOT EXISTS ix_classes_name     ON classes(name);
CREATE INDEX IF NOT EXISTS ix_classes_file     ON classes(file);
CREATE INDEX IF NOT EXISTS ix_netcalls_file    ON net_calls(file);
CREATE INDEX IF NOT EXISTS ix_netcalls_proto   ON net_calls(protocol);
CREATE INDEX IF NOT EXISTS ix_sqlops_table     ON sql_ops(tbl);
CREATE INDEX IF NOT EXISTS ix_sqlops_file      ON sql_ops(file);
CREATE INDEX IF NOT EXISTS ix_dbtables_file    ON db_tables(file);
CREATE INDEX IF NOT EXISTS ix_dbcolumns_file   ON db_columns(file);
CREATE INDEX IF NOT EXISTS ix_dbcolumns_tbl    ON db_columns(tbl);
CREATE INDEX IF NOT EXISTS ix_dbindexes_file   ON db_indexes(file);
CREATE INDEX IF NOT EXISTS ix_artefacts_file   ON artefacts(file);
CREATE INDEX IF NOT EXISTS ix_artefacts_stem   ON artefacts(stem);
CREATE INDEX IF NOT EXISTS ix_artefacts_name   ON artefacts(name);
CREATE INDEX IF NOT EXISTS ix_artefacts_rout   ON artefacts(routine_id);
CREATE INDEX IF NOT EXISTS ix_constants_file   ON constants(file);
CREATE INDEX IF NOT EXISTS ix_constants_name   ON constants(name);
CREATE INDEX IF NOT EXISTS ix_constants_module ON constants(module);
"""


class StaleGraphError(RuntimeError):
    """A stored map was written by a different version of DunneFlow.

    Raised only on read paths. `analyze` rebuilds instead, because it has the source
    in hand; a reader does not, and answering out of an emptied graph would be a
    confident wrong answer -- the one outcome this tool may not produce.
    """


class Store:
    """A connection to one analysed program's graph."""

    def __init__(self, path: Path | str, *, writable: bool = True,
                 shared: bool = False) -> None:
        """Open one program's graph.

        `writable=False` is how every orientation command opens it, and the
        distinction is load-bearing rather than tidy. Discarding a stale graph is safe
        for `analyze`, which re-extracts in the same breath; for `touches`, `impact` or
        `query` it empties the map and then answers out of the hole, and `(no rows)` is
        indistinguishable from a true empty result. So a reader refuses a stale graph
        and says how to rebuild it, and only `analyze` is allowed to drop anything.
        """
        self.path = Path(path)
        self.writable = writable
        if writable:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        # `shared` hands the connection to more than one thread, and the caller then
        # owes it a lock. Only the server asks for it: `ThreadingHTTPServer` answers each
        # request on its own thread, and sqlite refuses a connection used off the thread
        # that made it -- serialising the calls is not enough on its own, which is worth
        # saying because a lock looks like it should be.
        self.conn = sqlite3.connect(self.path, check_same_thread=not shared)
        self.conn.row_factory = sqlite3.Row
        self._refuse_wrong_kind()
        if not writable:
            self.rebuilt = False
            self._refuse_if_stale()
            return
        self.rebuilt = self._discard_if_stale()
        self.conn.executescript(SCHEMA_SQL)
        self.set_meta("kind", "graph")
        self.set_meta("schema_version", str(SCHEMA_VERSION))
        self.set_meta("extractor", f"{SCHEMA_VERSION}:{rules_fingerprint()}")
        # Paths in this graph are relative to the tree it was read from, and the tree is
        # deliberately not recorded -- see `migrate.py`. Stated rather than assumed,
        # because a store with no rows has no absolute path to find and "empty" must not
        # be read as "already relative".
        self.set_meta(META_PATHS, PATHS_RELATIVE)

    def _refuse_wrong_kind(self) -> bool:
        """Refuse to open a database that is not a code graph.

        Found the hard way, in one keystroke: `--db output/<program>/docs.db` opened the
        document store as a graph, failed the staleness check, and dropped every table
        in it. A destructive fallback that looks like a version upgrade is exactly the
        silent-wrong-input failure this project keeps paying for, so the kind is
        stamped on the file and checked before anything is allowed to drop anything.
        """
        try:
            row = self.conn.execute("SELECT value FROM meta WHERE key = 'kind'").fetchone()
        except sqlite3.Error:
            return True
        if row is not None and str(row[0]) != "graph":
            raise ValueError(
                f"{self.path} is a {row[0]} database, not a code graph -- refusing to "
                f"open it as one, because doing so would discard its contents"
            )
        return True

    def _is_stale(self) -> bool:
        """Was this graph written by a different version of DunneFlow?

        The decision, with no side effect. Kept apart from `_discard_if_stale` so a
        reader can ask the same question and refuse rather than destroy.
        """
        want = f"{SCHEMA_VERSION}:{rules_fingerprint()}"
        try:
            row = self.conn.execute(
                "SELECT value FROM meta WHERE key = 'extractor'"
            ).fetchone()
        except sqlite3.Error:
            return False                      # no meta table yet: a fresh database
        if row is None:
            # A graph from before this key existed. If it holds facts, it was written by
            # an older extractor and cannot be trusted; if it is empty, nothing is lost.
            try:
                n = self.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            except sqlite3.Error:
                return False
            return bool(n)
        return str(row[0]) != want

    def _refuse_if_stale(self) -> None:
        """A reader never drops. It says the map is stale and **which** fix applies.

        Two different fixes, and naming the wrong one is expensive. A graph written before
        paths became relative needs `dunneflow migrate`, which rewrites it in place and
        keeps a sealed snapshot whose source tree may be long gone; telling that reader to
        re-analyse would ask them to rebuild from a tree they do not have. Anything else
        is stale for reasons no migration can speak for, and does need re-analysis.
        """
        if not self._is_stale():
            return
        if not paths_are_relative(self.conn):
            raise StaleGraphError(
                f"{self.path} stores absolute paths, from before DunneFlow made them "
                f"relative to the tree they were read from -- run "
                f"`dunneflow migrate {self.path.parent}` to rewrite it in place"
            )
        raise StaleGraphError(
            f"{self.path} was written by a different version of DunneFlow and "
            f"cannot be read safely -- re-run `dunneflow analyze` to rebuild it"
        )

    def _discard_if_stale(self) -> bool:
        """Drop a graph written by a different version of DunneFlow.

        `CREATE TABLE IF NOT EXISTS` will not add a column to a table that already
        exists, so an upgraded tool reading an older graph silently gets the old
        shape -- and because the incremental cache keys on source content alone,
        nothing re-parses to reveal it. The result is a map that is wrong and says
        nothing about being wrong, which is the one outcome this tool may not have.

        The graph is derived data, rebuildable from source in seconds. Discarding it
        is safe *here*, because `analyze` re-extracts immediately; it is not safe on a
        read path, which is why `_is_stale` is separate from the dropping.
        """
        if not self._is_stale():
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

    # -- lifecycle -------------------------------------------------------- #

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def batch(self) -> Iterator[sqlite3.Connection]:
        """One transaction around a burst of writes."""
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # -- meta ------------------------------------------------------------- #

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def get_meta(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    # -- incremental gate -------------------------------------------------- #

    def known_hashes(self) -> dict[str, str]:
        """Every file already analysed, and the hash it was analysed at."""
        return {
            r["path"]: r["content_hash"]
            for r in self.conn.execute("SELECT path, content_hash FROM files")
        }

    def known_langs(self) -> dict[str, str]:
        """Every file already analysed, and the language it was read as.

        Kept apart from `known_hashes` because the two answer different questions and
        only one of them gates re-parsing; the source sidecar wants both.
        """
        return {
            r["path"]: r["lang"]
            for r in self.conn.execute("SELECT path, lang FROM files")
        }

    def forget_file(self, path: str) -> None:
        """Drop every fact derived from one file, so it can be re-derived cleanly."""
        c = self.conn
        c.execute(
            "DELETE FROM params WHERE routine_id IN (SELECT id FROM routines WHERE file = ?)",
            (path,),
        )
        c.execute(
            "DELETE FROM comments WHERE routine_id IN (SELECT id FROM routines WHERE file = ?)",
            (path,),
        )
        c.execute(
            "DELETE FROM annotations WHERE owner_id IN "
            "(SELECT id FROM routines WHERE file = ?"
            " UNION SELECT id FROM structures WHERE file = ?)",
            (path, path),
        )
        c.execute(
            "DELETE FROM fields WHERE structure_id IN (SELECT id FROM structures WHERE file = ?)",
            (path,),
        )
        for table in ("routines", "structures", "calls", "boundaries", "imports",
                      "entrypoints", "cli_apps", "cli_mounts", "sql_ops", "db_tables",
                      "db_columns", "db_indexes", "net_calls", "classes",
                      "artefacts", "constants"):
            c.execute(f"DELETE FROM {table} WHERE file = ?", (path,))
        c.execute("DELETE FROM files WHERE path = ?", (path,))

    def prune_missing(self, live_paths: Iterable[str]) -> int:
        """Forget files that have disappeared from the source tree."""
        live = set(live_paths)
        gone = [p for p in self.known_hashes() if p not in live]
        for p in gone:
            self.forget_file(p)
        return len(gone)

    # -- writes ------------------------------------------------------------ #

    def write_file_facts(self, ff: FileFacts) -> None:
        """Replace all facts for one file. Callers should wrap bursts in `batch()`."""
        c = self.conn
        self.forget_file(ff.path)
        c.execute(
            "INSERT INTO files(path, lang, module, content_hash, doc, errors)"
            " VALUES(?,?,?,?,?,?)",
            (ff.path, ff.lang, ff.module, ff.content_hash, ff.doc, json.dumps(ff.errors)),
        )
        for r in ff.routines:
            c.execute(
                "INSERT INTO routines(id,name,qualname,module,file,line_start,line_end,lang,"
                "returns,docstring,decorators,is_async,is_method,class_name,is_nested,"
                "visibility,body_hash)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    r.id, r.name, r.qualname, r.module, r.file, r.line_start, r.line_end,
                    r.lang, r.returns, r.docstring, json.dumps(r.decorators),
                    int(r.is_async), int(r.is_method), r.class_name, int(r.is_nested),
                    r.visibility, r.body_hash,
                ),
            )
            c.executemany(
                "INSERT INTO params(routine_id,idx,name,type,dflt,kind) VALUES(?,?,?,?,?,?)",
                [(r.id, i, p.name, p.type, p.default, p.kind) for i, p in enumerate(r.params)],
            )
            c.executemany(
                "INSERT INTO comments(routine_id,line,text,leading) VALUES(?,?,?,?)",
                [(r.id, cm.line, cm.text, int(cm.leading)) for cm in r.comments],
            )
            c.executemany(
                "INSERT INTO annotations(owner_id,owner_kind,kind,value,line,text)"
                " VALUES(?,?,?,?,?,?)",
                [(r.id, "routine", a.kind, a.value, a.line, a.text) for a in r.annotations],
            )
        for s in ff.structures:
            c.execute(
                "INSERT INTO structures(id,name,kind,module,file,line,lang,docstring,bases)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (s.id, s.name, s.kind.value, s.module, s.file, s.line, s.lang, s.docstring,
                 json.dumps(s.bases)),
            )
            c.executemany(
                "INSERT INTO fields(structure_id,idx,name,type,dflt,comment) VALUES(?,?,?,?,?,?)",
                [(s.id, i, f.name, f.type, f.default, f.comment) for i, f in enumerate(s.fields)],
            )
            c.executemany(
                "INSERT INTO annotations(owner_id,owner_kind,kind,value,line,text)"
                " VALUES(?,?,?,?,?,?)",
                [(s.id, "structure", a.kind, a.value, a.line, a.text) for a in s.annotations],
            )
        c.executemany(
            "INSERT INTO calls"
            "(file,caller_id,callee_expr,line,callee_id,confidence,external,at_boundary)"
            " VALUES(?,?,?,?,?,?,?,?)",
            [(ff.path, k.caller_id, k.callee_expr, k.line, k.callee_id, k.confidence.value,
              int(k.external), int(k.at_boundary)) for k in ff.calls],
        )
        c.executemany(
            "INSERT INTO boundaries(file,routine_id,kind,direction,target,line,evidence,salience)"
            " VALUES(?,?,?,?,?,?,?,?)",
            [(ff.path, b.routine_id, b.kind.value, b.direction.value, b.target, b.line,
              b.evidence, b.salience) for b in ff.boundaries],
        )
        c.executemany(
            "INSERT INTO imports(file,module,name,alias,is_from,line) VALUES(?,?,?,?,?,?)",
            [(ff.path, i.module, i.name, i.alias, int(i.is_from), i.line) for i in ff.imports],
        )
        c.executemany(
            "INSERT OR REPLACE INTO entrypoints"
            "(id,kind,name,routine_id,module,file,evidence,grp,parent_id,target_expr)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            [(e.id, e.kind.value, e.name, e.routine_id, e.module, ff.path, e.evidence,
              e.group, e.parent_id, e.target_expr) for e in ff.entrypoints],
        )
        c.executemany(
            "INSERT INTO classes(name,qualname,module,file,line,bases)"
            " VALUES(?,?,?,?,?,?)",
            [(k.name, k.qualname, k.module, ff.path, k.line, json.dumps(k.bases))
             for k in ff.classes],
        )
        c.executemany(
            "INSERT INTO net_calls(file,routine_id,expr,protocol,verb,destination,port,"
            "is_async,awaited,in_async_routine,timeout,retries,tls,payload,headers,"
            "topic,ack,line)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(ff.path, x.routine_id, x.expr, x.protocol, x.verb, x.destination, x.port,
              int(x.is_async), int(x.awaited), int(x.in_async_routine), x.timeout,
              x.retries, x.tls, x.payload, x.headers, x.topic, x.ack, x.line)
             for x in ff.network],
        )
        c.executemany(
            "INSERT INTO sql_ops(file,routine_id,operation,direction,tbl,sql,line)"
            " VALUES(?,?,?,?,?,?,?)",
            [(ff.path, q.routine_id, q.operation, q.direction, t, q.sql, q.line)
             for q in ff.sql for t in (q.tables or [""])],
        )
        c.executemany(
            "INSERT OR REPLACE INTO db_tables(name,file,line,temporary) VALUES(?,?,?,?)",
            [(t.name, ff.path, t.line, int(t.temporary)) for t in ff.tables],
        )
        c.executemany(
            "INSERT INTO db_columns(tbl,file,idx,name,type,constraints) VALUES(?,?,?,?,?,?)",
            [(t.name, ff.path, i, cn, ct, cc)
             for t in ff.tables for i, (cn, ct, cc) in enumerate(t.columns)],
        )
        c.executemany(
            "INSERT INTO db_indexes(name,tbl,columns,file,line,uniq) VALUES(?,?,?,?,?,?)",
            [(x.name, x.table, x.columns, ff.path, x.line, int(x.unique))
             for x in ff.indexes],
        )
        c.executemany(
            "INSERT OR REPLACE INTO cli_apps(id,var,module,file,line,title,factory)"
            " VALUES(?,?,?,?,?,?,?)",
            [(a.id, a.var, a.module, ff.path, a.line, a.title, a.factory)
             for a in ff.cli_apps],
        )
        c.executemany(
            "INSERT INTO cli_mounts(file,parent_var,parent_module,child_expr,line,name)"
            " VALUES(?,?,?,?,?,?)",
            [(ff.path, m.parent_var, m.parent_module, m.child_expr, m.line, m.name)
             for m in ff.cli_mounts],
        )
        c.executemany(
            "INSERT INTO artefacts(file,routine_id,name,stem,ext,kind,line,literal,is_pattern)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            [(ff.path, a.routine_id, a.name, a.stem, a.ext, a.kind, a.line, a.literal,
              int(a.is_pattern)) for a in ff.artefacts],
        )
        c.executemany(
            "INSERT INTO constants(file,module,name,value,type,is_final,comment,private,line)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            [(ff.path, ff.module, k.name, k.value, k.type or "", int(k.is_final),
              k.comment or "", int(k.private), k.line) for k in ff.constants],
        )

    def add_entrypoint(self, e: Entrypoint, file: str = "") -> None:
        """Record an entrypoint discovered outside any single file (e.g. packaging metadata)."""
        self.conn.execute(
            "INSERT OR REPLACE INTO entrypoints"
            "(id,kind,name,routine_id,module,file,evidence,grp,parent_id,target_expr)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (e.id, e.kind.value, e.name, e.routine_id, e.module, file, e.evidence,
             e.group, e.parent_id, e.target_expr),
        )

    def set_call_target(self, caller_id: str, expr: str, line: int,
                        callee_id: str | None, confidence: Confidence, external: bool) -> None:
        self.conn.execute(
            "UPDATE calls SET callee_id = ?, confidence = ?, external = ?"
            " WHERE caller_id = ? AND callee_expr = ? AND line = ?",
            (callee_id, confidence.value, int(external), caller_id, expr, line),
        )

    # -- reads ------------------------------------------------------------- #

    def optimize(self) -> None:
        """Give the query planner statistics. Cheap, and worth it before querying."""
        self.conn.execute("ANALYZE")
        self.conn.execute("PRAGMA optimize")
        self.conn.commit()

    def warm(self) -> None:
        """Pull the hot tables into cache so the first orientation query is not the
        one that pays for the disk."""
        for t in ("calls", "boundaries", "routines"):
            self.conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for t in ("files", "routines", "calls", "boundaries", "structures", "entrypoints",
                  "annotations", "cli_apps", "cli_mounts", "sql_ops", "db_tables",
                  "db_indexes", "net_calls"):
            out[t] = self.conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
        out["resolved_calls"] = self.conn.execute(
            "SELECT COUNT(*) AS n FROM calls WHERE callee_id IS NOT NULL"
        ).fetchone()["n"]
        return out

    def routine(self, rid: str) -> Routine | None:
        row = self.conn.execute("SELECT * FROM routines WHERE id = ?", (rid,)).fetchone()
        return self._routine_from_row(row) if row else None

    def routines(self, module: str | None = None) -> list[Routine]:
        if module:
            rows = self.conn.execute(
                "SELECT * FROM routines WHERE module = ? ORDER BY line_start", (module,)
            )
        else:
            rows = self.conn.execute("SELECT * FROM routines ORDER BY module, line_start")
        return [self._routine_from_row(r) for r in rows]

    def _routine_from_row(self, row: sqlite3.Row) -> Routine:
        rid = row["id"]
        params = [
            Param(p["name"], p["type"], p["dflt"], p["kind"])
            for p in self.conn.execute(
                "SELECT * FROM params WHERE routine_id = ? ORDER BY idx", (rid,)
            )
        ]
        comments = [
            Comment(c["text"], c["line"], bool(c["leading"]))
            for c in self.conn.execute(
                "SELECT * FROM comments WHERE routine_id = ? ORDER BY line", (rid,)
            )
        ]
        annots = [
            Annotation(a["kind"], a["value"], a["line"], a["text"])
            for a in self.conn.execute(
                "SELECT * FROM annotations WHERE owner_id = ? ORDER BY line", (rid,)
            )
        ]
        return Routine(
            id=rid, name=row["name"], qualname=row["qualname"], module=row["module"],
            file=row["file"], line_start=row["line_start"], line_end=row["line_end"],
            lang=row["lang"], params=params, returns=row["returns"],
            decorators=json.loads(row["decorators"]), docstring=row["docstring"],
            comments=comments, annotations=annots, is_async=bool(row["is_async"]),
            is_method=bool(row["is_method"]), class_name=row["class_name"],
            is_nested=bool(row["is_nested"]), visibility=row["visibility"],
            body_hash=row["body_hash"],
        )

    def entrypoints(self) -> list[Entrypoint]:
        return [
            Entrypoint(
                id=r["id"], kind=EntrypointKind(r["kind"]), name=r["name"],
                routine_id=r["routine_id"], module=r["module"], evidence=r["evidence"],
                group=r["grp"], parent_id=r["parent_id"], target_expr=r["target_expr"],
            )
            for r in self.conn.execute("SELECT * FROM entrypoints ORDER BY kind, name")
        ]

    def structures(self) -> list[DataStructure]:
        out = []
        for r in self.conn.execute("SELECT * FROM structures ORDER BY module, line"):
            flds = [
                Field_(f["name"], f["type"], f["dflt"], f["comment"])
                for f in self.conn.execute(
                    "SELECT * FROM fields WHERE structure_id = ? ORDER BY idx", (r["id"],)
                )
            ]
            out.append(DataStructure(
                id=r["id"], name=r["name"], kind=StructureKind(r["kind"]), module=r["module"],
                file=r["file"], line=r["line"], lang=r["lang"], fields=flds,
                docstring=r["docstring"], bases=json.loads(r["bases"]),
            ))
        return out

    def boundaries_of(self, routine_id: str) -> list[BoundaryHit]:
        return [
            BoundaryHit(
                routine_id=r["routine_id"], kind=BoundaryKind(r["kind"]),
                direction=Direction(r["direction"]), target=r["target"], line=r["line"],
                evidence=r["evidence"], salience=r["salience"],
            )
            for r in self.conn.execute(
                "SELECT * FROM boundaries WHERE routine_id = ? ORDER BY line", (routine_id,)
            )
        ]

    # -- orientation queries ----------------------------------------------- #
    #
    # Recursive SQL over indexed edges. These are the three questions the tool
    # exists to answer, and they must stay fast no matter how large the target is.

    def reachable_from(self, routine_id: str, max_depth: int = 40) -> list[str]:
        """Everything this routine can reach. "What does this touch?" """
        rows = self.conn.execute(
            """
            WITH RECURSIVE reach(id, depth) AS (
                SELECT ?, 0
                UNION
                SELECT c.callee_id, r.depth + 1
                  FROM calls c JOIN reach r ON c.caller_id = r.id
                 WHERE c.callee_id IS NOT NULL AND r.depth < ?
            )
            SELECT DISTINCT id FROM reach WHERE id IS NOT NULL
            """,
            (routine_id, max_depth),
        )
        return [r["id"] for r in rows]

    def callers_of(self, routine_id: str, max_depth: int = 40) -> list[str]:
        """Everything that can reach this routine. "What breaks if I change it?" """
        rows = self.conn.execute(
            """
            WITH RECURSIVE back(id, depth) AS (
                SELECT ?, 0
                UNION
                SELECT c.caller_id, b.depth + 1
                  FROM calls c JOIN back b ON c.callee_id = b.id
                 WHERE b.depth < ?
            )
            SELECT DISTINCT id FROM back WHERE id IS NOT NULL AND id != ?
            """,
            (routine_id, max_depth, routine_id),
        )
        return [r["id"] for r in rows]

    def boundaries_reached(self, routine_id: str, max_depth: int = 40) -> list[BoundaryHit]:
        """Every boundary this routine reaches, directly or through anything it calls."""
        rows = self.conn.execute(
            """
            WITH RECURSIVE reach(id, depth) AS (
                SELECT ?, 0
                UNION
                SELECT c.callee_id, r.depth + 1
                  FROM calls c JOIN reach r ON c.caller_id = r.id
                 WHERE c.callee_id IS NOT NULL AND r.depth < ?
            )
            SELECT DISTINCT b.* FROM boundaries b JOIN reach r ON b.routine_id = r.id
            ORDER BY b.kind, b.target
            """,
            (routine_id, max_depth),
        )
        return [
            BoundaryHit(
                routine_id=r["routine_id"], kind=BoundaryKind(r["kind"]),
                direction=Direction(r["direction"]), target=r["target"], line=r["line"],
                evidence=r["evidence"], salience=r["salience"],
            )
            for r in rows
        ]

    def reachable_from_many(self, routine_ids: list[str], max_depth: int = 40) -> set[str]:
        """Everything a *set* of routines can reach, as one traversal.

        An executable built from a command tree has no single root routine: its reach
        is the union over every command it exposes. Seeding the recursion with all of
        them at once costs one query instead of one per command.
        """
        if not routine_ids:
            return set()
        ph = ",".join("?" * len(routine_ids))
        rows = self.conn.execute(
            f"""
            WITH RECURSIVE seed(id) AS (SELECT value FROM (SELECT ? AS value)),
            reach(id, depth) AS (
                SELECT id, 0 FROM routines WHERE id IN ({ph})
                UNION
                SELECT c.callee_id, r.depth + 1
                  FROM calls c JOIN reach r ON c.caller_id = r.id
                 WHERE c.callee_id IS NOT NULL AND r.depth < ?
            )
            SELECT DISTINCT id FROM reach WHERE id IS NOT NULL
            """,
            (routine_ids[0], *routine_ids, max_depth),
        )
        return {r["id"] for r in rows}

    def boundaries_reached_many(self, routine_ids: list[str],
                               max_depth: int = 40) -> list[BoundaryHit]:
        """Every boundary a set of routines reaches, directly or transitively."""
        if not routine_ids:
            return []
        ph = ",".join("?" * len(routine_ids))
        rows = self.conn.execute(
            f"""
            WITH RECURSIVE reach(id, depth) AS (
                SELECT id, 0 FROM routines WHERE id IN ({ph})
                UNION
                SELECT c.callee_id, r.depth + 1
                  FROM calls c JOIN reach r ON c.caller_id = r.id
                 WHERE c.callee_id IS NOT NULL AND r.depth < ?
            )
            SELECT DISTINCT b.* FROM boundaries b JOIN reach r ON b.routine_id = r.id
            ORDER BY b.kind, b.target
            """,
            (*routine_ids, max_depth),
        )
        return [
            BoundaryHit(
                routine_id=r["routine_id"], kind=BoundaryKind(r["kind"]),
                direction=Direction(r["direction"]), target=r["target"], line=r["line"],
                evidence=r["evidence"], salience=r["salience"],
            )
            for r in rows
        ]

    def query(self, sql: str,
              args: tuple[Any, ...] | dict[str, Any] = ()) -> list[sqlite3.Row]:
        """Run one query. A dict binds named placeholders (`:root`), a tuple positional.

        Named binding matters for the dashboard's disk queries, where the same package
        expression is spliced into several statements and repeating its parameters
        positionally in each one is how they drift apart.
        """
        return list(self.conn.execute(sql, args))
