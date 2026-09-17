"""What differs between two versions of a program.

The interesting change is not *these lines moved* -- `git diff` says that better -- but
**what moves changed**: a routine that is in one and not the other, one that writes to a
table it does not write to over there, a signature whose types differ, a call that
resolves in one and not the other. That is the half a text diff cannot state, and it is
the whole reason this view exists.

**Two versions, and no claim about which is older.** One is the **base** -- the version
the whole map is showing -- and the other is the **compared**. Nothing here knows, or
pretends to know, which was written first: the only instant this tool records is when
*we* read the bytes, and a tree handed over on a memory stick has no history at all.
That is the case this view exists to serve, because it is the case where nothing else
can answer.

So the bands are named by **where a thing is**, never by what happened to it:

* **only in base** and **only in compared** -- presence, by id. `make_id` derives an id
  from a qualified name and never from a file position, so a routine keeps its identity
  when anything above it moves. A rename reads as one of each, which is honest: nothing
  in the source says the two are the same thing.
* **behaves differently** -- the same routine in both, and something it *does* differs.
* **edited only** -- the body differs and nothing it does does. This band is the largest
  in ordinary work and the least interesting, and saying so is the point: a routine
  whose internal computation changed is exactly what this tool exists not to report.

Beside the bands sit the **explanations**, which are not facts about what a routine does
and are never allowed to decide which band it is in. A rewritten comment and a rewritten
docstring are tags on the row (`comments`, `docstring`); a rewritten **module** docstring
has no routine to be a tag on and is its own lane, `modules_explained`, whose rows carry a
path because the subject is the file. Explanations are compared as prose -- see `_prose`,
which is a different canonical form from the one comments get, for a stated reason.

**Added and deleted are an interpretation, and they are not made here.** Which of the
two versions is newer is an assumption the reader owns; it is stated in the toolbar and
it is a Setting. This module reports set membership, which is a fact, and leaves the
labelling to whoever holds that assumption. The practical benefit is that changing the
assumption costs no re-query -- but the reason is that a store should not record a guess
as though it were something it read.

**No comparison key contains a position.** `calls`, `boundaries` and `sql_ops` all carry
a line, and a key including one makes every fact below an inserted import read as
changed -- thousands of false differences from one blank line. That is the argument
`make_id` was written from, one level further down, and it is the single easiest way to
render this whole view as noise.

The two graphs are joined with `ATTACH`, the same way `docs.db` has always been joined
to `graph.db`. Neither snapshot is copied, moved or rewritten to be compared.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any, NamedTuple

# The one language-specific question this module asks, and it asks it by name rather than
# by importing a parser: are these two writings the same expression. See `canonical/` --
# this module learns that a canonical form exists, never how one is made, which is what
# keeps the resolver, the renderers and this view ignorant of any particular language.
from ..canonical import canonical

# --------------------------------------------------------------------------- #
# What a routine *does*, stated per fact table as (owner column, compared columns).
#
# Every column that says what the routine does, and none that says where it sits.
# `file` and `line` are absent from every row here, deliberately -- see the module
# docstring. `calls.callee_id` is in, because a call that stopped resolving is a real
# change to what the program can be shown to do (it is how four of Mensores' routines
# changed without being edited); `callee_expr` is in beside it so a call whose *target*
# was rewritten is not silently equal to one whose resolution merely improved.
# --------------------------------------------------------------------------- #

FACTS: dict[str, tuple[str, str]] = {
    "calls":      ("caller_id",  "callee_id, callee_expr, external, at_boundary"),
    "boundaries": ("routine_id", "kind, direction, target"),
    "sql_ops":    ("routine_id", "operation, direction, tbl"),
    "net_calls":  ("routine_id", "protocol, verb, destination, port, timeout, retries"),
    "params":     ("routine_id", "idx, name, type, dflt, kind"),
}

# Owners whose facts differ between the two graphs, **either way round**. A fact only
# one side has is "this routine does something else over there" whichever side it is on,
# so both halves are asked and unioned. Neither half is the privileged one -- that is the
# same reason the bands are named for where a thing is rather than for what befell it.
#
# Each half is a complete sub-select, and that is not a matter of taste. SQLite's
# compound operators are **left-associative**, so
#
#     SELECT a EXCEPT SELECT b UNION ALL SELECT b EXCEPT SELECT a
#
# parses as `((A EXCEPT B) UNION ALL B) EXCEPT A`, which reduces to `B EXCEPT A` -- the
# gained half alone. Written that way this view reported every fact a routine acquired
# and no fact it lost, and nine tests passed over it because every one of them added
# something (rule 37). Parenthesising by putting each half in its own FROM is what makes
# the query say what its name says.
MOVED = """
SELECT o FROM (
    SELECT {owner} AS o, {cols} FROM {A}.{table}
    EXCEPT
    SELECT {owner} AS o, {cols} FROM {B}.{table}
)
UNION
SELECT o FROM (
    SELECT {owner} AS o, {cols} FROM {B}.{table}
    EXCEPT
    SELECT {owner} AS o, {cols} FROM {A}.{table}
)
"""

# What a caller *passed*, which `FACTS` cannot ask for and which is squarely the subject:
# an argument is a thing that moves. `f(db_path=None)` becoming
# `f(policy_path=project_dir / ".mensores" / "standards-policy.json")` read as no change at
# all until this existed.
#
# **Its own step rather than a sixth `FACTS` row**, and not for tidiness. Two things about it
# genuinely differ: `call_args` carries no owner, so it reaches one by joining `calls` through
# `site_id`; and its answer needs a second, verifying pass that none of the other five wants
# (see `_arguments_moved`). Five working comparisons are not disturbed to make a table look
# uniform.
#
# **`site_id` is deliberately absent from the key.** It embeds an ordinal among identical
# expressions in a caller -- `call_site_id` says so and states the residue -- so inserting a
# third `emit()` renumbers the ones after it and every argument of every renumbered site
# would read as changed. That is the module docstring's own rule arriving by a side door: not
# a line number, but a position all the same.
#
# What it costs is the mirror of what `FACTS["calls"]` already costs, and it is stated rather
# than discovered later: this is set comparison, so deleting one of two *identical* calls
# carrying *identical* arguments reads as no change. Rule 1 -- a false difference is worse
# than a missing one. Measured on Mensores' pair, both keys give the same fourteen routines,
# so the corpus does not separate them and the choice rests on the argument.
# `file` rides along and is **not** part of the comparison -- `_arguments_moved` slices it
# off before comparing. It is here because the canonical form of an expression is a question
# only that file's language can answer, and this module does not know what a language is.
ARG_FACTS = """
SELECT c.caller_id AS o, c.callee_expr, a.idx, a.expr, a.keyword, a.splat, c.file
  FROM {db}.call_args a JOIN {db}.calls c ON c.site_id = a.site_id
