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
