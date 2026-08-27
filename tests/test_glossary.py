"""A module's docstring is the only place most programs say what their words mean.

Rule 9 keeps docstrings out of code-shaped detectors, because a sentence about a
statement is not a statement -- reading them as code invented 248 phantom SQL
statements. The glossary is the opposite case: being prose is the qualification.
`disceptator/__init__.py` opens "Interview engine -- Y-combinator-style spec interview
orchestrator", which is the answer to "what is a disceptator?" and is stated nowhere
else in the program.

These tests guard that the docstring survives extraction whole, that it never leaks
back into the code-shaped detectors, and that a module without one is not given one.
"""

from __future__ import annotations

from pathlib import Path

from dunneflow.extractors.python.extract import extract_file
from dunneflow.store import Store

WITH_DOC = '''"""Interview engine -- Y-combinator-style spec interview orchestrator.

A quaestor is the audit substrate; this is not that. See ``_architect.py``
for the DISCUSS-time architect Protocol.
"""

import os


def run() -> None:
    os.getenv("HOME")
'''

NO_DOC = '''import os


def run() -> None:
    os.getenv("HOME")
'''

# A docstring that would look like SQL to a code-shaped detector. Rule 9's original
# defect: 248 phantom statements came from reading sentences of this shape as code.
SQL_SHAPED_DOC = '''"""Insert candidate into capture_queue and update the org-config row."""

def run() -> None:
    pass
'''


def _extract(tmp_path: Path, src: str, name: str = "m.py"):
    f = tmp_path / name
    f.write_text(src, encoding="utf-8")
    return extract_file(f, tmp_path)


def test_module_docstring_is_captured(tmp_path: Path) -> None:
    facts = _extract(tmp_path, WITH_DOC)
    assert facts.doc.startswith("Interview engine")
    assert "quaestor is the audit substrate" in facts.doc


def test_module_docstring_is_kept_whole(tmp_path: Path) -> None:
    """Never truncate at ingest -- a value shortened before the store is lost for good."""
    facts = _extract(tmp_path, WITH_DOC)
    assert "_architect.py" in facts.doc, "the tail of the docstring was dropped"
    assert facts.doc.count("\n") >= 2, "paragraph structure was flattened"


def test_absent_docstring_is_empty_not_invented(tmp_path: Path) -> None:
    facts = _extract(tmp_path, NO_DOC)
    assert facts.doc == ""


def test_docstring_still_does_not_reach_code_shaped_detectors(tmp_path: Path) -> None:
    """Capturing prose must not undo rule 9."""
    facts = _extract(tmp_path, SQL_SHAPED_DOC)
    assert facts.doc.startswith("Insert candidate into capture_queue")
    assert facts.sql == [], "a docstring was read as a SQL statement"
    assert facts.boundaries == [], "a docstring was read as a boundary touch"


def test_docstring_survives_the_store(tmp_path: Path) -> None:
    facts = _extract(tmp_path, WITH_DOC)
    with Store(tmp_path / "graph.db") as st:
        st.write_file_facts(facts)
        rows = st.query("SELECT doc FROM files WHERE path = ?", (facts.path,))
    assert rows, "the file was not recorded"
    doc = rows[0][0]
    assert doc.startswith("Interview engine")
    assert "_architect.py" in doc


def test_docstring_does_not_change_identity(tmp_path: Path) -> None:
    """Editing prose is not editing the program."""
    with_doc = _extract(tmp_path, WITH_DOC, "a.py")
    without = _extract(tmp_path, NO_DOC, "a.py")
    a = {r.qualname: r for r in with_doc.routines if r.name == "run"}
    b = {r.qualname: r for r in without.routines if r.name == "run"}
    assert a and b
    ra, rb = next(iter(a.values())), next(iter(b.values()))
    assert ra.id == rb.id, "adding a module docstring retired the routine"
    assert ra.body_hash == rb.body_hash, "prose changed the body hash"