"""

# Every comment a routine owns, in the order it is written, for the routines living in
# files whose bytes differ.
#
# **The bound is what makes this affordable, and it is sound rather than a sample.** A
# comment is text in a file, so a file both versions hold with the same content hash cannot
# hold a comment that moved -- the same argument `filediff.py` makes when it decides which
# twelve of 628 files are worth reading, and it needs no sidecar here because
# `files.content_hash` is already in the graph. Measured on Mensores' pair: 41 ms over all
# 18,731 comment lines a side, **5.2 ms** over the fifteen files whose bytes differ, and the
# same twenty routines either way. `/api/changes` has 20 ms of headroom and the first number
# does not fit in it.
#
# A routine that moved between files is covered without a special case: whichever file lost
# it and whichever gained it both differ in bytes by having done so, so both are in the set.
CHANGED_FILES = """
SELECT path FROM (SELECT path, content_hash FROM {B}.files
                  EXCEPT SELECT path, content_hash FROM {A}.files)
UNION
SELECT path FROM (SELECT path, content_hash FROM {A}.files
                  EXCEPT SELECT path, content_hash FROM {B}.files)
"""

# `ORDER BY line`, and the line number is used to **order** rather than to key -- the
# distinction the module docstring turns on. Inserting a line above a comment block moves
# every number in it and changes no order, so nothing here is disturbed by an edit
# elsewhere; what an order does carry is that moving one comment past another is a change to
# what explains what, which it is.
COMMENTS_IN = """
SELECT c.routine_id, c.text
  FROM {db}.comments c JOIN {db}.routines r ON r.id = c.routine_id
 WHERE r.file IN ({q})
 ORDER BY c.routine_id, c.line
"""

# What a routine says about itself, for the routines living in files whose bytes differ --
# the same bound `COMMENTS_IN` carries and sound for the same reason.
#
# **Only routines that have one**, either side. A docstring removed outright shows up on one
# side and not the other, which the set comparison already reads as a difference; carrying
# 1,017 empty strings a side to say so would be the same answer at a cost.
DOCSTRINGS_IN = """
SELECT r.id, r.docstring
  FROM {db}.routines r
 WHERE r.file IN ({q}) AND r.docstring IS NOT NULL AND r.docstring <> ''
"""

# What a **module** says it is. `files.doc` and not a routine's column, because it is not a
# routine's: `<module>` is minted only where a file has module-level work, so 487 of
# Mensores' 628 files have one and the other 141 do not -- while 619 of them state what the
# module is. Hanging this on `<module>` would cover it where it happens to exist and miss it
# silently everywhere else, which is the half answer this module is written not to give.
#
# Files in **both** versions only. A file one version has and the other does not is already
# stated by the file lane, and saying it twice is rule 40's defect in a diff.
MODULE_DOCS = """
SELECT f.path, f.module, f.doc FROM {db}.files f
 WHERE f.path IN ({q}) AND f.doc IS NOT NULL AND f.doc <> ''
"""

# --------------------------------------------------------------------------- #
# What a **structure** is. A class, a dataclass, an enum, a type alias -- the things
# `structures` holds -- and the third subject in this module after the routine and the file.
#
# It was compared by nothing at all until 2026-09-02: not its presence, not what it declares,
# not what it says about itself. On Mensores' pair that hid **8 structures that appeared or
# vanished**, reported nowhere, while the page could still say "No differences found".
#
# **The subject is the structure, and that was settled by measuring the alternative.** A
# diagram box *is* a class (rule 74), so routing these rows through `state.fold` looks
# obvious and is rule 77's defect exactly: a box is built from routine nodes, so it exists
# only where a class has methods. Measured -- 192 of 671 structures would have one, **every**
# TYPE_ALIAS (88), ENUM (42) and TYPEDDICT (8) has none and never can, and **4 of the 8 rows
# that actually move have no methods**. It would have been right about the majority and
# silently wrong about the rest, which is the cheap answer's dangerous failure mode.
#
# Nothing had to be minted: `describe()` already resolves a `structures.id` and returns a
# STRUCTURE specimen with its kind, module, fields and annotations. So these rows carry an
# **id** where the four `PRESENCE` lanes carry only a name -- not an inconsistency but the
# same rule applied honestly (rule 30): emit an identity where one exists, a name where none
# does. `db_tables` has no id because a table is not a node; a structure is.
# --------------------------------------------------------------------------- #

# Present on one side and not the other. Unbounded, unlike the prose lanes below: this is an
# indexed set difference over 671 rows, not a scan of text, and a structure whose whole file
# was removed must still be reported.
STRUCTURES_ONLY = """
SELECT s.id, s.name, s.kind, s.module, s.file, s.line
  FROM {X}.structures s
 WHERE s.id NOT IN (SELECT id FROM {Y}.structures)
 ORDER BY s.module, s.name
"""

# What a structure **declares**: its kind and what it inherits. The structure equivalent of
# `FACTS` -- what the thing is, never where it sits, so no `file` and no `line` (the module
# docstring's rule, and it applies to every subject here and not only to routines).
#
# `kind` is in because DATACLASS becoming CLASS is a real change to what the program can be
# shown to do, and `bases` because losing a base class changes what a structure inherits --
# the one row that moves on Mensores' pair is exactly that.
STRUCTURE_DECL = """
SELECT id, kind, bases FROM {db}.structures
"""

# Its fields, which are what a data structure actually *holds*. `name`, `type` and `dflt`,
# and deliberately not `comment`: a field's comment is its WHY and a change to it is a real
# change, but it is a different change from what the field is -- the same reason
# `CONSTANT_VALUES` leaves `comment` out (rule 32).
#
# `idx` is **not** compared. It is a position, and reordering two fields of a dataclass
# renumbers every one after it -- the `site_id` argument in a second costume, and the module
# docstring's rule against keying on a position.
STRUCTURE_FIELDS_IN = """
SELECT structure_id, name, COALESCE(type, ''), COALESCE(dflt, '') FROM {db}.fields
"""

# What a structure says about **itself**. Bounded to the files whose bytes differ, exactly as
# the other two prose lanes are, and through the same `_changed_files` so the three cannot
# disagree about which files are worth reading (rule 51).
#
# **Only structures that have one**, either side -- `DOCSTRINGS_IN`'s reasoning, unchanged: a
# docstring removed outright is on one side and not the other, which the set comparison reads
# as a difference already.
STRUCT_DOCS_IN = """
SELECT s.id, s.docstring
  FROM {db}.structures s
 WHERE s.file IN ({q}) AND s.docstring IS NOT NULL AND s.docstring <> ''
