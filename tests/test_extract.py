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
