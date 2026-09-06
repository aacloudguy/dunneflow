"""What the extractor must find, stated as facts about a known program."""

from __future__ import annotations

from pathlib import Path

from dunneflow.extractors.python.extract import extract_file, module_name
from dunneflow.schema import BoundaryKind, signature_parts


def _facts(sample_tree: Path):
    return extract_file(sample_tree / "sample.py", sample_tree)


def test_finds_every_routine(sample_tree):
    names = {r.name for r in _facts(sample_tree).routines}
    for expected in {"load_config", "save_widget", "read_widgets", "fetch_remote",
                     "run_tool", "sync", "purge", "main"}:
        assert expected in names


def test_signature_carries_types_and_defaults(sample_tree):
    rt = next(r for r in _facts(sample_tree).routines if r.name == "save_widget")
    assert rt.signature() == (
        "save_widget(conn: sqlite3.Connection, name: str, qty: int = 0) -> None"
    )


def test_a_signature_carries_the_markers_that_change_what_it_means(tmp_path):
    """`def f(a, *, b)` and `def f(a, b)` are different functions -- the first cannot be
    called `f(1, 2)` -- and `signature()` rendered them identically for as long as it
    existed. It handled the `*args` and `**kwargs` prefixes and never the bare separators
    between the groups, so a card printing it would have been specific, plausible and wrong.

    Every kind at once, because the bug was in the *transitions* between them, not in any
    one kind: `/` closes a run and `*` opens one, and `*args` opens it already.
    """
    src = tmp_path / "sig.py"
    src.write_text(
        "def every(a: int, b: str = 'x', /, c: float = 1.0, *args: int,\n"
        "          d: bool = True, **rest: object) -> None: ...\n"
        "def starred(a: int, *, b: str) -> None: ...\n"
        "def varargs(*a: int, b: str) -> None: ...\n",
        encoding="utf-8",
    )
    by = {r.name: r for r in extract_file(src, tmp_path).routines}

    assert by["every"].signature() == (
        "every(a: int, b: str = 'x', /, c: float = 1.0, *args: int, "
        "d: bool = True, **rest: object) -> None"
    )
    # The defect exactly: without the separator this reads as two ordinary parameters.
    assert by["starred"].signature() == "starred(a: int, *, b: str) -> None"
    # And no separator where `*args` has already opened the keyword-only group.
    assert by["varargs"].signature() == "varargs(*a: int, b: str) -> None"

    # The markers travel as their own pieces, so the card can lay them out without
    # re-parsing a string the renderer had already taken apart.
    parts = signature_parts([(p.name, p.type, p.default, p.kind)
                             for p in by["every"].params])
    assert [x["text"] for x in parts] == [
        "a: int", "b: str = 'x'", "/", "c: float = 1.0", "*args: int",
        "d: bool = True", "**rest: object",
    ]
    assert [x.get("marker") for x in parts] == [None, None, "/", None, None, None, None]

    # A marker is not a parameter and must never be coloured as one. Checked against
    # `starred`, not against `every`: `every` opens its keyword-only group with `*args`, so
    # it grows no bare `*` at all and this assertion had nothing to fail on -- it passed
    # against its own mutation until the mutation was run. Rule 37, in a fixture.
    star = signature_parts([(p.name, p.type, p.default, p.kind)
                            for p in by["starred"].params])
    assert [x["text"] for x in star] == ["a: int", "*", "b: str"]
    assert [x.get("marker") for x in star] == [None, "*", None]
    assert all("name" not in x and "type" not in x
               for x in star + parts if x.get("marker"))


def test_positional_only_survives_ingest(tmp_path):
    """Rule 8 in its smallest instance. `posonlyargs` was folded into `args` and recorded as
    plain `positional`, so the `/` was gone before anything could ask for it -- a value
    shortened at ingest is lost for good rather than merely unshown."""
    src = tmp_path / "po.py"
    src.write_text("def f(a, b, /, c): ...\n", encoding="utf-8")
    kinds = [p.kind for p in extract_file(src, tmp_path).routines[0].params]
    assert kinds == ["positional_only", "positional_only", "positional"]