"""

# A constant present in both versions, holding something different.
#
# `constants` has always been in `PRESENCE`, compared by name -- so a value that moved was
# invisible, `EXPECTED_SCHEMA_VERSION` going from 27 to 28 among them. A named value is a
# thing that moves, and what it holds is the whole of what it says.
#
# `value`, `type` and `is_final`, and nothing else. Not `file` or `line`, for the reason no
# key here carries a position. Not `comment`: a constant's comment is its WHY and a change to
# it is a real change, but it is a *different* change from what the constant is, and one row
# that means two things is a row that says neither (rule 32).
CONSTANT_VALUES = """
SELECT module, name, value, type, is_final FROM {db}.constants
"""

# `{B}` is the **base** and `{A}` the **compared**, everywhere in this module. The base
# is the version the dashboard is serving, which is why it is the one that is `main` when
# a comparison rides the connection the server already holds open (see `build`).
ONLY_IN_BASE = """
SELECT id, name, qualname, module, file, line_start
  FROM {B}.routines WHERE id NOT IN (SELECT id FROM {A}.routines)
 ORDER BY module, qualname
"""

ONLY_IN_COMPARED = """
SELECT id, name, qualname, module, file, line_start
  FROM {A}.routines WHERE id NOT IN (SELECT id FROM {B}.routines)
 ORDER BY module, qualname
"""

EDITED = """
SELECT y.id, y.name, y.qualname, y.module, y.file, y.line_start
  FROM {A}.routines x JOIN {B}.routines y ON y.id = x.id
 WHERE x.body_hash <> y.body_hash
 ORDER BY y.module, y.qualname
"""

RETURNS_MOVED = """
SELECT y.id AS o FROM {A}.routines x JOIN {B}.routines y ON y.id = x.id
 WHERE IFNULL(x.returns, '') <> IFNULL(y.returns, '')
