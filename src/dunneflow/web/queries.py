"""Every query the dashboard makes, as SQL text, in one place.

Kept as *text* rather than as Python that assembles rows, because the settled path to a
mailable static build is to run these same strings client-side against `sqlite-wasm` over
HTTP range requests. A query written as Python string-building is a query that has to be
written twice.

Nothing here interprets a row. Shaping belongs in `graph.py`; this module only says what
to ask. Anything already answered by `resolve/` -- ways in, flows, boundary index,
anomalies -- is *not* duplicated here. It is imported and reused.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Disks
#
# A disk is one 2D graph in the stack. Internal code is decomposed by top-level
# package, which is what turns a 10,000-node hairball into fifty-odd readable
# pictures; external systems are decomposed by boundary kind, because a database
# and a message queue are not the same sphere of influence.
#
# `substr(module, 10)` drops a leading "mensores." -- the program's own root
# package, whose length is passed in rather than assumed, since it differs per
# program.
# --------------------------------------------------------------------------- #

PACKAGE_EXPR = """
    CASE
      WHEN module = :root THEN '<root>'
      WHEN module LIKE :root_dot THEN
        CASE WHEN instr(substr(module, :cut), '.') > 0
             THEN substr(module, :cut, instr(substr(module, :cut), '.') - 1)
             ELSE substr(module, :cut) END
      ELSE '<external>'
    END
"""

ROUTINE_NODES = f"""
SELECT r.id                AS id,
       r.name              AS label,
       r.qualname          AS qualname,
       r.module            AS module,
       r.file              AS file,
       r.line_start        AS line,
       r.visibility        AS visibility,
       r.is_async          AS is_async,
       r.class_name        AS class_name,
       {PACKAGE_EXPR}      AS pkg
FROM routines r
"""

STRUCTURE_NODES = f"""
SELECT s.id           AS id,
       s.name         AS label,
       s.kind         AS struct_kind,
       s.module       AS module,
       s.file         AS file,
       s.line         AS line,
       {PACKAGE_EXPR} AS pkg
FROM structures s
"""

CONSTANT_NODES = f"""
SELECT 'const:' || module || '.' || name AS id,
       name           AS label,
       module         AS module,
       file           AS file,
       line           AS line,
       private        AS private,
       {PACKAGE_EXPR} AS pkg
FROM constants
"""

# One node per distinct external endpoint, not per touch. 3,950 boundary hits
# collapse to 1,684 endpoints; drawing a node per hit would draw the same
# database table hundreds of times.
BOUNDARY_NODES = """
SELECT 'bnd:' || kind || ':' || target AS id,
       target                          AS label,
       kind                            AS bkind,
       COUNT(*)                        AS hits,
       COUNT(DISTINCT routine_id)      AS callers,
       MIN(direction)                  AS direction
FROM boundaries
WHERE target <> ''
GROUP BY kind, target
"""

# Boundary touches with no named target still happened, and dropping them would
# silently shrink the program. They are folded into one node per kind rather
# than invented as separate endpoints, and the label says so.
UNNAMED_BOUNDARY_NODES = """
SELECT 'bnd:' || kind || ':' AS id,
       kind                  AS bkind,
       COUNT(*)              AS hits,
       COUNT(DISTINCT routine_id) AS callers
FROM boundaries
WHERE target = ''
GROUP BY kind
"""

# A file the program *names*: `tabularium.db`, `groma.json`, `STATUSQUO.md`. Rule 17 --
# a program names its files and those names are vocabulary. They reach no other detector,
# because a path assembled as `root / ".mensores" / "tabularium.db"` is not a boundary
# target, not a table and not a module, so without this they are absent from the map
# entirely. Searching the graph for `tabularium` is what showed they were missing.
#
# One node per distinct name rather than per mention: 350 mentions collapse to ~150 files,
# and drawing the same file once per reference would draw it fifty-two times.
ARTEFACT_NODES = """
SELECT 'art:' || name    AS id,
       name              AS label,
       ext               AS ext,
       MIN(kind)         AS akind,
       COUNT(*)          AS mentions,
       COUNT(DISTINCT routine_id) AS namers
