"""A broken program must still document, and every finding must state its doubt."""

from __future__ import annotations

from pathlib import Path

from dunneflow.anomalies import BROKEN, INFO, SUSPECT, detect
from dunneflow.resolve.calls import resolve_calls
from dunneflow.store import Store
from dunneflow.walk import analyze_tree

BROKEN_PROGRAM = '''
import os


def handler(a):          # no return type, untyped parameter
    return a


def handler(a, b):       # redefinition: the first is now unreachable
    return a + b


def orphan():
    """Never called, never a way in."""
    return os.getenv("NOTHING")
'''

UNPARSEABLE = "def broken( :\n    pass\n"


def _analyze(tmp_path: Path, files: dict[str, str]) -> Store:
    root = tmp_path / "prog"
    root.mkdir(exist_ok=True)
    for name, body in files.items():
        (root / name).write_text(body, encoding="utf-8")
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    resolve_calls(store)
    return store


def test_a_broken_program_still_produces_a_graph(tmp_path):
    """Ingest must never fail on bad input -- that is the whole point."""
    store = _analyze(tmp_path, {"bad.py": UNPARSEABLE, "good.py": BROKEN_PROGRAM})
    assert store.counts()["files"] == 2
    assert store.counts()["routines"] > 0  # the good file survived
    store.close()


def test_parse_failure_is_reported_as_broken(tmp_path):
    store = _analyze(tmp_path, {"bad.py": UNPARSEABLE})
    report = detect(store)
    parse = [a for a in report.items if a.kind == "PARSE_ERROR"]
    assert parse and parse[0].severity == BROKEN
    store.close()


def test_redefinition_is_found(tmp_path):
    store = _analyze(tmp_path, {"good.py": BROKEN_PROGRAM})
    kinds = {a.kind for a in detect(store).items}
    assert "REDEFINITION" in kinds
    store.close()


def test_dead_code_states_that_tests_were_excluded(tmp_path):
    """The blind spot that would have prevented six wrong conclusions."""
    store = _analyze(tmp_path, {"good.py": BROKEN_PROGRAM})
    dead = [a for a in detect(store, include_tests=False).items if a.kind == "DEAD_CODE"]
    assert dead
    assert "excluded" in dead[0].blind_spot.lower()
    included = [
        a for a in detect(store, include_tests=True).items if a.kind == "DEAD_CODE"
    ]
    assert "included" in included[0].blind_spot.lower()
    store.close()


def test_every_finding_carries_a_blind_spot(tmp_path):
    store = _analyze(tmp_path, {"bad.py": UNPARSEABLE, "good.py": BROKEN_PROGRAM})
    for a in detect(store).items:
        assert a.blind_spot.strip(), f"{a.kind} has no blind spot"
        assert a.severity in (BROKEN, SUSPECT, INFO)
        assert a.title.strip()
    store.close()


def test_severity_and_confidence_are_independent(tmp_path):
    """A finding can be certain but harmless, or severe but uncertain."""
    store = _analyze(tmp_path, {"bad.py": UNPARSEABLE, "good.py": BROKEN_PROGRAM})
    items = detect(store).items
    pairs = {(a.severity, a.confidence) for a in items}
    assert len({s for s, _ in pairs}) > 1
    store.close()


def test_report_sorts_broken_first(tmp_path):
    store = _analyze(tmp_path, {"bad.py": UNPARSEABLE, "good.py": BROKEN_PROGRAM})
    order = [a.severity for a in detect(store).sorted()]
    assert order == sorted(order, key=lambda s: {BROKEN: 0, SUSPECT: 1, INFO: 2}[s])
    store.close()


def test_clean_program_reports_nothing_broken(analyzed):
    assert detect(analyzed).broken == 0
