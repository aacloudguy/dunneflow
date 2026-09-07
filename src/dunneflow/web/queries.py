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

def package_expr(col: str = "module") -> str:
    """The package a module belongs to: the segment just under the program root.

    Takes the column so one join can ask it of two different tables. It used to be a bare
    string whose column name was patched in by substitution at the call site -- the kind of
    string surgery this project keeps paying for, correct only for as long as no column
    name happens to contain the word being substituted.

    **The rootless branch, and why it comes first.** `root_package` returns `""` when no
    single first segment accounts for every file, which is what analysing a directory that
    already *is* a package produces. Then the tree itself is the root and a module's package
    is its first segment -- `web.serve` is in `web`, `anomalies` is in `anomalies` -- which
    is exactly the grouping analysing the parent directory would have given. Two ways of
    pointing at one program, one answer.

    **`<outside the root>` was `<external>`, and the rename is the finding.** Every row this
    expression sees is the program's own -- `routines` and `structures` hold what was
    extracted from its files, and nothing else is in them. On a healthy map the branch never
    fires at all: **0 of 4,786** on Mensores. It fired only when the root was wrong, and
    what it then said was not *"this module is not under the root"* but *"this is somebody
    else's code"* -- 750 routines of 752, on the largest plate in the picture (rules 26
    and 30). It is now unreachable by construction, because a root either accounts for every
    file or is empty; it is kept, said honestly, so that a future change to root detection
    finds a branch that states what it knows rather than one that guesses.
    """
    return f"""
    CASE
      WHEN :root = '' THEN
        CASE WHEN instr({col}, '.') > 0
             THEN substr({col}, 1, instr({col}, '.') - 1)
             ELSE {col} END
      WHEN {col} = :root THEN '<root>'
      WHEN {col} LIKE :root_dot THEN
        CASE WHEN instr(substr({col}, :cut), '.') > 0
             THEN substr({col}, :cut, instr(substr({col}, :cut), '.') - 1)
             ELSE substr({col}, :cut) END
      ELSE '<outside the root>'
    END
"""


PACKAGE_EXPR = package_expr()

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

# --------------------------------------------------------------------------- #
# MODULES -- the stack's other altitude
#
# `graph.py` at `level="module"` folds every routine, constant and structure a file
# declares into one node. These answer for that node, and they all key on the dotted
# module rather than on a path: `routines.module` is what the fold itself grouped by,
# so the card and the picture cannot come apart (rule 13).
#
# Every one of them scopes *out of* the module as well as into it. "Who calls this
# module" means a caller somewhere else -- a routine calling its neighbour in the same
# file is the module talking to itself, which is the same thing `_add_edges` counts and
# does not draw. Reported as a count, never as an edge.
# --------------------------------------------------------------------------- #

MODULE_DETAIL = """
SELECT :module AS module, MIN(path) AS file, MIN(doc) AS doc
FROM files
WHERE module = :module
"""

# What it declares, in one pass per kind. Three statements rather than a union, because
# each table names its rows differently and a union would have to blank the columns the
# others do not have -- which is the routine-shaped object with fields missing that
# `describe()` refuses to return.
MODULE_ROUTINES = """
SELECT id, name, qualname, line_start AS line, visibility, is_async, class_name
FROM routines
WHERE module = :module
ORDER BY line_start
"""

MODULE_STRUCTURES = """
SELECT id, name, kind, line
FROM structures
WHERE module = :module
ORDER BY line
"""

MODULE_CONSTANTS = """
SELECT name, value, type, line, private
FROM constants
WHERE module = :module
ORDER BY line
"""

# Who reaches in, by module rather than by routine. 85 modules calling one is a list a
# reader can act on; the 1,400 individual calls under it are the haystack again (rule 45).
MODULE_CALLERS = """
SELECT src.module          AS module,
       COUNT(*)            AS calls,
       COUNT(DISTINCT src.id) AS routines,
       MAX(c.confidence = 'CERTAIN') AS certain
FROM calls c
JOIN routines src ON src.id = c.caller_id
JOIN routines dst ON dst.id = c.callee_id
WHERE dst.module = :module AND src.module <> :module AND c.at_boundary = 0
GROUP BY src.module
ORDER BY calls DESC, src.module
"""

MODULE_CALLEES = """
SELECT dst.module          AS module,
       COUNT(*)            AS calls,
       COUNT(DISTINCT dst.id) AS routines,
       MAX(c.confidence = 'CERTAIN') AS certain
FROM calls c
JOIN routines src ON src.id = c.caller_id
JOIN routines dst ON dst.id = c.callee_id
WHERE src.module = :module AND dst.module <> :module AND c.at_boundary = 0
GROUP BY dst.module
ORDER BY calls DESC, dst.module
"""

# What it touches, grouped the way the folded plate groups it: by kind, with the
# distinct targets counted rather than listed. The targets themselves are one click
# away on the routine that touches them, which is the level that knows the line.
MODULE_BOUNDARIES = """
SELECT b.kind                        AS kind,
       MIN(b.direction)              AS direction,
       COUNT(*)                      AS hits,
       COUNT(DISTINCT b.target)      AS targets,
       COUNT(DISTINCT b.routine_id)  AS routines
FROM boundaries b
JOIN routines r ON r.id = b.routine_id
WHERE r.module = :module
GROUP BY b.kind
ORDER BY hits DESC, b.kind
"""

MODULE_ARTEFACTS = """
SELECT a.name AS name, MIN(a.ext) AS ext, MIN(a.kind) AS kind, COUNT(*) AS mentions
FROM artefacts a
JOIN routines r ON r.id = a.routine_id
WHERE r.module = :module
GROUP BY a.name
ORDER BY mentions DESC, a.name
"""

# How much of this module never leaves it. The number `_add_edges` counts and refuses to
# draw, asked of the store so the card and the picture agree about one program.
MODULE_INNER_CALLS = """
SELECT COUNT(*) AS calls
FROM calls c
JOIN routines src ON src.id = c.caller_id
JOIN routines dst ON dst.id = c.callee_id
WHERE src.module = :module AND dst.module = :module AND c.at_boundary = 0
"""

# --------------------------------------------------------------------------- #
# OUTSIDE -- one boundary kind, folded
#
# The module level draws all of `STDIO`'s 991 targets as one node, so the card has to
# answer for the kind rather than for a target. `bnd:` already answers for one endpoint
# and this is deliberately not that query with a wildcard: the counts differ (991 targets
# against one) and a card that says "3 callers" where the truth is 214 is worse than one
# that says nothing.
# --------------------------------------------------------------------------- #

OUTSIDE_DETAIL = """
SELECT COUNT(*)                     AS hits,
       COUNT(DISTINCT target)       AS targets,
       COUNT(DISTINCT routine_id)   AS callers,
       MIN(direction)               AS direction
FROM boundaries
WHERE kind = :kind
"""

OUTSIDE_TOP_TARGETS = """
SELECT target, COUNT(*) AS hits, COUNT(DISTINCT routine_id) AS callers
FROM boundaries
WHERE kind = :kind AND target <> ''
GROUP BY target
ORDER BY hits DESC, target
"""

OUTSIDE_MODULES = """
SELECT r.module AS module, COUNT(*) AS hits
FROM boundaries b
JOIN routines r ON r.id = b.routine_id
WHERE b.kind = :kind
GROUP BY r.module
ORDER BY hits DESC, r.module
"""

# The artefact plate folds too, and it is not a boundary kind -- naming a file is not
# touching one (rule 17). Its own pair, for the same reason `ARTEFACT_NODES` is separate.
OUTSIDE_ARTEFACT_DETAIL = """
SELECT COUNT(*) AS hits, COUNT(DISTINCT name) AS targets,
       COUNT(DISTINCT routine_id) AS callers
FROM artefacts
WHERE name <> ''
"""

OUTSIDE_ARTEFACT_TOP = """
SELECT name AS target, COUNT(*) AS hits, COUNT(DISTINCT routine_id) AS callers
FROM artefacts
WHERE name <> ''
GROUP BY name
ORDER BY hits DESC, name
"""