FROM artefacts
WHERE name <> ''
GROUP BY name
"""

ARTEFACT_EDGES = """
SELECT routine_id     AS src,
       'art:' || name AS dst,
       COUNT(*)       AS weight
FROM artefacts
WHERE routine_id IS NOT NULL AND name <> ''
GROUP BY routine_id, name
"""

# --------------------------------------------------------------------------- #
# Edges
# --------------------------------------------------------------------------- #

CALL_EDGES = """
SELECT caller_id AS src, callee_id AS dst, confidence AS confidence, COUNT(*) AS weight
FROM calls
WHERE callee_id IS NOT NULL AND at_boundary = 0
GROUP BY caller_id, callee_id, confidence
"""

BOUNDARY_EDGES = """
SELECT routine_id                              AS src,
       'bnd:' || kind || ':' || target         AS dst,
       kind                                    AS bkind,
       MIN(direction)                          AS direction,
       COUNT(*)                                AS weight
FROM boundaries
WHERE routine_id IS NOT NULL
GROUP BY routine_id, kind, target
"""

# --------------------------------------------------------------------------- #
# Stored layout
#
# Layout is a fact: computed once, kept, and identical on every later open, so
# the map holds still and spatial memory works. Keyed by (node, disk) because
# one entity holds a position per disk it appears on -- its real one, and one
# for every disk that shadows it.
# --------------------------------------------------------------------------- #

LAYOUT_READ = """
SELECT node_id, disk, x, y, z, is_shadow
FROM layout
WHERE program = ?
"""

LAYOUT_CLEAR = "DELETE FROM layout WHERE program = ?"

LAYOUT_WRITE = """
INSERT OR REPLACE INTO layout (program, node_id, disk, x, y, z, is_shadow)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""

LAYOUT_STAMP_READ = "SELECT value FROM meta WHERE key = 'layout_fingerprint'"


# --------------------------------------------------------------------------- #
# The inspector
#
# Flow-first, in the order the inspector reads: how a routine is reached, what it
# calls, what it touches, and why it exists. A signature is not the headline --
# it is demoted into the params view, because what moves through a routine is the
# subject and its type annotations are not.
#
# Confidence travels with every call in both directions. Rule 6 says CERTAIN and
# INFERRED are never blurred, and design rule 5 says the difference is shape
# rather than colour -- so the value has to reach the client to be drawn at all.
# --------------------------------------------------------------------------- #

ROUTINE_DETAIL = """
SELECT r.id, r.name, r.qualname, r.module, r.file, r.line_start, r.line_end,
       r.lang, r.returns, r.docstring, r.decorators, r.is_async, r.is_method,
       r.class_name, r.is_nested, r.visibility
FROM routines r
WHERE r.id = :id
"""

ROUTINE_PARAMS = """
SELECT idx, name, type, dflt, kind
FROM params
WHERE routine_id = :id
ORDER BY idx
"""

# IN. Who calls this, and how sure we are. `callee_expr` is kept because the text
# at the call site is often more informative than the resolved name -- it is what
# the reader will actually find when they open the file.
ROUTINE_CALLERS = """
SELECT c.caller_id AS id, c.line, c.confidence, c.callee_expr, c.ambiguous,
       r.name, r.qualname, r.module, r.file
FROM calls c
JOIN routines r ON r.id = c.caller_id
WHERE c.callee_id = :id
ORDER BY r.qualname, c.line
"""

# A routine that is itself a way in. Declared registration, not inferred reach:
# `touches` and `impact` answer the transitive question and are not duplicated here.
ROUTINE_ENTRYPOINTS = """
SELECT kind, name, evidence, grp, target_expr
FROM entrypoints
WHERE routine_id = :id
ORDER BY kind, name
"""

