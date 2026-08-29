"""Documentation is the other half of the input, and it lies differently from code.

Every test here exists because of something real. The counter-examples are all drawn
from the Society of Mensores corpus: a research paper that reads exactly like a naming
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
2. **Always the binomial** — `acme quaestor`, never bare `quaestor`.

## Identifiers

All private functions must start with a leading underscore.
Every module name uses snake_case.

## Trademark status

**Action before any filing:** a registered attorney must run full clearance.

## The pantheon

| Component | Latin name | Role / meaning |
|---|---|---|
| Harness (the fork: `/acme-*`) | **groma** | the instrument, invoked as `acme-<role>` |
| Audit tools | **quaestor** | the magistrate who audits the records |
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

## Mensor

<dl>
<dt>mensor <em>(noun)</em></dt>
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
    assert "groma" in terms and "quaestor" in terms


def test_a_placeholder_in_prose_is_not_an_html_tag(tmp_path: Path) -> None:
    """`acme-<role>` lost its placeholder to a tag stripper. Never truncate at ingest."""
    facts = _extract(tmp_path, "NAMING.md", NAMING_STANDARD)
    groma = [d for d in facts.definitions if d.term == "groma"]
    assert groma and "<role>" in groma[0].definition


def test_html_definition_lists_are_read(tmp_path: Path) -> None:
    facts = _extract(tmp_path, "glossary.md", GLOSSARY)
    assert facts.doc_class is DocClass.GLOSSARY
    mensor = [d for d in facts.definitions if d.term.startswith("mensor")]
    assert mensor and "provenance and audit trail" in mensor[0].definition


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
# agent worktrees under `.claude/worktrees/` put 335 May-era copies of Mensores' own
# governance documents into the corpus -- 14% of it. The duplicate detector caught 303
# and every consumer filters `duplicate_of`, so most numbers were protected. The 32
# that had drifted from their originals were no longer identical and escaped it,
# putting ten definitions into the glossary -- `mensor`, `mensores` and `Society of
# Mensores` among them -- sourced from a directory that is not the project.
#
# Each test below is written against a specific way this can half-work, because a
# guard that has only ever passed is a claim nobody has tested (rule 37).
# --------------------------------------------------------------------------- #


def _corpus(root: Path) -> Path:
    """A tree shaped like the real one: a checkout, with documents, holding a worktree."""
    (root / ".git").mkdir()                      # the corpus is itself a checkout
    (root / "README.md").write_text("# The program\n")
    (root / ".claude").mkdir()
    (root / ".claude" / "CLAUDE.md").write_text("# The charter\n")
    nest = root / ".claude" / "worktrees" / "agent-1"
    nest.mkdir(parents=True)
    (nest / ".git").write_text("gitdir: /elsewhere\n")   # a worktree: a .git *file*
    (nest / "README.md").write_text("# A stale copy\n")
    (nest / "deep").mkdir()
    (nest / "deep" / "PLAN.md").write_text("# Also stale\n")
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
    (root / "README.md").write_text("# The program\n")
    nest = root / "docs" / "vendored"
    nest.mkdir(parents=True)
    (nest / ".git").mkdir()
    (nest / "GUIDE.md").write_text("# Someone else's\n")

    found = {p.relative_to(root).as_posix() for p in discover_docs(root)}
    assert found == {"README.md"}, sorted(found)


@pytest.mark.parametrize("marker", [".git", ".hg", ".svn"])
def test_every_marker_is_a_checkout(tmp_path: Path, marker: str) -> None:
    """Version control must stay pluggable: the same claim in three dialects."""
    from dunneflow.walk import discover_docs

    root = tmp_path
    (root / "README.md").write_text("# The program\n")
    nest = root / "sub"
    nest.mkdir()
    (nest / marker).mkdir()
    (nest / "OTHER.md").write_text("# Not ours\n")

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
    (root / "README.md").write_text("# The program\n")
    (root / "docs").mkdir()
    (root / "docs" / "guide.md").write_text("# A guide\n")

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
    assert nested[0].endswith("worktrees/agent-1"), nested


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
