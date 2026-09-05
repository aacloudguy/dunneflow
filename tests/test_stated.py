"""The stated lane: naming rules quoted out of the project's own documents.

Three things matter here and only one of them is about the rules.

**Three absences are three answers.** No documentation was read; documents were read and
there were none; documents were read and none of them states a naming rule. They arrive as
the same empty list and the page must be able to tell them apart, or *"we did not look"*
renders as *"there is nothing there"* -- the one claim this tool exists not to make.

**One reading, three readers.** `11-naming.md`, the dashboard and these tests all ask the
same question, and a query kept beside one caller is right until the second arrives
(rule 51). The `checkable` sentence is the sharper half: it had never been printed at all
until tables were read, and the first thing it said on its first outing was wrong.

**Nothing here is a comparison.** `checkable` records that a rule names both a class of
identifier and a spelling, so a check *could* be written. No check is run, and no claim on
either naming page depends on one.
"""

from __future__ import annotations

from pathlib import Path

from dunneflow import revisions
from dunneflow.docstore import DocStore
from dunneflow.render.naming import stated_rules as render_stated_rules
from dunneflow.resolve.stated import checkable_sentence, stated_rules
from dunneflow.store import Store
from dunneflow.walk import analyze_docs_tree
from dunneflow.web import serve as serve_mod
from dunneflow.web.vocabulary import stated_naming

# A naming standard written as a table, which is how most enterprises write one -- and the
# shape that yielded zero FORM rules across 2,064 real documents until `_table()` learned to
# offer its rows to the rule detector.
STANDARD = """---
paths: ['src/**/*.md']
---

# House style

## Naming Conventions

| Type | Convention | Example |
|---|---|---|
| Files | kebab-case | `my-file.md` |
| Bash variables | CAPS_UNDERSCORES | `MY_VAR` |
| Step names | snake_case | `run_step` |

## Naming rules

- **Latin-only** — no Greek borrowings, because the house voice is Roman throughout.
"""

PLAIN = """# Notes

This document talks about names at length and states no rule about any of them.
It mentions kebab-case in passing, which is not the same as requiring it.
"""


def _scan(root: Path, files: dict[str, str]) -> DocStore:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    store = DocStore(root / "docs.db")
    analyze_docs_tree(root, store, jobs=1)
    return store


# -- the three absences ------------------------------------------------------- #


def test_no_documentation_read_is_not_no_rules_stated(tmp_path: Path) -> None:
    """`--no-docs` and a project that states nothing must not read alike."""
    got = stated_naming(None)
    assert got["read"] is False
    assert got["rules"] == []
    assert got["documents_seen"] == 0


def test_documents_read_and_none_of_them_states_a_rule(tmp_path: Path) -> None:
    """The ordinary case, and the one design rule 21 is for."""
    with _scan(tmp_path, {"notes.md": PLAIN}) as docs:
        got = stated_naming(docs)
    assert got["read"] is True, "the scan happened; that is the fact the page needs"
    assert got["rules"] == []
    assert got["documents_seen"] == 1, "a document was read and said nothing"


def test_documents_read_and_there_were_none(tmp_path: Path) -> None:
    with _scan(tmp_path, {}) as docs:
        got = stated_naming(docs)
    assert got["read"] is True and got["documents_seen"] == 0


# -- the rules themselves ----------------------------------------------------- #


def test_a_table_and_a_paragraph_land_in_their_own_lanes(tmp_path: Path) -> None:
    """Two shapes of rule, and reading them the same way makes each read worse."""
    with _scan(tmp_path, {"style.md": STANDARD}) as docs:
        got = stated_naming(docs)
    lanes = {r["lane"] for r in got["rules"]}
    assert lanes == {"FORM", "VOCABULARY"}, \
        "a table is the Form lane and a house-voice rule is the Vocabulary one"
    form = [r for r in got["rules"] if r["lane"] == "FORM"]
    assert {r["scope"] for r in form} >= {"files", "variables"}
    assert {r["pattern"] for r in form} >= {"kebab-case", "CAPS_UNDERSCORES"}


def test_a_rule_naming_no_class_of_identifier_is_kept_not_dropped(tmp_path: Path) -> None:
    """Design rule 1. "Step names: snake_case" gives a spelling and no population.

    It is a rule this tool has no population for, which is a different thing from a rule
    that was never read -- and the reason it is `checkable = 0` rather than absent.
    """
    with _scan(tmp_path, {"style.md": STANDARD}) as docs:
        got = stated_naming(docs)
    steps = [r for r in got["rules"] if "Step names" in r["text"]]
    assert len(steps) == 1, "the row vanished instead of being kept with an empty scope"
    assert steps[0]["scope"] == ""
    assert steps[0]["checkable"] is False
    assert steps[0]["pattern"] == "snake_case", "the half it does have is still carried"


def test_every_rule_carries_the_document_and_the_line_it_came_from(tmp_path: Path) -> None:
    """A quotation proves itself by opening. Design rule 13 for the stated lane."""
    with _scan(tmp_path, {"style.md": STANDARD}) as docs:
        got = stated_naming(docs)
    assert got["rules"]
    for r in got["rules"]:
        assert r["doc"], "a rule with no document cannot be opened"
        assert r["line"] > 0, "a rule with no line opens the top of a file"
        assert r["text"].strip(), "an empty quotation is not a quotation"


