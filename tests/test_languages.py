"""`lang` as a discriminator: stamped in one place, verified, and said out loud.

Every claim this file makes was true of v1 by accident — one language, so a default of
`"python"` was never wrong, a missing rules file never happened, and *only Python is
extracted* was a fact rather than a guess. Each test here is the point where the accident
stops being one.
"""

from __future__ import annotations

import argparse
import ast
import inspect
import re
from pathlib import Path

import pytest

from dunneflow import canonical, ingest, walk
from dunneflow.detectors import RulesMissing, load_rules
from dunneflow.ingest.contract import (
    DiscoveryRules,
    PluginManifest,
    PluginRefused,
    stamp_lang,
)
from dunneflow.resolve import languages
from dunneflow.resolve.mirror import BANDS
from dunneflow.schema import DataStructure, FileFacts, Routine, StructureKind
from dunneflow.store import Store


def _routine(lang: str = "") -> Routine:
    return Routine(id="r1", name="f", qualname="m.f", module="m", file="m.py",
                   line_start=1, line_end=2, lang=lang)


def _structure(lang: str = "") -> DataStructure:
    return DataStructure(id="s1", name="S", kind=StructureKind.CLASS, module="m",
                         file="m.py", line=1, lang=lang)


def _facts(lang: str = "python", **kw: object) -> FileFacts:
    return FileFacts(path="m.py", lang=lang, module="m", content_hash="h", **kw)  # type: ignore[arg-type]


# ------------------------------------------------------------------ the field --- #

def test_a_record_that_nobody_stamped_claims_nothing():
    """It defaulted to `"python"`, which is a fact about a record nothing in it decided.

    A plugin that forgot to say would have had every routine it emitted claim to be
    Python — and `lang` is the one column nothing reads twice, so the map would have been
    wrong where no later pass could notice.
    """
    assert _routine().lang == ""
    assert _structure().lang == ""


def test_the_file_says_the_language_and_the_records_are_stamped_from_it():
    facts = _facts(routines=[_routine()], structures=[_structure()])
    stamp_lang(facts)
    assert [r.lang for r in facts.routines] == ["python"]
    assert [s.lang for s in facts.structures] == ["python"]


def test_a_file_with_no_language_is_refused_rather_than_stored():
    with pytest.raises(PluginRefused) as exc:
        stamp_lang(_facts(lang="", routines=[_routine()]))
    assert "no language" in str(exc.value)


def test_a_record_that_brings_its_own_language_is_refused():
    """Two answers to one question, and they are only ever noticed when they differ."""
    with pytest.raises(PluginRefused) as exc:
        stamp_lang(_facts(lang="python", routines=[_routine("typescript")]))
    said = str(exc.value)
    assert "python" in said and "typescript" in said


def test_the_python_reader_stamps_what_it_reads(tmp_path):
    """The in-process reader is stamped by the same function a codec will use."""
    (tmp_path / "m.py").write_text("class S:\n    pass\n\ndef f():\n    return 1\n",
                                   encoding="utf-8")
    plugin = ingest.PLUGINS["python"]
    out = list(plugin.extract([tmp_path / "m.py"], tmp_path))
    assert out and out[0].lang == "python"
    assert {r.lang for r in out[0].routines} == {"python"}
    # A plain `class S` is a class and not a data shape, so it is a `classes` row rather
    # than a structure -- which is why this asks the structures only when there are any.
    assert all(s.lang == "python" for s in out[0].structures)