OUTSIDE_ARTEFACT_MODULES = """
SELECT r.module AS module, COUNT(*) AS hits
FROM artefacts a
JOIN routines r ON r.id = a.routine_id
WHERE a.name <> ''
GROUP BY r.module
ORDER BY hits DESC, r.module
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
# The hover card
#
# What the pop-up says about a node the cursor is merely passing over. Two rules
# shape it and both are about *not* answering.
#
# It does not count callers or callees. The picture already has those numbers --
# `inbound` and `outbound` in the engine, the same maps the selection itself is
# drawn from -- and a second count taken from `calls` here would be over a
# different population (externals included) and would disagree. Rule 32 is
# exactly that failure: three correct numbers, no two of them counting the same
# thing, and a reader reasonably reading the wrong one.
#
# It counts the **externals**, which is the opposite move and is what makes the
# rest reconcile. `guarded_cwd` shows `3<- 5->` on the card and `Out 8` in the
# inspector, and both are right: eight calls leave it, five reach a routine this
# map holds and three leave the program, so the graph can only draw five. Stating
# the three is what turns two competing numbers into one arithmetic. It is not a
# second count of the same thing -- externals resolve to no node and are in
# neither of the engine's maps -- and design rule 8 says an external is
# first-class anyway.
#
# And it is a query, not a slice of the payload. Fifteen thousand node entries
# already cross the wire; carrying every node's touch counts, governance ids and
# comment text would charge all of them for the handful anybody hovers. The store
# is the spine, so this is a lookup on an indexed id and costs nothing until
# somebody looks.
# --------------------------------------------------------------------------- #

HOVER_ROUTINE = """
SELECT r.name, r.qualname, r.module, r.file, r.line_start, r.line_end,
       r.is_async, r.is_method, r.class_name, r.visibility, r.docstring, r.returns,
       (SELECT COUNT(*) FROM comments c WHERE c.routine_id = r.id) AS n_comments,
       (SELECT COUNT(*) FROM calls c
         WHERE c.caller_id = r.id AND c.external = 1) AS n_external
FROM routines r
WHERE r.id = :id
"""

# Grouped, because a bare total cannot say what it counted. "3 boundaries" is not
# a fact anybody can act on; "2 ENV, 1 FILE" is the shape of what this routine
# reaches. `first` gives the card one name to show beside the count, taken by
# salience so the one shown is the one that mattered most to the detector.
#
# **A boundary already named by a more specific record on the same line is not
# counted again.** This was found by looking at the card rather than by any test:
# `write_spec_seal_atomic` showed three tables *and* "DATABASE 20", which reads as
# twenty-three database things and is in fact the same seventeen statements seen by
# two detectors. Measured across Mensores it is not an oddity of one routine -- 991
# of 1,316 DATABASE boundaries sit on a line with a `sql_ops` row, and **all twenty**
# NETWORK boundaries sit on a `net_calls` row. A summary that states the same act
# twice is rule 32 in miniature: two correct numbers, neither of them saying what it
# counted.
#
# The exclusion is per line rather than per routine, because a routine that opens a
# connection *and* runs statements genuinely does two things and the boundary is the
# only record of the first -- 43 routines have a DATABASE boundary and no `sql_ops`
# at all, and their card would go blank under a coarser rule.
#
# The one-line tolerance is a judgment and is stated as one: the detectors disagree
# by a line on multi-line statements, recording the call site and the statement start
# (1233 against 1234 in the routine above). Two lines would start swallowing genuinely
# separate adjacent acts.
HOVER_BOUNDARY_KINDS = """
SELECT kind, COUNT(*) AS n,
       (SELECT b2.target FROM boundaries b2
         WHERE b2.routine_id = :id AND b2.kind = b.kind AND b2.target <> ''
         ORDER BY b2.salience DESC, b2.line LIMIT 1) AS first
FROM boundaries b
WHERE b.routine_id = :id
  AND NOT EXISTS (SELECT 1 FROM sql_ops s
                   WHERE s.routine_id = b.routine_id AND abs(s.line - b.line) <= 1)
  AND NOT EXISTS (SELECT 1 FROM net_calls n
                   WHERE n.routine_id = b.routine_id AND abs(n.line - b.line) <= 1)
  AND NOT EXISTS (SELECT 1 FROM artefacts a
                   WHERE a.routine_id = b.routine_id AND abs(a.line - b.line) <= 1)
GROUP BY kind
ORDER BY n DESC, kind
"""

# Distinct tables, not operations: a routine that reads one table in a loop of
# four statements touches one table. The direction is what the reader wants next
# and it is what the database report is built on, so it travels too -- a table
# written is a different neighbour from a table read.
HOVER_TABLES = """
SELECT tbl AS name,
       SUM(direction = 'WRITE') AS writes,
       SUM(direction = 'READ')  AS reads,
       COUNT(*)                 AS ops
FROM sql_ops
WHERE routine_id = :id AND tbl <> ''
GROUP BY tbl
ORDER BY tbl
"""

# The statements with no table of their own -- `BEGIN`, `COMMIT`, `ROLLBACK`,
# `CREATE TABLE`. Ten of `write_spec_seal_atomic`'s seventeen operations are these,
# and without a row for them the card would state three tables and quietly drop more
# than half of what the routine does to the database. Design rule 1: a filter is
# never silent, and dropping them was exactly the omission the boundary anti-join
# above would otherwise have introduced.
#
# Grouped by direction because DDL is not transaction control: a routine that creates
# a table and a routine that wraps two writes in a transaction are different animals,
# and `CONTROL` alone would call them the same.
HOVER_SQL_UNTABLED = """
SELECT direction AS kind, COUNT(*) AS n,
       (SELECT s2.operation FROM sql_ops s2
         WHERE s2.routine_id = :id AND s2.tbl = '' AND s2.direction = s.direction
         ORDER BY s2.line LIMIT 1) AS first
FROM sql_ops s
WHERE s.routine_id = :id AND s.tbl = ''
GROUP BY direction
ORDER BY n DESC, direction
"""

HOVER_NET = """
SELECT protocol AS kind, COUNT(*) AS n,
       (SELECT n2.destination FROM net_calls n2
         WHERE n2.routine_id = :id AND n2.protocol = n.protocol
               AND n2.destination <> ''
         ORDER BY n2.line LIMIT 1) AS first
FROM net_calls n
WHERE n.routine_id = :id
GROUP BY protocol
ORDER BY n DESC, protocol
"""

HOVER_ARTEFACTS = """
SELECT COUNT(DISTINCT name) AS n,
       (SELECT a2.name FROM artefacts a2 WHERE a2.routine_id = :id
         ORDER BY a2.line LIMIT 1) AS first
FROM artefacts a
WHERE a.routine_id = :id
"""

# The governance ids only, deduplicated. The card has room for a line of them and
# the inspector has room for all of them with their text; sending the text here
# would be paying for a paragraph to render a chip.
# Distinct on the **value**, not on the pair. `ISS-123` is recorded once as an
# ISSUE and once as a TICKET by two different markers in the same file, and a card
# listing it twice is stating a fact about this tool's detectors rather than about
# the program. `MIN(kind)` keeps the choice stable rather than whichever row the
# planner happened to reach first.
#
# The card has room for four of these, so the order decides which four a reader sees
# and it may not be alphabetical: sorted by value, Mensores' 3,713 TICKETs beginning
# `AC-` crowd out every PLAN and ADR on the routine. The order is by what the id
# *is* -- a decision, then the record of one, then the plan, then the issue -- and
# then by how often this routine cites it. It is a stated ranking rather than a
# guess, and the inspector still shows every one of them with its text.
HOVER_ANNOTATIONS = """
SELECT value, MIN(kind) AS kind, COUNT(*) AS n
FROM annotations
WHERE owner_id = :id AND owner_kind = 'routine'
GROUP BY value
ORDER BY CASE MIN(kind)
           WHEN 'DECISION' THEN 0 WHEN 'ADR' THEN 1 WHEN 'PLAN' THEN 2
           WHEN 'ISSUE' THEN 3 WHEN 'GATE' THEN 4 ELSE 5 END,
         n DESC, value
"""

# The WHY, and it has to say which kind of WHY it is.
#
# A comment above a `def` is about the routine; a comment forty lines inside it is
# about a statement. `leading` tells them apart -- and on Mensores only 243 of
# 18,414 comments are leading ones, so a card that accepted nothing else would be
# blank on the overwhelming majority of routines that are in fact well explained.
#
# So the order is: the block above the definition, then the first comment inside
# it. The two are **not** interchangeable and the caller must not present them as
# though they were, which is why `leading` comes back with the text rather than
# being consumed here. A first-line comment shown as "what this routine is for"
# would be this tool inventing a summary; shown with its line number it is a
# quotation, and design rule 13 is satisfied by the reader being able to go and
# read it.
HOVER_WHY_COMMENT = """
SELECT line, text, leading
FROM comments
WHERE routine_id = :id
ORDER BY leading DESC, line
LIMIT 1
"""

HOVER_STRUCTURE = """
SELECT s.name, s.kind, s.module, s.file, s.line, s.docstring, s.bases,
       (SELECT COUNT(*) FROM fields f WHERE f.structure_id = s.id) AS n_fields
FROM structures s
WHERE s.id = :id
"""

HOVER_CONSTANT = """
SELECT name, module, file, line, value, type, is_final, private, comment
FROM constants
WHERE module = :module AND name = :name
LIMIT 1
"""

# An external's card answers "who of mine talks to it", which is the only question
# about a thing we have no source for. Counted two ways because they differ and the
# difference is the interesting part: forty touches from three routines is a
# different shape from forty touches from forty.
HOVER_BOUNDARY_NODE = """
SELECT COUNT(*) AS hits, COUNT(DISTINCT routine_id) AS callers,
       (SELECT b2.direction FROM boundaries b2
         WHERE b2.kind = :kind AND COALESCE(b2.target,'') = COALESCE(:target,'')
         ORDER BY b2.salience DESC LIMIT 1) AS direction
