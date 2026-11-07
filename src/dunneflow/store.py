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
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .detectors import core_fingerprint, frontier_words, lang_fingerprint
from .migrate import (
    META_PATHS,
    PATHS_RELATIVE,
    PREVIOUS_CODE_EXTRACTOR,
    migration_speaks_for,
)
from .schema import (
    SCHEMA_VERSION,
    Annotation,
    BoundaryHit,
    BoundaryKind,
    Comment,
    DataStructure,
    Direction,
    Entrypoint,
    EntrypointKind,
    Field_,
    FileFacts,
    Param,
    Routine,
    StructureKind,
    SuppliedBinding,
    SuppliedEdge,
    SuppliedMacroCallee,
    SuppliedUse,
    TargetKind,
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
    errors       TEXT NOT NULL DEFAULT '[]',
    -- **Which reader produced this row, as a version and a hash of its bytes.** The
    -- other half of rule 12's split: `meta.extractor` says what every language passed
    -- through, and this says what *this* file passed through. It is what makes a partial
    -- discard possible -- editing the TypeScript reader costs the TypeScript rows and
    -- leaves the Python ones alone -- and it is the only place that fact is recorded, so
    -- a map cannot hold two answers about which reader read a file (rule 40).
    extractor    TEXT NOT NULL DEFAULT '',
    -- `FileFacts.read_through`: the file this one was parsed as part of, or ''.
    read_through TEXT NOT NULL DEFAULT '',
    macro_directive_uses INTEGER NOT NULL DEFAULT 0,
    skipped_lines INTEGER NOT NULL DEFAULT 0,
    first_missing TEXT NOT NULL DEFAULT ''
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
    body_hash  TEXT NOT NULL DEFAULT '',
    name_by    TEXT NOT NULL DEFAULT '',
    body_by    TEXT NOT NULL DEFAULT '',
    opaque_asm INTEGER NOT NULL DEFAULT 0
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
    ambiguous   INTEGER NOT NULL DEFAULT 0,
    site_id     TEXT NOT NULL DEFAULT '',
    -- `new Foo()` against `Foo()`. Two spellings that call one name and do two different
    -- things, so they stay two facts (rule 30, and `ingest/dotted.py` clause 7). Always 0
    -- for Python, which has no such syntax.
    construction INTEGER NOT NULL DEFAULT 0,
    -- The callee is a name the calling routine binds itself (a parameter, an assignment),
    -- so it is not resolved by name against the rest of the program.
    bound_locally INTEGER NOT NULL DEFAULT 0,
    -- The qualname of this program's class that the call builds, when the class defines
    -- no constructor to draw an edge to. Such a call is not external: what it builds is
    -- here, and only the routine is missing because there is none.
    constructs  TEXT NOT NULL DEFAULT '',
    -- **Where the map stops, and why** (schema 17, `SuppliedEdge.frontier`/`reason`): for a
    -- call with no edge, the far end as its reader knows it and one word for why there is
    -- no edge. Empty where the reader said nothing, which every reader but Rust's is.
    frontier    TEXT NOT NULL DEFAULT '',
    reason      TEXT NOT NULL DEFAULT ''
);

-- What one caller actually passed, as written. Hangs off `calls.site_id` rather than
-- off a rowid, because a rowid is a position in this file and an argument has to stay
-- attached to its call site across two versions of the same program.
CREATE TABLE IF NOT EXISTS call_args (
    site_id TEXT NOT NULL,
    idx     INTEGER NOT NULL,
    expr    TEXT NOT NULL,
    keyword TEXT,
    splat   INTEGER NOT NULL DEFAULT 0
);

-- Where a call goes, according to a reader whose toolchain resolved it. Not `calls`'
-- column, because it is a different provenance answering a different question: `calls`
-- holds what the caller *wrote*, and the resolver's answer lands in `calls.callee_id`
-- like every other language's. This is the evidence that answer was made from.
--
-- **Keyed by language and replaced whole**, never by file -- see `SuppliedEdge`. A checker
-- answers about a compilation, so a per-file delete would leave half a set behind, and the
-- half left behind is the stale half. `forget_file` therefore does not touch it.
CREATE TABLE IF NOT EXISTS supplied_edges (
    lang       TEXT NOT NULL,
    site_id    TEXT NOT NULL,
    caller_id  TEXT NOT NULL,
    file       TEXT NOT NULL DEFAULT '',
    line       INTEGER NOT NULL DEFAULT 0,
    name       TEXT NOT NULL DEFAULT '',
    how        TEXT NOT NULL DEFAULT '',
    candidates INTEGER NOT NULL DEFAULT 0,
    constructs TEXT NOT NULL DEFAULT '',
    frontier   TEXT NOT NULL DEFAULT '',
    reason     TEXT NOT NULL DEFAULT '',
    -- `SuppliedEdge.answers`, as JSON `[[file, line, name], …]`: the bodies a `dynamic`
    -- call may reach. Read by `resolve/dispatch.py` and by nothing else.
    answers    TEXT NOT NULL DEFAULT '[]'
);

-- `schema.SuppliedBinding`: the routine a way in starts, as the reader's toolchain knows it,
-- or why none. Whole per language, like `supplied_edges`, and for the same reason: the edge
-- pass answers about the whole compilation. Read by `resolve/supplied.bind_ways_in`, which
-- sets `entrypoints.routine_id`, and by `resolve/entrypoints.binding_note` for `why`.
CREATE TABLE IF NOT EXISTS supplied_bindings (
    lang          TEXT NOT NULL,
    entrypoint_id TEXT NOT NULL,
    file          TEXT NOT NULL DEFAULT '',
    line          INTEGER NOT NULL DEFAULT 0,
    name          TEXT NOT NULL DEFAULT '',
    why           TEXT NOT NULL DEFAULT '',
    -- `SuppliedBinding.answers`, as JSON `[[file, line, name], …]`.
    answers       TEXT NOT NULL DEFAULT '[]'
);

-- The routines a way in with no body of its own may start: any one of them, which is why this
-- is not `entrypoints.routine_id` and that stays NULL. Written whole by
-- `resolve/supplied.bind_ways_in`, from `supplied_bindings.answers`.
CREATE TABLE IF NOT EXISTS entrypoint_roots (
    entrypoint_id TEXT NOT NULL,
    routine_id    TEXT NOT NULL,
    PRIMARY KEY (entrypoint_id, routine_id)
);

-- `schema.SuppliedUse`: a routine a reader saw named as a value -- a callback passed or
-- stored. Whole per language. Read by `anomalies._dead_code`, which does not list a routine
-- that is used even where nothing calls it by name.
CREATE TABLE IF NOT EXISTS value_uses (
    lang TEXT NOT NULL,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    name TEXT NOT NULL
);

-- Names a file hands to an IPC dispatch (`schema.IpcRegistration`). Per file, like
-- `entrypoints`: the registrar is a site in one file and is forgotten with it.
CREATE TABLE IF NOT EXISTS ipc_registrations (
    file TEXT NOT NULL,
    name TEXT NOT NULL,
    line INTEGER NOT NULL
);

-- A call site that sends a command by name, and the way in that answers it -- or, where
-- `entrypoint_id` is NULL, the reason none does (`status`). **Never `calls.callee_id`**
-- (rule 2): the site is a boundary call into the client library, and this is a second
-- fact about where the far end is, made by matching a string. `resolve/ipc.py` derives it
-- from the whole tree after edges and replaces it whole, so `forget_file` does not touch
-- it, for `supplied_edges`' reason.
--
-- `status` is `linked`, `unknown` (no command answers the name), `ambiguous` (two
-- applications answer it equally near) or `dynamic` (the name is not written as a
-- literal, so nothing is matched and nothing is guessed). `how` says how the match was
-- made, and `confidence` is `INFERRED` because a string is not a reference.
CREATE TABLE IF NOT EXISTS ipc_links (
    site_id       TEXT NOT NULL,
    caller_id     TEXT NOT NULL,
    file          TEXT NOT NULL,
    line          INTEGER NOT NULL,
    command       TEXT NOT NULL DEFAULT '',
    carrier_id    TEXT,
    entrypoint_id TEXT,
    routine_id    TEXT,
    status        TEXT NOT NULL,
    how           TEXT NOT NULL DEFAULT '',
    confidence    TEXT NOT NULL DEFAULT 'INFERRED'
);

-- A dispatched call and one body that may answer it (`schema.Answer`), one row per body.
-- **Never `calls.callee_id`** (rule 2): the checker resolved the call to a slot that
-- several bodies fill, and which one runs is the object's at run time. So this is a fact
-- beside the call graph that every walk crosses as an arm of its own, and `how` says *by
-- dispatch* wherever a surface shows it: any of these may run, and none is said to. Derived
-- by `resolve/dispatch.py` after edges and replaced whole, for `ipc_links`' reason.
CREATE TABLE IF NOT EXISTS dispatch_links (
    site_id    TEXT NOT NULL,
    caller_id  TEXT NOT NULL,
    routine_id TEXT NOT NULL,
    how        TEXT NOT NULL DEFAULT 'by dispatch'
);

