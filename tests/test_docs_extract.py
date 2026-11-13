"""Documentation is the other half of the input, and it lies differently from code.

Every test here exists because of something real. The counter-examples are all drawn
from the Comitia of Lictores corpus: a research paper that reads exactly like a naming
standard, a naming standard whose title made every section look like a glossary, a
placeholder in prose that a tag-stripper ate, and three hundred copies of the same
document sitting in agent worktrees.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow.docstore import DocStore
from dunneflow.extractors.docs import extract_doc
from dunneflow.schema import DocClass, RuleLane
from dunneflow.store import Store

NAMING_STANDARD = '''# Acme Naming System — house vocabulary

## Naming rules (BINDING)

1. **Latin-only** — no Greek borrowings, ever.
2. **Always the binomial** — `acme tribunus`, never bare `tribunus`.

## Identifiers

All private functions must start with a leading underscore.
Every module name uses snake_case.

## Trademark status

**Action before any filing:** a registered attorney must run full clearance.

## The rollcall

| Component | Latin name | Role / meaning |
|---|---|---|
| Harness (the fork: `/acme-*`) | **groma** | the instrument, invoked as `acme-<role>` |
| Audit tools | **tribunus** | the magistrate who audits the records |
'''

RESEARCH_PAPER = '''---
kind: research
title: Naming-Standards Importer Design
---

# Naming-Standards Importer Design

## 1. Naming conventions importer

Recommended locks:

1. The importer must read a `files` glob pattern (e.g. `"**/*.tsx"`) that scopes
   which files the rules apply to.
2. All rule selectors must be RE2-compatible.
'''

GLOSSARY = '''---
kind: reference
title: Glossary
---

# Glossary

## Lictor

<dl>
<dt>lictor <em>(noun)</em></dt>
<dd>A vector with applied measurement metadata — provenance and audit trail.</dd>
</dl>
'''

FENCED = '''# Guide

## Glossary

```python
# **widget** — a thing that must never be defined from inside a fence
WIDGET = 1
```

**sprocket** — a thing that may be defined, because it is prose.
'''


def _extract(tmp_path: Path, name: str, body: str):
    f = tmp_path / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    return extract_doc(f, tmp_path)


# -- classification ---------------------------------------------------------- #


def test_naming_standard_is_recognised(tmp_path: Path) -> None:
    facts = _extract(tmp_path, "NAMING.md", NAMING_STANDARD)
    assert facts.doc_class is DocClass.NAMING_STANDARD


def test_a_paper_about_naming_standards_is_not_one(tmp_path: Path) -> None:
    """The counter-example that shaped the whole detector.

    A research document headed "Naming-Standards Importer Design" yielded ten confident
    naming rules -- glob patterns, RE2 recommendations -- every one of them a
    description of software being built to read standards, not a standard.
    """
    facts = _extract(tmp_path, "conventions-naming.md", RESEARCH_PAPER)
    assert facts.doc_class is DocClass.RESEARCH
    assert facts.rules == [], "a paper about naming standards was mined as one"


def test_filename_outranks_the_drawer_it_was_filed_in(tmp_path: Path) -> None:
    """`milestones/NAMING.md` is a naming standard, not a plan."""
    facts = _extract(tmp_path, "milestones/v1.1/NAMING.md", NAMING_STANDARD)
    assert facts.doc_class is DocClass.NAMING_STANDARD


# -- the two lanes ----------------------------------------------------------- #


def test_vocabulary_rules_are_quoted_whole(tmp_path: Path) -> None:
    facts = _extract(tmp_path, "NAMING.md", NAMING_STANDARD)
    vocab = [r for r in facts.rules if r.lane is RuleLane.VOCABULARY]
    latin = [r for r in vocab if "Latin-only" in r.text]
    assert latin, "the binding vocabulary rule was not found"
    assert "no Greek borrowings, ever." in latin[0].text, "the rule was cut short"


def test_form_rules_carry_scope_and_pattern(tmp_path: Path) -> None:
    facts = _extract(tmp_path, "NAMING.md", NAMING_STANDARD)
    form = [r for r in facts.rules if r.lane is RuleLane.FORM]
    assert form, "no form rule was found in a section that states two"
    underscore = [r for r in form if "underscore" in r.text]
    assert underscore and underscore[0].scope == "functions"
    assert underscore[0].checkable


def test_a_spelling_rule_never_lands_in_the_vocabulary_lane(tmp_path: Path) -> None:
    facts = _extract(tmp_path, "NAMING.md", NAMING_STANDARD)
    for rule in facts.rules:
        if "snake_case" in rule.text:
            assert rule.lane is RuleLane.FORM


def test_a_status_section_states_no_rules(tmp_path: Path) -> None:
    """"Action before any filing" is normative, and is not a naming rule."""
    facts = _extract(tmp_path, "NAMING.md", NAMING_STANDARD)
    assert not [r for r in facts.rules if "attorney" in r.text]


# -- definitions ------------------------------------------------------------- #


def test_definition_table_yields_every_term_column(tmp_path: Path) -> None:
    facts = _extract(tmp_path, "NAMING.md", NAMING_STANDARD)
    terms = {d.term for d in facts.definitions}
    assert "groma" in terms and "tribunus" in terms


def test_a_placeholder_in_prose_is_not_an_html_tag(tmp_path: Path) -> None:
    """`acme-<role>` lost its placeholder to a tag stripper. Never truncate at ingest."""
    facts = _extract(tmp_path, "NAMING.md", NAMING_STANDARD)
    groma = [d for d in facts.definitions if d.term == "groma"]
    assert groma and "<role>" in groma[0].definition


def test_html_definition_lists_are_read(tmp_path: Path) -> None:
    facts = _extract(tmp_path, "glossary.md", GLOSSARY)
    assert facts.doc_class is DocClass.GLOSSARY
    lictor = [d for d in facts.definitions if d.term.startswith("lictor")]
    assert lictor and "provenance and audit trail" in lictor[0].definition


def test_a_fenced_block_is_code_and_yields_nothing(tmp_path: Path) -> None:
    """Rule 9's mirror: an example is a statement, not a sentence about one."""
    facts = _extract(tmp_path, "guide.md", FENCED)
    terms = {d.term for d in facts.definitions}
    assert "widget" not in terms, "a definition was mined out of a code fence"
    assert "sprocket" in terms, "prose beside a fence was lost with it"


