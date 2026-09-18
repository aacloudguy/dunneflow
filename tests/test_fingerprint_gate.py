"""The gate that says a frozen binary and this checkout can read each other's maps.

`tools/fingerprints.py`, and the three release scripts that run it. Two things are proved
here and they are different: that the comparison **refuses** what it is for, and that the
release scripts cannot go back to asking the question themselves.

**The second is the one worth having.** `release-linux.sh` and `release.ps1` each asked by
writing `from dunneflow.detectors import rules_fingerprint` inline. Chunk 5 split that
function into a core stamp and one per language; both steps raised `ImportError` from then
until chunk 13, in the step written to defend rule 12, and nothing in 1,813 tests noticed
because no test has ever read a release script. A Python question kept at a shell call site
rots as the Python moves (rule 51) -- so what is asserted is not that today's spelling is
right but that **no script spells it at all**.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from dunneflow.ingest import PLUGINS

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    ROOT / "packaging" / "release.sh",
    ROOT / "packaging" / "release.ps1",
    ROOT / "packaging" / "release-linux.sh",
)


def _tool():
    """`tools/fingerprints.py`, loaded by path.

    `tools/` is not a package and is deliberately not on `sys.path`: these are scripts a
    person runs, not modules the application imports, and putting them on the path would
    make `golden.py` importable as `golden` from anywhere in the suite.
    """
    path = ROOT / "tools" / "fingerprints.py"
    spec = importlib.util.spec_from_file_location("_fingerprints", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Registered before it is run, because `@dataclass` resolves its annotations through
    # `sys.modules[cls.__module__]` and raises on a module that is not there yet.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


fp = _tool()


# -- the probe tree ---------------------------------------------------------------------

def test_the_default_probe_tree_holds_every_language_this_build_reads():
    """The property that makes the gate mean anything, and the one that was missing.

    `release-linux.sh` read `src/dunneflow/web` and `release.ps1` read
    `src/dunneflow/canonical`. Both are Python to the last file, so the TypeScript stamp
    was never compared by either -- and both steps passed, which is rule 37: a guard that
    checks a name appears has not checked that anything happened.

    Asserted per registered language rather than by naming TypeScript, so a third reader
    joining this build fails here until the probe tree can exercise it (rule 92).
    """
    tree = fp.ROOT / fp.PROBE
    for lang in sorted(PLUGINS):
        assert fp.candidates(tree, lang) > 0, (
            f"{fp.PROBE} holds no file the {lang} reader claims, so running the gate "
            f"against it would compare {lang}'s stamp against nothing and pass")


def test_a_test_is_not_a_file_a_stamp_can_be_measured_from(tmp_path):
    """`candidates` asks the plugin's own rules, so *none* means what the walk means.

    Counted per language, because the three spellings of *this is a test* are the
    plugin's: `test_a.py` is Python's prefix rule and `a.test.ts` is TypeScript's
    whole-name one, and a shared rule would get both wrong in opposite directions
    (`DiscoveryRules`, and the 322 DunneNote files it was written from).
    """
    (tmp_path / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "a.test.ts").write_text("test('a', () => {})\n", encoding="utf-8")
    (tmp_path / "b.ts").write_text("export const x = 1\n", encoding="utf-8")
    assert fp.candidates(tmp_path, "python") == 1
    assert fp.candidates(tmp_path, "typescript") == 1


# -- what the gate refuses --------------------------------------------------------------

def _stamps(core="14:aaaa", langs=None, rows=None):
    return fp.Stamps(core=core, langs=dict(langs or {}), rows=dict(rows or {}))


def test_the_core_stamp_moving_is_every_language_refused(tmp_path):
    mine = fp.mine()
    theirs = _stamps("14:different", mine.langs, {lang: 1 for lang in mine.langs})
    bad = fp.compare(theirs, mine, tmp_path)
    assert len(bad) == 1
    assert bad[0].startswith("core:")
    assert "14:different" in bad[0] and mine.core in bad[0]


def test_one_language_moving_names_that_language_and_no_other():
    """The whole point of chunk 5's split, stated as a refusal.

    Core agreeing and one reader disagreeing is the case that costs **that language's**
    rows and nothing else. A message that said only *this map is stale* would send
    somebody looking at the wrong half (rule 89).
    """
    mine = fp.mine()
    moved = dict(mine.langs)
    moved["typescript"] = "1.1.0:0000000000000000"
    theirs = _stamps(mine.core, moved, {lang: 1 for lang in mine.langs})
    bad = fp.compare(theirs, mine, Path("."))
    assert len(bad) == 1
    assert bad[0].startswith("typescript:")
    assert "python" not in bad[0]


def test_a_language_that_contributed_no_rows_is_a_refusal_and_not_a_pass():
    """Rule 37. A stamp that was never compared is not a stamp that agrees."""
    mine = fp.mine()
    read = {lang: mine.langs[lang] for lang in mine.langs if lang != "typescript"}
    theirs = _stamps(mine.core, read, {lang: 1 for lang in read})
    bad = fp.compare(theirs, mine, fp.ROOT / fp.PROBE)
    assert len(bad) == 1
    assert bad[0].startswith("typescript:")
    assert "never compared" in bad[0]


def test_a_language_this_checkout_cannot_read_at_all_is_its_own_answer():
    """The binary is a different program, and that is not a stale stamp."""
    mine = fp.mine()
    theirs = _stamps(mine.core, {**mine.langs, "rust": "0.1.0:beef"},
                     {**{lang: 1 for lang in mine.langs}, "rust": 12})
    bad = fp.compare(theirs, mine, Path("."))
    assert len(bad) == 1
    assert "not the same program" in bad[0]


def test_every_disagreement_is_reported_and_not_only_the_first():
    """A core mismatch and a language mismatch have different remedies.

    Stopping at the first would hide the second behind it, and somebody would fix the
    bundle layout, re-run, and meet the plugin.
    """
    mine = fp.mine()
    moved = dict(mine.langs)
    moved["typescript"] = "1.1.0:0000000000000000"
    theirs = _stamps("14:different", moved, {lang: 1 for lang in mine.langs})
    bad = fp.compare(theirs, mine, Path("."))
    assert len(bad) == 2


# -- the two sentences for a language that read nothing ---------------------------------

def test_a_tree_with_none_of_a_language_says_so_about_the_tree(tmp_path):
    (tmp_path / "only.py").write_text("x = 1\n", encoding="utf-8")
    said = fp.why_nothing(tmp_path, "typescript")
    assert "holds no file it claims" in said
    assert ".ts" in said
    assert "node" not in said, "this is a fact about the tree, not about the machine"


def test_a_tree_that_holds_them_names_the_toolchain_instead(tmp_path):
    """Rule 89: the refusal names the thing that can act on it, from the manifest.

    The install sentence is the plugin's own -- kept here it would be a second answer,
    right until node stopped being how TypeScript is read (rule 51).
    """
    (tmp_path / "a.ts").write_text("export const x = 1\n", encoding="utf-8")
    said = fp.why_nothing(tmp_path, "typescript")
    assert "holds 1 files this build claims" in said
    toolchain = PLUGINS["typescript"].manifest.toolchain
    assert toolchain is not None
    assert toolchain.install in said


def test_a_declaration_file_is_not_a_file_to_measure_a_stamp_from(tmp_path):
    """`.d.ts` is TypeScript's header file and the walk does not read it (chunk 11).

    So a tree of nothing but declarations must read as *this tree holds none*, or the
    gate would blame a missing toolchain for a tree that was never going to yield a row.
    """
    (tmp_path / "types.d.ts").write_text("export declare const x: number\n", encoding="utf-8")
    assert fp.candidates(tmp_path, "typescript") == 0
    assert "holds no file it claims" in fp.why_nothing(tmp_path, "typescript")


# -- the release scripts ----------------------------------------------------------------

@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_no_release_script_asks_the_fingerprint_question_itself(script):
    """The guard that makes chunk 5's silent breakage unrepeatable.

    Not *the name is spelled correctly* -- it was, once. What is asserted is that no
    script names a Python symbol at all, so the next split of the fingerprint cannot
    break a step that no test runs.
    """
    text = script.read_text(encoding="utf-8")
    body = "\n".join(line for line in text.splitlines()
                     if not line.lstrip().startswith(("#", "<#")))
    for spelling in ("from dunneflow", "import dunneflow", "fingerprint()"):
        assert spelling not in body, (
            f"{script.name} asks a Python question by writing {spelling!r}. That is the "
            f"call site chunk 5 broke and nothing noticed — run tools/fingerprints.py "
            f"instead (rule 51)")


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_every_release_script_runs_the_gate(script):
    """All three, including macOS — which had no fingerprint check until chunk 13.

    Linux had one and Windows had one; the platform whose builds are signed, notarised
    and handed to somebody else did not, although `CLAUDE.md` described the check as the
    gate's one figure that is not a ground-truth number.
    """
    text = script.read_text(encoding="utf-8")
    assert "tools/fingerprints.py" in text or "tools\\fingerprints.py" in text, (
        f"{script.name} never runs the rule-12 gate, so a build it blesses may write maps "
        f"this checkout refuses")