# OUT. External and boundary-bound calls are kept in the same list rather than
# split off, because the reader's question is "what does this do next" and the
# answer includes leaving the program. `external` and `at_boundary` say which.
ROUTINE_CALLEES = """
SELECT c.callee_id AS id, c.callee_expr, c.line, c.confidence, c.external,
       c.at_boundary, c.ambiguous,
       r.name, r.qualname, r.module, r.file
FROM calls c
LEFT JOIN routines r ON r.id = c.callee_id
WHERE c.caller_id = :id
ORDER BY c.line
"""

# TOUCHES, in four kinds. Each keeps the evidence that admitted it: a claim
# without its provenance is an assertion wearing a uniform (design rule 13).
ROUTINE_BOUNDARIES = """
SELECT kind, direction, target, line, evidence, salience
FROM boundaries
WHERE routine_id = :id
ORDER BY salience DESC, line
"""

ROUTINE_SQL_OPS = """
SELECT operation, direction, tbl, sql, line
FROM sql_ops
WHERE routine_id = :id
ORDER BY line
"""

# The full record, not a summary. Rule 8: never truncate at ingest, and never
# quietly at egress either -- a timeout nobody set is a fact about the program.
ROUTINE_NET_CALLS = """
SELECT expr, protocol, verb, destination, port, is_async, awaited,
       in_async_routine, timeout, retries, tls, payload, headers, topic, ack, line
FROM net_calls
WHERE routine_id = :id
ORDER BY line
"""

ROUTINE_ARTEFACTS = """
SELECT name, stem, ext, kind, line, literal, is_pattern
FROM artefacts
WHERE routine_id = :id
ORDER BY line
"""

# GOVERNANCE and WHY. Comments carry `line` so the inspector can place each one
# against the thing it explains rather than pooling them in a block -- which is
# the whole reason the comment gap was worth closing.
ROUTINE_ANNOTATIONS = """
SELECT kind, value, line, text
FROM annotations
WHERE owner_id = :id AND owner_kind = 'routine'
ORDER BY line
"""

ROUTINE_COMMENTS = """
SELECT line, text, leading
FROM comments
WHERE routine_id = :id
ORDER BY line
"""

# --------------------------------------------------------------------------- #
# The other node kinds. Each answers the same shape of question with whatever it
# actually has, rather than pretending to be a routine with fields missing.
# --------------------------------------------------------------------------- #

STRUCTURE_DETAIL = """
SELECT id, name, kind, module, file, line, lang, docstring, bases
FROM structures
WHERE id = :id
"""

STRUCTURE_FIELDS = """
SELECT idx, name, type, dflt, comment
FROM fields
WHERE structure_id = :id
ORDER BY idx
"""

STRUCTURE_ANNOTATIONS = """
SELECT kind, value, line, text
FROM annotations
WHERE owner_id = :id AND owner_kind = 'structure'
ORDER BY line
"""

# A constant has no id of its own in the store -- it is identified by the file and
# name that declare it, which is also how the graph builds its node id.
CONSTANT_DETAIL = """
SELECT file, module, name, value, type, is_final, comment, private, line
FROM constants
WHERE module = :module AND name = :name
"""

# Who reaches an external. The inspector's question at a boundary node is never
# "what is this" -- it is "which of my code talks to it", so the answer is the
# callers, with the evidence that identified each touch.
BOUNDARY_TOUCHERS = """
SELECT b.kind, b.direction, b.target, b.line, b.evidence, b.salience,
       b.file, r.id, r.name, r.qualname, r.module
FROM boundaries b
LEFT JOIN routines r ON r.id = b.routine_id
WHERE b.kind = :kind AND COALESCE(b.target, '') = COALESCE(:target, '')
ORDER BY b.salience DESC, r.qualname, b.line
"""

ARTEFACT_NAMERS = """
SELECT a.name, a.stem, a.ext, a.kind, a.line, a.literal, a.is_pattern,
       a.file, r.id, r.name AS routine, r.qualname, r.module
FROM artefacts a
LEFT JOIN routines r ON r.id = a.routine_id
WHERE a.name = :name
ORDER BY a.file, a.line
"""