CREATE TABLE IF NOT EXISTS boundaries (
    file       TEXT NOT NULL,
    routine_id TEXT NOT NULL,
    kind       TEXT NOT NULL,
    direction  TEXT NOT NULL,
    target     TEXT NOT NULL,
    line       INTEGER NOT NULL,
    evidence   TEXT NOT NULL DEFAULT '',
    salience   TEXT NOT NULL DEFAULT 'normal',
    through_macro TEXT NOT NULL DEFAULT '',
    -- From the edge pass rather than from this file's own facts, so replaced with it.
    expanded   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS control (
    point_id   TEXT NOT NULL,
    file       TEXT NOT NULL,
    routine_id TEXT NOT NULL,
    kind       TEXT NOT NULL,
    line_start INTEGER NOT NULL,
    line_end   INTEGER NOT NULL,
    depth      INTEGER NOT NULL DEFAULT 1,
    header     TEXT NOT NULL DEFAULT '',
    arms       INTEGER NOT NULL DEFAULT 1,
    exits      TEXT NOT NULL DEFAULT '',
    -- The word the source opened this point with, and the lines it evaluates once
    -- before the first pass. `once_start`/`once_end` are 0/0 wherever nothing runs
    -- once -- a `while`, every decision, and a loop written on a single line, where
    -- the element and the iterable share a line and a line cannot choose between
    -- them. Four statements in `web/queries.py` read these because they ask the same
    -- range question in SQL and cannot import `resolve/shape.py` (rule 51).
    word       TEXT NOT NULL DEFAULT '',
    once_start INTEGER NOT NULL DEFAULT 0,
    once_end   INTEGER NOT NULL DEFAULT 0
);

-- The ways through one control point, and only where there is more than one. Hangs off
-- `control.point_id` rather than off a file, for `call_args`' reason: an arm has to stay
-- attached to its own decision across two versions of the same program, and a rowid is a
-- position in this file.
CREATE TABLE IF NOT EXISTS control_arms (
    point_id   TEXT NOT NULL,
    routine_id TEXT NOT NULL,
    idx        INTEGER NOT NULL,
    kind       TEXT NOT NULL,
    line_start INTEGER NOT NULL,
    line_end   INTEGER NOT NULL,
    header     TEXT NOT NULL DEFAULT ''
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
    bases     TEXT NOT NULL DEFAULT '[]',
    name_by   TEXT NOT NULL DEFAULT ''
);

-- **One row per definition, and a definition is not owned by the file that uses it**: a header
-- outside the tree has no `files` row, and a re-read of one file must not take away a definition
-- other files still use. So nothing forgets these per file; `sweep_macro_defs` removes the ones
-- no use reaches, once, when an analysis finishes.
CREATE TABLE IF NOT EXISTS macro_defs (
    id     TEXT PRIMARY KEY,
    name   TEXT NOT NULL,
    file   TEXT NOT NULL,
    line   INTEGER NOT NULL,
    origin TEXT NOT NULL
);

-- One row per use. The name is here as well as on the definition so that `web/changes.py` can
-- compare uses across two versions, where a definition's id moves with its line.
CREATE TABLE IF NOT EXISTS macro_sites (
    file       TEXT NOT NULL,
    line       INTEGER NOT NULL,
    def_id     TEXT NOT NULL,
    name       TEXT NOT NULL,
    position   TEXT NOT NULL,
    routine_id TEXT,
    shadows    TEXT NOT NULL DEFAULT ''
);

-- `schema.SuppliedMacroCallee`. Whole per language, for `supplied_edges`' reason. A callee is
-- joined to its routine by location, as `value_uses` is, because the host and not the reader
-- owns routine ids.
CREATE TABLE IF NOT EXISTS macro_callees (
    lang        TEXT NOT NULL,
    file        TEXT NOT NULL,
    line        INTEGER NOT NULL,
    def_id      TEXT NOT NULL,
    routine_id  TEXT NOT NULL,
    callee      TEXT NOT NULL DEFAULT '',
    target_file TEXT NOT NULL DEFAULT '',
    target_line INTEGER NOT NULL DEFAULT 0,
    target_name TEXT NOT NULL DEFAULT '',
    candidates  INTEGER NOT NULL DEFAULT 0,
    indirect    INTEGER NOT NULL DEFAULT 0,
    count       INTEGER NOT NULL DEFAULT 1
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
    target_expr TEXT NOT NULL DEFAULT '',
    -- Read out of a manifest, as against recognised in code. See `Entrypoint.declared`.
    declared   INTEGER NOT NULL DEFAULT 0,
    -- What `target_expr` names, where this was declared. See `schema.TargetKind`.
    target_kind TEXT NOT NULL DEFAULT 'NONE'
);

-- Every manifest this analysis read, and what each one declared.
--
-- **A table rather than a sentence**, because the claim on the cover -- *this program
-- declares two versions* -- is one a reader must be able to put a query behind (design
-- rule 13). `dunneflow query --sql "SELECT * FROM manifests"` returns the rows the
-- sentence was made from.
--
-- `ways_in` is a count and not a join: the entrypoints a manifest declared are in
-- `entrypoints`, keyed by their own ids, and a second copy of that relationship here
-- would be two numbers about one thing (rule 40). What this column carries is how many
-- this provider produced, which is what makes *read and declared nothing* legible.
--
-- `at_root` separates the program's own declaration from a member's. Declared rather
-- than inferred from the shape of `path`, because `../pyproject.toml` and
-- `packages/api-types/package.json` are both outside the analysed directory in
-- different directions (rule 30).
CREATE TABLE IF NOT EXISTS manifests (
    path     TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    name     TEXT NOT NULL DEFAULT '',
    version  TEXT NOT NULL DEFAULT '',
    ways_in  INTEGER NOT NULL DEFAULT 0,
    at_root  INTEGER NOT NULL DEFAULT 0,
    note     TEXT NOT NULL DEFAULT ''
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

-- Files the program names in its own source: `app.db`, `settings.json`,
-- `STATUS.md`. One row per reference site, never deduplicated at ingest, so
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
CREATE INDEX IF NOT EXISTS ix_bindings_ep      ON supplied_bindings(entrypoint_id);
CREATE INDEX IF NOT EXISTS ix_value_uses_at    ON value_uses(file, line, name);
CREATE INDEX IF NOT EXISTS ix_calls_callee     ON calls(callee_id);
CREATE INDEX IF NOT EXISTS ix_calls_file       ON calls(file);
CREATE INDEX IF NOT EXISTS ix_calls_site       ON calls(site_id);
CREATE INDEX IF NOT EXISTS ix_callargs_site    ON call_args(site_id);
CREATE INDEX IF NOT EXISTS ix_supplied_site    ON supplied_edges(site_id);
CREATE INDEX IF NOT EXISTS ix_supplied_lang    ON supplied_edges(lang);
CREATE INDEX IF NOT EXISTS ix_ipcreg_name      ON ipc_registrations(name);
CREATE INDEX IF NOT EXISTS ix_ipclink_caller   ON ipc_links(caller_id);
CREATE INDEX IF NOT EXISTS ix_ipclink_routine  ON ipc_links(routine_id);
CREATE INDEX IF NOT EXISTS ix_disp_caller      ON dispatch_links(caller_id);
CREATE INDEX IF NOT EXISTS ix_disp_routine     ON dispatch_links(routine_id);
CREATE INDEX IF NOT EXISTS ix_bound_routine    ON boundaries(routine_id);
CREATE INDEX IF NOT EXISTS ix_bound_kind       ON boundaries(kind);
CREATE INDEX IF NOT EXISTS ix_bound_sal        ON boundaries(salience);
CREATE INDEX IF NOT EXISTS ix_bound_file       ON boundaries(file);
CREATE INDEX IF NOT EXISTS ix_control_routine  ON control(routine_id, line_start, line_end);
CREATE INDEX IF NOT EXISTS ix_control_point    ON control(point_id);
CREATE INDEX IF NOT EXISTS ix_arms_point       ON control_arms(point_id);
CREATE INDEX IF NOT EXISTS ix_macro_sites_def   ON macro_sites(def_id);
CREATE INDEX IF NOT EXISTS ix_macro_callees_def ON macro_callees(def_id);
CREATE INDEX IF NOT EXISTS ix_macro_callees_who ON macro_callees(routine_id);
CREATE INDEX IF NOT EXISTS ix_macro_callees_at
    ON macro_callees(target_file, target_line, target_name);
CREATE INDEX IF NOT EXISTS ix_macro_sites_file  ON macro_sites(file);
CREATE INDEX IF NOT EXISTS ix_macro_sites_owner ON macro_sites(routine_id);
CREATE INDEX IF NOT EXISTS ix_arms_routine     ON control_arms(routine_id, line_start, line_end);
CREATE INDEX IF NOT EXISTS ix_control_kind     ON control(kind);
CREATE INDEX IF NOT EXISTS ix_control_file     ON control(file);
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

# **How large the write-ahead log may get before a burst stops to let it drain**, and it is
# `cache_size` above said in bytes. The two belong together: SQLite cannot checkpoint a WAL
# while a write transaction is open, so a burst that never commits grows one without bound —
# and the moment it outgrows the page cache, every index insert starts reading pages back out
# of it. That is not a slowdown, it is a different cost curve.
#
# **Measured rather than chosen.** Analysing the whole of `UnrealEngine-release` — 84,159 C++
# files in one transaction — the log reached 734 MB and throughput fell from 98% CPU to 0.1%,
# about 2 MB a minute and still falling, after 1 h 45 m. Sampled there:
# `sqlite3BtreeIndexMoveto` → `sqlite3PagerGet` → `sqlite3WalReadFrame`, with
# `sqlite3PcacheFetchStress` spilling dirty pages continuously. `Engine/Source/Runtime`,
# 18,191 files, went through the same single transaction in 8 m 54 s because its log stayed
# inside the cache. The cap is where that difference is.
#
# Half the cache and not all of it, because the cache also holds what is being *read* —
# `known_hashes`, the index pages an insert walks — and a WAL exactly the size of the cache
# leaves that nothing.
#
# **What it is worth, measured on one part rather than argued.** `Engine/Source/Runtime`,
# 18,191 files, extracted to the external volume:
#
#     with this cap     700 s, log held at 136 MB, 62 drains, 17,664 files committed at 10 min
#     without it        stopped at 29 min, log 533 MB and growing, **0 files committed**
#
# Two separate wins in those rows and only the first is about speed. The second is that the
# capped run had **committed** all but a few hundred files by the time the other had committed
# none: one transaction means a run interrupted at 28 minutes has nothing to show for it, and
# `known_hashes` cannot resume what was never written.
#
# It costs nothing where it is not needed: 3,169 files took 12.9 s capped against 13.0 s
# uncapped, and 9,591 took 42.3 s against 40.7 s — 4%, for a log held at 93 MB instead of
# 264 MB.
WAL_CAP_BYTES = 32 * 1024 * 1024

# How often the log is measured, in files. A `stat` is cheap and this is a run that is
# already reading files off a disk, but it is not free and nothing needs it per file: the cap
# is a soft ceiling, and overshooting it by a few hundred files' worth of rows costs a
# checkpoint that was going to happen anyway.
WAL_CHECK_EVERY = 256


class UnfinishedMapError(RuntimeError):
    """An analysis started writing this map and never finished. **Rule 80.**

    A killed `analyze` leaves a graph that **opens perfectly and lies**. Measured on the
    Society tree by stopping one twelve seconds in: 628 files, 4,786 routines, 4,070
    boundary touches -- and `resolved_calls = 0`, because it died before `resolve_calls`.
    It carries `analysed_at`, `tool_version` and `inference = none`, so every part of the
    dashboard vouches for it, and it reports a program that calls nothing.

    Reachable with no stop button anywhere: Ctrl-C, a laptop that slept, an OOM kill, a
    full disk. So the writer records its own state and every reader that presents a map as
    *finished* refuses -- rule 20's shape, with `analyze` itself deliberately exempt,
    because opening one is exactly how it recovers.

    **Three states, never two.** `complete` missing means the map predates this key and is
    fine; `""` means started and never finished; `"yes"` means finished. Absence alone
    cannot carry the claim, because every map made before today lacks the key.
    """


def unfinished_sentence(name: str, step: str) -> str:
    """Why this map may not be read, in one sentence, said the same way everywhere.

    Four readers refuse an unfinished map -- the dashboard's switch, `serve`'s boot, the
    program list and `check` -- and a sentence written at each of them would be four
    readings of one fact by the fourth time somebody added a reader (rule 51).

    **It names the step and stops there.** Saying *"nothing resolved its calls"* would be
    a claim about which step it died on, true of the one measured case and false of the
    others; what is always true is that a part of a program is not a program (rule 13).

    And it names the **way out**, because rule 80's last line is that a refusal which only
    ever says no teaches people to work around it.
    """
    where = f" while {step}" if step else ""
    return (f"{name} was never finished: an analysis stopped{where}. What it holds is part "
            f"of a program, not a program. Analysing it again completes it — the "
            f"extraction is cached, so it takes seconds rather than the whole run.")


class StaleGraphError(RuntimeError):
    """A stored map was written by a different version of DunneFlow.

    Raised only on read paths. `analyze` rebuilds instead, because it has the source
    in hand; a reader does not, and answering out of an emptied graph would be a
    confident wrong answer -- the one outcome this tool may not produce.
    """


def read_only_uri(path: Path) -> str:
    """A path, as a SQLite URI that cannot write — and the one place that spelling lives.

    `f"file:{path}?mode=ro"` is what four sites in this codebase already write by hand,
    and it is right until a path contains a character the URI grammar has already spent.
    A `?` in a directory name ends the path and starts the query; a `#` ends it and starts
    a fragment; a `%` begins an escape that is probably not one. Each yields a URI naming
    a database nobody asked for, and — because `mode=ro` was in the part that got eaten —
    one that SQLite would then happily **create**, which is the exact failure
    `refuse_missing` below exists to prevent, arriving through the fix for something else.

    Rule 91: a sentence has to fit the channel it is put in, and a filename inside a URI
    is on that rule's own list of channels narrower than the text going through them.
    Nothing validates on the way in; the failure is at the far end.

    `safe="/"` keeps the separators separators. A Windows `\\` is escaped to `%5C` and
    SQLite decodes it back before opening, so both spellings survive the round trip.
    """
    return f"file:{quote(str(path), safe='/')}?mode=ro"


def refuse_missing(path: Path, what: str) -> None:
    """A read of a path that is not there refuses, and never brings one into being.

    **`sqlite3.connect` creates.** So a reader handed a path that does not exist does not
    fail: it manufactures an empty database, answers out of it, and — the expensive half —
    **leaves the file behind**. `revisions.program_dirs()` and `revisions.newest()` glob
    `graph*.db`, so the leftover becomes a phantom revision of a program that never had
    one: a bare `graph.db` is read as *"a directory written before this layout existed"*
    (`revisions.py`), and this one holds nothing at all.

    Rule 20 from the side nobody expects. That rule says a read may refuse but may never
    *repair*; here the read repaired nothing and simply **wrote**, into the one directory
    this project treats as an artifact. Found by doing it: a one-line probe against
    `output/mensores/graph.db` — a path that does not exist there, since mensores keeps
    only `graph@<revision>.db` — put a 0-byte file into the output tree, invisible to
    `git status` because `output/` is untracked.

    **This is rule 51 exactly, and the count is the argument.** Seven read paths each
    carried their own `if not path.exists()` — `cli._open_store`, `_Live._docs_for`,
    `_open_source`, `_open_docsource`, and the version-listing branch in `_r_revisions` —
    and the guard held for exactly as long as somebody remembered to write it. Every one
    of them is now redundant and correct rather than load-bearing, which is the state rule
    51 asks for: the rule lives where they all pass.

    `FileNotFoundError` rather than an exception of ours, for two reasons that already
    exist in the code. It is an `OSError`, which is precisely what the four sites in
    `serve.py` catch to mean *"absent is a real state, never an error"* — so a missing
    sidecar goes on answering `None` and `corpus.serving()`'s four states are untouched.
    And `serve.why()` states in so many words that a class name earns its place in front
    of an `OSError`, so the sentence a reader sees is right without wiring.

    Read paths only. A writer creating its own file is the entire point of a writer.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist, so there is nothing to read — refusing to open "
            f"{what} there, because opening it would create an empty one and an empty "
            f"map answers every question with silence"
        )



def _frontier(rows: list[sqlite3.Row]) -> dict[str, Any]:
    """Group frontier rows: outside by the far end's first segment, the rest by why.

    **By the sentence, not the reason.** A reason is a word each reader uses in its own
    language's sense -- C's `untyped` is not Rust's -- so the rows are grouped by what each
    one means in its language (`detectors.frontier_words`) and the key is that sentence.
    Two languages that mean one thing by it share a row; two that do not, do not.
    """
    outside: dict[str, int] = {}
    unresolved: dict[str, int] = {}
    unsaid = 0
    for r in rows:
        if r["reason"] == "outside":
            head = str(r["frontier"]).split("::", 1)[0] or "?"
            outside[head] = outside.get(head, 0) + int(r["n"])
        elif r["reason"]:
            said = frontier_words(str(r["lang"] or ""), str(r["reason"]))
            unresolved[said] = unresolved.get(said, 0) + int(r["n"])
        else:
            unsaid += int(r["n"])
    by_count = lambda d: sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))  # noqa: E731
    return {"outside": by_count(outside), "unresolved": by_count(unresolved),
            "unsaid": unsaid}


class Store:
    """A connection to one analysed program's graph."""

    #: What this store *is*, when it refuses to open something that is not there.
    #: `SourceStore.WHAT` is the same idea, arrived at first and for rule 16's sake.
    WHAT = "a code graph"

    def __init__(self, path: Path | str, *, writable: bool = True,
                 shared: bool = False) -> None:
        """Open one program's graph.

        `writable=False` is how every orientation command opens it, and the
        distinction is load-bearing rather than tidy. Discarding a stale graph is safe
        for `analyze`, which re-extracts in the same breath; for `touches`, `impact` or
        `query` it empties the map and then answers out of the hole, and `(no rows)` is
        indistinguishable from a true empty result. So a reader refuses a stale graph
        and says how to rebuild it, and only `analyze` is allowed to drop anything.

        A reader also refuses a path that is not there at all, and `refuse_missing` says
        why that is a different failure from a stale one and a worse one.

        **And `writable=False` opens a connection that cannot write**, which it did not
        until 2026-09-17. It was assigned to `self.writable` and never read again: it
        chose mkdir-versus-refuse and refuse-versus-discard, and the connection underneath
        was an ordinary read-write handle on all fourteen reading sites. So
        `dunneflow query --sql "DELETE FROM routines"` emptied a table through a store
        whose whole name for itself was *not writable*. Tolerable while a person was the
        one typing it; not once a language model composes the statement, which is what
        `dunneflow mcp` now lets one do.

        `?mode=ro` rather than a second parameter beside this one. `Store(readonly=True)`
        was the shape first proposed, and two parameters answering *"can this connection
        write"* is rule 30: the lie would have stayed in place at thirteen sites in order
        to close it at one. Measured against the golden graph before it was chosen -- WAL,
        with the sidecar files present, with them removed, and with the containing
        directory made read-only -- all 4,823 routines read in every case.

        The residue, because it is not nothing: SQLite refuses the *writes*, not every
        statement. `PRAGMA writable_schema=ON` is accepted here and does nothing, and
        `ATTACH` is accepted and reaches a database that is not this one -- which is why
        `mcp/tools.py` classifies a statement as well, rather than trusting this alone.
        """
        self.path = Path(path)
        self.writable = writable
        if writable:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        else:
            refuse_missing(self.path, self.WHAT)
        # `shared` hands the connection to more than one thread, and the caller then
        # owes it a lock. Only the server asks for it: `ThreadingHTTPServer` answers each
        # request on its own thread, and sqlite refuses a connection used off the thread
        # that made it -- serialising the calls is not enough on its own, which is worth
        # saying because a lock looks like it should be.
        #
        # `uri=True` is only ever passed on the read path, and that is deliberate rather
        # than incidental: a writer is handed a plain `Path`, and `changes.py:857` records
        # the trap from the other side -- a URI handed to something that opens it without
        # `uri=True` names a file called `file:...?mode=ro`.
        self.conn = (
            sqlite3.connect(read_only_uri(self.path), uri=True, check_same_thread=not shared)
            if not writable else
            sqlite3.connect(self.path, check_same_thread=not shared)
        )
        self.conn.row_factory = sqlite3.Row
        # How many times a burst stopped to let the log drain, and how many files since the
        # log was last measured. `settled` is reported rather than kept private: a run that
        # had to settle nine times is a run whose tree is near the guard's bound, and that is
        # worth a reader knowing.
        self.settled = 0
        self._since_check = 0
        self._refuse_wrong_kind()
        if not writable:
            self.rebuilt = False
            self.reread = {}
            self._refuse_if_stale()
            self._refuse_if_a_language_is_stale()
            return
        self.rebuilt = self._discard_if_stale()
        self.conn.executescript(SCHEMA_SQL)
        # **The other half of the split, and it happens after the schema exists** -- a
        # brand-new database has no `files` table until the line above has run. Whole
        # languages only; the reader that changed loses its rows and nothing else does.
        self.reread = self._discard_stale_languages()
        self.set_meta("kind", "graph")
        self.set_meta("schema_version", str(SCHEMA_VERSION))
        self.set_meta("extractor", f"{SCHEMA_VERSION}:{core_fingerprint()}")
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
        want = f"{SCHEMA_VERSION}:{core_fingerprint()}"
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

        **Which is asked of `migration_speaks_for`, not of the paths.** This branched on
        absolute paths alone until 2026-09-08, so *"written before paths went relative"*
        and *"a version this migration can speak for"* were one test standing for two
        facts -- and every older store was handed a command that refuses it. See that
        function; the same sentence is built one file over in `docstore.py`, on the
        document store's own fingerprint (rule 51).
        """
        if not self._is_stale():
            return
        if migration_speaks_for(self.conn, PREVIOUS_CODE_EXTRACTOR):
            raise StaleGraphError(
                f"{self.path} stores absolute paths, from before DunneFlow made them "
                f"relative to the tree they were read from -- run "
                f"`dunneflow migrate {self.path.parent}` to rewrite it in place"
            )
        raise StaleGraphError(
            f"{self.path} was written by a different version of DunneFlow and "
            f"cannot be read safely -- re-run `dunneflow analyze` to rebuild it"
        )

    def _refuse_if_a_language_is_stale(self) -> None:
        """A reader never serves facts a different reader produced -- per language.

        The same rule as `_refuse_if_stale`, one axis in, and the sentence says what the
        cheaper remedy costs: analysing again re-reads **that language** and leaves every
        other language's rows where they are. Naming the language matters, because *this
        map is stale* over a Python map whose forty TypeScript files are the problem sends
        somebody looking in the wrong place (rule 89).
        """
        stale = self.stale_languages()
        if not stale:
            return
        named = "; ".join(f"{lang} (read by {was})" for lang, was in sorted(stale.items()))
        raise StaleGraphError(
            f"{self.path} holds facts from a reader this build is not: {named}. Re-run "
            f"`dunneflow analyze` -- it re-reads only the language that changed, and "
            f"leaves the rest of the map alone."
        )

    def language_stamps(self) -> dict[str, set[str]]:
        """Which reader stamps this map holds, per language.

        **Three states, never two** (rule 63, and `finished()`'s shape one store over): a
        map written before this column existed has no column at all and says nothing --
        `dunneflow migrate` re-stamps a store that predates it -- which is a different
        fact from a map whose rows name a reader this build does not match. Reading a
        column that is not there is an exception rather than an empty answer, so the
        question is asked of the table first.
        """
        have = {str(r[1]) for r in self.conn.execute("PRAGMA table_info(files)")}
        if "extractor" not in have:
            return {}
        out: dict[str, set[str]] = {}
        for row in self.conn.execute(
                "SELECT DISTINCT lang, extractor FROM files WHERE lang <> ''"):
            out.setdefault(str(row[0]), set()).add(str(row[1]))
        return out

    def stale_languages(self) -> dict[str, str]:
        """Languages whose rows were read by a reader this build is not, and by which.

        A language this build has **no reader for** is deliberately absent: its rows
        cannot be re-read and cannot be checked, and refusing a map over a plugin somebody
        uninstalled would refuse the map for ever. The walk already says that language was
        not read this time, which is the fact a reader can act on (rule 89).
        """
        from .ingest import PLUGINS

        out: dict[str, str] = {}
        for lang, stamps in self.language_stamps().items():
            if lang not in PLUGINS:
                continue
            want = lang_fingerprint(lang)
            others = sorted(x for x in stamps if x != want)
            if others:
                out[lang] = ", ".join(x or "(unrecorded)" for x in others)
        return out

    def _discard_stale_languages(self) -> dict[str, int]:
        """Forget the files one reader produced, when that reader has changed.

        The point of splitting rule 12's key. Core mismatch is still everything dropped;
        a reader that changed costs **its own** files a re-extraction and costs every
        other language nothing -- which is what makes a TypeScript plugin editable in a
        repository that is mostly Python.

        No new destruction mechanism: `forget_file` is the one `write_file_facts` already
        calls per file, so a language's rows leave by the same door every re-read uses,
        and `source.db` is never touched (rule 25).
        """
        stale = self.stale_languages()
        out: dict[str, int] = {}
        for lang in sorted(stale):
            paths = [str(r[0]) for r in self.conn.execute(
                "SELECT path FROM files WHERE lang = ?", (lang,))]
            for path in paths:
                self.forget_file(path)
            self.conn.commit()
            out[lang] = len(paths)
        return out

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

    def settle_if_large(self) -> bool:
        """Commit mid-burst when the write-ahead log has outgrown the page cache.

        **A burst must be one transaction and a burst must also end**, and until this existed
        only the first half was true. `batch()` is right that per-file commits dominate a run
        of ordinary size; what it could not say is that the transaction it opens keeps SQLite
        from checkpointing the log, so a long enough burst builds a log nothing can drain and
        then pays to read its own writes back out of it. `WAL_CAP_BYTES` carries the
        measurement.

        Committing here is safe because of where the loop already stands, and each of the
        three is a real constraint rather than a hope:

        * **`prune_missing` has already run**, so no commit can publish a half-pruned map;
        * **`supplied_edges` is written after the loop** and is replaced whole per language,
          so it never straddles one of these;
        * **rule 80 is unaffected** -- `complete` is written last and committed on its own, so
          a map that stops between two of these still says it is not finished.

        What it buys beyond the crawl is that a killed run **keeps what it committed**, and
        `known_hashes` makes the next run skip those files rather than start again. Before
        this, a run stopped anywhere in a language lost that whole language.

        Returns whether it committed, so a caller can count them -- which is how this is
        tested, rather than by timing anything.
        """
        self._since_check += 1
        if self._since_check < WAL_CHECK_EVERY:
            return False
        self._since_check = 0
        # The WAL sits beside the database and is absent until the first write, so a missing
        # one is "nothing to drain" rather than anything to report.
        try:
            size = self.path.with_name(self.path.name + "-wal").stat().st_size
        except OSError:
            return False
        if size < WAL_CAP_BYTES:
            return False
        self.conn.commit()
        self.settled += 1
        return True

    # -- meta ------------------------------------------------------------- #

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def set_meta_now(self, key: str, value: str) -> None:
        """`set_meta`, committed -- for the facts that have to survive a `kill -9`.

        Ordinary meta rides out on whatever commit comes next, which is right for
        everything that only matters if the run finishes. The completion marker is the
        opposite: it exists **for** the run that does not finish, and an uncommitted one is
        lost exactly when it was the only thing that could have spoken.

        Its own method rather than a flag on `set_meta`, because the choice is about the
        fact rather than about the caller (rule 51) -- and a `commit=True` default nobody
        passes is how a durability decision goes quiet.

        Rule 80's second half: a marker that is not durable at the moment of the
        interruption is not a marker.
        """
        self.set_meta(key, value)
        self.conn.commit()

    def refuse_if_unfinished(self, name: str) -> None:
        """Raise unless this map's own analysis said it had finished.

        `None` passes: a map written before the key existed is not broken, and refusing one
        would refuse every map made before today. Only a recorded-and-not-`yes` marker is a
        run that started and stopped -- the same missing-versus-blank distinction
        `/api/about` keeps, one store over.

        A **read**-path rule, like `StaleGraphError`, and rule 80's third half. `analyze`
        never calls it: opening an unfinished map is exactly how it finishes one, and a
        refusal that locked out the only thing that can repair would be rule 20 turned
        against itself.
        """
        state = self.finished()
        if state is None or state == "yes":
            return
        raise UnfinishedMapError(unfinished_sentence(name, self.get_meta("step") or ""))

    def finished(self) -> str | None:
        """Did the analysis that wrote this map finish? `None` if the map cannot say.

        The three states are the caller's to tell apart, so this returns the raw value:
        `None` (predates the key), `""` (started, never finished), `"yes"`. Flattening
        them here would put the missing-versus-blank decision in the wrong place -- the
        same distinction `/api/about` keeps for `inference` and `model`.
        """
        return self.get_meta("complete")

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
        # Arguments hang off a call site, not off a file, so they have to go before the
        # call sites do -- once `calls` is emptied of this file there is nothing left to
        # name them by and they would sit in the store for ever, attached to a site that
        # no longer exists.
        c.execute(
            "DELETE FROM call_args WHERE site_id IN (SELECT site_id FROM calls WHERE file = ?)",
            (path,),
        )
        # An arm hangs off a control point, not off a file -- so it goes before `control`
        # does, for the reason `call_args` goes before `calls`: once the points of this
        # file are gone there is nothing left to name its arms by.
        c.execute(
            "DELETE FROM control_arms WHERE point_id IN"
            " (SELECT point_id FROM control WHERE file = ?)",
            (path,),
        )
        for table in ("routines", "structures", "calls", "boundaries", "imports",
                      "entrypoints", "cli_apps", "cli_mounts", "sql_ops", "db_tables",
                      "db_columns", "db_indexes", "net_calls", "classes",
                      "artefacts", "constants", "control", "ipc_registrations",
                      "macro_sites", "macro_callees"):
            c.execute(f"DELETE FROM {table} WHERE file = ?", (path,))
        c.execute("DELETE FROM files WHERE path = ?", (path,))
        # **`supplied_edges` is deliberately not here**, and it is the one table a file's
        # facts do not own. Its rows are keyed by language rather than by file because a
        # checker answers about a compilation: an edge out of this file was computed from
        # every other file, and a row naming *this* file as a target belongs to a caller
        # somewhere else. Deleting either half per file leaves the other half stale, with
        # nothing to say so. The set is replaced whole by `replace_supplied_edges`
        # whenever its reader is opened, which is every run where any file of that
        # language changed.

    def prune_missing(self, live_paths: Iterable[str]) -> int:
        """Forget files that have disappeared from the source tree."""
        live = set(live_paths)
        gone = [p for p in self.known_hashes() if p not in live]
        for p in gone:
            self.forget_file(p)
        return len(gone)

    def replace_supplied_edges(self, lang: str, edges: Iterable[SuppliedEdge]) -> int:
        """Everything this language's reader says about where its calls go. Whole, never partial.

        One `DELETE` and one `executemany`, because the answer is a whole-program answer
        and a half-replaced set is exactly the staleness this table exists to avoid --
        see `SuppliedEdge` and the note in `forget_file`. Per language, so a TypeScript
        session cannot disturb what another reader supplied.

        A reader that supplies **nothing** still clears its own rows, and that is the
        point rather than an edge case: a plugin whose checker stopped resolving would
        otherwise keep answering out of the last run that worked.
        """
        c = self.conn
        c.execute("DELETE FROM supplied_edges WHERE lang = ?", (lang,))
        rows = [(lang, e.site_id, e.caller_id, e.file, e.line, e.name, e.how, e.candidates,
                 e.constructs, e.frontier, e.reason,
                 json.dumps([[a.file, a.line, a.name] for a in e.answers]))
                for e in edges]
        c.executemany(
            "INSERT INTO supplied_edges(lang,site_id,caller_id,file,line,name,how,candidates,"
            "constructs,frontier,reason,answers) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        return len(rows)

    def replace_macro_callees(self, lang: str, rows: Iterable[SuppliedMacroCallee]) -> None:
        """Where this language's macros go, and the boundaries that makes. Whole, as above.

        The boundaries live with the rest so that nothing reading them has to know where they
        came from, and `expanded` is what lets this take back its own and only its own.
        """
        c = self.conn
        c.execute("DELETE FROM macro_callees WHERE lang = ?", (lang,))
        c.execute(
            "DELETE FROM boundaries WHERE expanded = 1"
            " AND file IN (SELECT path FROM files WHERE lang = ?)", (lang,))
        listed = list(rows)
        c.executemany(
            "INSERT INTO macro_callees(lang,file,line,def_id,routine_id,callee,target_file,"
            "target_line,target_name,candidates,indirect,count) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            [(lang, m.file, m.line, m.def_id, m.routine_id, m.callee, m.target_file,
              m.target_line, m.target_name, m.candidates, int(m.indirect), m.count)
             for m in listed],
        )
        c.executemany(
            "INSERT INTO boundaries(file,routine_id,kind,direction,target,line,evidence,salience,"
            "through_macro,expanded) VALUES(?,?,?,?,?,?,?,?,?,1)",
            [(m.file, m.routine_id, b.kind.value, b.direction.value, b.target, b.line,
              b.evidence, b.salience, m.def_id) for m in listed for b in m.hits],
        )

    def replace_supplied_bindings(self, lang: str,
                                  bindings: Iterable[SuppliedBinding]) -> int:
        """Every way in this language's reader bound, or said why it could not. Whole.

        Replaced whole for `replace_supplied_edges`' reason, and a reader that sends none
        still clears its own: a binding kept from the last run would be a way in bound to a
        body the reader no longer says it has.
        """
        c = self.conn
        c.execute("DELETE FROM supplied_bindings WHERE lang = ?", (lang,))
        rows = [(lang, b.entrypoint_id, b.file, b.line, b.name, b.why,
                 json.dumps([[a.file, a.line, a.name] for a in b.answers])) for b in bindings]
        c.executemany(
            "INSERT INTO supplied_bindings(lang,entrypoint_id,file,line,name,why,answers)"
            " VALUES(?,?,?,?,?,?,?)", rows)
        return len(rows)

    def replace_value_uses(self, lang: str, uses: Iterable[SuppliedUse]) -> int:
        """Every routine this language's reader saw named as a value. Whole, like the edges."""
        c = self.conn
        c.execute("DELETE FROM value_uses WHERE lang = ?", (lang,))
        rows = sorted({(lang, u.file, u.line, u.name) for u in uses})
        c.executemany("INSERT INTO value_uses(lang,file,line,name) VALUES(?,?,?,?)", rows)
        return len(rows)

    # -- writes ------------------------------------------------------------ #

    def write_file_facts(self, ff: FileFacts) -> None:
        """Replace all facts for one file. Callers should wrap bursts in `batch()`."""
        c = self.conn
        self.forget_file(ff.path)
        c.execute(
            "INSERT INTO files(path, lang, module, content_hash, doc, errors, extractor,"
            " read_through, macro_directive_uses, skipped_lines, first_missing)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (ff.path, ff.lang, ff.module, ff.content_hash, ff.doc, json.dumps(ff.errors),
             lang_fingerprint(ff.lang), ff.read_through, ff.macro_directive_uses,
             ff.skipped_lines, ff.first_missing),
        )
        for r in ff.routines:
            c.execute(
                "INSERT INTO routines(id,name,qualname,module,file,line_start,line_end,lang,"
                "returns,docstring,decorators,is_async,is_method,class_name,is_nested,"
                "visibility,body_hash,name_by,body_by,opaque_asm)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    r.id, r.name, r.qualname, r.module, r.file, r.line_start, r.line_end,
                    r.lang, r.returns, r.docstring, json.dumps(r.decorators),
                    int(r.is_async), int(r.is_method), r.class_name, int(r.is_nested),
                    r.visibility, r.body_hash, r.name_by, r.body_by, r.opaque_asm,
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
                "INSERT INTO structures(id,name,kind,module,file,line,lang,docstring,bases,"
                "name_by) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (s.id, s.name, s.kind.value, s.module, s.file, s.line, s.lang, s.docstring,
                 json.dumps(s.bases), s.name_by),
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
            "(file,caller_id,callee_expr,line,callee_id,confidence,external,at_boundary,"
            "site_id,construction,bound_locally) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            [(ff.path, k.caller_id, k.callee_expr, k.line, k.callee_id, k.confidence.value,
              int(k.external), int(k.at_boundary), k.site_id, int(k.is_construction),
              int(k.bound_locally))
             for k in ff.calls],
        )
        c.executemany(
            "INSERT INTO call_args(site_id,idx,expr,keyword,splat) VALUES(?,?,?,?,?)",
            [(k.site_id, a.idx, a.expr, a.keyword, int(a.splat))
             for k in ff.calls for a in k.args],
        )
        c.executemany(
            "INSERT INTO boundaries(file,routine_id,kind,direction,target,line,evidence,salience,"
            "through_macro) VALUES(?,?,?,?,?,?,?,?,?)",
            [(ff.path, b.routine_id, b.kind.value, b.direction.value, b.target, b.line,
              b.evidence, b.salience, b.through_macro) for b in ff.boundaries],
        )
        c.executemany(
            "INSERT INTO control"
            "(point_id,file,routine_id,kind,line_start,line_end,depth,header,arms,exits,"
            " word,once_start,once_end)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(p.point_id, ff.path, p.routine_id, p.kind.value, p.line_start, p.line_end,
              p.depth, p.header, p.arms, p.exits, p.word, p.once_start, p.once_end)
             for p in ff.control],
        )
        c.executemany(
            "INSERT OR IGNORE INTO macro_defs(id,name,file,line,origin) VALUES(?,?,?,?,?)",
            [(d.id, d.name, d.file, d.line, d.origin.value) for d in ff.macro_defs],
        )
        c.executemany(
            "INSERT INTO macro_sites(file,line,def_id,name,position,routine_id,shadows)"
            " VALUES(?,?,?,?,?,?,?)",
            [(ff.path, m.line, m.def_id, m.name, m.position.value, m.routine_id, m.shadows)
             for m in ff.macro_sites],
        )
        c.executemany(
            "INSERT INTO control_arms"
            "(point_id,routine_id,idx,kind,line_start,line_end,header)"
            " VALUES(?,?,?,?,?,?,?)",
            [(a.point_id, a.routine_id, a.idx, a.kind.value, a.line_start, a.line_end,
              a.header) for a in ff.control_arms],
        )
        c.executemany(
            "INSERT INTO imports(file,module,name,alias,is_from,line) VALUES(?,?,?,?,?,?)",
            [(ff.path, i.module, i.name, i.alias, int(i.is_from), i.line) for i in ff.imports],
        )
        c.executemany(
            "INSERT OR REPLACE INTO entrypoints"
            "(id,kind,name,routine_id,module,file,evidence,grp,parent_id,target_expr,"
            "declared,target_kind)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            [(e.id, e.kind.value, e.name, e.routine_id, e.module, ff.path, e.evidence,
              e.group, e.parent_id, e.target_expr, int(e.declared), e.target_kind.value)
             for e in ff.entrypoints],
        )
        c.executemany(
            "INSERT INTO ipc_registrations(file,name,line) VALUES(?,?,?)",
            [(ff.path, g.name, g.line) for g in ff.ipc_registrations],
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
            "(id,kind,name,routine_id,module,file,evidence,grp,parent_id,target_expr,"
            "declared,target_kind)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (e.id, e.kind.value, e.name, e.routine_id, e.module, file, e.evidence,
             e.group, e.parent_id, e.target_expr, int(e.declared), e.target_kind.value),
        )

    def replace_manifests(self, rows: Sequence[tuple[str, str, str, str, int, int, str]]
                          ) -> None:
        """What this analysis read out of the tree's manifests, rewritten whole.

        **Replaced rather than merged**, unlike a file's facts. A manifest is not
        content-addressed and is not cached: every analysis reads every one it walks
        past, so the rows this run computed *are* the answer, and a manifest deleted
        between two runs must leave with them. The same argument `replace_supplied_edges`
        is written under one table over.
        """
        with self.batch():
            self.conn.execute("DELETE FROM manifests")
            self.conn.executemany(
                "INSERT OR REPLACE INTO manifests"
                "(path,provider,name,version,ways_in,at_root,note)"
                " VALUES(?,?,?,?,?,?,?)",
                rows,
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

    def sweep_macro_defs(self) -> None:
        """Remove the definitions no use reaches. Once per analysis: asked per file, over
        18,000 files, this one query would be most of a run (rule 55)."""
        self.conn.execute(
            "DELETE FROM macro_defs WHERE id NOT IN (SELECT def_id FROM macro_sites)"
        )

    def counts(self) -> dict[str, int]:
        if not self.writable and self.get_meta("complete") == "yes":
            # Recorded by the analysis that finished this map, which nothing has written to
            # since -- a read-only handle cannot. Counted afresh only where it is absent: a
            # map from before 2026-10-02, or one whose analysis did not finish (BACKLOG 8).
            stored = self.get_meta("counts")
            if stored:
                return {str(k): int(v) for k, v in json.loads(stored).items()}
        out: dict[str, int] = {}
        for t in ("files", "routines", "calls", "boundaries", "structures", "entrypoints",
                  "annotations", "cli_apps", "cli_mounts", "sql_ops", "db_tables",
                  "db_indexes", "net_calls", "control", "control_arms",
                  "macro_defs", "macro_sites", "macro_callees"):
            out[t] = self.conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
        # Beside `routines` and never subtracted from it: how many the program has and how many
        # of those nobody typed are two numbers (rule 32).
        out["routines_by_macro"] = self.conn.execute(
            "SELECT COUNT(*) AS n FROM routines WHERE body_by <> ''"
        ).fetchone()["n"]
        out["resolved_calls"] = self.conn.execute(
            "SELECT COUNT(*) AS n FROM calls WHERE callee_id IS NOT NULL"
        ).fetchone()["n"]
        # Beside `resolved_calls` and never folded into it: *how many edges this map has*
        # and *how many of them a toolchain handed over* are two numbers, and one of them
        # is the whole difference between a name argument and a checker (rule 32).
        out["supplied_edges"] = self.conn.execute(
            "SELECT COUNT(*) AS n FROM supplied_edges"
        ).fetchone()["n"]
        return out

    def routine(self, rid: str) -> Routine | None:
        row = self.conn.execute("SELECT * FROM routines WHERE id = ?", (rid,)).fetchone()
        return self._routine_from_row(row) if row else None

    def routines(self, module: str | None = None) -> list[Routine]:
        """Every routine, or one module's, with its parameters, comments and annotations.

        **Three child queries per routine** was 223,605 routines times three on Unreal's
        Runtime. Each child table is read once here instead, restricted by the same
        `module` test through a subquery (so no id list, and no parameter limit), ordered
        by owner and then by the keys the per-routine queries used, so every routine's
        lists come back in the order they always did.
        """
        where, args = ("WHERE module = ?", (module,)) if module else ("", ())
        order = ("ORDER BY line_start, file, qualname" if module
                 else "ORDER BY module, line_start, file, qualname")
        rows = self.conn.execute(f"SELECT * FROM routines {where} {order}", args).fetchall()
        owned = f"IN (SELECT id FROM routines {where})"
        params: dict[str, list[Param]] = {}
        for p in self.conn.execute(
                f"SELECT * FROM params WHERE routine_id {owned} ORDER BY routine_id, idx", args):
            params.setdefault(p["routine_id"], []).append(
                Param(p["name"], p["type"], p["dflt"], p["kind"]))
        comments: dict[str, list[Comment]] = {}
        for c in self.conn.execute(
                f"SELECT * FROM comments WHERE routine_id {owned}"
                " ORDER BY routine_id, line, text", args):
            comments.setdefault(c["routine_id"], []).append(
                Comment(c["text"], c["line"], bool(c["leading"])))
        annots: dict[str, list[Annotation]] = {}
        for a in self.conn.execute(
                f"SELECT * FROM annotations WHERE owner_id {owned}"
                " ORDER BY owner_id, line, kind, value, text", args):
            annots.setdefault(a["owner_id"], []).append(
                Annotation(a["kind"], a["value"], a["line"], a["text"]))
        return [self._routine_from_row(r, params.get(r["id"], []), comments.get(r["id"], []),
                                       annots.get(r["id"], [])) for r in rows]

    def _routine_from_row(self, row: sqlite3.Row, params: list[Param] | None = None,
                          comments: list[Comment] | None = None,
                          annots: list[Annotation] | None = None) -> Routine:
        """One routine from its row. Its children are read here unless the caller has
        already read them for many routines at once (`routines`)."""
        rid = row["id"]
        if params is None:
            params = [
                Param(p["name"], p["type"], p["dflt"], p["kind"])
                for p in self.conn.execute(
                    "SELECT * FROM params WHERE routine_id = ? ORDER BY idx", (rid,)
                )
            ]
        if comments is None:
            comments = [
                Comment(c["text"], c["line"], bool(c["leading"]))
                for c in self.conn.execute(
                    "SELECT * FROM comments WHERE routine_id = ? ORDER BY line, text", (rid,)
                )
            ]
        if annots is None:
            annots = [
                Annotation(a["kind"], a["value"], a["line"], a["text"])
                for a in self.conn.execute(
                    "SELECT * FROM annotations WHERE owner_id = ? ORDER BY line, kind, value, text",
                    (rid,)
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
            body_hash=row["body_hash"], name_by=row["name_by"], body_by=row["body_by"],
            opaque_asm=row["opaque_asm"],
        )

    def entrypoints(self) -> list[Entrypoint]:
        return [
            Entrypoint(
                id=r["id"], kind=EntrypointKind(r["kind"]), name=r["name"],
                routine_id=r["routine_id"], module=r["module"], evidence=r["evidence"],
                group=r["grp"], parent_id=r["parent_id"], target_expr=r["target_expr"],
                declared=bool(r["declared"]),
                target_kind=TargetKind(r["target_kind"]),
            )
            for r in self.conn.execute(
                # Two ways in can share a kind and a name and be different front doors --
                # `main` is the commonest name in any tree. Rule 66: the tail is what
                # makes this an order rather than a grouping.
                "SELECT * FROM entrypoints ORDER BY kind, name, module, id")
        ]

    def structures(self) -> list[DataStructure]:
        out = []
        for r in self.conn.execute(
                "SELECT * FROM structures ORDER BY module, line, file, name"):
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

    # -- orientation queries ----------------------------------------------- #
    #
    # Recursive SQL over indexed edges. These are the three questions the tool
    # exists to answer, and they must stay fast no matter how large the target is.
    #
    # **Two arms, and the second is the crossing between languages.** A command sent by
    # name (`ipc_links`, status `linked`) is reached from the routine that sends it, so
    # `touches` on a store method goes on into the Rust command and what *it* touches.
    # A second recursive arm rather than a `UNION` subquery over both tables, because a
    # subquery in the join takes `calls`' indexes away on exactly the large maps this
    # comment is about. Never an edge in `calls` (rule 2): only the walk crosses it.
    #
    # **And a third, the dispatch arm** (Tom, 2026-11-02). A call the reader marked
    # `dynamic` reaches every body that may answer it (`dispatch_links`), so a template
    # method's abstract step and an interface's implementations are inside the reach of
    # whatever calls them. Crossed by every walk, `cross=False` included: dispatch never
    # leaves the process. Never an edge either, and every surface that names one says *by
    # dispatch*: any of the bodies may run.

    def _reach_graph(self, cross: bool = True) -> dict[str, list[str]] | None:
        """Every call edge, caller to callees, read once -- on a store that cannot change.

        **BACKLOG 8's second step, and the larger one.** With the model fixed, opening Unreal's
        Runtime part spent 938.5 s of 1,185.7 on the cover, and all of it was reach: the
        recursive query below seeks `calls` through `ix_calls_caller` for a column the index
        does not hold, once per row per level, and revisits a routine at every depth it can
        be reached at -- on 947,786 calls, once per way in. Read in table order and walked in
        memory the same set costs one scan.

        **On a writable store too, keyed by what this connection has written.** A writable
        store is the one `resolve_calls` is still filling, and a cache taken before it
        finished would answer the previous graph, so until 2026-11-02 a writable store kept
        the recursive query. The dispatch arm made that a sixteenfold cost: the query
        deduplicates on `(id, depth)`, so a routine reachable at many depths is visited at
        each, and dispatch multiplies the paths -- traccar's `ways_in` went from 0.3 s to
        4.8 s inside every analysis. `total_changes` counts every row this connection has
        inserted, updated or deleted, and only this connection writes a writable store, so
        a cache stamped with it is the current graph exactly when the stamp still matches
        (rule 81: the key carries everything the work depends on).
        """
        stamp = self.conn.total_changes if self.writable else -1
        if getattr(self, "_reach_stamp", None) != stamp:
            for cached in ("_reach_cache", "_reach_cache_own", "_routine_id_cache",
                           "_boundary_cache"):
                if hasattr(self, cached):
                    delattr(self, cached)
            self._reach_stamp = stamp
        if not cross:
            # The walk that stops at a process boundary: the call edges alone.
            own = getattr(self, "_reach_cache_own", None)
            if own is None:
                own = {}
                for caller, callee in self.conn.execute(
                    "SELECT caller_id, callee_id FROM calls NOT INDEXED"
                    " WHERE callee_id IS NOT NULL"
                ):
                    own.setdefault(caller, []).append(callee)
                self._dispatch_into(own)
                self._reach_cache_own = own
            return own
        graph = getattr(self, "_reach_cache", None)
        if graph is None:
            graph = {}
            for caller, callee in self.conn.execute(
                "SELECT caller_id, callee_id FROM calls NOT INDEXED"
                " WHERE callee_id IS NOT NULL"
            ):
                graph.setdefault(caller, []).append(callee)
            # A command linked by name is reached through the site that sends it, as the
            # recursive queries' second arm reaches it (`resolve/ipc.py`).
            for caller, callee in self.conn.execute(
                "SELECT caller_id, routine_id FROM ipc_links"
                " WHERE status = 'linked' ORDER BY rowid"
            ):
                graph.setdefault(caller, []).append(callee)
            self._dispatch_into(graph)
            self._reach_cache = graph
        return graph

    def _dispatch_into(self, graph: dict[str, list[str]]) -> None:
        """The dispatch arm, in memory: a call reaches every body that may answer it
        (`resolve/dispatch.py`). In both graphs, because dispatch never leaves the process
        the call is made in, and `cross=False` is about a process boundary only."""
        for caller, callee in self.conn.execute(
            "SELECT caller_id, routine_id FROM dispatch_links ORDER BY rowid"
        ):
            graph.setdefault(caller, []).append(callee)

    def _routine_ids(self) -> set[str]:
        """Every routine id, read once on a store that cannot change -- the reach walk's
        seed check, which was an index search per call and 29 s of the cover on a large
        map. Only ever asked after `_reach_graph`, which drops it when the store has
        written anything since it was taken."""
        ids = getattr(self, "_routine_id_cache", None)
        if ids is None:
            ids = {r[0] for r in self.conn.execute("SELECT id FROM routines NOT INDEXED")}
            self._routine_id_cache = ids
        return ids

    @staticmethod
    def _walk(graph: dict[str, list[str]], seeds: Iterable[str], max_depth: int) -> set[str]:
        """Breadth-first to `max_depth`. The set any path of that length reaches is the set
        the shortest path reaches, so this answers what the recursive query answers."""
        seen = set(seeds)
        level = list(seen)
        for _ in range(max_depth):
            nxt = []
            for rid in level:
                for callee in graph.get(rid, ()):
                    if callee not in seen:
                        seen.add(callee)
                        nxt.append(callee)
            if not nxt:
                break
            level = nxt
        return seen

    def reachable_from(self, routine_id: str, max_depth: int = 40) -> list[str]:
        """Everything this routine can reach. "What does this touch?" """
        graph = self._reach_graph()
        if graph is not None:
            return sorted(self._walk(graph, [routine_id], max_depth))
        rows = self.conn.execute(
            """
            WITH RECURSIVE reach(id, depth) AS (
                SELECT ?, 0
                UNION
                SELECT c.callee_id, r.depth + 1
                  FROM calls c JOIN reach r ON c.caller_id = r.id
                 WHERE c.callee_id IS NOT NULL AND r.depth < ?
                UNION
                SELECT l.routine_id, r.depth + 1
                  FROM ipc_links l JOIN reach r ON l.caller_id = r.id
                 WHERE l.status = 'linked' AND r.depth < ?
                UNION
                SELECT d.routine_id, r.depth + 1
                  FROM dispatch_links d JOIN reach r ON d.caller_id = r.id
                 WHERE r.depth < ?
            )
            SELECT DISTINCT id FROM reach WHERE id IS NOT NULL
            """,
            (routine_id, max_depth, max_depth, max_depth),
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
                UNION
                SELECT l.caller_id, b.depth + 1
                  FROM ipc_links l JOIN back b ON l.routine_id = b.id
                 WHERE l.status = 'linked' AND b.depth < ?
                UNION
                SELECT d.caller_id, b.depth + 1
                  FROM dispatch_links d JOIN back b ON d.routine_id = b.id
                 WHERE b.depth < ?
            )
            SELECT DISTINCT id FROM back WHERE id IS NOT NULL AND id != ?
            """,
            (routine_id, max_depth, max_depth, max_depth, routine_id),
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
                UNION
                SELECT l.routine_id, r.depth + 1
                  FROM ipc_links l JOIN reach r ON l.caller_id = r.id
                 WHERE l.status = 'linked' AND r.depth < ?
                UNION
                SELECT d.routine_id, r.depth + 1
                  FROM dispatch_links d JOIN reach r ON d.caller_id = r.id
                 WHERE r.depth < ?
            )
            SELECT DISTINCT b.* FROM boundaries b JOIN reach r ON b.routine_id = r.id
            ORDER BY b.kind, b.target, b.direction, b.line, b.evidence
            """,
            (routine_id, max_depth, max_depth, max_depth),
        )
        return [
            BoundaryHit(
                routine_id=r["routine_id"], kind=BoundaryKind(r["kind"]),
                direction=Direction(r["direction"]), target=r["target"], line=r["line"],
                evidence=r["evidence"], salience=r["salience"],
            )
            for r in rows
        ]

    def frontier_reached(self, routine_id: str, max_depth: int = 40) -> dict[str, Any]:
        """Where this routine's reach stops, and why: every call with no edge in it or in
        anything it reaches, grouped (schema 17, `calls.frontier`/`calls.reason`).

        `outside` is by the far end's first segment — its crate, as the reader spells it —
        so a reader can see *std 120, rusqlite 40* rather than a count; `unresolved` is by
        reason. A call whose reader said nothing (`reason = ''`) is counted as `unsaid` and
        never folded into either, because *nobody said* is not *nothing to say* (rule 32).
        A boundary is not here: it is its own frontier fact, in `boundaries_reached`.
        """
        rows = self.conn.execute(
            """
            WITH RECURSIVE reach(id, depth) AS (
                SELECT ?, 0
                UNION
                SELECT c.callee_id, r.depth + 1
                  FROM calls c JOIN reach r ON c.caller_id = r.id
                 WHERE c.callee_id IS NOT NULL AND r.depth < ?
                UNION
                SELECT l.routine_id, r.depth + 1
                  FROM ipc_links l JOIN reach r ON l.caller_id = r.id
                 WHERE l.status = 'linked' AND r.depth < ?
                UNION
                SELECT d.routine_id, r.depth + 1
                  FROM dispatch_links d JOIN reach r ON d.caller_id = r.id
                 WHERE r.depth < ?
            )
            SELECT f.lang, c.reason, c.frontier, COUNT(*) AS n
              FROM calls c JOIN (SELECT DISTINCT id FROM reach) r ON c.caller_id = r.id
              LEFT JOIN files f ON f.path = c.file
             WHERE c.callee_id IS NULL AND c.at_boundary = 0 AND c.constructs = ''
             GROUP BY f.lang, c.reason, c.frontier
            """,
            (routine_id, max_depth, max_depth, max_depth),
        ).fetchall()
        return _frontier(rows)

    def ipc_sent(self, routine_ids: Iterable[str]) -> list[sqlite3.Row]:
        """Every command sent by name from these routines, linked or not, with the far end.

        For `touches`: the routines are a reach, and these are the places it crosses into
        another process -- and, where the link failed, the places it would have. One row
        per site, ordered by where it is written, never by the order of the reach.
        """
        ids = sorted(set(routine_ids))
        if not ids:
            return []
        self.conn.execute("CREATE TEMP TABLE IF NOT EXISTS _ipc_ids(id TEXT PRIMARY KEY)")
        self.conn.execute("DELETE FROM _ipc_ids")
        self.conn.executemany("INSERT OR IGNORE INTO _ipc_ids VALUES(?)", [(i,) for i in ids])
        return list(self.conn.execute(
            "SELECT l.*, r.qualname AS command_qualname, r.file AS command_file,"
            "       r.line_start AS command_line, s.qualname AS sender"
            "  FROM ipc_links l JOIN _ipc_ids i ON i.id = l.caller_id"
            "  LEFT JOIN routines r ON r.id = l.routine_id"
            "  LEFT JOIN routines s ON s.id = l.caller_id"
            " ORDER BY l.status, l.command, l.file, l.line, l.site_id"
        ))

    def ipc_received(self, routine_ids: Iterable[str]) -> list[sqlite3.Row]:
        """Every linked send whose command is one of these routines: `impact`'s crossings."""
        ids = sorted(set(routine_ids))
        if not ids:
            return []
        self.conn.execute("CREATE TEMP TABLE IF NOT EXISTS _ipc_ids(id TEXT PRIMARY KEY)")
        self.conn.execute("DELETE FROM _ipc_ids")
        self.conn.executemany("INSERT OR IGNORE INTO _ipc_ids VALUES(?)", [(i,) for i in ids])
        return list(self.conn.execute(
            "SELECT l.*, r.qualname AS command_qualname, s.qualname AS sender"
            "  FROM ipc_links l JOIN _ipc_ids i ON i.id = l.routine_id"
            "  LEFT JOIN routines r ON r.id = l.routine_id"
            "  LEFT JOIN routines s ON s.id = l.caller_id"
            " WHERE l.status = 'linked'"
            " ORDER BY l.command, l.file, l.line, l.site_id"
        ))

    def _ids_table(self, routine_ids: Iterable[str]) -> bool:
        ids = sorted(set(routine_ids))
        if not ids:
            return False
        self.conn.execute("CREATE TEMP TABLE IF NOT EXISTS _disp_ids(id TEXT PRIMARY KEY)")
        self.conn.execute("DELETE FROM _disp_ids")
        self.conn.executemany("INSERT OR IGNORE INTO _disp_ids VALUES(?)", [(i,) for i in ids])
        return True

    def dispatched(self, routine_ids: Iterable[str]) -> list[sqlite3.Row]:
        """Every dispatched call made from these routines, one row per call, with how many
        bodies it may reach: `touches`' account of where its reach went *by dispatch*.
        Ordered by where the call is written, never by the order of the reach."""
        if not self._ids_table(routine_ids):
            return []
        return list(self.conn.execute(
            "SELECT c.callee_expr, c.file, c.line, s.qualname AS caller,"
            "       COUNT(*) AS bodies, d.how"
            "  FROM dispatch_links d JOIN _disp_ids i ON i.id = d.caller_id"
            "  JOIN calls c ON c.site_id = d.site_id AND c.caller_id = d.caller_id"
            "  LEFT JOIN routines s ON s.id = d.caller_id"
            " GROUP BY d.site_id"
            " ORDER BY c.file, c.line, c.callee_expr, d.site_id"
        ))

    def dispatched_into(self, routine_ids: Iterable[str]) -> list[sqlite3.Row]:
        """Every dispatched call that may run one of these routines: `impact`'s account.
        One row per call and body, ordered by where the call is written."""
        if not self._ids_table(routine_ids):
            return []
        return list(self.conn.execute(
            "SELECT c.callee_expr, c.file, c.line, s.qualname AS caller,"
            "       r.qualname AS body, d.how"
            "  FROM dispatch_links d JOIN _disp_ids i ON i.id = d.routine_id"
            "  JOIN calls c ON c.site_id = d.site_id AND c.caller_id = d.caller_id"
            "  LEFT JOIN routines s ON s.id = d.caller_id"
            "  LEFT JOIN routines r ON r.id = d.routine_id"
            " ORDER BY c.file, c.line, c.callee_expr, r.qualname, d.site_id"
        ))

    def dispatch_of_map(self) -> dict[str, Any] | None:
        """Dispatched calls across the map (`resolve/dispatch.py`), for *About this map*.
        `None` where there are none, so a map without them gets no row (rule 32)."""
        row = self.conn.execute(
            "SELECT COUNT(DISTINCT site_id), COUNT(DISTINCT routine_id), COUNT(*)"
            "  FROM dispatch_links").fetchone()
        if not row or not row[2]:
            return None
        return {"calls": int(row[0]), "bodies": int(row[1]), "links": int(row[2]),
                "how": "by dispatch"}

    def frontier_of_map(self) -> dict[str, Any]:
        """`frontier_reached` over every call in the map, for *About this map*."""
        rows = self.conn.execute(
            "SELECT f.lang, c.reason, c.frontier, COUNT(*) AS n FROM calls c"
            " LEFT JOIN files f ON f.path = c.file"
            " WHERE c.callee_id IS NULL AND c.at_boundary = 0 AND c.constructs = ''"
            " GROUP BY f.lang, c.reason, c.frontier"
        ).fetchall()
        return _frontier(rows)

    def ipc_of_map(self) -> dict[str, Any] | None:
        """Commands sent by name across the map (`resolve/ipc.py`), for *About this map*.

        `None` where nothing is sent and nothing is a command, so a map with no client
        gets no row rather than a row of zeros (rule 32). Every figure is a count over the
        two tables the claim is made from, so the sentence beside it is a query (rule 13).
        """
        status = {str(r[0]): int(r[1]) for r in self.conn.execute(
            "SELECT status, COUNT(*) FROM ipc_links GROUP BY status ORDER BY status")}
        commands = int(self.conn.execute(
            "SELECT COUNT(*) FROM entrypoints WHERE kind = 'IPC_COMMAND'").fetchone()[0])
        if not status and not commands:
            return None
        registered = int(self.conn.execute(
            "SELECT COUNT(*) FROM entrypoints WHERE kind = 'IPC_COMMAND'"
            " AND name IN (SELECT name FROM ipc_registrations)").fetchone()[0])
        named = int(self.conn.execute(
            "SELECT COUNT(DISTINCT entrypoint_id) FROM ipc_links WHERE status = 'linked'"
        ).fetchone()[0])
        return {"sites": sum(status.values()), "status": status, "commands": commands,
                "registered": registered, "named": named, "how": "by name"}

    def unresolved_named(self, name: str) -> list[tuple[str, int]]:
        """Calls with no edge whose method is called `name`, by reason: the callers a routine
        may have that the map could not draw. `x.save()` on a receiver of unwritten type
        could be any `save`; that is a reason to look, never an edge (rule 1).

        A dispatched call whose bodies are linked (`dispatch_links`) is left out: `impact`
        already says it *reached by dispatch*, and the same call counted again here would
        be two facts about one thing (rule 40)."""
        rows = self.conn.execute(
            "SELECT reason, COUNT(*) AS n FROM calls"
            " WHERE callee_id IS NULL AND reason IN ('untyped', 'dynamic')"
            "   AND site_id NOT IN (SELECT site_id FROM dispatch_links)"
            "   AND (callee_expr = ? OR callee_expr LIKE ? ESCAPE '\\')"
            " GROUP BY reason ORDER BY n DESC, reason",
            # `_` is a wildcard to LIKE and in every other Rust name.
            (name, "%." + name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")),
        ).fetchall()
        return [(str(r["reason"]), int(r["n"])) for r in rows]

    def _macro_edges(self) -> dict[str, list[str]]:
        """Who reaches whom through a macro's expansion, joined by location (`macro_callees`).
        Not in `_reach_graph`, because flows and impact must not follow it: `FMsg::Logf` under
        `check` would make every routine in Core a neighbour of every other (rule 55)."""
        edges: dict[str, list[str]] = {}
        for caller, callee in self.conn.execute(
            "SELECT m.routine_id, r.id FROM macro_callees m JOIN routines r"
            " ON r.file = m.target_file AND r.line_start = m.target_line"
            " AND r.name = m.target_name WHERE m.target_file <> '' ORDER BY m.rowid"
        ):
            edges.setdefault(caller, []).append(callee)
        return edges

    def reachable_through_macros(self, routine_ids: list[str],
                                 max_depth: int = 40) -> set[str]:
        """`reachable_from_many`, following what macros expand to as well. For the questions
        that are about whether a routine can run at all, and no others."""
        reached = self.reachable_from_many(routine_ids, max_depth)
        macros = self._macro_edges()
        if not macros:
            return reached
        graph = dict(self._reach_graph() or {})
        for caller, callees in macros.items():
            graph[caller] = [*graph.get(caller, ()), *callees]
        return self._walk(graph, reached, max_depth) if graph else reached

    def reachable_from_many(self, routine_ids: list[str], max_depth: int = 40, *,
                            cross: bool = True) -> set[str]:
        """Everything a *set* of routines can reach, as one traversal.

        An executable built from a command tree has no single root routine: its reach
        is the union over every command it exposes. Seeding the recursion with all of
        them at once costs one query instead of one per command.

        `cross=False` stops at a command sent by name. *Which process is this routine in?*
        is a question a crossing must not answer: the Rust command a TypeScript store
        names runs in the other process, and following the link would put it in both. It
        still crosses dispatch, which never leaves the process.
        """
        if not routine_ids:
            return set()
        graph = self._reach_graph(cross)
        if graph is not None:
            # Seeded with the ids that are routines, as the query's seed is.
            known = self._routine_ids()
            return self._walk(graph, [r for r in routine_ids if r in known], max_depth)
        rows = self.conn.execute(
            """
            WITH RECURSIVE seed(id) AS (SELECT value FROM (SELECT ? AS value)),
            reach(id, depth) AS (
                SELECT id, 0 FROM routines WHERE id IN (SELECT value FROM json_each(?))
                UNION
                SELECT c.callee_id, r.depth + 1
                  FROM calls c JOIN reach r ON c.caller_id = r.id
                 WHERE c.callee_id IS NOT NULL AND r.depth < ?
                UNION
                SELECT l.routine_id, r.depth + 1
                  FROM ipc_links l JOIN reach r ON l.caller_id = r.id
                 WHERE l.status = 'linked' AND r.depth < ?
                UNION
                SELECT d.routine_id, r.depth + 1
                  FROM dispatch_links d JOIN reach r ON d.caller_id = r.id
                 WHERE r.depth < ?
            )
            SELECT DISTINCT id FROM reach WHERE id IS NOT NULL
            """,
            (routine_ids[0], json.dumps(list(routine_ids)),
             max_depth, max_depth if cross else -1, max_depth),
        )
        return {r["id"] for r in rows}

    def boundaries_reached_many(self, routine_ids: list[str], max_depth: int = 40, *,
                                through_macros: bool = False) -> list[BoundaryHit]:
        """Every boundary a set of routines reaches, directly or transitively. Through what
        macros expand to only where asked: *what does this touch* wants that, and a flow's
        inventory must not have it (`_macro_edges`)."""
        if not routine_ids:
            return []
        graph = self._reach_graph()
        if graph is not None or through_macros:
            # The reach walked in memory, and the boundaries -- a small table on every map
            # measured, 2,424 rows on the largest -- filtered against it, in the order and
            # with the `DISTINCT` the query below gives them (BACKLOG 8).
            reached = (self.reachable_through_macros(routine_ids, max_depth) if through_macros
                       else self.reachable_from_many(routine_ids, max_depth))
            every = getattr(self, "_boundary_cache", None)
            if every is None:
                # Read once: this is asked once per way in, and Unreal's Runtime part has
                # thousands of them.
                every = list(self.conn.execute(
                    "SELECT DISTINCT * FROM boundaries"
                    " ORDER BY kind, target, direction, line, evidence"))
                self._boundary_cache = every
            rows = [r for r in every if r["routine_id"] in reached]
        else:
            rows = list(self._boundaries_reached_query(routine_ids, max_depth))
        return [
            BoundaryHit(
                routine_id=r["routine_id"], kind=BoundaryKind(r["kind"]),
                direction=Direction(r["direction"]), target=r["target"], line=r["line"],
                evidence=r["evidence"], salience=r["salience"],
                through_macro=r["through_macro"],
            )
            for r in rows
        ]

    def _boundaries_reached_query(self, routine_ids: list[str],
                                  max_depth: int) -> Iterator[sqlite3.Row]:
        rows = self.conn.execute(
            """
            WITH RECURSIVE reach(id, depth) AS (
                SELECT id, 0 FROM routines WHERE id IN (SELECT value FROM json_each(?))
                UNION
                SELECT c.callee_id, r.depth + 1
                  FROM calls c JOIN reach r ON c.caller_id = r.id
                 WHERE c.callee_id IS NOT NULL AND r.depth < ?
                UNION
                SELECT l.routine_id, r.depth + 1
                  FROM ipc_links l JOIN reach r ON l.caller_id = r.id
                 WHERE l.status = 'linked' AND r.depth < ?
                UNION
                SELECT d.routine_id, r.depth + 1
                  FROM dispatch_links d JOIN reach r ON d.caller_id = r.id
                 WHERE r.depth < ?
            )
            SELECT DISTINCT b.* FROM boundaries b JOIN reach r ON b.routine_id = r.id
            ORDER BY b.kind, b.target, b.direction, b.line, b.evidence
            """,
            (json.dumps(list(routine_ids)), max_depth, max_depth, max_depth),
        )
        yield from rows

    def query(self, sql: str,
              args: tuple[Any, ...] | dict[str, Any] = ()) -> list[sqlite3.Row]:
        """Run one query. A dict binds named placeholders (`:root`), a tuple positional.

        Named binding matters for the dashboard's disk queries, where the same package
        expression is spliced into several statements and repeating its parameters
        positionally in each one is how they drift apart.
        """
        return list(self.conn.execute(sql, args))


def facts_held(out_dir: Path) -> bool:
    """Whether this program has a graph the next run could skip reading from.

    Asked of a read-only open, which refuses a stale graph and never discards one. The
    extraction cache is the graph's `files` table, so `source.db` surviving says nothing.
    """
    from . import revisions

    graph = revisions.newest(out_dir, "graph")
    if graph is None:
        return False
    try:
        store = Store(graph, writable=False)
    except StaleGraphError:
        return False
    try:
        return store.conn.execute("SELECT 1 FROM files LIMIT 1").fetchone() is not None
    finally:
        store.close()
