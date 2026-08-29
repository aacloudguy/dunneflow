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
