"""Named artefacts, and the mirror of the traceability report.

The interesting failures here are not "did the join work". They are the four ways this
report could confidently mislead:

* missing the artefact surface, which is the defect that motivated the whole feature --
  `tabularium` is glossed in Mensores' pantheon and read as abandoned vocabulary until
  DunneFlow learned to see the database the program writes to;
* admitting a heading as a term, which turns the definition extractor's over-reach into
  a finding about the program being read;
* matching `Gate` inside `aggregate`, which is rule 5 in prose;
* reading an artefact out of a docstring, which is rule 9.

Each has a test. The fixtures run the real extractors rather than writing rows by hand,
because a hand-built store cannot catch a detector that stops firing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow.docstore import DocStore
from dunneflow.extractors.python.extract import extract_file
from dunneflow.render.mirror import render_mirror
from dunneflow.render.page import Stamp
from dunneflow.resolve.mirror import (
    ARTEFACT_NAMES_SQL,
    BANDS,
    admit,
    key_of,
    measure,
)
from dunneflow.store import Store
from dunneflow.walk import analyze_docs_tree, analyze_tree

# A renderer is handed the map's three instants, never a bare string. The values do
# not matter here -- these tests are about what the page says of the program.
STAMP = Stamp(generated="2026-01-01 00:00 UTC", revision="", analysed="")

# --------------------------------------------------------------------------- #
# The program. Every artefact case that mattered on real code, and every near
# miss that must not be read as one.
# --------------------------------------------------------------------------- #

PROGRAM = '''
"""A program that names files.

This docstring mentions notes.md and secrets.db, and neither may be extracted:
documentation is never code (rule 9), in this direction as in the other.
"""
from pathlib import Path

MENSORES_DIRNAME = ".mensores"


def open_ledger(root: Path):
    """Open the ledger. The docstring names phantom.db, which is not a fact."""
    # tabularium.db is also named in this comment, and comments are not code either.
    db = root / MENSORES_DIRNAME / "tabularium.db"
    config = f"{root}/groma.json"
    return db, config


def near_misses(root: Path):
    version = "1.2.3"
    encoding = "utf-8"
    module = "mensores.cli"
    host = "freetsa.org"
    endpoint = "https://example.invalid/thing.json"
    prose = "see config.yaml for details"
    computed = f"{version}.db"
    return version, encoding, module, host, endpoint, prose, computed


def patterns(root: Path):
    return sorted(root.glob("chaos_*.py"))


def carries_the_word(disceptator_handle: str) -> None:
    """A parameter bears the word and nothing is named for it."""
    print(disceptator_handle)


def talks_about_it() -> None:
    # An aggregate is not what this means, and delegating is not it either.
    # The scriba writes the record.
    print("done")
'''

# `tabularium` is defined and the program names a file after it -> NAMED.
# `disceptator` is defined and only a parameter carries it -> BORNE.
# `scriba` is defined and only a comment says it -> SPOKEN.
# `quaesitor` is defined and appears nowhere -> ABSENT.
# `Gate` is defined and appears only inside `aggregate` and `delegating` -> ABSENT.
GLOSSARY_DOC = """# Glossary

- **tabularium** — the Roman state records office, where the ledger lives.
- **disceptator** — one who argues out a contested point.
- **scriba** — the clerk who writes the record.
- **quaesitor** — the investigating magistrate, never built.
- **Gate** — a quality check between phases.
"""

# Everything the admission rule must set aside, one document's worth.
NOISE_DOC = """# Glossary of notes