"""

# Presence-only tables, as `(key, label)`.
#
# The **key** decides identity across the two revisions and is the thing a reader would
# name it by, never a row id — an id that includes a position moves for the same reason
# routines' did. `entrypoints` is the exception and has to be: `name` is not unique there
# (Mensores has fourteen ways in and a great many of them are called `main`), so identity
# needs the id.
#
# The **label** is what is printed. Those two came apart exactly once and it was visible
# from the first look at the page: keying entrypoints on `id` also *printed* the id, so
# "Ways in +3" listed three sixteen-character hashes while Tables printed `work_items` and
# Named files printed real filenames. A label is not an identity (rule 30) and neither is
# an identity a label; where they differ, both are named here rather than one standing in
# for the other.
# The **subject** is what the reader can act on, and it is a third thing again. A row that
# names something and cannot open it is design rule 16's dead control with a label on it;
# `group()` in the shell rendered every one of these as a bare `<code>`, so a constant whose
# value had moved could be read and never reached.
#
# `nav` names the route and `subject` is what that route consumes, because the four are not
# one shape -- the same discovery rule 30 records about the navigator. A constant and a
# named file are **nodes** and select as themselves. A table is not a node at all, so its
# route selects the code that reads and writes it, and the subject is the table's name. A
# way in has neither: its route wants the routines it *starts*, `ways_in()` computes them,
# and this table has no access to them -- so it declares no subject and the shell prints it
# as text. Inventing an id to make that row clickable would be a link to nothing, which is
# the sentence `queries.py` wrote down before anything needed it.
class Presence(NamedTuple):
    key: str      # identity across the two revisions
    label: str    # what is printed
    nav: str      # the navigator route, "" where the row cannot be acted on
    subject: str  # SQL for what that route consumes, "" with nav


#
# **One residue, stated rather than discovered.** The `chg` route reads its ids through
# `navIds`, which splits `data-navid` on a space -- it was written for a route that can
# carry several. A *named file* is the one subject here whose name can contain one, and such
# a row would resolve to two ids that name nothing. Mensores has 0 of them, and a constant's
# `module.name` cannot hold a space at all, so the corpus does not exercise it; it is
# recorded because the next artefact-bearing corpus might, and because the fix belongs to
# `navIds` rather than here.
PRESENCE: dict[str, Presence] = {
    "db_tables":   Presence("name", "name", "t", "name"),
    "entrypoints": Presence("id", "name || ' — ' || module", "", ""),
    "artefacts":   Presence("name", "name", "chg", "'art:' || name"),
    "constants":   Presence("module || '.' || name", "module || '.' || name",
                            "chg", "'const:' || module || '.' || name"),
}


def _attach(compared: Path, base: Path) -> sqlite3.Connection:
    """Both graphs, read-only, in one connection. Neither is opened for writing.

    `uri=True` so the ATTACHes can carry `mode=ro`. Read-only is not a nicety: rule 20
    says a read may refuse but may never repair, and a diff is the most purely
    read-only thing this tool does — it must not leave so much as a journal file beside
    a snapshot someone sealed.

    **Only for graphs this process does not already hold open.** See `build`.
    """
    conn = sqlite3.connect(":memory:", uri=True)
    conn.row_factory = sqlite3.Row
    # Absolute, because a relative path inside a `file:` URI is not the same path --
    # it produced `unable to open database: file:output/mensores/graph@...db`, which
    # names the file it could not open and still does not say why.
    conn.execute("ATTACH DATABASE ? AS compared",
                 (f"file:{compared.resolve()}?mode=ro",))
    conn.execute("ATTACH DATABASE ? AS base", (f"file:{base.resolve()}?mode=ro",))
    return conn


def _rows(conn: sqlite3.Connection, sql: str, **kw: Any) -> list[sqlite3.Row]:
    return conn.execute(sql.format(**kw)).fetchall()


def _arguments_moved(conn: sqlite3.Connection, A: str, B: str) -> set[str]:
    """Routines that pass something different, in two passes.

    **The cheap pass says which routines the expensive one is worth running on**, which is
    the shape `filediff.py` already uses: there, equal content hashes decide which twelve of
    628 files `difflib` reads. Measured warm on Mensores' pair -- 43,926 arguments against
    43,464, 53 callers differing as written and 13 still differing once canonicalised:

        one scan a side, compared as written    188 ms
        canonicalising only what that flagged    17 ms

    Canonicalising both corpora outright is 556 ms for the same answer.

    **Two scans and a set comparison, rather than `EXCEPT` in SQL**, and it was chosen by
    measurement: the compound form is 364 ms because it sorts both sides twice, once per
    direction. A `group_concat` digest per caller is faster still at 164 ms and is **not**
    used -- SQLite does not specify the order an aggregate concatenates in, so two identical
    argument sets laid out differently in two files would digest differently and report a
    difference that is not there. Rule 1, for 24 ms.

    **The second pass is what keeps this out of the wrong band.** Arguments are stored as
    written and never re-rendered (rules 8 and 75), which is right for a reader who wants to
    find the string in the file and wrong for a comparison: Mensores has a `typer.echo` whose
    message was re-wrapped across two lines without one character of its content changing,
    and comparing what was written puts it in *behaves differently* -- next to a band that
    says *edited only, and nothing it does changed*. Rule 1: a false difference tells the
    reader something moved when it did not. Fourteen routines survive the first pass and
    thirteen survive both.

    **This module still does not know what a language is.** It asks `extractors.canonical`,
    handing it the file the expression came from; how a canonical form is made stays inside
    the extractor that owns the suffix, and a suffix nobody claims compares as written.
    """
    def side(db: str) -> dict[str, list[tuple[Any, ...]]]:
        # **Plain tuples, on a cursor of its own.** This is the one query here that reads
        # every row of the largest table in the store -- 43,926 arguments a side -- and
        # building a `sqlite3.Row` for each is 202 ms against 165 for the tuples SQLite
        # already has. Set on the *cursor*: `conn` may be the connection the whole dashboard
        # shares, and every other query on it is written against `Row`'s by-name access.
        cur = conn.cursor()
        cur.row_factory = None
        out: dict[str, list[tuple[Any, ...]]] = {}
        for owner, callee, idx, expr, keyword, splat, file in cur.execute(
                ARG_FACTS.format(db=db)):
            if owner:
                out.setdefault(owner, []).append(
                    (callee, idx, expr, keyword, splat, file))
        return out

    def written(rows: list[tuple[Any, ...]]) -> set[tuple[Any, ...]]:
        return {t[:5] for t in rows}

    def meant(rows: list[tuple[Any, ...]]) -> set[tuple[Any, ...]]:
        # A splat is a call-site form rather than an expression -- neither `**kwargs` nor
        # `*items` parses on its own, wrapped in brackets or not -- so it is compared as
        # written.
        #
        # **This branch changes no answer**, and it is kept anyway with that said out loud.
        # `canonical` would return every one of these unchanged through its own fallback, so
        # removing the test is behaviourally invisible; a mutation of it survives, and the
        # mutation is the weak one rather than the guard (rule 59's companion). What it buys
        # is 49 parse attempts not made on Mensores, and a reader not having to work out
        # whether splats were considered.
        return {(ce, i, e if sp else canonical(e, f), k, sp)
                for ce, i, e, k, sp, f in rows}

    here, there = side(A), side(B)
    return {rid for rid in here.keys() | there.keys()
            if written(here.get(rid, [])) != written(there.get(rid, []))
            and meant(here.get(rid, [])) != meant(there.get(rid, []))}


def _comments_moved(conn: sqlite3.Connection, A: str, B: str) -> set[str]:
    """Routines the two versions **explain** differently.

    The WHY layer, and the only one the code itself never carries. `FACTS` compares what a
    routine *does*; this compares what somebody wrote down about it, which is why it is its
    own band rather than a sixth fact kind (see `build`).

    **What was wrong before this existed, in three different ways.** A comment block leading
    a definition sits *above* the `def`, so it is outside that routine's `line_start` and
    outside its `body_hash`. Rewrite one and:

    * in a file with module-level work -- 487 of Mensores' 628 -- the change surfaces as
      `<module>` in *edited only*, which names the file rather than the routine whose intent
      was rewritten and files the WHY under "internal computation", the one thing this tool
      says it exists not to report;
    * in a file with none -- the other 141 -- nothing surfaces at all and the page states
      **"No differences found"**, which is a false claim rather than an omission;
    * and an *inline* comment re-wrapped, saying nothing new, lands in *edited only* as a
      body change.

    The first two are fixed by asking the `comments` table instead of a body hash: a leading
    comment is attached to the routine it leads, so the right subject is named for free.

    **Joined in line order and collapsed, not compared as written**, and the corpus was made
    to say which. Re-wrapping every comment in Mensores at three widths without altering one
    word -- 86% of its 18,731 comment lines live in a run of two or more, so this is the
    dominant edit, not an exotic one:

        compared as written    1,561 · 1,186 · 1,231 routines falsely reported
        joined and collapsed       0 ·     0 ·     0

    1,561 of the 1,870 routines that own a comment. Comparing as written is not a stricter
    reading, it is unusable, and rule 1 decides it: a false difference tells the reader
    something moved when it did not.

    `_constants_moved` said whoever added comments here would have to ask the canonical
    question a third time, and that the answer would depend on how the column is filled. It
    does. A constant reaches the store through `ast.unparse` and is already canonical; an
    argument is a byte slice and needs a pass; a comment is **one row per physical line**,
    stripped of its marker and nothing else, so the pass it needs is not about a language at
    all -- it is about where somebody pressed return. That is why it is done here rather than
    behind the `canonical/` seam: joining lines and collapsing runs of whitespace is prose
    handling, and prose is prose in every language (rule 15, from the other side).

    Two passes, for `_arguments_moved`'s reason and with the same soundness argument
    inverted: collapsing whitespace can only make two strings *more* equal, so the cheap
    pass -- comparing the joined strings as stored -- is a superset by construction and the
    second pass can only ever remove candidates.
    """
    files = _changed_files(conn, A, B)
    if not files:
        return set()
    q = ",".join("?" * len(files))

    def side(db: str) -> dict[str, str]:
        cur = conn.cursor()
        cur.row_factory = None
        out: dict[str, list[str]] = {}
        for rid, text in cur.execute(COMMENTS_IN.format(db=db, q=q), files):
            out.setdefault(rid, []).append(text)
        return {k: " ".join(v) for k, v in out.items()}

    here, there = side(A), side(B)
    return {rid for rid in here.keys() | there.keys()
            if here.get(rid, "") != there.get(rid, "")
            and " ".join(here.get(rid, "").split())
            != " ".join(there.get(rid, "").split())}


# A paragraph break, and the only whitespace in a docstring that survives comparison.
_PARA = re.compile(r"\n\s*\n")


def _prose(text: str) -> str:
    """A docstring's words, with the shape of its paragraphs and nothing else.

    **The canonical question, asked a fourth time and answered differently from the third**
    -- `_constants_moved` predicted it would come round and said the answer would depend on
    how the column is filled, which is exactly what decides it. A comment reaches the store
    as one row per *physical line* with no paragraph structure left to keep, so
    `_comments_moved` joins the lot and collapses; a docstring reaches it as one string
    through `ast.get_docstring`, which is `inspect.cleandoc` -- dedented, stripped top and
    tail, and with **its blank lines intact**. The structure is there, so it is kept.

    Measured over Mensores' 3,769 docstrings rather than argued, re-wrapping every one of
    them at three widths without altering a word -- the ordinary edit, and 52% of them are
    multi-line with a blank-line break:

        re-wrapped at 72 / 79 / 88   as written  2,060 · 1,652 · 1,602 falsely reported
                                     collapsed       0 ·     0 ·     0
                                     by paragraph    0 ·     0 ·     0

    Both canonical forms are silent on the noise, so that experiment does not choose between
    them. The one that does is its opposite: **merging every paragraph**, changing not one
    word and destroying the separation PEP 257 gives the summary line, is reported by
    neither `as written`'s rival nor by a full collapse --

        paragraphs merged, 1,996 affected   collapsed  0 reported
                                            by paragraph  1,996 reported

    -- so a full collapse buys nothing over this and is blind to a real change to how a
    routine is explained. Same zero on the noise, 1,996 more on the signal.

    Done here rather than behind the `canonical/` seam for `_comments_moved`'s reason:
    joining lines and collapsing runs of whitespace is prose handling, and prose is prose in
    every language (rule 15, from the other side). Where somebody pressed return is not a
    question about a parser.
    """
    return "\n\n".join(" ".join(p.split()) for p in _PARA.split(text) if p.strip())


def _docstrings_moved(conn: sqlite3.Connection, A: str, B: str) -> set[str]:
    """Routines the two versions **describe** differently.

    Beside `_comments_moved` and answering the same question from the other side: a comment
    is what somebody wrote *around* a routine and a docstring is what the routine says about
    itself. Both are the WHY, and neither is anything the code carries.

    **One wrong answer, where a comment had three, and it is the band rather than the
    silence.** A leading comment sits above the `def` and so outside `body_hash`, which is
    why rewriting one could vanish entirely. A docstring is *inside* the `def`, so it is
    always inside `body_hash` and a rewritten one is never invisible -- it is filed under
    **edited only**, whose whole claim is *the body differs and nothing it does does*, a band
    this tool describes in its own words as internal computation and the one thing it exists
    not to report. `_production_audit_db_path` on Mensores' pair had a deprecation notice and
    its entire reasoning rewritten and sits there, indistinguishable from a renamed local.

    So this is a **tag and never a band**, and the two follow from that same fact. It cannot
    put a row in `explained_only` -- nothing reaches that band by this route, because a
    docstring change is a body change by construction -- and it must not move a row out of
    the band it earned, because what a routine *does* is what decides that (rule 32).

    Two passes, `_comments_moved`'s shape and its soundness argument: collapsing whitespace
    can only make two strings more equal, so comparing them as stored is a superset by
    construction and the second pass can only ever remove candidates.
    """
    return _moved_prose(conn, A, B, DOCSTRINGS_IN)


def _module_docs_moved(conn: sqlite3.Connection, A: str,
                       B: str) -> list[dict[str, Any]]:
    """Files whose module docstring moved -- **the subject is the file, not a routine.**

    A module docstring is the only place a module states what it *is*, and it belongs to no
    routine. Hanging it on the synthetic `<module>` was the obvious cheap answer and is
    wrong: `<module>` exists only where a file has module-level work, so on Mensores it
    covers 487 of 628 files while 619 of them carry a module docstring. For the **138** that
    state what they are and run nothing at import, a rewritten module docstring changes no
    routine's `body_hash`, no fact, and no row -- and the page says **"No differences
    found."** That is the comment lane's worst answer still standing, in the one sentence a
    module writes about itself.

    A file is a subject the reader can act on -- the code browser already selects one -- so
    these rows carry a path and the router opens it, rather than naming something with no way
    in (rule 30).

    Rows are ordered by path, and only files **both** versions hold: a file only one side has
    is the file lane's answer already, and two lanes reporting one difference is rule 40.
    """
    files = _changed_files(conn, A, B)
    if not files:
        return []
    q = ",".join("?" * len(files))

    def side(db: str) -> dict[str, tuple[str, str]]:
        return {str(r[0]): (str(r[1] or ""), str(r[2]))
                for r in conn.execute(MODULE_DOCS.format(db=db, q=q), files)}

    here, there = side(A), side(B)
    return [{"path": path, "module": there.get(path, here.get(path, ("", "")))[0]}
            for path in sorted(here.keys() & there.keys())
            if here[path][1] != there[path][1]
            and _prose(here[path][1]) != _prose(there[path][1])]


def _structures_declared(conn: sqlite3.Connection, A: str,
                         B: str) -> dict[str, set[str]]:
    """Structures present in both versions that **declare** something different.

    The structure lane's answer to `behaves differently`, and named for the same reason:
    what the thing is, not what befell it (rule 65). Three kinds move independently and each
    is reported by name, because "this structure changed" is a row that says nothing a reader
    can act on -- `kind` (DATACLASS became CLASS), `bases` (it stopped inheriting something),
    and `fields` (what it holds).

    **Both directions, unioned**, for `MOVED`'s reason: a field only one side has is "this
    structure holds something else over there" whichever side it is on, and asking one
    direction reports everything gained and nothing lost.

    Only structures **both** versions have. One that is on a single side is already its own
    presence row, and a second lane repeating it is rule 40 in a diff -- two numbers about
    one thing.
    """
    def decl(db: str) -> dict[str, tuple[str, str]]:
        cur = conn.cursor()
        cur.row_factory = None
        return {str(r[0]): (str(r[1]), str(r[2]))
                for r in cur.execute(STRUCTURE_DECL.format(db=db))}

    def fields(db: str) -> dict[str, set[tuple[str, str, str]]]:
        out: dict[str, set[tuple[str, str, str]]] = {}
        cur = conn.cursor()
        cur.row_factory = None
        for sid, name, typ, dflt in cur.execute(STRUCTURE_FIELDS_IN.format(db=db)):
            out.setdefault(str(sid), set()).add((str(name), str(typ), str(dflt)))
        return out

    here_d, there_d = decl(A), decl(B)
    both = here_d.keys() & there_d.keys()
    here_f, there_f = fields(A), fields(B)

    moved: dict[str, set[str]] = {}
    for sid in both:
        if here_d[sid][0] != there_d[sid][0]:
            moved.setdefault(sid, set()).add("kind")
        if here_d[sid][1] != there_d[sid][1]:
            moved.setdefault(sid, set()).add("bases")
        if here_f.get(sid, set()) != there_f.get(sid, set()):
            moved.setdefault(sid, set()).add("fields")
    return moved


def _structure_docs_moved(conn: sqlite3.Connection, A: str, B: str) -> set[str]:
    """Structures the two versions **describe** differently.

    `_docstrings_moved` for a structure, and the one difference is the one that matters: for
    a routine a docstring is a **tag**, because it sits inside the `def` and so inside
    `body_hash`, which means the row is already in `edited only` and what wants correcting is
    the reason the row gives. A structure has no `body_hash` and no `edited` band at all, so
    a structure whose docstring was rewritten and nothing else is in **no band** -- reported
    by nothing, on a page free to say "No differences found".

    So here it can stand alone, and `structures_explained` is where it stands. That is rule
    77 arriving a third time: the same fact needs a different home depending on whether its
    subject has somewhere else to be.

    Same canonical form as the other two prose lanes, and same two passes: comparing as
    stored is a superset by construction, so the second pass can only remove candidates.
    """
    return _moved_prose(conn, A, B, STRUCT_DOCS_IN)


def _changed_files(conn: sqlite3.Connection, A: str, B: str) -> list[str]:
    """The files whose bytes differ, which is what every prose lane is bounded to.

    One place asks it, because three lanes now do -- and a bound computed twice is two
    answers to *which files are worth reading* waiting to disagree (rule 51).
    """
    return [str(r[0]) for r in conn.execute(CHANGED_FILES.format(A=A, B=B))]


def _moved_prose(conn: sqlite3.Connection, A: str, B: str, sql: str) -> set[str]:
    """Owners whose prose differs, as stored and then canonically.

    Shared by the docstring lane and nothing else today; written as one function because the
    comment lane has the same two-pass shape with a *different* canonical form, and folding
    all three together would mean one function that takes an argument saying which kind of
    prose it is holding -- the row that means two things (rule 32), in a signature.
    """
    files = _changed_files(conn, A, B)
    if not files:
        return set()
    q = ",".join("?" * len(files))

    def side(db: str) -> dict[str, str]:
        cur = conn.cursor()
        cur.row_factory = None
        return {str(k): str(v or "") for k, v in cur.execute(
            sql.format(db=db, q=q), files)}

    here, there = side(A), side(B)
    return {k for k in here.keys() | there.keys()
            if here.get(k, "") != there.get(k, "")
            and _prose(here.get(k, "")) != _prose(there.get(k, ""))}


def _presence_side(conn: sqlite3.Connection, table: str, p: Presence,
                   *, frm: str, notin: str) -> list[dict[str, Any]]:
    """One side of a presence band: what `frm` has that `notin` has not.

    Rows carry all three of the things `PRESENCE` separates -- the label that is printed,
    the id the route consumes, and the route itself -- rather than leaving the shell to
    derive any from the others. Building `const:` + a printed name in the browser would be
    constructing an identity out of a label, which is rule 30 with the arrow reversed.

    `nav` is empty wherever the kind declares no subject, and the shell prints those rows as
    plain text. A row that looks live and does nothing is the worse of the two failures
    (design rule 16), so the absence is carried rather than papered over with a route that
    would resolve to nothing.
    """
    subject = p.subject or "NULL"
    return [
        {"label": r[0], "id": r[1], "nav": p.nav if r[1] else ""}
        for r in conn.execute(
            f"SELECT {p.label}, {subject} FROM {frm}.{table} "
            f"WHERE {p.key} NOT IN (SELECT {p.key} FROM {notin}.{table}) ORDER BY 1")
    ]


def _constants_moved(conn: sqlite3.Connection, A: str, B: str) -> list[dict[str, Any]]:
    """Constants both versions declare, holding something different.

    Named `module.name` -- the same key `PRESENCE` compares them on, so a constant cannot be
    in the presence bands and this one at once, and the two cannot disagree about what a
    constant *is* (rule 51).

    **Not canonicalised, and that is the interesting half.** A constant's value reaches the
    store through `_literal`, which is `ast.unparse` -- so `{'a':1,  'b':2}` and
    `{'a': 1, 'b': 2}` are already the *same string* by the time they are written down, and
    a canonical pass here can never change the answer. It was written, measured at 384 ms
    over 374,529 characters a side, and removed on that evidence: work that cannot change an
    answer is not caution, it is a claim the code does not need to make.

    An **argument** is the opposite case and needs the pass, which is why only one of the two
    has it. `call_args.expr` comes from `_segment`, a byte slice of the file, deliberately
    *not* re-rendered so a reader can find the string where it was written (rules 8 and 75).
    Two writings of one message therefore reach the store as two strings, and only asking for
    a canonical form tells them apart.

    Written down because the symmetry is inviting and wrong: whoever adds `comments` here
    next will have to ask this same question a third time, and the answer will depend on how
    that column is filled rather than on what it holds.
    """
    def held(db: str) -> dict[str, tuple[Any, ...]]:
        return {
            f"{r['module']}.{r['name']}": (r["value"], r["type"], r["is_final"])
            for r in conn.execute(CONSTANT_VALUES.format(db=db))
        }
    base, other = held(B), held(A)
    # **Both values ride with the row**, because the whole claim of this band is that the
    # thing is not constant any more, and a name alone cannot make it: `EXPECTED_SCHEMA_
    # VERSION` moved says less than 27 → 28. They are already in hand -- the two maps above
    # are read to decide the band and were being thrown away -- so this costs a lookup, not
    # a query.
    #
    # `type` and `is_final` are compared and *not* carried. They are part of what "holding
    # something different" means, and a row that showed only the value while the difference
    # was a lost `Final` would print two identical strings under a heading saying they
    # differ -- rule 13, where a claim's evidence must be what produced it. The pane says
    # which of the three moved instead.
    # `nav` and the `const:` prefix come from `PRESENCE` rather than being written out here,
    # because this band and the two presence bands are the same rows reached three ways and
    # a second spelling of the route is a second thing to get wrong. It was: these rows were
    # built with a label and an id and **no route at all**, so the one band whose whole claim
    # is *this is not constant any more* was the one band a reader could not open -- 23 of
    # the 30 constant rows clickable and the 7 that mattered not.
    nav = PRESENCE["constants"].nav
    return [
        {
            "label": k,
            "id": f"const:{k}",
            "nav": nav,
            "base": base[k][0],
            "compared": other[k][0],
            "moved": [
                what for what, i in (("value", 0), ("type", 1), ("final", 2))
                if base[k][i] != other[k][i]
            ],
        }
        for k in sorted(base.keys() & other.keys())
        if base[k] != other[k]
    ]


def build(base: Path, compared: Path,
          *, serving: sqlite3.Connection | None = None) -> dict[str, Any]:
    """The whole difference list, both directions, with every row carrying its subject.

    `base` is the version the dashboard is showing; `compared` is the one it is held
    against. **Neither is claimed to be older.** Rows say which side a thing is on and
    stop there -- see the module docstring.

    Every row carries the node **id** the rest of the dashboard selects by, never a
    label -- a worklist whose rows cannot be acted on is design rule 16's dead control
    with a count beside it (rule 30).

    `serving` is a connection this process **already holds open on `base`**, and passing
    it is worth 36x. It is the base rather than the compared end because the base is what
    the server is serving -- one graph is open because the whole map is drawn from it.

    A second, read-only handle to a database this process has open in
    WAL mode cannot join the shared-memory WAL index -- it has no write access to the
    `-shm` -- so it re-derives it on every query. Measured on Mensores, one `calls`
    comparison: **8,855 ms with the dashboard holding the graph open, 242 ms with it
    stopped, 137 ms attached onto the connection that already had it.** Same query, same
    files, same page cache.

    That is worth stating plainly because the slow path is the *careful* one, and it is
    only slow while the tool is doing the thing it exists to do. Opened standalone it
    measures fine, which is exactly how it would have been recorded as fast and shipped:
    every measurement in this module before this one was taken with the server stopped.
    """
    conn = serving if serving is not None else _attach(compared, base)
    # When we are riding the server's connection, the graph it serves -- the base -- is
    # already `main`; only the compared end needs attaching, and it is one this process
    # does not hold open.
    A, B = ("chgcompared", "main") if serving is not None else ("compared", "base")
    if serving is not None:
        # A plain path, not a `mode=ro` URI, and both halves of that are deliberate.
        # `Store` opens without `uri=True`, so a URI here is taken as a literal filename
        # -- and read-only is what made this slow in the first place, so buying it back
        # on the connection the whole dashboard shares would spread the 36x to every
        # other query rather than remove it.
        #
        # The guarantee is kept the way rule 25 keeps it for `sourcedb`: by a test that
        # this module contains no write statement at all, because what is being guarded
        # against is a future edit rather than a present bug. Nothing here is conditional
        # and nothing here migrates; it is SELECTs and one DETACH.
        conn.execute("ATTACH DATABASE ? AS chgcompared", (str(compared.resolve()),))
    try:
        only_base = [dict(r) for r in conn.execute(ONLY_IN_BASE.format(A=A, B=B))]
        only_comp = [dict(r) for r in conn.execute(
            ONLY_IN_COMPARED.format(A=A, B=B))]
        edited = {r["id"]: dict(r) for r in conn.execute(EDITED.format(A=A, B=B))}

        moved: dict[str, set[str]] = {}
        for table, (owner, cols) in FACTS.items():
            for r in _rows(conn, MOVED, table=table, owner=owner, cols=cols,
                           A=A, B=B):
                if r["o"]:
                    moved.setdefault(r["o"], set()).add(table)
        for r in conn.execute(RETURNS_MOVED.format(A=A, B=B)):
            moved.setdefault(r["o"], set()).add("returns")
        # What the caller passed. Named for its table, like every other kind here.
        for rid in _arguments_moved(conn, A, B):
            moved.setdefault(rid, set()).add("call_args")

        # Only routines present in BOTH. A fact belonging to a routine that is on one
        # side only is already stated by its own band, and counting it here would report
        # one difference twice -- rule 40's defect, in a diff.
        both = {r["id"] for r in conn.execute(
            f"SELECT id FROM {A}.routines INTERSECT SELECT id FROM {B}.routines")}
        behaves = {rid: sorted(k) for rid, k in moved.items() if rid in both}

        # **Deliberately not a sixth `FACTS` row, and not folded into `moved`.** Putting it
        # there would make every routine whose comment was rewritten *behave differently* --
        # a band that promises something the routine **does** has moved, about a change that
        # moved nothing it does. That is the mistake the argument canonicaliser was written
        # to avoid, one fact type over. Tom's call, 2026-09-01: its own band, and a tag on
        # the rows that are already in one.
        commented = _comments_moved(conn, A, B) & both
        # **A tag, and it can never be a band.** A docstring is inside the `def`, so it is
        # inside `body_hash` -- every routine here is already in `edited_only` or in
        # `behaves`, and what it corrects is the *reason* the row gives rather than its
        # absence. See `_docstrings_moved`.
        documented = _docstrings_moved(conn, A, B) & both
        # The file lane of the same question, and the only one here whose subject is not a
        # routine. It is computed outside `moved` and outside the bands for that reason: a
        # file is not a routine and must not be counted as one (rule 74's shape -- a thing
        # is never one of the things it holds).
        modules = _module_docs_moved(conn, A, B)

        # The third subject, and the one that had nothing at all. Presence first, because it
        # is where the whole gap was: 8 of Mensores' structures appear or vanish and were
        # reported nowhere. Rows carry an id, so a reader can open what a row names.
        struct_only_base = [dict(r) for r in conn.execute(
            STRUCTURES_ONLY.format(X=B, Y=A))]
        struct_only_comp = [dict(r) for r in conn.execute(
            STRUCTURES_ONLY.format(X=A, Y=B))]
        # What it declares, and what it says about itself. `declared` is the band; `explained`
        # is a tag on a row already in it, and a band of its own for a structure that is in no
        # other -- the routine lane's shape, with the difference `_structure_docs_moved`
        # states: a structure has no `body_hash` to carry it into `edited only`.
        declared = _structures_declared(conn, A, B)
        # Structures **both** versions hold, and the intersection is load-bearing rather than
        # defensive. `_moved_prose` compares the union of the two id sets, so a structure that
        # exists on one side only reads as "described differently" -- its docstring is present
        # here and absent there. Every one of those is already a presence row, and reporting
        # it twice is rule 40: two lanes recording one act, two numbers about one thing.
        #
        # Measured before it was written and again after: on Mensores' pair this lane returned
        # **5 rows, all five of them presence rows and none of them a rewritten docstring**,
        # against a raw ground truth of zero. The routine lane guards it the same way at the
        # same place (`& both`), and the module lane guards it inside `_module_docs_moved` --
        # three lanes, one rule, and this is the third time it has had to be applied.
        struct_both = {r[0] for r in conn.execute(
            f"SELECT id FROM {A}.structures INTERSECT SELECT id FROM {B}.structures")}
        struct_documented = _structure_docs_moved(conn, A, B) & struct_both
        struct_named = {r["id"]: dict(r) for r in conn.execute(
            f"SELECT id, name, kind, module, file, line FROM {B}.structures")}
        # Both versions', because a structure explained differently may sit on either side of
        # a rename and the base is only one of the two places to find its name.
        for r in conn.execute(
                f"SELECT id, name, kind, module, file, line FROM {A}.structures"):
            struct_named.setdefault(r["id"], dict(r))

        structures_declared = [
            {**struct_named[sid],
             "moved": sorted(kinds) + (["docstring"] if sid in struct_documented else [])}
            for sid, kinds in sorted(
                declared.items(),
                key=lambda kv: (struct_named.get(kv[0], {}).get("module", ""),
                                struct_named.get(kv[0], {}).get("name", "")))
            if sid in struct_named
        ]
        # Defined by subtraction from the band beside it, exactly as `explained_only` is, so
        # the two stay a partition and no structure is counted twice (rule 40).
        structures_explained = [
            struct_named[sid] for sid in sorted(
                struct_documented - declared.keys(),
                key=lambda s: (struct_named.get(s, {}).get("module", ""),
                               struct_named.get(s, {}).get("name", "")))
            if sid in struct_named
        ]

        named = {r["id"]: dict(r) for r in conn.execute(
            f"SELECT id, name, qualname, module, file, line_start FROM {B}.routines")}

        def tags(rid: str, kinds: list[str]) -> list[str]:
            """What moved, with the two explanation tags last because they are not facts.

            They ride on the row rather than in `moved` itself so the band a routine lands in
            is decided by what it *does* and never by what explains it (rule 32: one row,
            one claim, and the tag says which claim it is).

            **Two tags rather than one**, and they are kept apart deliberately: a comment is
            what somebody wrote *around* a routine and a docstring is what the routine says
            about *itself*. One tag reading "prose" would be a row that means two things.
            """
            return [*kinds,
                    *(["comments"] if rid in commented else []),
                    *(["docstring"] if rid in documented else [])]

        behaves_rows = [
            {**named[rid], "moved": tags(rid, kinds)}
            for rid, kinds in sorted(behaves.items(),
                                     key=lambda kv: named.get(kv[0], {}).get("qualname", ""))
            if rid in named
        ]
        edited_only = [{**row, "moved": tags(rid, [])}
                       for rid, row in edited.items() if rid not in behaves]
        # The fifth band, and it holds exactly what would otherwise be in none: the same
        # routine, the same body, the same facts, and what explains it has moved. The four
        # bands stay a partition because this one is defined by subtraction from all of them.
        #
        # **In Python only comments can reach it**, and the subtraction is written over both
        # explanation sets anyway rather than over the one that can. A docstring lives inside
        # the `def`, so `body_hash` moves with it and `edited` has the row already; that is a
        # fact about how *this* extractor hashes a body, not about what a docstring is, and a
        # band defined by "what is in no other band" must be that and not a list of the ways
        # it has so far been reached.
        explained_only = [
            named[rid] for rid in sorted(
                (commented | documented) - behaves.keys() - edited.keys(),
                key=lambda r: named.get(r, {}).get("qualname", ""))
            if rid in named
        ]

        presence = {}
        for table, p in PRESENCE.items():
            # Compared on the key, printed as the label, acted on by the subject -- three
            # things, and `_presence_side` carries all three onto every row.
            presence[table] = {
                "only_in_base": _presence_side(conn, table, p, frm=B, notin=A),
                "only_in_compared": _presence_side(conn, table, p, frm=A, notin=B),
                # A third state, and only constants have one. The other three are names --
                # a table, a way in, a file the program names -- and a name either is there
                # or is not. A constant is a name *and* a value, so "in both, holding
                # something different" is a thing that can be true of it and of nothing else
                # here. Empty for the others rather than absent, so the renderer reads one
                # shape (rule 13).
                "moved": _constants_moved(conn, A, B) if table == "constants" else [],
            }

        # `identical` is a real answer and is stated as one. Two versions that differ
        # in no way the map can see is what a reader gets for comparing a tree with a
        # copy of itself, and four empty bands read as a comparison that failed rather
        # than as one that succeeded and found nothing (design rule 1).
        return {
            "counts": {
                "only_in_base": len(only_base),
                "only_in_compared": len(only_comp),
                "behaves": len(behaves_rows),
                "edited_only": len(edited_only),
                "explained_only": len(explained_only),
                "modules_explained": len(modules),
                "structures_only_in_base": len(struct_only_base),
                "structures_only_in_compared": len(struct_only_comp),
                "structures_declared": len(structures_declared),
                "structures_explained": len(structures_explained),
                "structures_base": conn.execute(
                    f"SELECT COUNT(*) FROM {B}.structures").fetchone()[0],
                "structures_compared": conn.execute(
                    f"SELECT COUNT(*) FROM {A}.structures").fetchone()[0],
                "routines_base": conn.execute(
                    f"SELECT COUNT(*) FROM {B}.routines").fetchone()[0],
                "routines_compared": conn.execute(
                    f"SELECT COUNT(*) FROM {A}.routines").fetchone()[0],
            },
            # `explained_only` is in here, and it is the whole reason the band exists: a
            # rewritten leading comment used to leave every other term zero, so the page
            # stated "No differences found" over a version whose intent had been rewritten.
            # Every lane, including the three structure ones. A term missing here is a
            # page that says "No differences found" over a difference it is listing below --
            # which is exactly what the comment lane did before `explained_only` joined it.
            "identical": not (only_base or only_comp or behaves_rows or edited_only
                              or explained_only or modules
                              or struct_only_base or struct_only_comp
                              or structures_declared or structures_explained
                              or any(v["only_in_base"] or v["only_in_compared"] or v["moved"]
                                     for v in presence.values())),
            "only_in_base": only_base,
            "only_in_compared": only_comp,
            "behaves": behaves_rows,
            "edited_only": edited_only,
            "explained_only": explained_only,
            # Rows whose subject is a **file**. Kept out of every routine band and out of
            # `counts`' routine totals for the reason it is its own lane at all: a module is
            # not one of its routines.
            "modules_explained": modules,
            # Rows whose subject is a **structure** -- a class, dataclass, enum or type
            # alias. Three lanes rather than one: what is only on one side, what declares
            # something different, and what describes itself differently. Kept out of the
            # routine bands and out of `counts`' routine totals for the reason the module
            # lane is: a structure is not one of its methods (rule 74).
            "structures_only_in_base": struct_only_base,
            "structures_only_in_compared": struct_only_comp,
            "structures_declared": structures_declared,
            "structures_explained": structures_explained,
            "presence": presence,
        }
    finally:
        # The server's connection outlives this call and must be handed back exactly as
        # it was found: an alias left attached makes the next comparison fail, and a
        # connection closed here would take the whole dashboard down with it.
        if serving is not None:
            conn.execute("DETACH DATABASE chgcompared")
        else:
            conn.close()
