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


# -- what a word has to be to count as one ----------------------------------- #
#
# 889 of the 1,154 words Society's glossary said nothing defines were fragments of
# compound constant names: `_GLOSSARY_DEFINITION_MAX_LEN` is one name a person chose, and
# splitting it on underscores yields its subject, its type and its unit. `DDL`, `EXTRAS`,
# `REASON`, `KEYS`, `BYTES`, `CHARS` were the head of the worklist and `witness`,
# `posture`, `claim` and `probe` were buried under them. Rule 1, in the mirror.

VOCAB_SOURCE = '''"""A witness records what happened."""

MENSORES_MAX_LEN = 100
WITNESS_BYTES = 8
witness = None
'''


def _bind(tmp_path: Path):
    from dunneflow.resolve.glossary import bind
    facts = _extract(tmp_path, VOCAB_SOURCE, "witness.py")
    st = Store(tmp_path / "graph.db")
    st.write_file_facts(facts)
    report = bind(st, None)
    st.close()
    return report


def test_a_fragment_of_a_compound_name_is_held_back(tmp_path: Path) -> None:
    """`BYTES` is the unit on somebody else's constant, not a word this program leans on."""
    report = _bind(tmp_path)
    held = {t.term.lower() for t in report.set_aside}
    assert "bytes" in held, "a unit is still being reported as a word nothing defines"
    assert "bytes" not in {t.term.lower() for t in report.undefined}
    assert "bytes" not in {t.term.lower() for t in report.terms}, (
        "a held-back word is still counted in the coverage denominator"
    )


def test_a_word_that_names_something_is_never_held_back(tmp_path: Path) -> None:
    """`witness` is a module here as well as the first word of two constants."""
    report = _bind(tmp_path)
    assert "witness" not in {t.term.lower() for t in report.set_aside}
    assert "witness" in {t.term.lower() for t in report.terms}


def test_the_program_s_own_word_is_held_back_and_that_is_why_it_is_offered(
        tmp_path: Path) -> None:
    """The case the reader has to settle, and the reason nothing decides it here.

    `MENSORES_MAX_LEN` is the program's own word in front of a modifier and a unit, and
    the split cannot tell the three apart. `MENSORES` may occur nowhere else at all --
    which is exactly when holding it back loses something, so it is *held*, listed, and
    offered back rather than dropped.
    """
    report = _bind(tmp_path)
    held = {t.term.lower() for t in report.set_aside}
    assert "mensores" in held, (
        "the program's own word, standing in front of a modifier, was dropped rather than "
        "held -- and dropped is the one state a reader cannot overturn"
    )
    # `MAX` and `LEN` never reach the split at all: `is_ordinary` refuses them upstream,
    # which is the older half of the same judgement and is left where it is.
    assert "max" not in {t.term.lower() for t in report.terms}


def test_a_defined_word_is_never_held_back(tmp_path: Path) -> None:
    """The third condition, and the one that keeps this from costing a definition.

    A word somebody troubled to define is vocabulary whatever the code does with it. It is
    why this rule takes 889 words off Society's worklist and no defined term with them.
    """
    from dunneflow.resolve.glossary import Sense, Term
    from dunneflow.schema import Provenance
    t = Term(term="BYTES")
    t.kinds["constant"] = 3
    assert t.only_inside_a_name
    t.senses.append(Sense(definition="the size of a thing",
                          provenance=Provenance.DECLARED_DOCS, source="d.md", line=1))
    assert not t.only_inside_a_name, "a defined word was held back"