- **test_adr_0012_has_carve_out_criteria_section** — asserts the carve-out exists.
- **read_all() -> dict** — returns everything.
- **1.1 Term identity model** — how terms are identified.
- **Files likely modified by this change** — the blast radius.
- **class _AbAssignment** — the assignment record.
"""


@pytest.fixture(scope="module")
def mirrored(tmp_path_factory):
    root = tmp_path_factory.mktemp("mirrored")
    (root / "prog.py").write_text(PROGRAM, encoding="utf-8")
    docs = root / "docs"
    docs.mkdir()
    (docs / "glossary.md").write_text(GLOSSARY_DOC, encoding="utf-8")
    (docs / "notes.md").write_text(NOISE_DOC, encoding="utf-8")

    store = Store(root / "graph.db")
    analyze_tree(root, store)
    doc_store = DocStore(root / "docs.db")
    analyze_docs_tree(docs, doc_store, jobs=1)
    doc_store.mark_duplicates()
    yield store, doc_store, root
    store.close()
    doc_store.close()


@pytest.fixture(scope="module")
def report(mirrored):
    store, docs, _ = mirrored
    return measure(store, docs)


def band_of(result, term: str) -> str:
    for t in result.terms:
        if t.term.lower() == term.lower():
            return t.band
    raise AssertionError(f"{term} not admitted; admitted: {[t.term for t in result.terms]}")


# --------------------------------------------------------------------------- #
# Artefacts: the surface the mirror was built on
# --------------------------------------------------------------------------- #


def _artefacts(tmp_path: Path, source: str):
    f = tmp_path / "t.py"
    f.write_text(source, encoding="utf-8")
    return extract_file(f, tmp_path).artefacts


def test_a_path_assembled_from_parts_still_names_its_file(tmp_path):
    """The defect that motivated the feature.

    `root / ".mensores" / "tabularium.db"` is not a module, not a table and not a
    boundary target, because only the parts are literals. If this stops working, the
    most-named thing in a program becomes invisible again.
    """
    found = _artefacts(tmp_path, 'p = root / ".mensores" / "tabularium.db"\n')
    assert [(a.name, a.stem, a.kind) for a in found] == [
        ("tabularium.db", "tabularium", "DATABASE")
    ]


def test_an_f_string_names_the_file_when_the_basename_is_literal(tmp_path):
    found = _artefacts(tmp_path, 'p = f"{root}/groma.json"\n')
    assert [a.name for a in found] == ["groma.json"]
    # The literal is recorded whole, placeholder included -- rule 8. A value shortened
    # before it reaches the store is lost rather than merely unshown.
    assert found[0].literal == "?/groma.json"


def test_an_interpolated_basename_names_nothing(tmp_path):
    """`f"{name}.db"` names a file whose name the reader cannot look up."""
    assert _artefacts(tmp_path, 'p = f"{name}.db"\n') == []


@pytest.mark.parametrize(
    "literal",
    [
        '"1.2.3"',                       # a version
        '"utf-8"',                       # an encoding
        '"mensores.cli"',                # a dotted module path
        '"freetsa.org"',                 # a hostname: `.org` is a TLD, not org-mode
        '"https://example.invalid/a.json"',   # a URL is a network boundary
        '"see config.yaml for details"',      # prose that contains a filename
    ],
)
def test_a_trailing_dotted_part_is_not_an_extension(tmp_path, literal):
    """Rule 5. The extension list in `detectors/*.yaml` is the whole defence."""
    assert _artefacts(tmp_path, f"x = {literal}\n") == []


def test_a_glob_is_marked_as_a_pattern(tmp_path):
    found = _artefacts(tmp_path, 'g = root.glob("chaos_*.py")\n')
    assert [(a.name, a.is_pattern) for a in found] == [("chaos_*.py", True)]


def test_a_docstring_never_yields_an_artefact(tmp_path):
    """Rule 9. A sentence naming a file is not the program naming a file."""
    source = '"""This module reads notes.md and writes secrets.db."""\nX = 1\n'
    assert _artefacts(tmp_path, source) == []


def test_the_same_file_named_twice_on_one_line_counts_once(tmp_path):
    """An f-string is visited whole and then descended into.

    Without the guard, `f"{root}/g.json"` names `g.json` twice -- once with the fuller
    literal and once from the bare constant part -- and every count on the page is
    inflated by however many f-strings mention a file.
    """
    found = _artefacts(tmp_path, 'p = f"{root}/groma.json"\nq = ("a.db", "b.db")\n')
    assert sorted(a.name for a in found) == ["a.db", "b.db", "groma.json"]


def test_artefacts_reach_the_store_and_survive_re_extraction(mirrored):
    store, _, _ = mirrored
    rows = {str(r["name"]): int(r["refs"]) for r in store.query(ARTEFACT_NAMES_SQL)}
    assert rows["tabularium.db"] == 1
    assert rows["groma.json"] == 1
    assert "freetsa.org" not in rows


# --------------------------------------------------------------------------- #
# Admission: what counts as a term at all
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("term", "reason"),
    [
        ("test_adr_0012_has_carve_out_criteria_section", "TEST_NAME"),
        ("read_all() -> dict", "CODE_SHAPED"),
        ("src/society/cli/_root.py (lines 110-115)", "CODE_SHAPED"),
        ("class _AbAssignment", "CODE_SHAPED"),
        ("1.1 Term identity model", "HEADING_SHAPED"),
        ("A3. GLOSSARY.md conventions", "HEADING_SHAPED"),
        ('"Touched" Definition', "HEADING_SHAPED"),
        ("Files likely modified by this change", "SENTENCE"),
        ("Cross-clause conflict, resolved", "SENTENCE"),
        ("CC", "TOO_SHORT"),
    ],
)
def test_the_admission_rule_sets_aside_what_is_not_a_word(term, reason):
    assert admit(term) == reason


@pytest.mark.parametrize(
    "term",
    ["tabularium", "Audit event", "Society of Mensores", "Decision graph", "SARIF"],
)
def test_the_admission_rule_keeps_real_vocabulary(term):
    assert admit(term) is None


def test_everything_set_aside_is_listed_whole(report):
    """No filter is ever silent. The count and the listing must agree exactly."""
    assert report.excluded_total == sum(len(v) for v in report.excluded.values())
    assert report.excluded_total > 0
    listed = {t for group in report.excluded.values() for t in group}
    assert len(listed) == report.excluded_total
    admitted = {t.term.lower() for t in report.terms}
    assert not (admitted & {t.lower() for t in listed})


# --------------------------------------------------------------------------- #
# The bands
# --------------------------------------------------------------------------- #


def test_a_word_a_file_is_named_for_is_named(report):
    """`tabularium` names no module, class or table -- only the database.

    This is the assertion the whole feature exists to make pass. Before the artefact
    surface it was ABSENT, and reading that as drift was wrong.
    """
    assert band_of(report, "tabularium") == "NAMED"


def test_a_word_only_a_parameter_carries_is_borne(report):
    assert band_of(report, "disceptator") == "BORNE"


def test_a_word_only_a_comment_says_is_spoken(report):
    assert band_of(report, "scriba") == "SPOKEN"


def test_a_word_nothing_uses_is_absent(report):
    assert band_of(report, "quaesitor") == "ABSENT"


def test_a_word_is_not_used_because_it_is_a_substring(report):
    """Rule 5 in prose. `Gate` appears only inside `aggregate` and `delegating`."""
    assert band_of(report, "Gate") == "ABSENT"


def test_key_matching_is_identity_not_containment():
    assert key_of("Audit event") == key_of("AuditEvent") == key_of("audit_event")
    assert key_of("Gate") != key_of("aggregate")


def test_every_term_lands_in_exactly_one_band(report):
    groups = report.by_band()
    assert sorted(groups) == sorted(b.key for b in BANDS)
    assert sum(len(v) for v in groups.values()) == len(report.terms)


def test_every_band_states_what_would_make_it_wrong():
    """A finding without its blind spot is a guess wearing a uniform."""
    for band in BANDS:
        assert band.blind_spot.strip()
        assert band.meaning.strip()


# --------------------------------------------------------------------------- #
# Rule 13: the query beside a number must return that number
# --------------------------------------------------------------------------- #


def test_the_artefact_query_returns_what_the_page_prints(mirrored, report):
    """A query that disagrees with the number beside it is worse than no query."""
    store, _, _ = mirrored
    rows = store.query(ARTEFACT_NAMES_SQL)
    assert report.artefact_names == len({str(r["name"]) for r in rows})
    assert report.artefacts_seen == sum(int(r["refs"]) for r in rows)


def test_the_definition_count_matches_what_was_carried_forward(report):
    assert report.definitions_seen >= len(report.terms) + report.excluded_total


# --------------------------------------------------------------------------- #
# Documentation is never a prerequisite
# --------------------------------------------------------------------------- #


def test_no_documentation_is_not_a_finding(mirrored, tmp_path):
    """Rule 11. A missing corpus must never be reported as vocabulary drift."""
    store, _, _ = mirrored
    result = measure(store, None)
    assert result.had_docs is False
    assert result.terms == []
    assert result.excluded_total == 0
    # The code half is still measured, so the page can say what it is waiting for.
    assert result.artefact_names > 0

    page = render_mirror(store, None, tmp_path, "sample", STAMP)
    body = page.read_text(encoding="utf-8")
    assert "No documentation was read" in body
    assert "there is no finding here" in body


def test_the_page_lists_every_term_and_every_exclusion(mirrored, tmp_path, report):
    """Nothing on this page is bounded -- rule 8."""
    store, docs, root = mirrored
    page = render_mirror(store, docs, tmp_path, "sample", STAMP)
    body = page.read_text(encoding="utf-8")
    assert page.name == "13-mirror.md"
    for term in report.terms:
        assert f"**{term.term}**" in body, f"{term.term} missing from the page"
    for group in report.excluded.values():
        for term in group:
            assert term in body, f"set-aside {term!r} missing from the page"
    for band in BANDS:
        assert band.blind_spot[:40] in body