def test_naming_rules_are_not_also_definitions(tmp_path: Path) -> None:
    """A document titled "... house vocabulary" made every section a glossary."""
    facts = _extract(tmp_path, "NAMING.md", NAMING_STANDARD)
    assert not [d for d in facts.definitions if d.term == "Latin-only"]


# -- structure and frontmatter ----------------------------------------------- #


def test_frontmatter_is_parsed(tmp_path: Path) -> None:
    facts = _extract(tmp_path, "r.md", RESEARCH_PAPER)
    assert facts.frontmatter.get("kind") == "research"
    assert facts.title == "Naming-Standards Importer Design"


def test_a_document_without_headings_is_not_given_any(tmp_path: Path) -> None:
    facts = _extract(tmp_path, "plain.md", "Just a sentence about nothing in particular.\n")
    assert facts.headings == []
    assert facts.definitions == []
    assert facts.rules == []


def test_broken_frontmatter_does_not_stop_the_read(tmp_path: Path) -> None:
    """Ingest never fails on a bad document."""
    facts = _extract(tmp_path, "bad.md", "---\nkind: [unclosed\n---\n\n# Title\n\nBody.\n")
    assert facts.title == "Title"
    assert facts.errors == []


# -- the store --------------------------------------------------------------- #


def test_duplicates_point_at_the_shallowest_copy(tmp_path: Path) -> None:
    """335 documents in agent worktrees were copies of the project's own research."""
    original = _extract(tmp_path, "docs/glossary.md", GLOSSARY)
    copy = _extract(tmp_path, "worktrees/agent-1/docs/glossary.md", GLOSSARY)
    with DocStore(tmp_path / "docs.db") as st:
        with st.batch():
            st.write_doc_facts(original)
            st.write_doc_facts(copy)
        assert st.mark_duplicates() == 1
        dups = st.duplicates()
    assert len(dups) == 1
    assert dups[0][0] == copy.path and dups[0][1] == original.path


def test_an_unchanged_document_is_not_read_twice(tmp_path: Path) -> None:
    """Re-analysis has to be cheap enough to be a habit rather than an event."""
    from dunneflow.walk import analyze_docs_tree

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "glossary.md").write_text(GLOSSARY, encoding="utf-8")
    with DocStore(tmp_path / "docs.db") as st:
        first = analyze_docs_tree(tmp_path, st, jobs=1)
        second = analyze_docs_tree(tmp_path, st, jobs=1)
    assert first.parsed == 1 and first.cached == 0
    assert second.parsed == 0 and second.cached == 1


def test_a_deleted_document_is_forgotten(tmp_path: Path) -> None:
    from dunneflow.walk import analyze_docs_tree

    doc = tmp_path / "glossary.md"
    doc.write_text(GLOSSARY, encoding="utf-8")
    with DocStore(tmp_path / "docs.db") as st:
        analyze_docs_tree(tmp_path, st, jobs=1)
        doc.unlink()
        stats = analyze_docs_tree(tmp_path, st, jobs=1)
        assert stats.removed == 1
        assert st.counts()["documents"] == 0
        assert st.counts()["definitions"] == 0, "facts outlived the document they came from"


def test_the_store_refuses_to_open_the_other_database(tmp_path: Path) -> None:
    """Opening docs.db as a graph dropped every table in it. Once was enough."""
    with DocStore(tmp_path / "docs.db") as st:
        st.write_doc_facts(_extract(tmp_path, "g.md", GLOSSARY))
    with pytest.raises(ValueError, match="not a code graph"):
        Store(tmp_path / "docs.db")
    with DocStore(tmp_path / "docs.db") as st:
        assert st.counts()["documents"] == 1, "the document store was damaged"

    Store(tmp_path / "graph.db").close()
    with pytest.raises(ValueError, match="not a document store"):
        DocStore(tmp_path / "graph.db")


