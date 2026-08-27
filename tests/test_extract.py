"""What the extractor must find, stated as facts about a known program."""

from __future__ import annotations

from pathlib import Path

from dunneflow.extractors.python.extract import extract_file, module_name
from dunneflow.schema import BoundaryKind


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