def test_a_reader_answering_about_another_language_is_refused(tmp_path, monkeypatch):
    """A manifest is a label; the running reader is the identity (rule 30)."""
    (tmp_path / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    plugin = ingest.PLUGINS["python"]

    def wrong(work, root, progress=None, jobs=None):
        yield _facts(lang="typescript")

    monkeypatch.setattr(plugin, "extract", wrong)
    store = Store(tmp_path / "graph.db")
    try:
        with pytest.raises(PluginRefused) as exc:
            walk.analyze_tree(tmp_path, store)
    finally:
        store.close()
    said = str(exc.value)
    assert "python" in said and "typescript" in said


# ------------------------------------------------------------------ the rules --- #

def test_asking_for_rules_is_asking_a_question(monkeypatch):
    """No default argument: `lang` is the question, and a question with a default answer
    is a question nobody has to ask."""
    assert inspect.signature(load_rules).parameters["lang"].default is inspect.Parameter.empty


def test_a_language_nobody_reads_is_refused_rather_than_answered_emptily():
    with pytest.raises(RulesMissing) as exc:
        load_rules("klingon")
    said = str(exc.value)
    assert "klingon" in said and "python" in said


def test_a_language_that_declares_no_rules_gets_an_empty_set(monkeypatch):
    """*Declared none* and *file missing* are different facts (rule 30).

    The first is a decision somebody wrote in a manifest. The second is a build defect
    that used to look exactly like it, and on a new language it costs every boundary,
    every way in and every CLI mount — silently.
    """
    quiet = PluginManifest(
        lang="quiet", display="Quiet", version="1.0.0", protocol=ingest.PROTOCOL,
        schema_version=0, discovery=DiscoveryRules(lang="quiet",
                                                   suffixes=frozenset({".q"})),
        rules="",
    )
    monkeypatch.setitem(ingest.PLUGINS, "quiet", _StubPlugin(quiet))
    load_rules.cache_clear()
    try:
        rules = load_rules("quiet")
    finally:
        load_rules.cache_clear()
    assert rules.boundaries == [] and rules.entrypoints == []


def test_a_declared_rules_file_that_is_not_there_is_a_refusal(monkeypatch):
    loud = PluginManifest(
        lang="loud", display="Loud", version="1.0.0", protocol=ingest.PROTOCOL,
        schema_version=0, discovery=DiscoveryRules(lang="loud",
                                                   suffixes=frozenset({".l"})),
        rules="loud.yaml",
    )
    monkeypatch.setitem(ingest.PLUGINS, "loud", _StubPlugin(loud))
    load_rules.cache_clear()
    try:
        with pytest.raises(RulesMissing) as exc:
            load_rules("loud")
    finally:
        load_rules.cache_clear()
    assert "loud.yaml" in str(exc.value)


class _StubPlugin:
    """Enough of a plugin to be asked what it declares, and nothing else."""

    def __init__(self, manifest: PluginManifest) -> None:
        self.manifest = manifest
        self.lost = 0


# --------------------------------------------------------------- the sentence --- #

def test_the_claim_counts_what_was_read_and_not_what_this_build_can_read(tmp_path):
    (tmp_path / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    store = Store(tmp_path / "graph.db")
    try:
        walk.analyze_tree(tmp_path, store)
        assert languages.read(store) == ["python"]
    finally:
        store.close()


@pytest.mark.parametrize(
    ("langs", "expected"),
    [
        ([], ""),
        (["python"], "Python"),
        (["python", "typescript"], "Python and TypeScript"),
        (["go", "python", "typescript"], "go, Python and TypeScript"),
    ],
)
def test_a_language_is_spelled_by_its_own_plugin_or_by_its_key(langs, expected):
    """`python` is the key and `Python` is the word; a language with no plugin here keeps
    its key, because inventing a capitalisation is a guess about somebody else's name.

    *The middle case read `typescript` until the TypeScript plugin shipped*, which is
    exactly what the lower-case arm was demonstrating: a language nobody here reads
    keeps its key. `go` still does, so the contrast is now between two real answers
    rather than between one answer and a placeholder.
    """
    assert languages.named(langs) == expected


def test_no_source_at_all_is_its_own_answer():
    """Three answers, never two (design rule 21): nothing read is not one language read."""
    assert "No source was extracted" in languages.only([])
    assert "Only Python was extracted" in languages.only(["python"])
    assert "were extracted" in languages.only(["python", "typescript"])


def test_every_bands_blind_spot_survives_being_filled_in():
    """One band carries `{languages}`; the rest are prose full of punctuation."""
    filled = [b.spot(["python"]) for b in BANDS]
    assert not any("{languages}" in s for s in filled)
    assert sum("Python" in s for s in filled) == 1


def test_the_mirror_page_says_what_it_was_read_from():
    """Rule 13 on the page whose whole subject is absence."""
    from dunneflow.render.mirror import _bands, _what_it_could_not_see
    from dunneflow.resolve.mirror import Mirror

    m = Mirror(langs=["python"])
    page = "\n".join(_what_it_could_not_see(m) + _bands(m))
    assert "Only Python was extracted" in page
    assert "{languages}" not in page


def test_the_walk_says_what_it_read_per_language(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    stats = walk.WalkStats()
    list(walk.discover(tmp_path, stats=stats))
    assert stats.by_lang == {"python": 1}
    assert walk.walk_languages(stats) == "python 1"


def test_nothing_read_says_nothing_rather_than_an_empty_list(tmp_path):
    (tmp_path / "notes.txt").write_text("hello\n", encoding="utf-8")
    stats = walk.WalkStats()
    list(walk.discover(tmp_path, stats=stats))
    assert walk.walk_languages(stats) == ""


# --------------------------------------------- what a new language must not touch --- #

# The surfaces `CLAUDE.md`'s **Adding a language** promises know nothing about which
# language a fact came from. Named as directories rather than derived, because that is the
# claim: a reader arrives at the graph and stops, and everything above the graph reads
# `files.lang` as data or not at all.
ABOVE_THE_GRAPH = ("render", "web")


def _language_literals(path: Path) -> list[str]:
    """Every string constant in this file that spells a language this build reads.

    **Constants, never the text** (rule 34). A docstring in `walk.py` gives *python 628 ·
    typescript 412* as an example of what the walk prints, and a comment in
    `resolve/traceability.py` explains which language its builtins belong to — a scan of
    the bytes would report both as violations of a rule they are describing, which is how a
    guard comes to be deleted for crying wolf (rule 43).

    Derived from `ingest.PLUGINS` rather than from a list of names, so a third reader is
    covered by this test on the day it is registered and not on the day somebody remembers
    (rule 92).
    """
    names = {lang.lower() for lang in ingest.PLUGINS}
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [f"{path.name}:{n.lineno} {n.value!r}"
            for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and n.value.lower() in names]


def test_nothing_above_the_graph_names_a_language():
    """The property that makes *nothing else changes* true, asserted rather than claimed.

    `CLAUDE.md` said *"write one extractor that emits `FileFacts`; nothing else changes —
    the resolver, renderers, and orientation queries know nothing about any specific
    language"* for a year, over a tool that had only ever been asked about one. It survived
    being asked twice, and this is what holds it: 40-odd modules of dashboard and two
    renderers, and not one of them spells `python`.
    """
    src = Path(ingest.__file__).resolve().parent.parent
    found: list[str] = []
    for where in ABOVE_THE_GRAPH:
        for path in sorted((src / where).rglob("*.py")):
            found += _language_literals(path)
    # **`anomalies.py` joined the guard on 2026-09-18, and it earned its way in.** It is a
    # judgement over the graph like the renderers are, and it had never been covered --
    # which is how `ASYNC_NOT_AWAITED` came to tell every language that its un-awaited call
    # left *"a coroutine created and never run"*. It says nothing about any language now:
    # what a dropped async call costs is `unawaited_async`, declared in each reader's own
    # rules file and read off `files.lang`.
    found += _language_literals(src / "anomalies.py")
    assert not found, (
        "a language is named above the graph, so adding one is no longer a plugin edit:\n  "
        + "\n  ".join(found))


def test_the_walk_dispatches_without_naming_anybody():
    """`walk.py` groups by language and hands each group to its plugin.

    It used to open `from .extractors.python.extract import extract_file`, which is the
    whole of what *only Python is extracted* meant: not a policy, an import.
    """
    assert not _language_literals(Path(walk.__file__).resolve())


def test_only_the_dispatch_table_names_a_resolver():
    """`resolve/` is the one layer that legitimately names languages, and only there.

    `RESOLVERS` is a dispatch table and naming them is its job — the comment beside it says
    why it is not derived from a manifest: what runs in this process is decided by a file
    that is under test, never by a data file. Every *other* module under `resolve/` outside
    a language's own package is asserted clean, so a second `load_rules("python")` cannot
    arrive quietly.

    **It was one and it is now none, and this test is how that was noticed.**
    `traceability.py` asked `load_rules("python").builtins` of every corpus — the shape
    open question 6 found in the naming lanes, one module over. It was pinned here at
    exactly one so it could not grow while it went unmeasured, and when it was measured and
    scoped to `languages.read(store)` the literal went with it, and this assertion failed
    saying so. A residue held at a number is a residue somebody finds out about.

    So the number is zero, and zero is now the whole rule rather than an allowance with one
    name in it: no module under `resolve/` outside a reader's own package and the dispatch
    table may spell a language at all.
    """
    src = Path(ingest.__file__).resolve().parent.parent
    langs = set(ingest.PLUGINS)
    found: list[str] = []
    for path in sorted((src / "resolve").rglob("*.py")):
        rel = path.relative_to(src / "resolve")
        if rel.parts[0] in langs or rel.name == "calls.py":
            continue                       # a reader's own package, and the dispatch table
        found += _language_literals(path)
    assert not found, (
        "a module under resolve/ has started naming a language:\n  "
        + "\n  ".join(found))


def test_the_canonical_seam_asks_ingest_which_language_owns_a_file():
    """One question, one table — and for a year there were two.

    `canonical/__init__.py` declared `LANG_SUFFIX = {".py": "python", ".pyi": "python"}`
    under a comment claiming *"here is the one place that consults it"*, while
    `ingest/__init__.py`'s docstring said the table had **moved there** and become derived
    from the manifests, quoting that same sentence as the thing that had stopped being
    true. The move was recorded and the copy was left behind, so the module that said it
    owned the question was not the one being asked it.

    **Both directions of drift were live when this was written**, which is what a second
    answer always does. It did not know `.ts`: a TypeScript canonicaliser could have been
    registered in `CANONICAL` and never once reached, because the lookup that decides
    whether to call one could not name the language — and the comparison would have fallen
    through to *as written*, indistinguishable from this module's honest fallback (rule
    49). And it claimed `.pyi`, which no reader claims at all.

    So the assertion is the one that cannot drift: `canonical` spells no suffix, and the
    answer it gives is the registry's.
    """
    mod = Path(canonical.__file__).resolve()
    body = mod.read_text()
    # `CANONICAL` names languages and that is its job, exactly as `RESOLVERS` does above —
    # what runs in this process is decided by a file under test, never by a data file. What
    # may not be here is a second answer to *which language owns this suffix*.
    assert not re.search(r"^LANG_SUFFIX\s*[:=]", body, re.M), (
        "canonical/__init__.py has declared a suffix table of its own again")
    assert "language_of" in body, (
        "canonical() must ask the registry which language owns a file")

    # The property, not a proxy for it (rule 37): every suffix the registry claims reaches
    # its language's entry, and one it does not claim reaches nobody's.
    for suffix, lang in ingest.LANG_SUFFIX.items():
        expr = "f( 1 ,2 )"
        got = canonical.canonical(expr, f"a{suffix}")
        if lang in canonical.CANONICAL:
            assert got != expr, f"{suffix} is claimed by {lang} and was not canonicalised"
        else:
            assert got == expr, f"{suffix} has no canonical form and must compare as written"
    assert canonical.canonical("f( 1 ,2 )", "a.nobody") == "f( 1 ,2 )"


# --------------------------------------------------------- declining a language --- #
#
# `--without <lang>` was named as the way out of a missing toolchain by two sentences in
# `ingest/outofprocess.py` long before it existed anywhere: `declined` was a parameter on
# three functions and **no caller ever passed it** (rule 35's shape, in an argument). So a
# reader on a machine with no node was handed a refusal naming a flag `--help` does not
# list, which is rule 89 broken by the sentence written to keep it. Found by chunk 14
# writing the chapter about refusals.

def _mixed(tmp_path: Path) -> Path:
    """A tree with two languages, some tests and a declaration file in it."""
    (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "test_a.py").write_text("def test_f(): pass\n", encoding="utf-8")
    (tmp_path / "c.ts").write_text("export const x = 1\n", encoding="utf-8")
    (tmp_path / "d.ts").write_text("export const y = 2\n", encoding="utf-8")
    (tmp_path / "c.test.ts").write_text("test('x', () => {})\n", encoding="utf-8")
    (tmp_path / "e.d.ts").write_text("export declare const z: number\n", encoding="utf-8")
    return tmp_path


def test_declining_a_language_nobody_reads_is_refused_naming_the_ones_that_are():
    """Rule 49. `--without pythn` that quietly declines nothing is the whole map."""
    with pytest.raises(PluginRefused) as exc:
        ingest.decline(["pythn"])
    assert "pythn" in str(exc.value)
    for lang in ingest.PLUGINS:
        assert lang in str(exc.value), "the refusal must say what it could have declined"


def test_declining_every_language_is_refused_rather_than_obeyed():
    """A map with no code in it is not a smaller map, and `--no-docs` is what was meant."""
    with pytest.raises(PluginRefused) as exc:
        ingest.decline(sorted(ingest.PLUGINS))
    assert "--no-docs" in str(exc.value)


def test_a_declined_name_is_a_key_and_is_matched_without_case():
    assert ingest.decline(["TypeScript", " typescript "]) == frozenset({"typescript"})
    assert ingest.decline([]) == frozenset()
    assert ingest.decline([""]) == frozenset()


def test_a_declined_language_is_its_own_answer_and_never_an_unread_suffix(tmp_path):
    """The placement is the feature (design rule 21).

    Taken off `rules` instead, a declined language's suffixes would leave `suffix_owners`
    and its files would be tallied as `unclaimed` — *no reader here claims `.ts`*, said by
    a build that has one. Two facts that look identical in a map and have opposite
    remedies: one is answered by installing a plugin and the other by dropping a flag.
    """
    tree = _mixed(tmp_path)
    stats = walk.WalkStats()
    list(walk.discover(tree, stats=stats, declined=frozenset({"typescript"})))
    assert stats.declined == {"typescript": 2}
    assert ".ts" not in stats.unclaimed
    assert "typescript" not in stats.by_lang


def test_declining_counts_exactly_what_would_otherwise_have_been_read(tmp_path):
    """The arithmetic closes, which is what makes the number answer *what did I lose*.

    Asked after the skip rules and the test rule, so a declined language's tests and its
    `.d.ts` are still reported as tests and as skipped — true, disjoint, and the same
    sentences an undeclined run prints.
    """
    tree = _mixed(tmp_path)
    full, without = walk.WalkStats(), walk.WalkStats()
    list(walk.discover(tree, stats=full))
    list(walk.discover(tree, stats=without, declined=frozenset({"typescript"})))

    assert without.declined["typescript"] == full.by_lang["typescript"]
    assert without.by_lang == {"python": full.by_lang["python"]}
    # The other two lanes are untouched: they are facts about the files, not about the run.
    assert without.tests_excluded == full.tests_excluded
    assert without.lang_skipped == full.lang_skipped


def test_the_walk_says_a_language_was_declined_and_by_whom(tmp_path):
    """Design rule 1: no filter is ever silent, and this one is the reader's own doing."""
    tree = _mixed(tmp_path)
    stats = walk.WalkStats()
    list(walk.discover(tree, stats=stats, declined=frozenset({"typescript"})))
    said = walk.walk_residue(stats)
    line = next(s for s in said if s.startswith("declined by you:"))
    assert "typescript" in line and "--without" in line
    assert "no reader here claims" not in line


def test_a_declined_language_is_recorded_in_the_map_itself():
    """`_args_said` records only what **removes** something, and this is the purest case.

    A map analysed `--without typescript` and a map of a tree with no TypeScript in it
    hold exactly the same rows, and only one of them is a program written in one language.
    """
    from dunneflow.cli import _args_said

    args = argparse.Namespace(
        without=["typescript"], include_tests=False, no_docs=False, docs=None,
        no_source=False, no_doc_source=False, no_render=False)
    assert "typescript not read" in _args_said(args)

    args.without = []
    assert "not read" not in _args_said(args)