# --------------------------------------------------------------------------- #
# Document mode
#
# Every row selects the graph's node id in the same statement that selects its
# text. That is the whole point: clicking a routine in the prose must select
# that routine in the graph, and matching a name against the store afterwards
# would light up every `main` in a program that has a great many (rule 5).
#
# A row whose id is null is still returned. It is a fact about the program
# either way, and the client shows it without a link rather than dropping it --
# a silently shorter table is the failure design rule 1 exists to prevent.
# --------------------------------------------------------------------------- #

DOC_ENTRYPOINTS = """
SELECT e.routine_id             AS node,
       e.name                   AS name,
       e.kind                   AS kind,
       COALESCE(r.qualname, '') AS routine,
       COALESCE(e.evidence, '') AS evidence,
       COALESCE(r.file, e.file) || ':' || COALESCE(r.line_start, 0) AS where_,
       COALESCE(r.file, e.file) AS file,
       COALESCE(r.line_start, 0) AS line
FROM entrypoints e
LEFT JOIN routines r ON r.id = e.routine_id
ORDER BY e.kind, e.name
"""

# The signature is assembled here rather than in Python so the whole document is
# one statement per section -- which is also what lets these same strings run
# client-side against sqlite-wasm later without a second implementation.
DOC_ROUTINES = """
SELECT r.id       AS node,
       r.name     AS name,
       r.module   AS module,
       CASE WHEN r.is_async THEN 'async ' ELSE '' END || r.name || '(' ||
         COALESCE((SELECT group_concat(p.name, ', ')
                   FROM (SELECT name FROM params
                         WHERE routine_id = r.id ORDER BY idx) p), '') || ')' ||
         CASE WHEN COALESCE(r.returns, '') <> '' THEN ' -> ' || r.returns ELSE '' END
                  AS signature,
       COALESCE(r.docstring, '') AS why,
       r.file || ':' || r.line_start AS where_,
       r.file     AS file,
       r.line_start AS line
FROM routines r
ORDER BY r.module, r.line_start
"""

DOC_STRUCTURES = """
SELECT s.id     AS node,
       s.name   AS name,
       s.module AS module,
       s.kind   AS kind,
       COALESCE((SELECT group_concat(f.name, ', ')
                 FROM (SELECT name FROM fields
                       WHERE structure_id = s.id ORDER BY idx) f), '') AS fields,
       COALESCE(s.docstring, '') AS why,
       s.file || ':' || s.line AS where_,
       s.file   AS file,
       s.line   AS line
FROM structures s
ORDER BY s.module, s.line
"""

DOC_CONSTANTS = """
SELECT 'const:' || c.module || '.' || c.name AS node,
       c.name   AS name,
       c.module AS module,
       c.value  AS value,
       COALESCE(c.comment, '') AS why,
       c.file || ':' || c.line AS where_,
       c.file   AS file,
       c.line   AS line
FROM constants c
ORDER BY c.module, c.line
"""

DOC_BOUNDARIES = """
SELECT 'bnd:' || b.kind || ':' || b.target AS node,
       b.kind      AS kind,
       b.target    AS target,
       b.direction AS direction,
       COALESCE(r.qualname, '(module scope)') AS routine,
       COALESCE(b.evidence, '') AS evidence,
       b.file || ':' || b.line AS where_,
       b.file      AS file,
       b.line      AS line
FROM boundaries b
LEFT JOIN routines r ON r.id = b.routine_id
ORDER BY b.kind, b.target, b.line
"""

# A declared table is not a node in the graph, so `node` is null and the client
# draws the row without a link. Inventing an id to make it clickable would be a
# link to nothing, which is worse than no link.
DOC_DB_TABLES = """
SELECT NULL      AS node,
       t.name    AS name,
       COALESCE((SELECT group_concat(c.name, ', ')
                 FROM (SELECT name FROM db_columns
                       WHERE tbl = t.name ORDER BY idx) c), '') AS columns,
       (SELECT COUNT(*) FROM sql_ops o
         WHERE o.tbl = t.name AND o.direction = 'read')  AS reads,
       (SELECT COUNT(*) FROM sql_ops o
         WHERE o.tbl = t.name AND o.direction = 'write') AS writes,
       t.file || ':' || t.line AS where_,
       t.file    AS file,
       t.line    AS line
FROM db_tables t
ORDER BY t.name
"""