def test_comment_becomes_the_why(sample_tree):
    rt = next(r for r in _facts(sample_tree).routines if r.name == "load_config")
    assert any("fails closed" in c.text for c in rt.comments)


def test_governance_marker_is_mined_from_the_comment(sample_tree):
    rt = next(r for r in _facts(sample_tree).routines if r.name == "load_config")
    assert ("PLAN", "Plan 01-02") in {(a.kind, a.value) for a in rt.annotations}


def test_boundaries_are_found_by_kind(sample_tree):
    f = _facts(sample_tree)
    kinds = {b.kind for b in f.boundaries}
    for expected in (BoundaryKind.ENV, BoundaryKind.FILE, BoundaryKind.DATABASE,
                     BoundaryKind.NETWORK, BoundaryKind.PROCESS):
        assert expected in kinds


def test_env_subscript_is_a_boundary(sample_tree):
    env = [b for b in _facts(sample_tree).boundaries if b.kind is BoundaryKind.ENV]
    assert any(b.target == "API_TOKEN" for b in env)


def test_local_variables_are_not_reported(sample_tree):
    """The reader asked not to see internals. `token` and `cfg` are locals."""
    f = _facts(sample_tree)
    reported = {r.name for r in f.routines} | {s.name for s in f.structures}
    assert "token" not in reported
    assert "cfg" not in reported


def test_module_name_strips_src_and_init():
    root = Path("/proj")
    assert module_name(Path("/proj/src/pkg/mod.py"), root) == "pkg.mod"
    assert module_name(Path("/proj/src/pkg/__init__.py"), root) == "pkg"