FROM boundaries b
WHERE b.kind = :kind AND COALESCE(b.target,'') = COALESCE(:target,'')
"""

HOVER_ARTEFACT_NODE = """
SELECT COUNT(*) AS mentions, COUNT(DISTINCT routine_id) AS namers,
       (SELECT a2.ext FROM artefacts a2 WHERE a2.name = :name LIMIT 1) AS ext,
       (SELECT a2.kind FROM artefacts a2 WHERE a2.name = :name LIMIT 1) AS akind
FROM artefacts a
WHERE a.name = :name
"""


# --------------------------------------------------------------------------- #
# Threads to pull
#
# Beside the call graph, the *reasons* a neighbour is worth a detour -- design
# rule 15's "adjacency by interest, not only by edge". The call graph answers
# "what runs next"; none of these do, and that is the point: the routine that
# shares your plan, the one at the other end of the table you write, the most
# commented thing on your plate. A reader following a thread is not tracing
# execution, they are following a *reason*.
#
# Two disciplines run through all of them.
#
# **A thread must lead somewhere.** Every query here excludes the subject itself
# and requires at least one other party, because a thread with nobody at the far
# end is a row that looks like a doorway and is a wall. This is rule 30 stated as
# a query: a label is not an identity, and a thread whose subject resolves to
# nothing is the same failure one layer down.
#
# **A thread states its size, and the smallest sorts first.** "9 other routines
# carry this plan" is a different invitation from "312 other routines carry this
# plan", and the reader is the one who should decide which is worth a detour. So
# the count travels and nothing is thresholded away -- a cut-off invented in the
# query is a filter the reader cannot see (design rule 1).
#
# What the query does decide is the *order*, and it is rarity ascending in every
# one of these, which is the opposite of the obvious. A thing shared with three
# routines is a piece of work you can hold in your head; the same thing shared
# with three hundred is a category, and a category is not a detour. The panel
# bounds the list for space, so what sorts to the top has to be what a reader can
# act on -- and the count beside it is what lets them disagree.
# --------------------------------------------------------------------------- #

# Governance kin: what else was this change about?
#
# Ordered by **rarity**, which is the opposite of the obvious. A plan carried by
# three routines is a piece of work you can hold in your head; the same plan
# carried by three hundred is a category, and a category is not a detour. Nothing
# is dropped for being large -- the count is shown and the reader chooses -- but
# what sorts to the top is what is small enough to look at.
THREAD_GOVERNANCE = """
SELECT mine.value                     AS value,
       MIN(mine.kind)                 AS kind,
       COUNT(DISTINCT other.owner_id) AS others
FROM annotations mine
JOIN annotations other
  ON other.value = mine.value
 AND other.owner_kind = 'routine'
 AND other.owner_id <> :id
WHERE mine.owner_id = :id AND mine.owner_kind = 'routine'
GROUP BY mine.value
ORDER BY others, mine.value
"""

# The other end of a table. This is the thread kind that finds code with **no call
# edge to the subject at all** -- two routines that never call each other and both
# write `audit_events` are coupled through the store, and nothing in a call graph
# can say so.
#
# Readers and writers are counted apart because they are different neighbours: the
# question "who else writes what I read" is the one that finds where a value comes
# from, and a single "others" total cannot answer it.
#
# **Declarers are counted too, and that was not foresight.** `spec_seals` first read
# "6 others -- 3 read, 0 write", three numbers that are each correct and cannot be
# reconciled by anybody looking at them. The missing three are `DDL`: the routines
# that *create* the table. They turned out to be the most interesting of the three
# groups -- the schema is where a table is defined -- and hiding them behind a total
# that did not add up is rule 32 in the plainest form.
#
# The three still do not partition, and must not be presented as though they did: a
# routine that reads and writes the same table is in two of them. Each says what it
# counted and none claims to be a share of the whole.
THREAD_TABLES = """
SELECT mine.tbl                             AS name,
       COUNT(DISTINCT other.routine_id)     AS others,
       COUNT(DISTINCT CASE WHEN other.direction = 'WRITE'
                           THEN other.routine_id END) AS writers,
       COUNT(DISTINCT CASE WHEN other.direction = 'READ'
                           THEN other.routine_id END) AS readers,
       COUNT(DISTINCT CASE WHEN other.direction = 'DDL'
                           THEN other.routine_id END) AS declarers,
       MAX(mine.direction = 'WRITE')        AS i_write,
       MAX(mine.direction = 'READ')         AS i_read
FROM sql_ops mine
JOIN sql_ops other ON other.tbl = mine.tbl AND other.routine_id <> :id
WHERE mine.routine_id = :id AND mine.tbl <> ''
GROUP BY mine.tbl
ORDER BY others, mine.tbl
"""

# The other end of a boundary. The endpoint is already a node in the graph
# (`bnd:KIND:target`), so following one selects the thing itself rather than a set
# standing in for it -- which is why boundaries get a node subject and tables,
# which are not nodes, get a set.
#
# **A boundary already named by a `sql_ops` row on the same line is excluded**, for
# the same reason the hover card excludes it, and here the consequence was louder:
# without it the three best threads off `write_spec_seal_atomic` were `ROLLBACK`,
# `COMMIT` and `BEGIN IMMEDIATE`, shared with 91, 87 and 84 other routines. Those
# are SQL keywords recorded as boundary targets, not endpoints anybody would want
# to visit, and following one selects a tenth of the storage layer. The tables the
# same routine touches are the real answer and they were sorted underneath.
THREAD_BOUNDARIES = """
SELECT mine.kind                         AS kind,
       mine.target                       AS target,
       COUNT(DISTINCT other.routine_id)  AS others,
       MIN(mine.direction)               AS direction
FROM boundaries mine
JOIN boundaries other
  ON other.kind = mine.kind AND other.target = mine.target
 AND other.routine_id <> :id
WHERE mine.routine_id = :id AND mine.target <> ''
  AND NOT EXISTS (SELECT 1 FROM sql_ops s
                   WHERE s.routine_id = mine.routine_id
                     AND abs(s.line - mine.line) <= 1)
  AND NOT EXISTS (SELECT 1 FROM net_calls n
                   WHERE n.routine_id = mine.routine_id
                     AND abs(n.line - mine.line) <= 1)
GROUP BY mine.kind, mine.target
ORDER BY others, mine.kind, mine.target
"""

THREAD_ARTEFACTS = """
SELECT mine.name                        AS name,
       MIN(mine.kind)                   AS akind,
       COUNT(DISTINCT other.routine_id) AS others
FROM artefacts mine
JOIN artefacts other ON other.name = mine.name AND other.routine_id <> :id
WHERE mine.routine_id = :id AND mine.name <> ''
GROUP BY mine.name
ORDER BY others, mine.name
"""

THREAD_NET = """
SELECT mine.destination                 AS target,
       MIN(mine.protocol)               AS protocol,
       COUNT(DISTINCT other.routine_id) AS others
FROM net_calls mine
JOIN net_calls other
  ON other.destination = mine.destination AND other.routine_id <> :id
WHERE mine.routine_id = :id AND mine.destination <> ''
GROUP BY mine.destination
ORDER BY others, mine.destination
"""

# --------------------------------------------------------------------------- #
# Outliers nearby
#
# The curiosity family, scoped to the package the reader is standing in. Not
# problems -- doorways. Each is a genuine measured maximum and carries its number,
# because "the most commented routine here" without the count is a claim the
# reader cannot weigh, and 264 comments and 7 comments are not the same discovery.
#
# The package is matched on the module prefix rather than through the CASE
# expression the node queries use, because here it is *known* -- the subject's own
# package -- and a prefix match says so in one line.
#
# Every one of them excludes the subject. Telling a reader that the most commented
# routine in this package is the one they are already looking at is true and is
# not a thread: there is nowhere to go.
# --------------------------------------------------------------------------- #

THREAD_MOST_COMMENTED = """
SELECT r.id, r.name, r.qualname, COUNT(*) AS n
FROM comments c
JOIN routines r ON r.id = c.routine_id
WHERE (r.module = :pkg OR r.module LIKE :pkg_dot) AND r.id <> :id
GROUP BY r.id
ORDER BY n DESC, r.qualname
LIMIT 1
"""

THREAD_MOST_CALLED = """
SELECT r.id, r.name, r.qualname, COUNT(DISTINCT c.caller_id) AS n
FROM calls c
JOIN routines r ON r.id = c.callee_id
WHERE (r.module = :pkg OR r.module LIKE :pkg_dot) AND r.id <> :id
GROUP BY r.id
ORDER BY n DESC, r.qualname
LIMIT 1
"""

# Nesting depth, measured as the qualname's segments below its module. A closure
# four factories deep is a real thing to find and there is no other record of it:
# rule 10 gave every nested routine its enclosing scope in its qualname precisely
# so that seven closures called `_close_ladybug` stay seven routines, and this
# reads that structure back out.
THREAD_DEEPEST = """
SELECT r.id, r.name, r.qualname,
       (length(r.qualname) - length(replace(r.qualname, '.', ''))) -
       (length(r.module)   - length(replace(r.module,   '.', ''))) AS depth