DOC_DB_OPS = """
SELECT o.routine_id AS node,
       o.tbl        AS tbl,
       o.operation  AS operation,
       o.direction  AS direction,
       COALESCE(r.qualname, '(module scope)') AS routine,
       o.sql        AS sql,
       o.file || ':' || o.line AS where_,
       o.file       AS file,
       o.line       AS line
FROM sql_ops o
LEFT JOIN routines r ON r.id = o.routine_id
ORDER BY o.tbl, o.line
"""

DOC_NET = """
SELECT n.routine_id AS node,
       COALESCE(n.protocol, 'unknown') AS protocol,
       COALESCE(n.destination, n.expr) AS destination,
       COALESCE(n.verb, '') AS verb,
       COALESCE(r.qualname, '(module scope)') AS routine,
       n.timeout    AS timeout,
       n.retries    AS retries,
       n.file || ':' || n.line AS where_,
       n.file       AS file,
       n.line       AS line
FROM net_calls n
LEFT JOIN routines r ON r.id = n.routine_id
ORDER BY n.protocol, n.line
"""

DOC_ARTEFACTS = """
SELECT 'art:' || a.name AS node,
       a.name           AS name,
       COALESCE(NULLIF(a.ext, ''), '(no extension)') AS ext,
       MIN(a.kind)      AS kind,
       COUNT(*)         AS mentions,
       COUNT(DISTINCT a.routine_id) AS namers
FROM artefacts a
WHERE a.name <> ''
GROUP BY a.name
ORDER BY COUNT(*) DESC, a.name
"""


# --------------------------------------------------------------------------- #
# The cover
#
# Four questions in the order a reader asks them. Each is a count over the
# store, never a summary the tool invented.
# --------------------------------------------------------------------------- #

# The most-touched target per kind is shown beside the count, because "DATABASE
# 1,316" says how much and "ROLLBACK" says what -- and the second is the one
# that makes a reader curious enough to click.
COVER_BOUNDARIES = """
SELECT kind             AS kind,
       COUNT(*)         AS n,
       (SELECT b2.target FROM boundaries b2
         WHERE b2.kind = b.kind AND b2.target <> ''
         GROUP BY b2.target ORDER BY COUNT(*) DESC, b2.target LIMIT 1) AS common
FROM boundaries b
GROUP BY kind
ORDER BY n DESC
"""

# Top-level package by routine count. The same decomposition the graph's disks
# use, so the navigator and the stack agree about what a package is.
COVER_PACKAGES = """
SELECT CASE
         WHEN instr(module, '.') = 0 THEN module
         ELSE substr(module, 1, instr(module, '.') - 1)
       END || CASE
         WHEN instr(substr(module, instr(module, '.') + 1), '.') > 0
           THEN '.' || substr(substr(module, instr(module, '.') + 1), 1,
                              instr(substr(module, instr(module, '.') + 1), '.') - 1)
         WHEN instr(module, '.') > 0
           THEN '.' || substr(module, instr(module, '.') + 1)
         ELSE ''
       END AS full_pkg,
       CASE
         WHEN instr(module, '.') = 0 THEN module
         WHEN instr(substr(module, instr(module, '.') + 1), '.') > 0
           THEN substr(substr(module, instr(module, '.') + 1), 1,
                       instr(substr(module, instr(module, '.') + 1), '.') - 1)
         ELSE substr(module, instr(module, '.') + 1)
       END AS pkg,
       COUNT(*) AS n
FROM routines
GROUP BY pkg
ORDER BY n DESC
"""

# Tables ranked by how much traffic they carry, which is the order a reader
# wants: the busiest table is where the program's state actually lives.
COVER_TABLES = """
SELECT t.name AS name,
       (SELECT COUNT(*) FROM sql_ops o WHERE o.tbl = t.name) AS n
FROM db_tables t
ORDER BY n DESC, t.name
"""
