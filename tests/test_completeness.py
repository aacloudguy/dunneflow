"""Documentation does not cut corners.

Reference lists are complete. A diagram may abbreviate, because a picture of
thousands of nodes conveys nothing -- but only where the full content sits beside it
in a table. Nothing is ever dropped at ingest, where the loss would be permanent.
"""

from __future__ import annotations

import re
from pathlib import Path

from dunneflow.extractors.python.extract import extract_file
from dunneflow.render.markdown import render_all
from dunneflow.resolve.calls import resolve_calls
from dunneflow.store import Store
from dunneflow.walk import analyze_tree

LONG_DEFAULT = "x" * 400
WIDE_MODULE = (
    "import os\n\n\n"
    + "".join(
        f"def routine_{i:03d}(arg: str = '{LONG_DEFAULT}') -> str:\n"
        f"    # caveat {i}: this one matters and the sentence keeps going for a while\n"
        f"    return os.getenv('VAR_{i:03d}', arg)\n\n\n"
        for i in range(120)
    )
)


def _render(tmp_path: Path) -> Path:
    root = tmp_path / "prog"
    root.mkdir()
    (root / "wide.py").write_text(WIDE_MODULE, encoding="utf-8")
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    resolve_calls(store)
    out = tmp_path / "out"
    render_all(store, out, "wide")
    store.close()
    return out


def test_every_routine_is_listed(tmp_path):
    """120 routines in one module: all 120 appear, not the first 60."""
    doc = (_render(tmp_path) / "03-routines.md").read_text(encoding="utf-8")
    for i in range(120):
        assert f"routine_{i:03d}" in doc, f"routine_{i:03d} missing"


def test_no_truncation_notices_anywhere(tmp_path):
    out = _render(tmp_path)
    pattern = re.compile(r"\*[^*\n]{0,80}\b(?:more|not listed|further)\b[^*\n]{0,80}\*")
    for path in out.glob("*.md"):
        found = pattern.findall(path.read_text(encoding="utf-8"))
        assert not found, f"{path.name} still hides content: {found[:3]}"


def test_every_boundary_target_is_listed(tmp_path):
    doc = (_render(tmp_path) / "05-boundaries.md").read_text(encoding="utf-8")
    for i in range(120):
        assert f"VAR_{i:03d}" in doc, f"VAR_{i:03d} missing from the boundary ledger"


def test_ingest_records_long_values_whole(tmp_path):
    """Truncating at ingest loses the value for good, not merely from one view."""
    root = tmp_path / "src"
    root.mkdir()
    f = root / "m.py"
    f.write_text(f"def g(a: str = '{LONG_DEFAULT}') -> None:\n    pass\n", encoding="utf-8")
    facts = extract_file(f, root)
    default = facts.routines[0].params[0].default
    assert default is not None
    assert LONG_DEFAULT in default, "the default argument was shortened at ingest"


def test_comments_are_recorded_whole(tmp_path):
    root = tmp_path / "src"
    root.mkdir()
    long_comment = "this caveat runs on and on and must survive intact " * 8
    f = root / "m.py"
    f.write_text(f"# {long_comment}\ndef g() -> None:\n    pass\n", encoding="utf-8")
    facts = extract_file(f, root)
    assert any(long_comment.strip() in c.text for c in facts.routines[0].comments)


def test_diagram_abbreviation_is_backed_by_a_full_listing(tmp_path):
    """A bounded picture is allowed only where the complete content sits beside it."""
    doc = (_render(tmp_path) / "02-flows.md").read_text(encoding="utf-8")
    if "conveys nothing" in doc:  # a diagram was bounded
        assert "Every routine reachable from" in doc, (
            "a diagram was abbreviated with no complete inventory beneath it"
        )