def test_unparseable_file_yields_an_error_not_an_exception(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("def broken( :\n", encoding="utf-8")
    facts = extract_file(bad, tmp_path)
    assert facts.errors and not facts.routines


def test_standards_are_not_governance_tickets(tmp_path: Path) -> None:
    """A bare LETTERS-DIGITS pattern matches every cipher and standard a program names.

    SHA-256, UTF-8, ISO-8601, RFC-3161 and IEEE-29148 produced 121 phantom tickets on
    Mensores. A false governance link claims traceability that does not exist, which is
    worse than a missing one.
    """
    src = tmp_path / "m.py"
    src.write_text(
        "def run() -> None:\n"
        "    # ISS-293 and AC-7 are real work items.\n"
        "    # The digest is SHA-256 over UTF-8, per RFC-3161 and ISO-8601 timestamps.\n"
        "    # Requirements follow IEEE-29148.\n"
        "    pass\n",
        encoding="utf-8",
    )
    facts = extract_file(src, tmp_path)
    values = {a.value for r in facts.routines for a in r.annotations}
    assert "ISS-293" in values
    assert "AC-7" in values
    for noise in ("SHA-256", "UTF-8", "RFC-3161", "ISO-8601", "IEEE-29148"):
        assert noise not in values, f"{noise} was recorded as a governance ticket"


# --------------------------------------------------------------------------- #
# An f-string still names its table
#
# Mensores' migration 0028 creates `work_items` as `f"CREATE TABLE {_TABLE} (...)"`,
# so the name interpolated to a placeholder and the table was never recorded: the
# database map read 40 tables before the migration and 40 after, while a table had
# arrived. The value was never missing -- rule 19 records `_TABLE = "work_items"` as a
# module constant six lines above.
#
# Substituting is a *lexical binding in one file*, so rule 5 never arises: nothing
# searches for the name anywhere else in the program. Everything ambiguous is refused,
# and each test below is one of the refusals.
# --------------------------------------------------------------------------- #


def _sql(tmp_path: Path, body: str):
    src = tmp_path / "m.py"
    src.write_text(body)
    return extract_file(src, tmp_path).sql


def test_an_fstring_names_its_table_from_a_module_constant(tmp_path):
    ops = _sql(tmp_path, '_TABLE = "work_items"\n'
                         'DDL = f"CREATE TABLE {_TABLE} (id TEXT PRIMARY KEY)"\n')
    named = [t for o in ops for t in o.tables]
    assert named == ["work_items"], [(o.operation, o.tables) for o in ops]


def test_a_name_bound_twice_resolves_to_nothing(tmp_path):
    """Which binding reached the f-string is a question about control flow.

    The half-working version keeps the last binding and is confident about it: the
    statement would be recorded against `other_table`, which is a *wrong* name rather
    than a missing one -- and rule 1 says a false fact is worse than an absent one.
    """
    ops = _sql(tmp_path, '_TABLE = "work_items"\n'
                         '_TABLE = "other_table"\n'
                         'DDL = f"CREATE TABLE {_TABLE} (id TEXT)"\n')
    assert all(t != "other_table" for o in ops for t in o.tables), [o.tables for o in ops]
    assert all(t != "work_items" for o in ops for t in o.tables), [o.tables for o in ops]


def test_only_a_bare_name_substitutes(tmp_path):
    """An attribute or a call is a value this pass cannot claim to know.

    `TABLE` is bound here *deliberately*, because an implementation that reads
    `node.value.attr` finds it and answers `work_items` for `cfg.TABLE` -- which is
    somebody else's module's constant. A version that only ever returns None for an
    attribute passes a test where nothing binds the attribute name, so the collision
    is the whole test: this is rule 5 in an f-string, and the failure is a confident
    wrong name rather than a missing one.
    """
    ops = _sql(tmp_path, 'import cfg\n'
                         'TABLE = "work_items"\n'
                         'DDL = f"CREATE TABLE {cfg.TABLE} (id TEXT)"\n'
                         'DDL2 = f"CREATE TABLE {name()} (id TEXT)"\n')
    assert all(t != "work_items" for o in ops for t in o.tables), [o.tables for o in ops]


def test_a_format_spec_is_not_a_substitution(tmp_path):
    """`{x:>10}` pads; `{x!r}` quotes. Neither yields the name as written."""
    ops = _sql(tmp_path, '_TABLE = "work_items"\n'
                         'DDL = f"CREATE TABLE {_TABLE:>20} (id TEXT)"\n'
                         'DDL2 = f"CREATE TABLE {_TABLE!r} (id TEXT)"\n')
    assert all(t != "work_items" for o in ops for t in o.tables), [o.tables for o in ops]


def test_a_name_bound_to_a_non_string_resolves_to_nothing(tmp_path):
    ops = _sql(tmp_path, '_TABLE = 17\n'
                         'DDL = f"CREATE TABLE {_TABLE} (id TEXT)"\n')
    assert all(t not in ("17", "_TABLE") for o in ops for t in o.tables), [o.tables for o in ops]


def test_a_name_bound_inside_a_function_is_not_module_level(tmp_path):
    """Module level means *runs at import*, and it is a property of position (rule 19).

    The half-working version scans every Assign in the file, so a local in some
    unrelated function silently names a table at module scope.
    """
    ops = _sql(tmp_path, 'def f():\n'
                         '    _TABLE = "work_items"\n'
                         'DDL = f"CREATE TABLE {_TABLE} (id TEXT)"\n')
    assert all(t != "work_items" for o in ops for t in o.tables), [o.tables for o in ops]


def test_an_unresolvable_placeholder_still_records_the_statement(tmp_path):
    """Rule 8: never truncate at ingest. An unnamed table is not a discarded statement."""
    ops = _sql(tmp_path, 'DDL = f"CREATE TABLE {whatever} (id TEXT PRIMARY KEY)"\n')
    assert ops, "the statement itself must survive"
    assert any("CREATE TABLE" in o.sql for o in ops), [o.sql for o in ops]


# --------------------------------------------------------------------------- #
# The shape a routine takes. `ControlPoint` is a **span and nothing more** -- what a
# loop does is reached by joining the tables that already exist, so these tests are
# about the span, the nesting and the arms, and never about a value.
# --------------------------------------------------------------------------- #


def _control(tmp_path: Path, src: str):
    (tmp_path / "m.py").write_text(src)
    return extract_file(tmp_path / "m.py", tmp_path).control


def test_an_elif_ladder_is_one_decision_with_its_ways_out(tmp_path):
    """A seven-way decision is one thing a reader counts, not six two-way ones.

    `elif` is an `If` in the `orelse` of an `If`, so the tree says "2 arms" once per
    `elif`. Counting nodes instead of ladders is a picture of the syntax rather than of
    the decision, and it is not a small error: over Mensores it turned **69** decisions
    of three or more arms into **97**, and **3,931** guard clauses into 3,937, because an
    `elif` tail that ends in `return` reads as a guard of its own. Both figures were
    written into the plan from a script that walked every node, and both were corrected
    by the store.
    """
    pts = _control(tmp_path, """
def f(x):
    if x == 1:
        g()
    elif x == 2:
        g()
    elif x == 3:
        g()
    else:
        g()
""")
    decisions = [p for p in pts if p.kind.value == "DECISION"]
    assert len(decisions) == 1, (
        f"an elif ladder is {len(decisions)} decisions, so every count over it is wrong"
    )
    assert decisions[0].arms == 4, "the ways out are not counted, so a ladder has no size"
    # ...and the tails' contents are still walked, at the head's depth -- an `elif` arm is
    # a sibling of the `if` arm, not a level below it.
    assert decisions[0].header == "x == 1", "the decision does not carry its test as written"


def test_a_guard_is_a_decision_narrowed_by_how_it_leaves(tmp_path):
    """`if not x: return` and `if not x: raise` are the same sentence, opposite facts.

    So `exits` is recorded rather than read back off the header. 62.6% of Mensores'
    branches are one of these four -- refusals are the largest single shape in it.
    """
    pts = _control(tmp_path, """
def f(x):
    if not x:
        return None
    if x < 0:
        raise ValueError(x)
    for i in x:
        if i is None:
            continue
        g(i)
""")
    guards = {p.exits for p in pts if p.kind.value == "GUARD"}
    assert guards == {"return", "raise", "continue"}, (
        f"guards do not record how they leave: {guards}"
    )
    assert not [p for p in pts if p.kind.value == "DECISION"], (
        "a one-armed branch that leaves is being counted as an ordinary decision too, so "
        "every decision figure is inflated by the 3,931 refusals"
    )


def test_control_nesting_is_not_function_nesting(tmp_path):
    """`depth` counts enclosing *control*, and `Routine.is_nested` counts enclosing
    *functions*. The two disagree on every closure, and a function declared inside a loop
    must start its own body at depth 0 -- otherwise a closure's first `if` reads as three
    levels deep because of where it happens to be written.
    """
    pts = _control(tmp_path, """
def outer(rows):
    for r in rows:
        if r:
            for c in r:
                g(c)
        def inner(v):
            if v:
                g(v)
""")
    by_line = {p.line_start: p for p in pts}
    depths = sorted(p.depth for p in pts if p.kind.value == "LOOP")
    assert depths == [1, 3], f"loop nesting is {depths}, so the outline indents wrongly"
    inner_if = [p for p in pts if p.header == "v"]
    assert inner_if and inner_if[0].depth == 1, (
        "a closure carries its enclosing loop's depth, so its body reads as buried"
    )
    assert by_line, "nothing was recorded at all"


def test_a_comprehension_is_a_loop_that_is_an_expression(tmp_path):
    """Counted apart from `LOOP` because a reader scanning for loops does not see one.

    Which is exactly why a boundary inside one is worth saying out loud: 42 of Mensores'
    974 comprehensions reach one, against 219 of its 976 loops.
    """
    pts = _control(tmp_path, "x = [g(i) for i in rows]\ny = {k: g(k) for k in rows}\n")
    kinds = [p.kind.value for p in pts]
    assert kinds == ["COMPREHENSION", "COMPREHENSION"], kinds
    assert [p.header for p in pts] == ["rows", "rows"], (
        "a comprehension does not say what it is over"
    )


def test_a_control_point_carries_its_header_as_written(tmp_path):
    """Sliced on **byte** offsets (rule 75), never `ast.unparse`d.

    `call_args`' argument one subject over: what is stored is what the reader will go
    looking for in the file, and a re-rendering normalises the spacing they would search.
    """
    pts = _control(tmp_path, "def f(rows):\n    for r in rows [ 0 ] :\n        g(r)\n")
    assert pts[0].header == "rows [ 0 ]", (
        f"the header was re-rendered rather than sliced: {pts[0].header!r}"
    )
