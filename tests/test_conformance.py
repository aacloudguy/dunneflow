"""Reality against intent, and the ways it goes confidently wrong.

The feature is one question -- *does the program do what the rule says* -- and almost every
way of answering it is worse than not answering. What is guarded here is the answering:

**The population is never inferred from the scope word.** Measured on Mensores before this
existed: all six of its `checkable` rules come from a harness standard and not one is a
question about the code graph. *"Files: kebab-case"*, checked against the graph, is
**0 of 628** Python files -- a catastrophic claim about a rule its own document scopes to
`src/**/*.md`, three documents. That is the defect these tests exist for.

**Three verdicts must stay three.** A rule that holds, a rule with nothing here to measure,
and a rule whose spelling this tool cannot test are three facts. Collapse any two and *"we
could not check"* renders as *"it passes"*.
"""

from __future__ import annotations

from pathlib import Path

from dunneflow.docstore import DocStore
from dunneflow.resolve.conformance import (
    CHECKED,
    NO_POPULATION,
    NOT_CHECKABLE,
    check_stated,
    glob_to_regex,
    scope_globs,
)
from dunneflow.store import Store
from dunneflow.walk import analyze_docs_tree, analyze_tree

# A standard scoped at markdown under `src/`, which is the real shape: the corpus's one true
# naming table governs documents, not code.
DOC_SCOPED = """---
paths: ['src/**/*.md']
---

# House style

## Naming Conventions

| Type | Convention | Example |
|---|---|---|
| Files | kebab-case | `plan-phase.md` |
| Step names | snake_case | `load_state` |
"""

# The same rule with nothing saying which files it governs. Two rows, because
# `MIN_RULE_TABLE_ROWS` is 2 -- one row out of one is a 100% majority and means nothing.
UNSCOPED = """# House style

## Naming Conventions

| Type | Convention | Example |
|---|---|---|
| Files | kebab-case | `plan-phase.md` |
| Step names | snake_case | `load_state` |
"""

# A corporate standard aimed at code, which is what an imported one usually is.
CODE_SCOPED = """---
paths: ['**/*.py']
---

# Corp standard

## Naming Conventions

| Type | Convention | Example |
|---|---|---|
| Modules | snake_case | `call_args.py` |
| Classes | PascalCase | `DocStore` |
| Bash variables | CAPS_UNDERSCORES | `MY_VAR` |
"""

PROGRAM = '''"""A tiny program with well-named parts."""


class DocStore:
    """A store."""

    def read(self) -> int:
        return 1
'''


def _docs(root: Path, files: dict[str, str]) -> DocStore:
    for name, text in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    store = DocStore(root / "docs.db")
    analyze_docs_tree(root, store, jobs=1)
    return store


def _code(root: Path) -> Store:
    src = root / "src" / "prog"
    src.mkdir(parents=True, exist_ok=True)
    (src / "doc_store.py").write_text(PROGRAM, encoding="utf-8")
    store = Store(root / "graph.db")
    analyze_tree(root, store)
    return store


def _by_scope(checks: list, scope: str):
    return [c for c in checks if c.rule.scope == scope]


# -- the population, which is the whole feature ------------------------------ #


def test_a_file_rule_with_no_declared_scope_is_refused_rather_than_widened(
        tmp_path: Path) -> None:
    """The defect that reordered the whole feature.

    *"Files"* does not say **which** files, and no reading of the word supplies it. Widening
    to everything the map holds is the plausible substitute rule 49 was written about: it
    produces a number, the number looks like a measurement, and it is a claim about a
    population the rule never named.
    """
    with _docs(tmp_path / "d", {"style.md": UNSCOPED}) as docs:
        checks = check_stated(None, docs, None)
    files = _by_scope(checks, "files")
    assert files, "the table states a rule about files, or this test is blind"
    assert files[0].verdict == NO_POPULATION, \
        "a file rule with no declared scope must not be measured against everything"
    assert "declares no" in files[0].reason and "will not guess" in files[0].reason, \
        f"the refusal must say which half is missing, got {files[0].reason!r}"