FROM routines r
WHERE (r.module = :pkg OR r.module LIKE :pkg_dot) AND r.id <> :id
  AND r.is_nested = 1
ORDER BY depth DESC, r.qualname
LIMIT 1
"""

# A table this package writes far more often than it reads, or the reverse. The
# lopsidedness is the doorway: something writes a great deal that nobody here
# reads back, which is either an audit log or a question.
THREAD_LOPSIDED_TABLE = """
SELECT s.tbl AS name,
       SUM(s.direction = 'WRITE') AS writes,
       SUM(s.direction = 'READ')  AS reads
FROM sql_ops s
JOIN routines r ON r.id = s.routine_id
WHERE (r.module = :pkg OR r.module LIKE :pkg_dot) AND s.tbl <> ''
GROUP BY s.tbl
HAVING writes > 0 AND reads > 0
ORDER BY MAX(CAST(writes AS REAL) / reads, CAST(reads AS REAL) / writes) DESC, s.tbl
LIMIT 1
"""

# --------------------------------------------------------------------------- #
# Following a thread
#
# What a thread's subject resolves to. Boundaries and artefacts are nodes already
# and need none of this; a governance id and a table are not nodes, so following
# one means selecting the code that carries or touches it -- the same reasoning
# `TABLE_ROUTINES` was written under, and the reason there is no invented id for
# either of them.
# --------------------------------------------------------------------------- #

GOVERNANCE_ROUTINES = """
SELECT DISTINCT a.owner_id AS node
FROM annotations a
JOIN routines r ON r.id = a.owner_id
WHERE a.value = :value AND a.owner_kind = 'routine'
ORDER BY r.qualname
"""

# Every routine a measured naming convention is about. `GLOB` rather than `LIKE`
# because the glob is the string the convention was counted with -- rule 13 says a
# claim's query must return exactly what is printed beside it, and translating the
# pattern into a second dialect on the way here would be a second population
# wearing the first one's number.
#
# Nested routines and dunders are excluded exactly as the mining pass excludes
# them: `<module>` is a name DunneFlow invents rather than one anybody chose, and
# counting them once made a convention that holds in every real case read as 92%.
CONVENTION_ROUTINES = """
SELECT r.id AS node
FROM routines r
WHERE r.is_nested = 0
  AND r.name NOT GLOB '__*__'
  AND r.name NOT GLOB '<*>'
  AND r.name GLOB :glob
ORDER BY r.qualname
"""

# Every routine whose name uses one of the program's own words.
#
# **Whole segments, never substrings**, and this is rule 5 in its most literal form. A
# term matched anywhere inside a name matches half the program: `mensor` would claim
# every `dimensions` and `groma` every `programmatic`. Rule 18 found the same defect in
# `walk.is_test_path`, where `test_` as a substring dropped the real `_test_stage.py` out
# of the map entirely -- a marker must sit at an edge of a segment.
#
# Six globs rather than one because GLOB has no alternation, and lowercased on both sides
# because GLOB is case-sensitive while a term is a word rather than an identifier. That
# costs the index on a query run once per click, which is the right way round.
TERM_ROUTINES = """
SELECT r.id AS node
FROM routines r
WHERE r.is_nested = 0
  AND r.name NOT GLOB '<*>'
  AND (   lower(r.name)   = :term
       OR lower(r.name)   GLOB :n_pre
       OR lower(r.name)   GLOB :n_suf
       OR lower(r.name)   GLOB :n_mid
       OR lower(r.module) = :term
       OR lower(r.module) GLOB :m_pre
       OR lower(r.module) GLOB :m_suf
       OR lower(r.module) GLOB :m_mid )
ORDER BY r.qualname
"""

NET_ROUTINES = """
SELECT DISTINCT n.routine_id AS node
FROM net_calls n
JOIN routines r ON r.id = n.routine_id
WHERE n.destination = :target
ORDER BY r.qualname
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
#
# **The location column is aliased `"where"`, in quotes, and the quotes are not
# decoration.** `where` is a SQL keyword and an unquoted alias is a syntax error,
# so this was `AS where_` for as long as the family existed -- while
# `documents.py` keyed the same column `Column("where", ...)`. `row.get("where")`
# returned `None`, and the "Where" cell of **every row of all eight documents**
# rendered blank. Nothing ever noticed, because nothing rendered them.
#
# Fixed at this end rather than the other because the key is the contract the
# client reads and it should not carry a SQL-syntax scar. A guard now runs every
# statement in the family and asserts that each `Column` key is a column the
# query actually returns (design rule 16), so unquoting this fails by name
# instead of emptying a column.
# --------------------------------------------------------------------------- #

DOC_ENTRYPOINTS = """
SELECT e.routine_id             AS node,
       e.name                   AS name,
       e.kind                   AS kind,
       COALESCE(r.qualname, '') AS routine,
       COALESCE(e.evidence, '') AS evidence,
       COALESCE(r.file, e.file) || ':' || COALESCE(r.line_start, 0) AS "where",
       COALESCE(r.file, e.file) AS file,
       COALESCE(r.line_start, 0) AS line
FROM entrypoints e
LEFT JOIN routines r ON r.id = e.routine_id
ORDER BY e.kind, e.name
"""

# The signature is assembled here rather than in Python so the whole document is
# one statement per section -- which is also what lets these same strings run
# client-side against sqlite-wasm later without a second implementation.
# The routine list the navigator and table mode read.
#
# It carries the **package** as well as the module, and takes it from `PACKAGE_EXPR` -- the
# same expression the disks are built from -- so a package heading in the list names a plate
# in the stack rather than a second thing that happens to share its spelling. That is the
# whole reason this is not `DOC_ROUTINES`: `documents.py` deliberately keeps the package
# expression out of its query family, and binding parameters a statement does not name is
# how two families drift into depending on each other's shape.
#
# `why` is here because table mode shows it. The signature is not: 4,734 signatures is most
# of the payload and neither the navigator nor the table has anywhere to put one.
NAV_ROUTINES = f"""
SELECT r.id           AS id,
       r.name         AS name,
       r.module       AS module,
       {PACKAGE_EXPR} AS pkg,
       COALESCE(r.docstring, '') AS why
FROM routines r
ORDER BY r.module, r.line_start
"""

# Every structure, for the navigator's own group and for the search across it. 671 rows on
# Mensores against `NAV_ROUTINES`' 4,786, riding with them because both are wanted at the
# same moment and a second request would be a second round trip for a seventh of the weight.
#
# `kind` is carried because it is what separates one of these from another: a vanished
# TYPE_ALIAS and a vanished CLASS are different news, and a list that prints only names says
# neither. The docstring is **not** carried -- the inspector fetches it per structure, and
# 535 of these have one.
NAV_STRUCTURES = f"""
SELECT s.id           AS id,
       s.name         AS name,
       s.module       AS module,
       s.kind         AS kind,
       {PACKAGE_EXPR} AS pkg
FROM structures s
ORDER BY s.module, s.line
"""

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
       r.file || ':' || r.line_start AS "where",
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
       s.file || ':' || s.line AS "where",
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
       c.file || ':' || c.line AS "where",
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
       b.file || ':' || b.line AS "where",
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
       t.file || ':' || t.line AS "where",
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
       o.file || ':' || o.line AS "where",
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
       n.file || ':' || n.line AS "where",
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