def test_a_prose_rule_change_discards_only_the_document_store(tmp_path: Path) -> None:
    """Rule 12, applied to the other corpus."""
    import dunneflow.docstore as docstore

    with DocStore(tmp_path / "docs.db") as st:
        st.write_doc_facts(_extract(tmp_path, "g.md", GLOSSARY))

    original = docstore.doc_rules_fingerprint
    docstore.doc_rules_fingerprint = lambda: "0000000000000000"  # a rule file was edited
    try:
        with DocStore(tmp_path / "docs.db") as st:
            assert st.rebuilt, "a prose rule change did not discard the document store"
            assert st.counts()["documents"] == 0
    finally:
        docstore.doc_rules_fingerprint = original


# --------------------------------------------------------------------------- #
# Nested checkouts
#
# `.claude` and `.groma` are admitted for documents because that is where a project
# files its charter. Nothing scoped that admission below the top level, so two stale
# agent worktrees under `.claude/worktrees/` put 335 May-era copies of Lictores' own
# governance documents into the corpus -- 14% of it. The duplicate detector caught 303
# and every consumer filters `duplicate_of`, so most numbers were protected. The 32
# that had drifted from their originals were no longer identical and escaped it,
# putting ten definitions into the glossary -- `lictor`, `lictores` and `Comitia of
# Lictores` among them -- sourced from a directory that is not the project.
#
# Each test below is written against a specific way this can half-work, because a
# guard that has only ever passed is a claim nobody has tested (rule 37).
# --------------------------------------------------------------------------- #