def test_the_checkable_sentence_never_claims_a_check_is_run(tmp_path: Path) -> None:
    """The field is right and the sentence was wrong once, on its first outing.

    `checkable` means the rule names both a class of identifier and a spelling, so a check
    could be written for it. It has never meant that one is run, and the first time the true
    branch was ever printed it said "Mechanically checkable." beside a rule DunneFlow has no
    population for.
    """
    with _scan(tmp_path, {"style.md": STANDARD}) as docs:
        rules = stated_rules(docs)
    assert rules
    for r in rules:
        note = checkable_sentence(r)
        assert note
        if r.checkable:
            assert "does not yet run one" in note
        else:
            assert "No query can decide" in note


def test_the_served_note_is_the_rendered_one(tmp_path: Path) -> None:
    """Rule 51: two surfaces spelling one fact two ways is two facts."""
    with _scan(tmp_path, {"style.md": STANDARD}) as docs:
        served = stated_naming(docs)
        rules = stated_rules(docs)
    assert [r["note"] for r in served["rules"]] == [checkable_sentence(r) for r in rules]


# -- one reading, three readers ----------------------------------------------- #


def test_the_report_and_the_dashboard_read_the_same_rules(tmp_path: Path) -> None:
    """`render/naming.py` re-exports the shared reader rather than keeping its own.

    It had its own copy of the query and its own `StatedRule` until the dashboard needed
    them. A second reading is correct on the day it is written and is the thing that drifts.
    """
    with _scan(tmp_path, {"style.md": STANDARD}) as docs:
        rendered = render_stated_rules(docs)
        served = stated_naming(docs)
    assert render_stated_rules is stated_rules, "the renderer kept a second reading"
    assert [(r.doc, r.line, r.lane) for r in rendered] \
        == [(r["doc"], r["line"], r["lane"]) for r in served["rules"]]


def test_a_duplicate_document_states_its_rule_once(tmp_path: Path) -> None:
    """335 documents in agent worktrees were copies of the project's own research.

    Design rule 1 says the filter is never silent, which is why `duplicates` travels with
    the rules -- but a rule quoted out of two byte-identical files is one rule.
    """
    with _scan(tmp_path, {"style.md": STANDARD,
                          "worktrees/agent-1/style.md": STANDARD}) as docs:
        docs.mark_duplicates()
        got = stated_naming(docs)
    docs_named = {r["doc"] for r in got["rules"]}
    assert len(docs_named) == 1, f"the copy was quoted too: {docs_named}"
    assert got["documents_seen"] == 2 and got["duplicates"] == 1, \
        "the fold is stated rather than silent"


# -- the route ----------------------------------------------------------------- #

TINY = "def open_it(path):\n    return path\n"


class _Cap:
    """Enough of a handler to call one route and keep what it answered."""

    def __init__(self, live: object) -> None:
        self._live = live
        self.body: dict = {}

    def _json(self, body: dict) -> None:
        self.body = body


def _served(tmp_path: Path, *, with_docs: bool) -> dict:
    """`/api/stated` over a real base, with or without a document store beside it."""
    from dunneflow.extractors.python.extract import extract_file

    out = tmp_path / "prog"
    out.mkdir()
    rev = "2026-09-05T10:00:00Z"
    graph = revisions.db_path(out, revisions.GRAPH, rev)
    store = Store(graph)
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "m.py").write_text(TINY, encoding="utf-8")
    store.write_file_facts(extract_file(tree / "m.py", tree))
    store.set_meta("revision", rev)
    store.set_meta("program", "tinyprog")
    store.conn.commit()
    store.close()

    if with_docs:
        docs_root = tmp_path / "prose"
        docs_root.mkdir()
        (docs_root / "style.md").write_text(STANDARD, encoding="utf-8")
        with DocStore(revisions.db_path(out, revisions.DOCS, rev)) as st:
            analyze_docs_tree(docs_root, st, jobs=1)

    live = serve_mod._Live(out / "source.db", out)
    live.open(graph)
    cap = _Cap(live)
    serve_mod._Handler._r_stated(cap, {})      # type: ignore[arg-type]
    return cap.body


def test_the_route_answers_with_the_rules_and_the_corpus(tmp_path: Path) -> None:
    """Design rule 16: the hop into a document is a capability, never an assumption.

    Every rule names a document and a line, and *"read it in the document"* needs
    `docsource.db` to hold the version on screen. That is a fact about the process and the
    base rather than about the rules, so it rides on the route -- and without it the button
    would render on a map with no document sidecar and do nothing at all.
    """
    body = _served(tmp_path, with_docs=True)
    assert body["read"] is True
    assert [r["lane"] for r in body["rules"]].count("FORM") == 3
    assert "corpus" in body, "the page has no way to learn whether the hop can work"
    assert body["corpus"]["opens"] is False, "no bodies were captured beside this map"
    assert body["corpus"]["reason"], "a refusal with no reason is a blank (design rule 21)"


def test_the_route_answers_when_no_documentation_was_read(tmp_path: Path) -> None:
    """The ordinary map. `read` is False and every other field is still answered."""
    body = _served(tmp_path, with_docs=False)
    assert body["read"] is False
    assert body["rules"] == [] and body["documents_seen"] == 0
    assert body["corpus"]["opens"] is False and body["corpus"]["reason"]