# Top-level package by routine count, **under the same expression the disks use** -- so a
# navigator row and a plate are the same thing rather than two things with one name.
#
# It used to take the second dotted segment on its own, without knowing the program root,
# and the comment here claimed it was "the same decomposition the graph's disks use". It was
# not, and `PACKAGE_SIZES` said so a hundred lines below: *two definitions of "package" in
# one dashboard is how a reader ends up comparing two numbers that were never the same
# measurement.* What neither noticed is that the navigator selects **by plate id**
# (`sel: pkg:${p.id}`), so a row the disks have no plate for selects nothing at all and the
# centre pane says "Nothing to show." with no explanation available to it.
#
# Measured, which is how it stopped being a stylistic point: on a map analysed at the parent
# directory the two agree except for the root module itself -- Mensores had **1 dead row of
# 46**, `mensores`, whose plate is `<root>` -- and on a map analysed at the package the
# second segment is a *module*, giving **36 dead rows of 48**. Tom found the second by
# clicking them.
#
# `full_pkg` was selected here and read by nothing, in this file or any other; it goes with
# the second decomposition it belonged to.
COVER_PACKAGES = f"""
SELECT {PACKAGE_EXPR} AS pkg,
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

# The routines that touch one table -- what picking a table out of the navigator
# selects.
#
# A table is deliberately *not* a node: `DOC_DB_TABLES` says so in as many words, and
# inventing an id to make a row clickable would be a link to nothing. So selecting a
# table cannot mean selecting the table; it means selecting the code that reads and
# writes it, which is the question a reader has when they click the busiest one.
#
# `routine_id` is null for an operation at module scope. Those rows are dropped here
# rather than folded into a synthetic node: the count beside the name comes from
# COVER_TABLES and counts *operations*, so the two are different populations on
# purpose, and the client says which it is showing.
TABLE_ROUTINES = """
SELECT DISTINCT o.routine_id AS node
FROM sql_ops o
WHERE o.tbl = :name AND o.routine_id IS NOT NULL
"""


# ── one table, as the thing it is ────────────────────────────────────────────────── #

# Where a table is *declared*, which is a different question from where it is used and
# is often unanswered: a program reads tables somebody else created. Rows here come from
# `sql.py` reading `CREATE TABLE` statements the code contains, so a table with no row
# is one this program only ever talks to -- a fact about it, and not a miss (design
# rule 21). More than one row is a table created in more than one file, which is also a
# fact and is why this is not a lookup returning at most one.
TABLE_DECLARED = """
SELECT name, file, line, temporary
FROM db_tables
WHERE name = :name
ORDER BY file, line
"""

# The columns as declared, in the order they were written. `idx` is the position in the
# `CREATE TABLE`, so ordering by it is quoting the statement rather than sorting it.
TABLE_COLUMNS = """
SELECT file, idx, name, type, constraints
FROM db_columns
WHERE tbl = :name
ORDER BY file, idx
"""

# Who touches this table, with what each routine does to it. `BOUNDARY_TOUCHERS` one
# subject over, and the same shape on purpose: the inspector's question at a table is
# the boundary's question -- not "what is this" but "which of my code talks to it".
#
# `routine_id` is null for an operation at module scope, and those rows are **kept**
# with a null id rather than dropped: a table written at import time is exactly the
# thing a reader is looking for, and `TABLE_ROUTINES` drops them only because its
# answer is a list of nodes to select (design rule 1).
TABLE_TOUCHERS = """
SELECT o.tbl, o.direction, o.operation, o.line, o.file,
       r.id, r.name, r.qualname, r.module,
       (SELECT COUNT(*) FROM sql_ops o2
         WHERE o2.tbl = o.tbl AND COALESCE(o2.routine_id,'') = COALESCE(o.routine_id,'')
       ) AS ops
FROM sql_ops o
LEFT JOIN routines r ON r.id = o.routine_id
WHERE o.tbl = :name
ORDER BY r.qualname, o.line
"""


# ── the package overview ─────────────────────────────────────────────────────────── #

# The orientation altitude: every package as one box, and what passes between them.
#
# Counted **from the store, not from the drawn model**. The 2.5D model stores every
# crossing twice -- once per plate, each copy ending in a shadow -- because that is what
# lets both plates lay out under the same forces (rule 23). Aggregating those would double
# every weight here, silently and plausibly. The store holds each call exactly once, so
# counting from it cannot make that mistake.
#
# Confidence does not blur (rule 6). An aggregate is CERTAIN when *any* constituent call is
# certain -- we are certain the two packages are connected, whatever we could not resolve
# about individual calls -- and INFERRED only when every one of them was inferred.
PACKAGE_EDGES = f"""
SELECT {package_expr("caller.module")} AS src,
       {package_expr("callee.module")} AS dst,
       COUNT(*)                                          AS weight,
       MAX(c.confidence = 'CERTAIN')                     AS any_certain
FROM calls c
JOIN routines caller ON caller.id = c.caller_id
JOIN routines callee ON callee.id = c.callee_id
WHERE c.callee_id IS NOT NULL
  AND c.external = 0
GROUP BY src, dst
HAVING src <> dst
ORDER BY weight DESC
"""

# A package reaching outside the program. The boundary kind is the destination, which is
# what design rule 8 asks for: an external is a first-class node badged as outside our
# control, not an edge that stops at the edge of the picture.
PACKAGE_BOUNDARY_EDGES = f"""
SELECT {package_expr("r.module")} AS src,
       b.kind                                       AS dst,
       COUNT(*)                                     AS weight,
       COUNT(DISTINCT b.target)                     AS targets
FROM boundaries b
JOIN routines r ON r.id = b.routine_id
GROUP BY src, dst
ORDER BY weight DESC
"""

# Which packages hold a way in. An entrypoint's package is where a reader starts, so the
# overview puts them first and the layout ranks outward from them.
PACKAGE_ENTRYPOINTS = f"""
SELECT DISTINCT {package_expr("r.module")} AS pkg
FROM entrypoints e
JOIN routines r ON r.id = e.routine_id
"""


# The program root: the one leading segment every module shares, or nothing.
#
# `COVER_PACKAGES` says it takes the second segment "without knowing the program root", and
# this is that root, asked for directly. It exists because a field that shortens a module
# has to know which end carries information: **all 566 of Mensores' modules begin
# `mensores.`**, so a rule keeping both ends of a name spends its head on a word that is
# identical on every row -- and, for a three-segment module, elides the *package* to keep
# it.
#
# Grouped rather than assumed. One row means every module agrees and the segment is a root;
# more than one means the program has several top-level names and there is nothing to strip.
# `mensores` is itself a package id in `COVER_PACKAGES` -- top-level modules belong to it --
# which is exactly why "a segment that names a package" is the wrong test and this one is
# right.
COVER_ROOT = """
SELECT CASE WHEN instr(module, '.') = 0 THEN module
            ELSE substr(module, 1, instr(module, '.') - 1) END AS head,
       COUNT(*) AS n
FROM (SELECT DISTINCT module FROM routines)
GROUP BY head
"""


# Package sizes under the *same* expression the disks use, so the overview and the stack
# agree about what a package is. `COVER_PACKAGES` now asks through this expression too --
# it used to take the second segment without knowing the program root, and this note stood
# beside that difference calling it a hazard for two months before anybody clicked one of
# the rows it produced. One expression, three callers (rule 51). `COVER_ROOT` is still its
# own question and still separate: it asks what prefix a *narrow field* may drop, which is
# a display decision rather than a decomposition.
PACKAGE_SIZES = f"""
SELECT {PACKAGE_EXPR} AS pkg, COUNT(*) AS n
FROM routines
GROUP BY pkg
ORDER BY n DESC
"""


# ── the code browser ─────────────────────────────────────────────────────────────── #
#
# What separates this from `less` is that almost every fact table here carries a `file`
# *and* a `line`. A file drawn with those beside it is the map and the code in one place.
#
# Counted per file rather than correlated per row: five small aggregates merged in Python
# beat one query with five correlated subqueries over 4,734 routines, and each of these is
# a plain index scan. `<module>` is excluded from the routine count because it is the
# synthetic scope that owns what no function does (rule 18) -- real to the graph, and not a
# routine anybody wrote.

CODE_FILES = """
SELECT f.path AS path, f.module AS module, f.lang AS lang, f.errors AS errors
FROM files f
ORDER BY f.path
"""

CODE_FILE_ROUTINE_COUNTS = """
SELECT file, COUNT(*) AS n FROM routines WHERE name <> '<module>' GROUP BY file
"""

CODE_FILE_BOUNDARY_COUNTS = """
SELECT file, COUNT(*) AS n FROM boundaries GROUP BY file
"""

# Governance ids per file, over both owners. An annotation hangs off a routine or a
# structure, never off a file, so the file has to be reached through its owner -- and
# leaving either side out would under-count a file whose ids all sit on class bodies.
CODE_FILE_ID_COUNTS = """
SELECT file, COUNT(DISTINCT value) AS n FROM (
  SELECT r.file AS file, a.value AS value
    FROM annotations a JOIN routines r ON r.id = a.owner_id
   WHERE a.owner_kind = 'routine'
  UNION ALL
  SELECT s.file AS file, a.value AS value
    FROM annotations a JOIN structures s ON s.id = a.owner_id
   WHERE a.owner_kind = 'structure'
)
GROUP BY file
"""

CODE_FILE_COMMENT_COUNTS = """
SELECT r.file AS file, COUNT(*) AS n
FROM comments c JOIN routines r ON r.id = c.routine_id
GROUP BY r.file
"""

# ── one file, and what every line of it is ───────────────────────────────────────── #

CODE_DEFS_ROUTINES = """
SELECT r.id AS id, r.name AS name, r.qualname AS qualname,
       r.line_start AS line, r.line_end AS line_end,
       r.is_method AS is_method, COALESCE(r.class_name, '') AS class_name,
       r.visibility AS visibility, r.is_nested AS is_nested