def _corpus(root: Path) -> Path:
    """A tree shaped like the real one: a checkout, with documents, holding a worktree."""
    (root / ".git").mkdir()                      # the corpus is itself a checkout
    (root / "README.md").write_text("# The program\n", encoding="utf-8")
    (root / ".claude").mkdir()
    (root / ".claude" / "CLAUDE.md").write_text("# The charter\n", encoding="utf-8")
    nest = root / ".claude" / "worktrees" / "agent-1"
    nest.mkdir(parents=True)
    # a worktree: a .git *file*
    (nest / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")
    (nest / "README.md").write_text("# A stale copy\n", encoding="utf-8")
    (nest / "deep").mkdir()
    (nest / "deep" / "PLAN.md").write_text("# Also stale\n", encoding="utf-8")
    return root


def test_a_nested_worktree_is_not_this_program(tmp_path: Path) -> None:
    """A `.git` *file* marks a worktree, and everything under it is someone else's."""
    from dunneflow.walk import discover_docs

    root = _corpus(tmp_path)
    found = {p.relative_to(root).as_posix() for p in discover_docs(root)}

    assert "README.md" in found
    assert ".claude/CLAUDE.md" in found, (
        "the admission of `.claude` must survive -- skipping the whole directory would "
        "pass the pruning test and lose the charter, which is why it is admitted at all"
    )
    assert not any("worktrees" in f for f in found), sorted(found)


def test_a_nested_clone_is_not_this_program(tmp_path: Path) -> None:
    """A `.git` *directory* marks a clone. Checking only for a file misses it."""
    from dunneflow.walk import discover_docs

    root = tmp_path
    (root / "README.md").write_text("# The program\n", encoding="utf-8")
    nest = root / "docs" / "vendored"
    nest.mkdir(parents=True)
    (nest / ".git").mkdir()
    (nest / "GUIDE.md").write_text("# Someone else's\n", encoding="utf-8")

    found = {p.relative_to(root).as_posix() for p in discover_docs(root)}
    assert found == {"README.md"}, sorted(found)


@pytest.mark.parametrize("marker", [".git", ".hg", ".svn"])
def test_every_marker_is_a_checkout(tmp_path: Path, marker: str) -> None:
    """Version control must stay pluggable: the same claim in three dialects."""
    from dunneflow.walk import discover_docs

    root = tmp_path
    (root / "README.md").write_text("# The program\n", encoding="utf-8")
    nest = root / "sub"
    nest.mkdir()
    (nest / marker).mkdir()
    (nest / "OTHER.md").write_text("# Not ours\n", encoding="utf-8")

    found = {p.relative_to(root).as_posix() for p in discover_docs(root)}
    assert found == {"README.md"}, f"{marker}: {sorted(found)}"


def test_the_root_is_never_treated_as_nested(tmp_path: Path) -> None:
    """The corpus is itself a checkout, and that is the point.

    The half-working version: test the marker without excepting the root, and the walk
    prunes everything on its first step. It yields nothing, reports nothing, and looks
    exactly like a program with no documentation -- which design rule 11 says is a
    normal case, so nobody would question it.
    """
    from dunneflow.walk import discover_docs

    root = tmp_path
    (root / ".git").mkdir()
    (root / "README.md").write_text("# The program\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "guide.md").write_text("# A guide\n", encoding="utf-8")

    found = {p.relative_to(root).as_posix() for p in discover_docs(root)}
    assert found == {"README.md", "docs/guide.md"}, sorted(found)


def test_a_pruned_checkout_is_named(tmp_path: Path) -> None:
    """Design rule 1: no filter is ever silent.

    The half-working version prunes correctly and says nothing. A corpus 14% smaller
    than the tree it was read from is indistinguishable from a smaller project -- and
    across two points in time, from a project that deleted 335 documents.
    """
    from dunneflow.walk import discover_docs

    root = _corpus(tmp_path)
    nested: list[str] = []
    list(discover_docs(root, nested=nested))

    assert len(nested) == 1, nested
    # Compared as a path rather than as text. This one is **not** a stored key: it is read
    # off the screen by whoever ran the command, so it is spelled the way that reader's own
    # platform spells a path (`stored_path` governs what goes into a store, and nothing
    # here goes into one). Asserting on `/` would be asserting on the separator.
    assert Path(nested[0]).parts[-2:] == ("worktrees", "agent-1"), nested


def test_the_walk_reports_what_it_skipped(tmp_path: Path) -> None:
    """And the report must survive the trip to `WalkStats`, not stop at the generator."""
    from dunneflow.docstore import DocStore
    from dunneflow.walk import analyze_docs_tree

    root = _corpus(tmp_path)
    store = DocStore(tmp_path / "out.db")
    stats = analyze_docs_tree(root, store)

    assert stats.found == 2, stats.found          # README.md and .claude/CLAUDE.md
    assert len(stats.nested) == 1, stats.nested
    assert "agent-1" in stats.nested[0]


# --------------------------------------------------------------------------- #
# A naming standard written as a table
#
# The shape the extractor could not read, and the reason the FORM lane was empty
# across a 2,064-document corpus. `_table` consumes a table whole and the loop
# `continue`s, so the prose rule detector is never offered its lines -- while the
# best standard in that corpus states seven conventions as `Type | Convention |
# Example`. Every fixture below is taken from a real table, including every one
# that must yield nothing.
# --------------------------------------------------------------------------- #

CONVENTION_TABLE = """\
# PAUL Style Rules

## Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Files | kebab-case | `plan-phase.md` |
| Commands | `paul:kebab-case` | `paul:plan` |
| Step names | snake_case | `name="load_project_state"` |
| Bash variables | CAPS_UNDERSCORES | `PHASE_ARG` |
| Phase directories | `NN-kebab-name` | `02-rules-layer` |
"""

# The most dangerous near-miss in the corpus: a **glossary** table, in a naming
# standard, under a naming heading, already mined as definitions.
ROLLCALL_TABLE = """\
# Naming

## The rollcall

| Component | Latin name | Role / meaning |
|---|---|---|
| Interview engine | `conciliator` | the one who debates |
| Ledger | `tribunus` | the one who audits |
| Surveyor | `groma` | the surveying instrument |
"""

# Normative in voice, in a naming standard, and a registry lookup rather than a rule.
AVAILABILITY_TABLE = """\
# Naming

## Sub-name availability pass — RESULTS

| Type | Convention | PyPI |
|---|---|---|
| Files | kebab-case | free |
| Commands | snake_case | taken |
| Modules | kebab-case | free |
"""

# The header is unrecognised on both halves, so **only the cells** can carry this one —
# which is the path that has to work for a standard written by somebody who does not work
# here, and the only thing the table-cell pattern vocabulary earns.
UNFAMILIAR_HEADER_TABLE = """\
# Engineering handbook

## Naming

| Thing we mean | How we spell it |
|---|---|
| Modules | CAPS_UNDERSCORES |
| Packages | colon separator |
| Classes | kebab-case |
"""

# One row, so a majority means nothing: one of one is 100%.
ONE_ROW_TABLE = """\
# Engineering handbook

## Naming

| Whatever | However |
|---|---|
| Modules | kebab-case |
"""

# **One half each**, which is what the both-halves rule is actually about. A fixture missing
# *both* halves cannot tell you the rule is enforced — it is refused twice over, and every
# mutation that drops one half still passes. These two isolate it.
SCOPE_ONLY_TABLE = """\
# Engineering handbook

## Naming

| Type | Owner |
|---|---|
| Modules | platform |
| Classes | core |
| Packages | platform |
"""

PATTERN_ONLY_TABLE = """\
# Engineering handbook

## Naming

| Style | Example |
|---|---|
| kebab-case | `a-b` |
| snake_case | `a_b` |
| PascalCase | `Ab` |
"""

# A real table with a gap in it. Documents are written by people and a cell is often left
# blank; a rule minted from one says "Modules:" and nothing else.
GAPPY_TABLE = """\
# Engineering handbook

## Naming

| Type | Convention |
|---|---|
| Modules | kebab-case |
| Classes |  |
|  | snake_case |
| Packages | PascalCase |
"""

# Neither half. `| Name | Port |` is not a glossary, and this is not a standard.
HALF_A_TABLE = """\
# Contributing

## Conventions

| Phase | Status |
|---|---|
| PLAN | done |
| APPLY | done |
| UNIFY | open |
"""


def _form(facts) -> list:
    return [r for r in facts.rules if r.lane is RuleLane.FORM]


def test_a_conventions_table_becomes_one_rule_per_row(tmp_path: Path) -> None:
    """Five rows, five rules, each carrying the row's own line.

    The line matters as much as the rule. `_add_def`'s arithmetic is header, separator,
    then rows, and a citation that opens at the table's first line lands the reader on the
    header rather than on the rule they clicked — adjacent, plausible, and wrong.
    """
    facts = _extract(tmp_path, "rules/style.md", CONVENTION_TABLE)
    form = _form(facts)
    assert len(form) == 5, f"expected one rule per row, got {[r.text for r in form]}"
    by_text = {r.text: r for r in form}
    assert "Files: kebab-case" in by_text
    files = by_text["Files: kebab-case"]
    assert files.scope == "files" and files.pattern == "kebab-case"
    assert files.checkable
    # Rows start at the header's line + 2. The table's header is on line 5 here.
    assert [r.line for r in form] == [7, 8, 9, 10, 11], (
        "the rules do not carry their own rows' lines, so a citation opens at the header"
    )


def test_a_row_naming_no_identifier_class_is_kept_and_not_checkable(
        tmp_path: Path) -> None:
    """Dropping it would be the silent filter design rule 1 exists to prevent.

    "Step names: snake_case" is a real rule somebody wrote. DunneFlow has no population
    called *step names*, so it carries no scope and is not checkable — which is the honest
    pair, and a different claim from the rule not existing.
    """
    facts = _extract(tmp_path, "rules/style.md", CONVENTION_TABLE)
    step = [r for r in _form(facts) if r.text.startswith("Step names")]
    assert step, "a row whose scope is unrecognised was dropped rather than kept"
    assert step[0].scope == "" and not step[0].checkable
    assert step[0].pattern == "snake_case", "the pattern was lost with the scope"


def test_a_glossary_table_in_a_naming_standard_states_no_rules(tmp_path: Path) -> None:
    """The near-miss that would have put ten rollcall mappings into the standard.

    It is a table, in a NAMING_STANDARD, under a heading matching `naming_headings`, and
    every cell is a name. What it is not is a *spelling* rule: no column shows a pattern,
    so the pattern half is missing and the table yields nothing. It is already mined as
    definitions, which is the right lane for it.
    """
    facts = _extract(tmp_path, "NAMING.md", ROLLCALL_TABLE)
    assert facts.doc_class is DocClass.NAMING_STANDARD
    assert _form(facts) == [], (
        "a glossary table was read as a naming standard — the pattern half was not required"
    )
    assert facts.definitions, "and it stopped being read as the definitions it is"


def test_a_reporting_table_states_no_rules_even_in_a_naming_standard(
        tmp_path: Path) -> None:
    """`reports_rather_than_rules` applied to tables, which it was not before.

    A registry availability pass is normative in voice, sits in a naming standard, and is
    a lookup rather than a rule anyone follows when naming a function.
    """
    facts = _extract(tmp_path, "NAMING.md", AVAILABILITY_TABLE)
    assert facts.doc_class is DocClass.NAMING_STANDARD
    assert _form(facts) == [], "a results table entered the standard"


def test_a_scope_column_alone_is_not_a_standard(tmp_path: Path) -> None:
    """Names a class of identifier per row and says nothing about spelling.

    Isolated deliberately. A fixture missing *both* halves is refused twice over, so every
    mutation that drops one half still passes against it — which is how the first version of
    this guard survived three of them (rule 37: it named the right rule and caught nothing).
    """
    facts = _extract(tmp_path, "handbook.md", SCOPE_ONLY_TABLE)
    assert _form(facts) == [], (
        "a table with a scope column and no pattern column was read as a standard, so "
        "`| Type | Owner |` states a naming rule"
    )


def test_a_pattern_column_alone_is_not_a_standard(tmp_path: Path) -> None:
    """Shows spellings and never says what they are the spelling *of*."""
    facts = _extract(tmp_path, "handbook.md", PATTERN_ONLY_TABLE)
    assert _form(facts) == [], (
        "a table of spellings with nothing to attach them to was read as a standard"
    )


def test_neither_half_is_not_a_standard(tmp_path: Path) -> None:
    """`| Name | Port |` is not a glossary, and `| Phase | Status |` is not a standard."""
    facts = _extract(tmp_path, "CONTRIBUTING.md", HALF_A_TABLE)
    assert _form(facts) == [], (
        "a table with neither column role was read as a naming standard"
    )


def test_the_cells_carry_a_table_whose_header_is_unrecognised(tmp_path: Path) -> None:
    """The path the table-cell pattern vocabulary exists for, and the only thing it earns.

    Measured: the one real table in the corpus is headed `Convention`, which
    `pattern_columns` matches, so it yields its rules with those regexes removed. They earn
    the **cell** path instead — 3 of 7 cells match without them, 5 of 7 with — and the cell
    path is what has to carry a standard written by somebody who does not work here. No
    header here is in either list; if this passes on the headers alone, the guard is blind.
    """
    facts = _extract(tmp_path, "handbook.md", UNFAMILIAR_HEADER_TABLE)
    form = _form(facts)
    assert len(form) == 3, (
        "a table whose header neither list knows was not read from its cells, so a standard "
        f"written outside this project cannot be imported at all: {[r.text for r in form]}"
    )
    assert {r.scope for r in form} == {"modules", "packages", "classes"}


def test_one_row_is_never_a_majority(tmp_path: Path) -> None:
    """One cell of one is 100%, which is not evidence of anything."""
    facts = _extract(tmp_path, "handbook.md", ONE_ROW_TABLE)
    assert _form(facts) == [], "a single-row table was read as a standard on a 100% majority"


def test_a_row_with_an_empty_cell_states_no_rule(tmp_path: Path) -> None:
    """A blank cell is not a rule, and a rule that reads "Classes:" is worse than none.

    Documents are written by people and half a row is common. Both halves are needed for
    the row for the same reason both are needed for the table: without the spelling there
    is no rule, and without the thing there is nothing the spelling is *of*.
    """
    facts = _extract(tmp_path, "handbook.md", GAPPY_TABLE)
    form = _form(facts)
    assert [r.text for r in form] == ["Modules: kebab-case", "Packages: PascalCase"], (
        f"a half-empty row was minted as a rule: {[r.text for r in form]}"
    )


def test_a_conventions_table_in_a_plan_states_no_rules(tmp_path: Path) -> None:
    """The class gate, which tables did not go through at all before.

    Recall is what precision costs: a plan really can settle a convention and that rule is
    lost here, exactly as it is for prose. The model pass is where it comes back.
    """
    facts = _extract(tmp_path, "phases/03-storage/03-01-PLAN.md", CONVENTION_TABLE)
    assert facts.doc_class is not DocClass.NAMING_STANDARD
    assert _form(facts) == [], "a table in a plan was mined as a standard"


# --------------------------------------------------------------------------- #
# A program's own output is not its own documentation
#
# Found by pointing DunneFlow at itself: 46 of 54 documents came out of
# `output/`, including 369,684 words of `06-governance.md` about a *different*
# program, and all 942 rules it then claimed came from them. Rule 57 with the
# tool's own output in place of a stale worktree.
# --------------------------------------------------------------------------- #

def test_a_map_beside_the_docs_is_not_documentation(tmp_path: Path) -> None:
    """Every directory holding a graph is pruned; the rest of the tree is not."""
    from dunneflow import revisions
    from dunneflow.walk import discover_docs

    (tmp_path / "README.md").write_text("# Real prose", encoding="utf-8")
    out = tmp_path / "output"
    for prog in ("lictores", "dunneflow"):
        d = out / prog
        d.mkdir(parents=True)
        (d / "graph@2026-01-01T00-00-00Z.db").write_bytes(b"")
        (d / "11-naming.md").write_text("# Generated report", encoding="utf-8")
    # A directory of hand-written prose, sitting right beside the maps.
    notes = out / "notes"
    notes.mkdir()
    (notes / "decisions.md").write_text("# Ours", encoding="utf-8")

    exclude = frozenset({out / "lictores"}) | revisions.program_dirs(out)
    found = {p.relative_to(tmp_path).as_posix()
             for p in discover_docs(tmp_path, exclude=exclude)}
    assert "README.md" in found
    assert "output/notes/decisions.md" in found, (
        "hand-written prose beside the maps was dropped — the name `output` was "
        "blacklisted rather than the maps recognised"
    )
    assert not [f for f in found if f.startswith("output/lictores")], (
        "the program's own generated report was read as its documentation"
    )
    assert not [f for f in found if f.startswith("output/dunneflow")], (
        "another program's generated report was read as this one's documentation — the "
        "same mistake one directory up, and the one that actually happened"
    )


# Rule 92, the same subject one door over. Everything above hands `discover_docs` an
# `exclude` set computed from the output root, which is what `analyze` did -- and that set
# is empty of anything in this tree whenever the output root is somewhere else, which is
# where an installed application always keeps it. So the question is asked of the tree by
# the walk itself, and these are the four things that has to get right.


def test_a_map_nested_deeper_than_one_level_is_pruned(tmp_path: Path) -> None:
    """The half `program_dirs` could not reach, and the shape that actually bit.

    `program_dirs` looks at the output root and one level of children, because program
    directories are siblings by construction. A checkout's `output/` is two levels down
    from the tree root and deeper still in a monorepo, so nothing above is even asked
    about it. DunneFlow's own map, built by the packaged application: 122 of 147
    documents came out of a directory no exclude set had ever heard of.
    """
    from dunneflow.walk import discover_docs

    (tmp_path / "README.md").write_text("# Real prose", encoding="utf-8")
    buried = tmp_path / "a" / "b" / "c" / "lictores"
    buried.mkdir(parents=True)
    (buried / "graph@2026-01-01T00-00-00Z.db").write_bytes(b"")
    (buried / "06-governance.md").write_text("# Generated", encoding="utf-8")
    (buried / "map@2026-01-01T00-00-00Z").mkdir()
    (buried / "map@2026-01-01T00-00-00Z" / "11-naming.md").write_text(
        "# Generated", encoding="utf-8")

    found = {p.relative_to(tmp_path).as_posix() for p in discover_docs(tmp_path)}
    assert found == {"README.md"}, (
        f"a map four levels down was read as documentation: {sorted(found)} -- no "
        "exclusion computed from the output root can see it (rule 92)"
    )


def test_a_docs_root_that_is_itself_a_map_yields_nothing(tmp_path: Path) -> None:
    """The one place this marker and the checkout marker disagree, deliberately.

    `test_the_root_is_never_treated_as_nested` exempts the root from the VCS test because
    the corpus is itself a checkout and that is the point. A corpus is never itself a
    *map*, so the opposite holds: `--docs` aimed into a program directory is the failure
    and not the ordinary case. It cannot fire by accident on the default path, where the
    docs root is the nearest ancestor holding a `pyproject.toml` and a program directory
    holds none.
    """
    from dunneflow.walk import discover_docs

    prog = tmp_path / "lictores"
    prog.mkdir()
    (prog / "graph@2026-01-01T00-00-00Z.db").write_bytes(b"")
    (prog / "06-governance.md").write_text("# Generated", encoding="utf-8")

    maps: list[str] = []
    found = list(discover_docs(prog, maps=maps))
    assert not found, f"the root's own map was read as documentation: {found}"
    assert maps == [str(prog.resolve())], (
        f"a docs root that yielded nothing did not say why: {maps}"
    )


def test_a_pruned_map_is_named(tmp_path: Path) -> None:
    """Design rule 1, and the number is larger here than for a checkout.

    A pruned worktree was 14% of Lictores' corpus. A pruned map was **122 of 147
    documents** of DunneFlow's own, so the version that prunes correctly and says nothing
    reports a corpus 83% smaller than what the reader can see in the directory -- and
    across two points in time, a project that deleted most of its documentation.
    """
    from dunneflow.walk import discover_docs

    (tmp_path / "README.md").write_text("# Real prose", encoding="utf-8")
    prog = tmp_path / "output" / "lictores"
    prog.mkdir(parents=True)
    (prog / "graph@2026-01-01T00-00-00Z.db").write_bytes(b"")
    (prog / "06-governance.md").write_text("# Generated", encoding="utf-8")

    maps: list[str] = []
    found = {p.relative_to(tmp_path).as_posix()
             for p in discover_docs(tmp_path, maps=maps)}
    assert found == {"README.md"}, sorted(found)
    assert maps == [str(prog.resolve())], (
        f"the walk pruned a map and did not name it: {maps}"
    )


def test_a_directory_called_output_holding_prose_is_still_read(tmp_path: Path) -> None:
    """The property the name test was rejected for, asserted against the new mechanism.

    `output/` is a fine name for a directory of hand-written documents, and nothing may
    drop one because a tool its author has never heard of writes there (rule 30). The
    exclude set honoured that and this has to honour it too, or the fix trades one false
    corpus for another.
    """
    from dunneflow.walk import discover_docs

    out = tmp_path / "output"
    (out / "notes").mkdir(parents=True)
    (out / "decisions.md").write_text("# Ours", encoding="utf-8")
    (out / "notes" / "more.md").write_text("# Also ours", encoding="utf-8")

    maps: list[str] = []
    found = {p.relative_to(tmp_path).as_posix()
             for p in discover_docs(tmp_path, maps=maps)}
    assert found == {"output/decisions.md", "output/notes/more.md"}, sorted(found)
    assert not maps, f"prose was mistaken for a map: {maps}"


def test_program_dirs_recognises_a_map_and_not_a_name(tmp_path: Path) -> None:
    """A graph makes a program directory. Being called `output` does not."""
    from dunneflow import revisions

    root = tmp_path / "output"
    (root / "withmap").mkdir(parents=True)
    (root / "withmap" / "graph.db").write_bytes(b"")
    (root / "justdocs").mkdir()
    (root / "justdocs" / "notes.md").write_text("hi", encoding="utf-8")
    got = {p.name for p in revisions.program_dirs(root)}
    assert got == {"withmap"}, f"recognised on something other than a graph: {got}"
    assert revisions.program_dirs(tmp_path / "nope") == frozenset(), (
        "a missing directory raised instead of answering nothing"
    )


CONSTRAINT_PLAN = '''# Plan 22-03 — the interview shell

## AC-19: Performance budget for glossary tools + N=1000 fixture

Each write tool runs validation BEFORE store or lock calls:

- `term_name`: anchored regex `^[A-Za-z0-9][A-Za-z0-9 _\\-\\.]{0,99}$` (max 100 chars)
- `definition`: 1 ≤ len ≤ 5000 chars
- `cross_references`: list, ≤50 entries, each entry ≤100 chars
- `neo4j_node_id`: null reserved-future (Phase 15 populates)
- `escalate`: the tool hands the turn back to a person, and says why

**Tier-1 budget** — lock wall-time to ≤30s p95 and ≤200 words of output at Plan 17-01.
'''


def test_a_constraint_is_not_a_definition(tmp_path: Path) -> None:
    """A validation list, written in the shape a gloss is written in.

    `definition: 1 ≤ len ≤ 5000 chars` reached Comitia's glossary as one of sixty
    defined terms, so the page said the program defines the word *definition* and meant
    a bound on a string's length. The section admits definitions because its heading
    mentions the glossary, which is left standing deliberately; what is refused is the
    gloss that states a shape rather than a meaning.
    """
    facts = _extract(tmp_path, "22-03-PLAN.md", CONSTRAINT_PLAN)
    terms = {d.term for d in facts.definitions}
    for refused in ("definition", "cross_references", "term_name", "neo4j_node_id"):
        assert refused not in terms, f"{refused} was read as a defined word"


def test_the_test_is_on_the_opening_not_on_the_numbers(tmp_path: Path) -> None:
    """A sentence that reaches a bound partway through is prose about a budget.

    Three of Comitia's definitions quote a number in that way and all three are kept; the
    refusal fires only where the gloss *begins* by stating a shape. Without that the rule
    takes real definitions with it, which is how a precision fix becomes a recall defect.
    """
    facts = _extract(tmp_path, "22-03-PLAN.md", CONSTRAINT_PLAN)
    kept = {d.term: d.definition for d in facts.definitions}
    assert "escalate" in kept, "a definition beside four constraints was refused with them"
    assert "hands the turn back" in kept["escalate"]
    # The half a mutation reaches first: `match` rather than `search`. This gloss holds two
    # bounds and states a meaning, and searching anywhere in it refuses the meaning too.
    assert "Tier-1 budget" in kept, (
        "the refusal is looking past the opening, so a sentence that quotes a bound is "
        "being read as a constraint"
    )


FIGURE = '''# Tutorial

## The glossary

![The glossary page: "81 of 223 defined" [Go to it] and a list of terms.](images/10-glossary.jpg)

The page lists every word.

## Sprocket

A toothed wheel that drives a chain.

![a sprocket](images/sprocket.png)
'''


def test_a_heading_over_a_picture_is_not_a_definition(tmp_path):
    """BACKLOG 26: the alt text of a screenshot was read as what "The glossary" means."""
    facts = _extract(tmp_path, "docs/tutorial/glossary.md", FIGURE)
    defs = {d.term: d.definition for d in facts.definitions}
    assert "The glossary" not in defs, defs.get("The glossary")
    assert not any("![" in d or "Go to it" in d for d in defs.values()), defs


def test_a_heading_over_a_paragraph_is_still_a_definition(tmp_path):
    """The positive control: the form the image rule must not swallow."""
    body = "# Guide\n\n## Glossary\n\n### Sprocket\n\nA toothed wheel that drives a chain.\n"
    facts = _extract(tmp_path, "docs/glossary.md", body)
    defs = {d.term: d.definition for d in facts.definitions}
    assert defs.get("Sprocket", "").startswith("A toothed wheel"), defs


# ---- a name in somebody else's tree is not a promise about what is behind it --- #

def _hostile(tmp_path):
    import os
    import sys

    import pytest

    if sys.platform == "win32":
        pytest.skip("needs symbolic links and named pipes, which this account cannot make")
    tree, outside = tmp_path / "tree", tmp_path / "outside"
    (tree / "sub").mkdir(parents=True)
    outside.mkdir()
    (outside / "secret.py").write_text('KEY = "outside-secret"\n', encoding="utf-8")
    (outside / "notes.md").write_text("# Outside\n\noutside-doc\n", encoding="utf-8")
    (tree / "ok.py").write_text("def inside():\n    return 1\n", encoding="utf-8")
    (tree / "README.md").write_text("# Inside\n", encoding="utf-8")
    os.symlink(outside / "secret.py", tree / "leak.py")
    os.symlink(outside / "notes.md", tree / "NOTES.md")
    os.symlink(outside / "secret.py", tree / "pyproject.toml")
    os.symlink(tree / "ok.py", tree / "sub" / "same.py")      # inside: an ordinary layout
    os.symlink(tree / "gone.py", tree / "dangling.py")
    os.mkfifo(tree / "pipe.py")
    os.mkfifo(tree / "PIPE.md")
    return tree


def test_the_code_walk_reads_only_files_of_the_tree_and_says_what_it_passed(tmp_path):
    """Both happened on 2026-11-12. A link to a file outside the tree was read like any
    other, and its constants were in the rendered map; a named pipe called `pipe.py` was
    opened and the analysis waited on it for ever. A link to a file *inside* the tree is
    an ordinary layout and is still read. A linked manifest is not offered either."""
    from dunneflow.walk import WalkStats, discover

    tree = _hostile(tmp_path)
    stats = WalkStats()
    found = sorted(p.relative_to(tree).as_posix() for p in discover(tree, stats=stats))
    assert found == ["ok.py", "sub/same.py"]
    assert stats.manifests == []
    assert stats.not_files == {
        "links to a file outside the tree": 2,          # leak.py and the manifest
        "links to nothing": 1,
        "that are a pipe, a socket or a device": 1,
    }


def test_the_document_walk_obeys_the_same_rule(tmp_path):
    """Rule 61: a second way into the store, taught what the first was."""
    from dunneflow.walk import discover_docs

    tree = _hostile(tmp_path)
    passed: dict[str, int] = {}
    found = sorted(p.name for p in discover_docs(tree, not_files=passed))
    assert found == ["README.md"]
    assert passed == {"links to a file outside the tree": 1,
                      "that are a pipe, a socket or a device": 1}
