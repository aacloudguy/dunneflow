"""The ingest guard, and the transaction bound under it.

Two separate claims and they are tested separately, because they fail for different reasons
and one can be right while the other is wrong:

* **The guard** refuses a tree larger than this tool is known to finish, and hands back parts
  that cover it. What makes it worth having is not the refusal but the breakdown: a refusal
  with nowhere to go is rule 89's failure.
* **The bound** ends a burst when the write-ahead log outgrows the page cache, which is what
  makes a tree of any size finishable at all. Asserted by **counting commits**, never by
  timing anything -- a test that measures a rate measures the machine it runs on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow import revisions
from dunneflow import store as store_mod
from dunneflow.cli import build_parser, cmd_analyze, part_argv
from dunneflow.store import Store
from dunneflow.walk import analyze_tree, discover, parts_under


def _tree(root: Path, spec: dict[str, int]) -> None:
    """A tree of `n` trivial modules under each named directory."""
    for where, n in spec.items():
        d = root / where
        d.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            (d / f"m{i}.py").write_text(f"def f{i}():\n    return {i}\n", encoding="utf-8")


def _cpp(root: Path, spec: dict[str, int]) -> None:
    """The same, in a second language -- and the second language is the whole point.

    **A skip rule belongs to one reader**, which is why `Engine/Binaries` holds 3,146 files
    from the top of Unreal rather than none: the C++ reader skips the directory by name and
    the Python reader reads straight through it. A fixture written in one language cannot
    show that asymmetry, and it is the asymmetry the defect lives in.
    """
    for where, n in spec.items():
        d = root / where
        d.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            (d / f"u{i}.cpp").write_text(f"void f{i}() {{ }}\n", encoding="utf-8")


# ------------------------------------------------------------------- the guard --- #

def test_a_tree_within_the_bound_has_no_parts(tmp_path):
    """No parts is the answer *this tree is one part*, not an empty list (design rule 21)."""
    _tree(tmp_path, {"a": 3, "b": 4})
    cut = parts_under(tmp_path, bound=100)
    assert cut.total == 7
    assert cut.whole and cut.parts == [] and cut.uncovered == []


def test_the_parts_cover_every_file_exactly_once(tmp_path):
    """The property that makes the breakdown worth pasting into a shell.

    A cut that loses files gives a reader a set of commands that quietly reads less than the
    tree they asked about, which is design rule 1's failure in an instruction.
    """
    _tree(tmp_path, {"big/one": 6, "big/two": 6, "small": 3, "big": 2})
    cut = parts_under(tmp_path, bound=8)
    assert cut.parts, "a tree over the bound must be cut"
    assert sum(n for _, n in cut.parts) + sum(n for _, n in cut.uncovered) == cut.total == 17

    # **The property that matters: the commands do not overlap.** A part is a directory and
    # `analyze` descends, so two parts where one contains the other would read the same files
    # into two programs -- and a split directory offered as a part would be the oversized
    # analysis the guard exists to refuse. That is why `big`'s own two files are `uncovered`
    # rather than a part of their own.
    seen: set[Path] = set()
    for d, _ in cut.parts:
        here = set(discover(d))
        assert not (seen & here), f"{d} overlaps a part already counted"
        seen |= here
    assert len(seen) == cut.total - sum(n for _, n in cut.uncovered)


def test_no_part_is_larger_than_the_bound_where_one_can_be_cut(tmp_path):
    _tree(tmp_path, {"a": 9, "b": 9, "c": 9})
    cut = parts_under(tmp_path, bound=10)
    assert cut.parts and all(n <= 10 for _, n in cut.parts), cut.parts


def test_a_directory_that_cannot_be_cut_is_reported_as_it_is(tmp_path):
    """There is nowhere left to descend, so the honest answer is the oversized part itself.

    Silently dropping it would lose those files from the breakdown; pretending it is within
    the bound would be a claim the walk can disprove. It comes back oversized and the reader
    can see that it is.
    """
    _tree(tmp_path, {"flat": 12, "other": 3})
    cut = parts_under(tmp_path, bound=10)
    assert [n for d, n in cut.parts if d.name == "flat"] == [12]


def test_files_in_a_split_directory_are_reported_as_reached_by_no_part(tmp_path):
    """The one thing the breakdown cannot cover, said rather than dropped.

    `top` holds two files of its own and two children that force it to split. `analyze top`
    would read all sixteen, so `top` cannot be a part -- and its two files are then in no
    part at all. Design rule 1: the gap is stated, with its size, rather than being the
    difference between two numbers nobody prints.
    """
    _tree(tmp_path, {"top/a": 7, "top/b": 7, "top": 2})
    cut = parts_under(tmp_path, bound=8)
    assert cut.total == 16
    assert not any(d.name == "top" for d, _ in cut.parts), "a split directory is not a part"
    assert cut.uncovered == [(tmp_path / "top", 2)]
    assert sum(n for _, n in cut.parts) + 2 == cut.total


# -------------------------------------------------------------- the transaction --- #

def test_a_long_burst_commits_more_than_once(tmp_path, monkeypatch):
    """The whole of the fix, as a behaviour rather than as a duration.

    Before this, a language's files were one transaction however many there were, so SQLite
    could not checkpoint the log it was writing and a tree of 84,159 files built one of
    734 MB. The cap is lowered here rather than the corpus enlarged: what is being asserted
    is that the loop *stops*, and a test that needed a 700 MB log to say so would be a test
    nobody runs.
    """
    _tree(tmp_path / "src", {"pkg": 60})
    monkeypatch.setattr(store_mod, "WAL_CAP_BYTES", 1)
    monkeypatch.setattr(store_mod, "WAL_CHECK_EVERY", 5)
    st = Store(tmp_path / "g.db")
    try:
        analyze_tree(tmp_path / "src", st)
        assert st.settled >= 2, "the burst never stopped to let the log drain"
        assert st.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 60
    finally:
        st.close()


def test_the_default_cap_leaves_an_ordinary_run_alone(tmp_path):
    """One transaction per reader is still the rule; the cap is for the case it cannot cover.

    A run of ordinary size must not pay a commit it does not need — the comment in
    `analyze_tree` defends a real measurement and this is what keeps it true.
    """
    _tree(tmp_path / "src", {"pkg": 40})
    st = Store(tmp_path / "g.db")
    try:
        analyze_tree(tmp_path / "src", st)
        assert st.settled == 0
    finally:
        st.close()


def test_a_run_stopped_between_commits_keeps_what_it_committed(tmp_path, monkeypatch):
    """What the bound buys beyond the crawl, and rule 80 is untouched by it.

    Before this a run stopped anywhere in a language lost that whole language. Now the
    committed files survive and `known_hashes` makes the next run skip them — while
    `finished()` still says the map is not one, because `complete` is written last.
    """
    _tree(tmp_path / "src", {"pkg": 40})
    monkeypatch.setattr(store_mod, "WAL_CAP_BYTES", 1)
    monkeypatch.setattr(store_mod, "WAL_CHECK_EVERY", 5)

    st = Store(tmp_path / "g.db")
    real = st.write_file_facts
    written = {"n": 0}

    def stop_after_twenty(ff):
        real(ff)
        written["n"] += 1
        if written["n"] == 20:
            raise KeyboardInterrupt("as if somebody pressed ctrl-c")

    monkeypatch.setattr(st, "write_file_facts", stop_after_twenty)
    with pytest.raises(KeyboardInterrupt):
        analyze_tree(tmp_path / "src", st)
    st.close()

    kept = Store(tmp_path / "g.db")
    try:
        held = kept.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        assert held > 0, "the whole language was lost, which is what this fixes"
        assert held < 40, "the run was supposed to stop part way"
        assert not kept.finished(), "a partial map must never claim to be finished (rule 80)"
    finally:
        kept.close()


def test_a_directory_a_reader_skips_is_proposed_with_the_flag_that_makes_it_true(tmp_path):
    """The defect the breakdown shipped with, and the shape the fix took.

    A plugin's `skip_dirs` is matched against the path **relative to the analysed root**, so
    a directory named there yields different files depending on where the walk started.
    `Engine/Source/ThirdParty` is 620 files seen from the top of Unreal and **57,373** walked
    as its own root: the word the C++ reader hides on is no longer in any relative path.

    Both cases were observed rather than reasoned. The breakdown proposed `Engine/Binaries`,
    and analysing it read **3,619** files where the part claimed 3,146 -- 473 nobody asked
    for, silently. It proposed `Engine/Source/ThirdParty`, and that one was refused by the
    guard itself for being over the bound, which is the system catching its own advice.

    **Refusing to propose them was the interim answer and it covered less of the tree than
    the tree has.** The count the breakdown holds was always right -- it comes off the one
    `discover(root)` above, so the directory is bucketed with the files the *tree* admits.
    What was missing was a command that would read exactly those, and `--part-of` is it. So
    the directory is a part again, and what keeps the proposal true is that every command
    carries the flag -- asserted here off `part_argv` rather than by matching text, because
    a guard that checks a name appears has not checked that anything happens (rules 34, 37).
    """
    _tree(tmp_path, {"good/a": 6, "good/b": 6, "ThirdParty/vendored": 5})
    _cpp(tmp_path, {"ThirdParty/vendored": 5})
    cut = parts_under(tmp_path, bound=8)

    # Seventeen, not twenty-two: the five C++ files are what the C++ reader hides, and the
    # five Python ones beside them are what makes the directory non-empty at all.
    assert cut.total == 17
    named = {d.name for d, _ in cut.parts}
    assert "ThirdParty" in named, "a covered directory must be offered as a part"
    assert (tmp_path / "ThirdParty", 5) not in cut.uncovered

    # And the arithmetic still closes: every file is either in a part or stated as in none.
    assert sum(n for _, n in cut.parts) + sum(n for _, n in cut.uncovered) == cut.total

    # The flag, on every one of them, naming the tree.
    for d, _ in cut.parts:
        argv = part_argv(d, tmp_path, tmp_path.parent / "out")
        assert "--part-of" in argv, f"{d} would be read as a root of its own"
        assert argv[argv.index("--part-of") + 1] == str(tmp_path)


def test_a_part_under_a_skipped_directory_reads_what_the_tree_admits(tmp_path):
    """`ThirdParty`'s two numbers, in miniature, and the flag that reconciles them.

    The whole of `BACKLOG.md` item 10 in three walks: the tree hides these files, the part
    on its own does not, and the part told which tree it belongs to agrees with the tree.
    Python's own `site-packages` rather than C++'s `ThirdParty`, because a skip rule belongs
    to **one** reader -- which is why Unreal's `Engine/Binaries` holds 3,146 files at all,
    the C++ reader skipping a directory the Python reader reads right through.
    """
    _tree(tmp_path, {"ThirdParty/vendored": 5, "own": 2})
    _cpp(tmp_path, {"ThirdParty/vendored": 5})
    part = tmp_path / "ThirdParty"

    from_the_tree = sorted(p for p in discover(tmp_path) if part in p.parents)
    as_its_own_root = sorted(discover(part))
    as_a_part = sorted(discover(part, judge_root=tmp_path))

    assert len(from_the_tree) == 5, "the tree hides the five the C++ reader skips"
    assert len(as_its_own_root) == 10, "and rooting inside it un-hides every one of them"
    assert as_a_part == from_the_tree, "a part judged from its tree agrees with its tree"


def test_a_part_that_is_a_test_directory_is_hidden_by_the_tree_it_belongs_to(tmp_path):
    """The half no breakdown can propose, and which nothing guarded.

    `DiscoveryRules.is_test` matches `test_dirs` against `rel.parts` exactly as `skip_dirs`
    does, so pointing `analyze` at a `tests/` directory admits every file in it -- measured
    as *0 files from the top, all of them as its own root*. No breakdown can offer such a
    directory, because from the top it has no discovered files to be counted and so is in no
    part's tally; but anybody may type it, and until `--part-of` there was nothing to type
    instead.
    """
    _tree(tmp_path, {"tests/unit": 4, "own": 2})
    part = tmp_path / "tests"

    assert [p for p in discover(tmp_path) if part in p.parents] == []
    assert len(list(discover(part))) == 4
    assert list(discover(part, judge_root=tmp_path)) == []

    # And `--include-tests` still overrules it, from either root: the flag says where a rule
    # is measured from, never whether it applies.
    assert len(list(discover(part, judge_root=tmp_path, include_tests=True))) == 4


def test_the_flag_changes_nothing_where_the_tree_hides_nothing(tmp_path):
    """Which is why it is on every part rather than on the ones somebody judged to need it.

    The components `--part-of` adds to the judged path are exactly the ones that match no
    rule, so for all but a handful of parts the two answers are the same walk. A condition
    here would be a rule kept at a call site, and the call sites are where this defect came
    from in the first place (rule 51).
    """
    _tree(tmp_path, {"lib/deep/deeper": 4})
    part = tmp_path / "lib" / "deep"
    assert list(discover(part)) == list(discover(part, judge_root=tmp_path))


def test_a_part_of_a_tree_it_does_not_sit_under_is_refused(tmp_path):
    """Refused from the arguments alone, before a store is open.

    The flag decides which files are read, so a wrong one is a map with the wrong facts in
    it rather than a command that fails -- and finding that out after a store is open means
    abandoning a half-written map. Both paths are in the sentence, because neither alone
    tells a reader which end they got wrong (rule 89).
    """
    _tree(tmp_path, {"part": 2, "elsewhere": 2})
    args = build_parser().parse_args(
        ["analyze", str(tmp_path / "part"), "--name", "p",
         "--output", str(tmp_path / "out"), "--part-of", str(tmp_path / "elsewhere"),
         "--no-docs", "--no-render", "--quiet"])
    assert cmd_analyze(args) == 2


def test_a_part_records_where_in_its_tree_it_was_read(tmp_path):
    """A figure taken off a part cannot be reproduced by somebody who does not know that.

    Rule 24, and it is the reason this belongs beside `--without` on `analysis_args` rather
    than being left unsaid: `Engine/Binaries` is 3,146 files read as a part and 3,619 read
    as a root, and the two maps look equally healthy from the inside. The **relative**
    position, never the tree's own path -- an absolute path is one machine's directory
    layout written into a map built to be handed over (rule 60).
    """
    _tree(tmp_path, {"part/sub": 2})
    out = tmp_path / "out"
    args = build_parser().parse_args(
        ["analyze", str(tmp_path / "part"), "--name", "p", "--output", str(out),
         "--part-of", str(tmp_path), "--no-docs", "--no-render", "--quiet"])
    assert cmd_analyze(args) == 0

    written = revisions.newest(out / "p", revisions.GRAPH)
    assert written is not None
    store = Store(written, writable=False)
    try:
        said = store.get_meta("analysis_args") or ""
    finally:
        store.close()
    assert "part" in said and str(tmp_path) not in said, said


def test_a_tree_given_as_its_own_part_of_says_nothing(tmp_path):
    """The whole-program case spelled the long way removes nothing, so it claims nothing.

    Design rule 1 runs both directions: a map must say what was filtered out of it, and it
    must not say something was when it was not (rule 13).
    """
    _tree(tmp_path, {"m": 2})
    out = tmp_path / "out"
    args = build_parser().parse_args(
        ["analyze", str(tmp_path), "--name", "p", "--output", str(out),
         "--part-of", str(tmp_path), "--no-docs", "--no-render", "--quiet"])
    assert cmd_analyze(args) == 0

    written = revisions.newest(out / "p", revisions.GRAPH)
    assert written is not None
    store = Store(written, writable=False)
    try:
        said = store.get_meta("analysis_args") or ""
    finally:
        store.close()
    # The other two flags of this run do remove something and do say so; only the clause
    # this test is about must be absent.
    assert "part of its tree" not in said, said