FROM routines r
WHERE r.file = :file
ORDER BY r.line_start
"""

CODE_DEFS_STRUCTURES = """
SELECT s.id AS id, s.name AS name, s.kind AS kind, s.line AS line
FROM structures s
WHERE s.file = :file
ORDER BY s.line
"""

# The clickable half. `callee_id` is the whole reason a name in the source can be a link
# without matching on a name (rule 5): the resolver already decided which routine this call
# reaches, and this only has to find where on the line it was written.
CODE_CALLS = """
SELECT c.line AS line, c.callee_expr AS expr, c.callee_id AS id,
       c.confidence AS confidence, c.external AS external,
       c.at_boundary AS at_boundary, c.ambiguous AS ambiguous
FROM calls c
WHERE c.file = :file
ORDER BY c.line
"""

CODE_BOUNDARIES = """
SELECT b.line AS line, b.kind AS kind, b.direction AS direction,
       b.target AS target, b.evidence AS evidence
FROM boundaries b
WHERE b.file = :file
ORDER BY b.line
"""

CODE_SQL_OPS = """
SELECT o.line AS line, o.operation AS operation, o.direction AS direction,
       COALESCE(o.tbl, '') AS tbl
FROM sql_ops o
WHERE o.file = :file
ORDER BY o.line
"""

CODE_CONSTANTS = """
SELECT k.line AS line, k.name AS name, k.module AS module,
       COALESCE(k.type, '') AS type, k.is_final AS is_final
FROM constants k
WHERE k.file = :file
ORDER BY k.line
"""

CODE_IMPORTS = """
SELECT i.line AS line, i.module AS module, i.name AS name,
       COALESCE(i.alias, '') AS alias, i.is_from AS is_from
FROM imports i
WHERE i.file = :file
ORDER BY i.line
"""

CODE_ARTEFACTS = """
SELECT a.line AS line, a.name AS name, a.ext AS ext, a.kind AS kind,
       a.is_pattern AS is_pattern
FROM artefacts a
WHERE a.file = :file
ORDER BY a.line
"""

CODE_NET_CALLS = """
SELECT n.line AS line, n.protocol AS protocol, COALESCE(n.verb, '') AS verb,
       COALESCE(n.destination, '') AS destination,
       COALESCE(n.timeout, '') AS timeout, COALESCE(n.retries, '') AS retries
FROM net_calls n
WHERE n.file = :file
ORDER BY n.line
"""

CODE_DB_TABLES = """
SELECT t.line AS line, t.name AS name, t.temporary AS temporary
FROM db_tables t
WHERE t.file = :file
ORDER BY t.line
"""

# Reached through the owner for the same reason the per-file counts are: an annotation
# hangs off a routine or a structure, and a file whose ids all sit on class bodies would
# show none of them if only one side were asked.
# A call that left this program, pinned by an import rather than guessed.
#
# `calls.external` is set for three genuinely different things and only one of them earns a
# mark in the gutter. **Builtins**: 11,256 of Mensores' 23,829, and `len(x)` is internal
# computation, which CLAUDE.md says in as many words is not the subject. **Boundary
# touches**: 3,943, every one of which already has a boundary or a `sql_ops` row on the same
# line, so marking them here is rule 40 for the third time. What is left is a call into
# somebody else's code, and that is worth saying.
#
# The first segment must be a name this file imported. Without that test `out.append`,
# `payload.get` and `super.__init__` read as library calls -- they are methods on local
# variables, and telling them apart from `json.loads` by shape alone is impossible. Rule 5:
# match on something pinned, never on a bare name. It takes 8,630 down to 3,086, and every
# one of the 5,544 dropped is a method on something local.
CODE_LIBRARY_CALLS = """
SELECT c.line AS line, c.callee_expr AS expr,
       substr(c.callee_expr, 1, instr(c.callee_expr, '.') - 1) AS via
FROM calls c
WHERE c.file = :file
  AND c.external = 1
  AND c.at_boundary = 0
  AND c.callee_expr LIKE '%.%'
  AND EXISTS (SELECT 1 FROM imports i
              WHERE i.file = c.file
                AND i.alias = substr(c.callee_expr, 1, instr(c.callee_expr, '.') - 1))
ORDER BY c.line
"""

CODE_ANNOTATIONS = """
SELECT line, kind, value FROM (
  SELECT a.line AS line, a.kind AS kind, a.value AS value
    FROM annotations a JOIN routines r ON r.id = a.owner_id
   WHERE a.owner_kind = 'routine' AND r.file = :file
  UNION
  SELECT a.line, a.kind, a.value
    FROM annotations a JOIN structures s ON s.id = a.owner_id
   WHERE a.owner_kind = 'structure' AND s.file = :file
)
ORDER BY line
"""


# --------------------------------------------------------------------------- #
# FOLDS -- a set of routines asked about as one thing
#
# A diagram box is a **fold**: a class and its methods, or a file and its loose
# functions. It has no id in the store, so every question about it is a question
# about the set of routines it stands for.
#
# Keyed by a JSON array through `json_each` rather than by generated `IN (...)`
# placeholders. Three reasons, and the third is the one that decided it: a JSON
# array is one bound parameter, so a fold larger than SQLite's parameter limit is
# not a different code path; the SQL text is constant, so it can be quoted beside
# the claim it produces (design rule 13) and reproduced with `dunneflow query`;
# and a query built by string concatenation per call cannot be prepared once.
#
# Every one of these carries `routine_id` back. A fold's rows are the union of its
# members' rows, and a row that cannot say which member it came from has lost the
# thing that makes it clickable (rule 30).
# --------------------------------------------------------------------------- #

FOLD_MEMBERS = """
SELECT r.id, r.name, r.qualname, r.module, r.file, r.line_start, r.line_end,
       r.returns, r.is_async, r.is_method, r.class_name, r.visibility
FROM routines r
JOIN json_each(:ids) j ON j.value = r.id
ORDER BY r.line_start, r.qualname
"""

# The members' signatures, in one pass rather than one query per member. Grouped
# by owner in Python, because `signature_parts` renders a whole parameter list and
# splitting that across rows would be a second answer to what a signature is.
FOLD_PARAMS = """
SELECT p.routine_id, p.idx, p.name, p.type, p.dflt, p.kind
FROM params p
JOIN json_each(:ids) j ON j.value = p.routine_id
ORDER BY p.routine_id, p.idx
"""

FOLD_BOUNDARIES = """
SELECT b.routine_id, b.kind, b.direction, b.target, b.line, b.evidence, b.salience
FROM boundaries b
JOIN json_each(:ids) j ON j.value = b.routine_id
ORDER BY b.salience DESC, b.line
"""

FOLD_SQL_OPS = """
SELECT s.routine_id, s.operation, s.direction, s.tbl, s.sql, s.line
FROM sql_ops s
JOIN json_each(:ids) j ON j.value = s.routine_id
ORDER BY s.line
"""

FOLD_NET_CALLS = """
SELECT n.routine_id, n.expr, n.protocol, n.verb, n.destination, n.port,
       n.is_async, n.awaited, n.in_async_routine, n.timeout, n.retries, n.tls,
       n.payload, n.headers, n.topic, n.ack, n.line
FROM net_calls n
JOIN json_each(:ids) j ON j.value = n.routine_id
ORDER BY n.line
"""

FOLD_ARTEFACTS = """
SELECT a.routine_id, a.name, a.stem, a.ext, a.kind, a.line, a.literal, a.is_pattern
FROM artefacts a
JOIN json_each(:ids) j ON j.value = a.routine_id
ORDER BY a.line
"""

FOLD_ANNOTATIONS = """
SELECT a.owner_id AS routine_id, a.kind, a.value, a.line, a.text
FROM annotations a
JOIN json_each(:ids) j ON j.value = a.owner_id
WHERE a.owner_kind = 'routine'
ORDER BY a.line
"""

# Comments are counted rather than listed. A fold of 61 methods carries hundreds,
# and the inspector's Governance section places each one against the line it
# explains -- which is a claim about one routine and reads as noise about sixty.
# The count says there is something there and the member row is one click away.
FOLD_COMMENTS = """
SELECT c.routine_id, COUNT(*) AS n
FROM comments c
JOIN json_each(:ids) j ON j.value = c.routine_id
GROUP BY c.routine_id
"""


# What a fold looks like from the inside: the calls among its own members, and the
# calls that leave it. The second level of the diagram is drawn from these two.
#
# `NOT IN (SELECT value FROM json_each(:ids))` rather than a second join, because the
# question is about *absence* from the set and a join cannot express that. Both are
# grouped, so what comes back is one row per connection rather than one per call site --
# a picture wants the connection, and the call sites are what `/api/flow` is for.
FOLD_INNER_CALLS = """
SELECT c.caller_id AS src, c.callee_id AS dst, COUNT(*) AS weight,
       MAX(c.confidence = 'CERTAIN') AS certain