def test_a_document_scoped_rule_is_never_measured_against_the_code_graph(
        tmp_path: Path) -> None:
    """The catastrophic case, asserted as a negative.

    `src/**/*.md` selects documents. A check that reached for the graph's Python files
    instead would report a confident 0% against a rule that governs three markdown files --
    which is exactly what Mensores would have shown.
    """
    root = tmp_path / "p"
    store = _code(root)
    with _docs(root / "d", {"style.md": DOC_SCOPED}) as docs:
        checks = check_stated(store, docs, None)
    store.close()
    files = _by_scope(checks, "files")[0]
    assert files.verdict in (CHECKED, NO_POPULATION)
    assert "src/**/*.md" in files.scoped_by, "the declared scope must travel with the answer"
    assert not any(e.name == "doc_store" for e in files.exceptions), \
        "a rule scoped at markdown must never judge a Python module"


def test_a_scoped_file_rule_counts_the_files_its_own_document_names(
        tmp_path: Path) -> None:
    """The population is the declared one, and the stem is what carries the spelling.

    The standard's own example is `plan-phase.md` -- the extension is not part of what is
    being spelled, so a file is judged on its stem.
    """
    root = tmp_path / "p"
    docs = _docs(root, {
        "style.md": DOC_SCOPED,
        "src/good-name.md": "# fine\n",
        "src/deep/also-good.md": "# fine\n",
        "src/BadName.md": "# not kebab\n",
        "notes/ignored-entirely.md": "# outside the scope\n",
    })
    with docs:
        checks = check_stated(None, docs, None)
    got = _by_scope(checks, "files")[0]
    assert got.verdict == CHECKED, f"expected a measurement, got {got.reason!r}"
    assert got.total == 3, \
        f"only the three files under src/ are governed, counted {got.total}"
    assert [e.name for e in got.exceptions] == ["BadName"], \
        f"one file breaks kebab-case, got {[e.name for e in got.exceptions]}"


def test_a_star_does_not_cross_a_directory_and_a_double_star_does() -> None:
    """`fnmatch` would make `src/*.md` select the whole tree.

    Its `*` matches `/`, so every markdown file at any depth would join a population scoped
    to one directory -- a silent widening of exactly the kind this module refuses to make
    deliberately.
    """
    assert glob_to_regex("src/*.md").match("src/a.md")
    assert not glob_to_regex("src/*.md").match("src/deep/a.md"), \
        "a single star must not cross a directory boundary"
    assert glob_to_regex("src/**/*.md").match("src/deep/a.md")
    assert glob_to_regex("src/**/*.md").match("src/a.md"), \
        "`**/` matches zero directories as well as many"
    assert not glob_to_regex("**/*.py").match("notes/a.md")


def test_a_yaml_list_arrives_as_a_string_and_is_read_anyway() -> None:
    """`frontmatter` is `dict[str, str]` all the way from the extractor.

    A list is stored as its literal text, so anything reading `paths` must parse it. Teaching
    the extractor to keep types instead would change output that is hashed into the document
    cache key and discard every document store on the machine.
    """
    assert scope_globs({"paths": "['src/**/*.md']"}) == ["src/**/*.md"]
    assert scope_globs({"paths": "['a', 'b']"}) == ["a", "b"]
    assert scope_globs({"applies_to": "docs/**"}) == ["docs/**"]
    assert scope_globs({"owner": "platform"}) == [], \
        "a key that is not a scope must contribute no glob"


# -- the three verdicts ------------------------------------------------------ #


def test_a_scope_this_tool_records_nothing_for_says_so_in_its_own_words(
        tmp_path: Path) -> None:
    """*"No population"* and *"not checkable"* are different answers.

    DunneFlow deliberately does not record variables -- that absence is a design decision,
    not a gap, and a reader is owed the difference between *"we hold none of those"* and
    *"we cannot test that spelling"*.
    """
    root = tmp_path / "p"
    store = _code(root)
    with _docs(root / "d", {"corp.md": CODE_SCOPED}) as docs:
        checks = check_stated(store, docs, None)
    store.close()
    got = _by_scope(checks, "variables")[0]
    assert got.verdict == NO_POPULATION, "a variables rule has nothing here to measure"
    assert "does not record variables" in got.reason, \
        f"the reason must name the design decision, got {got.reason!r}"


