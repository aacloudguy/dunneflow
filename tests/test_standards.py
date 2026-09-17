"""A standards directory: somebody else's rules, admitted without being absorbed.

Two things matter here, and the second is the reason the first is written this way.

**A standard must not become the program's own prose.** `docs.db` is read by the glossary,
the mirror, traceability and Document mode's corpus lane. If an outside organisation's
naming standard landed there, every one of those would silently include documents the
program does not carry -- and each would need a filter it must remember. The rules land in
`standards.db` instead, so the isolation is structural rather than remembered.

**Rule 57, one directory further out.** That rule was paid for by two stale worktrees
putting 335 of Mensores' 2,381 documents into the map. Letting a reader *name* a root opens
three more ways for a program to be read as its own standard, and the refusals are asserted
here **by their sentence**, not merely by their exit code: a refusal nobody can read is a
refusal they will work around.
"""

from __future__ import annotations

from pathlib import Path

from dunneflow.docstore import DocStore
from dunneflow.standards import standards_refusal
from dunneflow.walk import analyze_docs_tree

# A corporate standard: scoped at every Python file, which is what makes it a question
# about the *graph* -- unlike the harness rules a project carries about its own markdown.
CORP = """---
paths: ['**/*.py']
owner: platform
---

# DunneCorp naming standard

## Naming Conventions

| Type | Convention | Example |
|---|---|---|
| Modules | snake_case | `call_args.py` |
| Classes | PascalCase | `DocStore` |
| Constants | SCREAMING_SNAKE_CASE | `MIN_POPULATION` |
"""


def _scan(root: Path, files: dict[str, str]) -> DocStore:
    """Write a tiny corpus and read it, exactly as `test_stated.py` does."""
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    store = DocStore(root / "standards.db")
    analyze_docs_tree(root, store, jobs=1)
    return store


def _roots(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """A tree, a documentation root, an output root and an unrelated standards root."""
    docs_root = tmp_path / "project"
    tree = docs_root / "src"
    out_root = tmp_path / "output"
    outside = tmp_path / "corp"
    for p in (tree, out_root, outside):
        p.mkdir(parents=True, exist_ok=True)
    return tree, docs_root, out_root, outside


def test_a_standard_outside_every_root_is_admitted(tmp_path: Path) -> None:
    """The ordinary case, and it has to be stated or the refusals prove nothing."""
    tree, docs_root, out_root, outside = _roots(tmp_path)
    assert standards_refusal(outside, tree=tree, out_root=out_root,
                             docs_root=docs_root) is None, \
        "a directory belonging to none of the three roots is what this feature is for"


def test_the_tools_own_output_is_refused_and_says_it_would_mint_rules(
        tmp_path: Path) -> None:
    """The refusal a reader cannot see coming.

    `output/` holds a map *about* a program. Reading a generated report back as somebody's
    naming standard would mint rules out of this tool's own prose -- the failure `walk.py`
    already names for the document corpus, arriving through a flag instead of a walk.
    """
    tree, docs_root, out_root, _ = _roots(tmp_path)
    why = standards_refusal(out_root / "mensores", tree=tree, out_root=out_root,
                            docs_root=docs_root)
    assert why and "output root" in why and "mint rules" in why, \
        f"the sentence must say what reading a map back would do, got {why!r}"


def test_the_programs_own_documentation_is_refused_as_a_standard(tmp_path: Path) -> None:
    """A program's own words are not a baseline to measure it against.

    Admitting it twice would count one rule as two, and present the program's own prose
    back to it as an outside standard -- the one comparison this feature exists not to make.
    """
    tree, docs_root, out_root, _ = _roots(tmp_path)
    why = standards_refusal(docs_root / "harness", tree=tree, out_root=out_root,
                            docs_root=docs_root)
    assert why and "documentation root" in why, \
        f"the sentence must name the documentation root, got {why!r}"


def test_the_analysed_tree_is_refused_even_when_no_documentation_is_read(
        tmp_path: Path) -> None:
    """`--no-docs` is why the tree is tested separately rather than assumed.

    With no documentation root there is no broader containment to catch this, so the source
    tree is the live test rather than a subset of one already made.
    """
    tree, _, out_root, _ = _roots(tmp_path)
    why = standards_refusal(tree / "pkg", tree=tree, out_root=out_root, docs_root=None)
    assert why and "analysed tree" in why, \
        f"under --no-docs the tree must still refuse its own subdirectories, got {why!r}"


def test_a_missing_root_is_refused_rather_than_quietly_scanning_nothing(
        tmp_path: Path) -> None:
    """A typo must not read as a standard that states nothing.

    An empty store and a directory that was never there look identical downstream, and only
    one of them is a program with no standard to meet (design rule 21).
    """
    tree, docs_root, out_root, _ = _roots(tmp_path)
    why = standards_refusal(tmp_path / "nowhere", tree=tree, out_root=out_root,
                            docs_root=docs_root)
    assert why and "does not exist" in why, f"a missing root must say so, got {why!r}"


def test_a_file_is_refused_because_a_standards_root_is_a_directory(
        tmp_path: Path) -> None:
    """Pointing at the standard itself is the obvious mistake, so it gets its own answer."""
    tree, docs_root, out_root, outside = _roots(tmp_path)
    one = outside / "naming.md"
    one.write_text(CORP, encoding="utf-8")
    why = standards_refusal(one, tree=tree, out_root=out_root, docs_root=docs_root)
    assert why and "is a directory" in why, \
        f"the sentence must say what was expected instead, got {why!r}"


def test_a_scanned_standard_yields_checkable_rules_scoped_at_code(
        tmp_path: Path) -> None:
    """The point of importing one: rules whose population is the graph.

    Every checkable rule the real corpus states is about *documents* -- markdown files,
    plan files, phase directories. An imported corporate standard is the case that makes
    the comparison a question about code at all.
    """
    with _scan(tmp_path / "corp", {"naming.md": CORP}) as store:
        rows = list(store.query(
            "SELECT scope, pattern, checkable FROM doc_rules WHERE lane = 'FORM'"))
    scopes = {str(r["scope"]) for r in rows}
    assert scopes >= {"modules", "classes", "constants"}, \
        f"a three-row convention table yields three scopes, got {scopes}"
    assert all(int(r["checkable"]) == 1 for r in rows), \
        "a row naming both an identifier class and a spelling is checkable"


def test_a_standards_scan_writes_its_own_store_and_not_the_corpus(
        tmp_path: Path) -> None:
    """The isolation, asserted as a file rather than as a filter.

    This is the whole reason `standards.db` is a separate file: the corpus store is never
    opened by the standards scan, so no consumer of `docs.db` can absorb an outside
    organisation's documents by forgetting a `WHERE`.
    """
    corpus_root = tmp_path / "project"
    corpus_root.mkdir()
    (corpus_root / "README.md").write_text("# The program\n\nIts own prose.\n",
                                           encoding="utf-8")
    corpus = DocStore(corpus_root / "docs.db")
    analyze_docs_tree(corpus_root, corpus, jobs=1)
    before = int(corpus.counts()["doc_rules"])

    with _scan(tmp_path / "corp", {"naming.md": CORP}) as standards:
        assert int(standards.counts()["doc_rules"]) > 0, \
            "the standard states rules, or this test proves nothing about isolation"
    after = int(corpus.counts()["doc_rules"])
    corpus.close()

    assert before == after == 0, \
        "scanning a standard must leave the program's own corpus exactly as it was"