FROM calls c
JOIN json_each(:ids) a ON a.value = c.caller_id
JOIN json_each(:ids) b ON b.value = c.callee_id
WHERE c.at_boundary = 0 AND c.caller_id <> c.callee_id
GROUP BY c.caller_id, c.callee_id
"""

FOLD_CALLS_OUT = """
SELECT c.caller_id AS mine, c.callee_id AS other, COUNT(*) AS weight
FROM calls c
JOIN json_each(:ids) a ON a.value = c.caller_id
WHERE c.callee_id IS NOT NULL AND c.at_boundary = 0
  AND c.callee_id NOT IN (SELECT value FROM json_each(:ids))
GROUP BY c.caller_id, c.callee_id
"""

FOLD_CALLS_IN = """
SELECT c.callee_id AS mine, c.caller_id AS other, COUNT(*) AS weight
FROM calls c
JOIN json_each(:ids) b ON b.value = c.callee_id
WHERE c.at_boundary = 0
  AND c.caller_id NOT IN (SELECT value FROM json_each(:ids))
GROUP BY c.callee_id, c.caller_id
"""

# --------------------------------------------------------------------------- #
# One edge of the diagram, opened: every call site between two sets of routines.
#
# Two id sets, two JSON arrays, the same `json_each` idiom the fold queries use --
# constant SQL text, one bound parameter per side, and no limit to trip over.
#
# **Grouped by nothing.** The fold queries return one row per *connection* because a
# picture wants the connection; this returns one row per **call site**, because the
# question an edge answers is "what actually passes along here" and an aggregate
# cannot say it. `site_id` comes back so the arguments can be hung off the right one:
# two identical expressions on one line are two calls (287 of them on Mensores).
# --------------------------------------------------------------------------- #

FLOW_CALL_SITES = """
SELECT c.site_id, c.caller_id, c.callee_id, c.callee_expr, c.file, c.line,
       c.confidence, c.external, c.ambiguous,
       rc.qualname AS caller_name, rc.class_name AS caller_class,
       re.qualname AS callee_name, re.file AS callee_file,
       re.line_start AS callee_line, re.returns AS callee_returns,
       re.is_async AS callee_async, re.is_method AS callee_method
FROM calls c
JOIN json_each(:src) a ON a.value = c.caller_id
JOIN json_each(:dst) b ON b.value = c.callee_id
LEFT JOIN routines rc ON rc.id = c.caller_id
LEFT JOIN routines re ON re.id = c.callee_id
WHERE c.at_boundary = 0
ORDER BY c.file, c.line, c.site_id
"""

# The arguments, for a set of call sites named by the answer above. Kept a second query
# rather than joined into the first because a call site with four arguments would
# otherwise repeat every column of its own row four times, and the call site is the
# thing being listed.
FLOW_CALL_ARGS = """
SELECT a.site_id, a.idx, a.expr, a.keyword, a.splat
FROM call_args a
JOIN json_each(:sites) j ON j.value = a.site_id
ORDER BY a.site_id, a.idx
"""

# An edge into a boundary reuses `FOLD_SQL_OPS`, `FOLD_NET_CALLS`, `FOLD_BOUNDARIES` and
# `FOLD_ARTEFACTS` **as they are**, scoped to the routines on the near side. No aliases:
# `FLOW_SQL_OPS = FOLD_SQL_OPS` would be a second name for one query, and two names are
# how two answers to one question begin (rule 13). Which operations belong to the edge is
# decided in Python against the box the reader clicked, because `sql_ops` records a table
# and `boundaries` records a kind, and one query asked to know both is two questions
# wearing one name.

# The boundaries of a set of routines that **no more specific record already names**.
# Rule 40, set-scoped: 991 of Mensores' 1,316 DATABASE boundaries sit on a line with a
# `sql_ops` row and all twenty NETWORK boundaries sit on a `net_calls` row, so listing
# both is listing one act twice. The exclusion is per line and not per routine, because
# 43 routines open a connection and run nothing -- the boundary is the only record of
# what they do, and a coarser rule blanks them. The one-line tolerance is a judgment,
# stated as one: the two detectors disagree by a line on a multi-line statement,
# recording the call site and the statement start.
FLOW_BOUNDARIES_UNNAMED = """
SELECT b.routine_id, b.kind, b.direction, b.target, b.line, b.evidence, b.salience
FROM boundaries b
JOIN json_each(:ids) j ON j.value = b.routine_id
WHERE NOT EXISTS (SELECT 1 FROM sql_ops s
                   WHERE s.routine_id = b.routine_id AND abs(s.line - b.line) <= 1)
  AND NOT EXISTS (SELECT 1 FROM net_calls n
                   WHERE n.routine_id = b.routine_id AND abs(n.line - b.line) <= 1)
ORDER BY b.salience DESC, b.line
"""


# --------------------------------------------------------------------------- #
# Curiosities: the doorway panel, program-wide
#
# Design rule 15's fourth piece of furniture. `THREAD_*` above answers the same
# family of questions scoped to the package a reader is standing on; these ask it
# of the whole program.
#
# **Every number printed beside a curiosity comes out of the one statement that
# found it.** That is design rule 13 taken literally: the query a card offers is
# not a query *about* the number, it is the query that returned it, and it runs
# verbatim through `dunneflow query`. So each of these returns the extremum, the
# **median**, how many things tie with the extremum, and the size of the
# population it came out of -- four numbers a reader can weigh against each other,
# from one scan they can reproduce.
#
# The middle is not decoration. Every program has a most-commented routine, so a
# maximum on its own is a claim nobody can weigh: 1,126 comments against a middle
# of 3 is a discovery and 3 levels of nesting against a middle of 2 is not, and
# the panel has to be able to say the second as plainly as the first. Rule 14's
# lesson -- at enough measures, something always comes out furthest -- in the one
# place in this product that goes looking for extremes on purpose.
#
# Every one is a **measurement, never a judgement.** A long routine, a wide
# parameter list and a lopsided table are all things worth looking at and none of
# them is a finding; `anomalies.py` is where a claim about what is *wrong* lives,
# and it states a blind spot because it makes one. These do not, and must not read
# as though they did.
#
# The shape is the same nine times over and it is load-bearing for cost. `m`
# materialises **only the key and the measure** -- never a name, never a join --
# and the extremum's name is resolved once, for the one row that won. Written the
# obvious way instead, with the join inside `m`, the call-argument family joined
# 43,926 rows to `calls` and `routines` and did it four times over, once per
# reference to the CTE: **7.47 s, against 54 ms for this.** `MATERIALIZED` is what
# stops the recomputation and is stated rather than hoped for.
# --------------------------------------------------------------------------- #

# Comments on one routine. `<module>` is a real node -- the synthetic module scope
# that owns everything no function does (rule 18) -- and it is genuinely the most
# commented thing in most files, so it is left in and rendered as the module it is.
CURIO_COMMENTS = """
WITH m AS MATERIALIZED (
    SELECT c.routine_id AS k, COUNT(*) AS n FROM comments c GROUP BY c.routine_id),
top AS (SELECT k, n FROM m ORDER BY n DESC, k LIMIT 1)
SELECT r.id AS node, r.name AS name, r.qualname AS qualname,
       r.file || ':' || r.line_start AS whence, top.n AS value,
       (SELECT n FROM m ORDER BY n LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM m)) AS middle,
       (SELECT COUNT(*) FROM m WHERE m.n = top.n)                             AS ties,
       (SELECT COUNT(*) FROM m)                                               AS population
FROM top JOIN routines r ON r.id = top.k
"""

# Callers of one routine, counted **distinct**: a routine calling another twice is
# one caller, and the number says callers rather than call sites (rule 32).
CURIO_CALLERS = """
WITH m AS MATERIALIZED (
    SELECT c.callee_id AS k, COUNT(DISTINCT c.caller_id) AS n
    FROM calls c WHERE c.callee_id IS NOT NULL AND c.callee_id <> '' GROUP BY c.callee_id),
top AS (SELECT k, n FROM m ORDER BY n DESC, k LIMIT 1)
SELECT r.id AS node, r.name AS name, r.qualname AS qualname,
       r.file || ':' || r.line_start AS whence, top.n AS value,
       (SELECT n FROM m ORDER BY n LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM m)) AS middle,
       (SELECT COUNT(*) FROM m WHERE m.n = top.n)                             AS ties,
       (SELECT COUNT(*) FROM m)                                               AS population
FROM top JOIN routines r ON r.id = top.k
"""

# Lines in one routine. The declaration's span, not a report on what is inside it:
# this tool does not read control flow and does not start here. Size is a measure
# real standards are written about, and how long a routine is is a fact about the
# shape of the map -- so it is reported flatly, with the middle beside it, and
# implies nothing about whether it should be shorter.
#
# `<module>` is excluded, and this is the one family it must be: the module scope
# spans its whole file, so it would win every time and would be measuring files.
CURIO_LINES = """
WITH m AS MATERIALIZED (
    SELECT r.id AS k, r.line_end - r.line_start + 1 AS n
    FROM routines r WHERE r.name <> '<module>' AND r.line_end >= r.line_start),