def test_a_pattern_that_is_not_a_case_style_is_quoted_back_not_guessed_at(
        tmp_path: Path) -> None:
    """A template is refused deliberately.

    Inventing a syntax for `NN-kebab-name` would mean guessing what a placeholder meant, and
    a guess renders identically to a measurement.
    """
    doc = """# Rules

## Naming Conventions

| Type | Convention | Example |
|---|---|---|
| Phase directories | `NN-kebab-name` | `02-rules-layer` |
| Files | kebab-case | `a-b.md` |
"""
    with _docs(tmp_path / "d", {"r.md": doc}) as docs:
        checks = check_stated(None, docs, None)
    got = _by_scope(checks, "directories")[0]
    assert got.verdict == NOT_CHECKABLE, "a template is not a spelling this tool tests"
    assert "NN-kebab-name" in got.reason, \
        "the refusal must quote the pattern it could not test"


def test_a_dotted_module_name_is_not_an_exception_to_its_own_convention(
        tmp_path: Path) -> None:
    """Rule 51's cost, reproduced once and then guarded.

    `naming.py` learned that a dotted path is not one identifier -- reading
    `mensores.cli.main` as a word made every module an exception. Reusing `POPULATIONS`
    without reusing `DOTTED` reproduced it exactly: `modules / snake_case` reported **1 of
    628** on Mensores before this was fixed.
    """
    root = tmp_path / "p"
    store = _code(root)
    with _docs(root / "d", {"corp.md": CODE_SCOPED}) as docs:
        checks = check_stated(store, docs, None)
    store.close()
    got = _by_scope(checks, "modules")[0]
    assert got.verdict == CHECKED, f"expected a measurement, got {got.reason!r}"
    assert got.total > 0 and got.holds == got.total, (
        f"a dotted module path is not a snake_case violation, but "
        f"{[e.name for e in got.exceptions]} were reported"
    )


def test_an_imported_rule_and_the_programs_own_rule_are_told_apart(
        tmp_path: Path) -> None:
    """A reader who cannot tell them apart cannot weigh either.

    An outside standard imposes; a project's own document describes. Same shape on the wire,
    different claims, so `source` travels with every check.
    """
    root = tmp_path / "p"
    store = _code(root)
    docs = _docs(root / "own", {"style.md": DOC_SCOPED})
    standards = _docs(root / "corp", {"corp.md": CODE_SCOPED})
    with docs, standards:
        checks = check_stated(store, docs, standards)
    store.close()
    sources = {c.source for c in checks}
    assert len(sources) == 2, f"both origins must be represented, got {sources}"
    own = {c.source for c in _by_scope(checks, "files")}
    imported = {c.source for c in _by_scope(checks, "classes")}
    assert own != imported, "a rule's origin must not be lost on the way to the page"


def test_an_imported_rule_measures_the_program_not_the_standards_directory(
        tmp_path: Path) -> None:
    """The population is always *this* program.

    A standards directory is full of markdown, and a `files` rule inside it must not end up
    counting the standard's own documents -- which is a map of the wrong thing entirely.
    """
    root = tmp_path / "p"
    docs = _docs(root / "own", {"src/a-good-name.md": "# fine\n"})
    standards = _docs(root / "corp", {"corp.md": DOC_SCOPED, "src/BadCorpDoc.md": "# x\n"})
    with docs, standards:
        checks = check_stated(None, docs, standards)
    got = _by_scope(checks, "files")[0]
    assert got.verdict == CHECKED, f"expected a measurement, got {got.reason!r}"
    assert not any(e.name == "BadCorpDoc" for e in got.exceptions), \
        "an imported rule must judge the program, never the standard it came from"
