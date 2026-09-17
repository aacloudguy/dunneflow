"""`lang` as a discriminator: stamped in one place, verified, and said out loud.

Every claim this file makes was true of v1 by accident — one language, so a default of
`"python"` was never wrong, a missing rules file never happened, and *only Python is
extracted* was a fact rather than a guess. Each test here is the point where the accident
stops being one.
"""

from __future__ import annotations

import inspect

import pytest

from dunneflow import ingest, walk
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
        (["python", "typescript"], "Python and typescript"),
        (["go", "python", "typescript"], "go, Python and typescript"),
    ],
)
def test_a_language_is_spelled_by_its_own_plugin_or_by_its_key(langs, expected):
    """`python` is the key and `Python` is the word; a language with no plugin here keeps
    its key, because inventing a capitalisation is a guess about somebody else's name."""
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