top AS (SELECT k, n FROM m ORDER BY n DESC, k LIMIT 1)
SELECT r.id AS node, r.name AS name, r.qualname AS qualname,
       r.file || ':' || r.line_start AS whence, top.n AS value,
       (SELECT n FROM m ORDER BY n LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM m)) AS middle,
       (SELECT COUNT(*) FROM m WHERE m.n = top.n)                             AS ties,
       (SELECT COUNT(*) FROM m)                                               AS population
FROM top JOIN routines r ON r.id = top.k
"""

# Parameters on one routine -- what moves *in*, which is squarely this tool's
# subject. The population is routines that take any at all, so the middle is the
# middle of those rather than of everything including the nullary ones.
CURIO_PARAMS = """
WITH m AS MATERIALIZED (
    SELECT p.routine_id AS k, COUNT(*) AS n FROM params p GROUP BY p.routine_id),
top AS (SELECT k, n FROM m ORDER BY n DESC, k LIMIT 1)
SELECT r.id AS node, r.name AS name, r.qualname AS qualname,
       r.file || ':' || r.line_start AS whence, top.n AS value,
       (SELECT n FROM m ORDER BY n LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM m)) AS middle,
       (SELECT COUNT(*) FROM m WHERE m.n = top.n)                             AS ties,
       (SELECT COUNT(*) FROM m)                                               AS population
FROM top JOIN routines r ON r.id = top.k
"""

# How deep a closure is nested, read out of the qualname the way `THREAD_DEEPEST`
# reads it: rule 10 gave every nested routine its enclosing scope precisely so that
# seven closures called `_close_ladybug` stay seven routines, and the segments below
# the module are the depth. Ties are the norm here rather than the exception, which
# is why every one of these carries a tie count.
CURIO_DEPTH = """
WITH m AS MATERIALIZED (
    SELECT r.id AS k,
           (length(r.qualname) - length(replace(r.qualname, '.', ''))) -
           (length(r.module)   - length(replace(r.module,   '.', ''))) AS n
    FROM routines r WHERE r.is_nested = 1),
top AS (SELECT k, n FROM m ORDER BY n DESC, k LIMIT 1)
SELECT r.id AS node, r.name AS name, r.qualname AS qualname,
       r.file || ':' || r.line_start AS whence, top.n AS value,
       (SELECT n FROM m ORDER BY n LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM m)) AS middle,
       (SELECT COUNT(*) FROM m WHERE m.n = top.n)                             AS ties,
       (SELECT COUNT(*) FROM m)                                               AS population
FROM top JOIN routines r ON r.id = top.k
"""

# How many boundaries one routine reaches -- the thing that touches the outside
# world in the most places. Counted as recorded, which means a routine running
# seventeen statements against a database has seventeen; rule 40's de-duplication
# is about not stating one act twice on **one card**, and here there is one number.
CURIO_BOUNDARIES = """
WITH m AS MATERIALIZED (
    SELECT b.routine_id AS k, COUNT(*) AS n FROM boundaries b GROUP BY b.routine_id),
top AS (SELECT k, n FROM m ORDER BY n DESC, k LIMIT 1)
SELECT r.id AS node, r.name AS name, r.qualname AS qualname,
       r.file || ':' || r.line_start AS whence, top.n AS value,
       (SELECT n FROM m ORDER BY n LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM m)) AS middle,
       (SELECT COUNT(*) FROM m WHERE m.n = top.n)                             AS ties,
       (SELECT COUNT(*) FROM m)                                               AS population
FROM top JOIN routines r ON r.id = top.k
"""

# The longest thing anybody passed to anything, in characters of the expression **as
# written** (rules 8 and 75 -- never re-rendered, never shortened). The subject is the
# routine that wrote it, because an argument is not a node; `whence` is where to look.
CURIO_ARGUMENT = """
WITH m AS MATERIALIZED (
    SELECT a.site_id AS k, a.idx AS i, length(a.expr) AS n FROM call_args a),
top AS (SELECT k, i, n FROM m ORDER BY n DESC, k, i LIMIT 1)
SELECT c.caller_id AS node, r.name AS name, r.qualname AS qualname,
       c.file || ':' || c.line AS whence, top.n AS value,
       (SELECT n FROM m ORDER BY n LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM m)) AS middle,
       (SELECT COUNT(*) FROM m WHERE m.n = top.n)                             AS ties,
       (SELECT COUNT(*) FROM m)                                               AS population
FROM top JOIN calls c ON c.site_id = top.k JOIN routines r ON r.id = c.caller_id
"""

# The longest constant value, in characters. `_literal` unparses these on the way in,
# so unlike an argument this is a rendering rather than the source text -- and it is
# still never truncated (rule 8), which is what makes the number mean anything.
CURIO_CONSTANT = """
WITH m AS MATERIALIZED (
    SELECT k.module || '.' || k.name AS k, length(k.value) AS n FROM constants k),
top AS (SELECT k, n FROM m ORDER BY n DESC, k LIMIT 1)
SELECT 'const:' || top.k AS node, c.name AS name, top.k AS qualname,
       c.file || ':' || c.line AS whence, top.n AS value,
       (SELECT n FROM m ORDER BY n LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM m)) AS middle,
       (SELECT COUNT(*) FROM m WHERE m.n = top.n)                             AS ties,
       (SELECT COUNT(*) FROM m)                                               AS population
FROM top JOIN constants c ON c.module || '.' || c.name = top.k
"""

# The most lopsided table: read far more often than it is written, or the reverse.
# The lopsidedness is the doorway -- something writes a great deal nobody reads back,
# which is either an audit log or a question.
#
# A table is **not a node** (`queries.py` wrote that down before anything needed it),
# so `node` is empty and the subject is the code that touches it. Both sides must be
# non-zero: a table only ever written is not lopsided, it is write-only, and dividing
# by nothing would rank it above everything real for ever.
CURIO_TABLE = """
WITH m AS MATERIALIZED (
    SELECT s.tbl AS k,
           SUM(s.direction = 'WRITE') AS writes, SUM(s.direction = 'READ') AS reads,
           MAX(CAST(SUM(s.direction = 'WRITE') AS REAL) / SUM(s.direction = 'READ'),
               CAST(SUM(s.direction = 'READ')  AS REAL) / SUM(s.direction = 'WRITE')) AS n
    FROM sql_ops s WHERE s.tbl <> '' GROUP BY s.tbl
    HAVING SUM(s.direction = 'WRITE') > 0 AND SUM(s.direction = 'READ') > 0),
top AS (SELECT k, writes, reads, n FROM m ORDER BY n DESC, k LIMIT 1)
SELECT '' AS node, top.k AS name, '' AS qualname,
       top.writes || ' written, ' || top.reads || ' read' AS whence, top.n AS value,
       (SELECT n FROM m ORDER BY n LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM m)) AS middle,
       (SELECT COUNT(*) FROM m WHERE m.n = top.n)                             AS ties,
       (SELECT COUNT(*) FROM m)                                               AS population
FROM top
"""

# The governance id the most code carries -- the WHY layer's widest thread. Counted
# over distinct owners, so a routine citing `AC-4` three times is one. A governance
# id is not a node either, so following it selects the code that carries it.
#
# **Routines only, and that is the whole of rule 32 in one clause.** An annotation's
# owner is a routine *or a structure*, so counting every owner and calling the total
# "routines" was two mistakes at once: a wrong noun, and a number the reader could
# catch out by clicking. `AC-4` has 112 routine owners and 9 structure owners, the card
# said 121 routines, and following it selected 112 with nothing to explain the gap --
# because `GOVERNANCE_ROUTINES`, which resolves the cohort, has always been scoped to
# `owner_kind = 'routine'`. The measure is now over exactly the set the subject opens.
# Found by following the card and counting what came back.
CURIO_GOVERNANCE = """
WITH m AS MATERIALIZED (
    SELECT a.value AS k, COUNT(DISTINCT a.owner_id) AS n
    FROM annotations a JOIN routines r ON r.id = a.owner_id
    WHERE a.value <> '' AND a.owner_kind = 'routine' GROUP BY a.value),
top AS (SELECT k, n FROM m ORDER BY n DESC, k LIMIT 1)
SELECT '' AS node, top.k AS name, '' AS qualname,
       (SELECT lower(MIN(a.kind)) FROM annotations a WHERE a.value = top.k) AS whence,
       top.n AS value,
       (SELECT n FROM m ORDER BY n LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM m)) AS middle,
       (SELECT COUNT(*) FROM m WHERE m.n = top.n)                             AS ties,
       (SELECT COUNT(*) FROM m)                                               AS population
FROM top
"""
