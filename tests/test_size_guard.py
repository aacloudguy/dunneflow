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

from dunneflow import store as store_mod
from dunneflow.store import Store
from dunneflow.walk import analyze_tree, discover, parts_under


def _tree(root: Path, spec: dict[str, int]) -> None:
    """A tree of `n` trivial modules under each named directory."""
    for where, n in spec.items():
        d = root / where
        d.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            (d / f"m{i}.py").write_text(f"def f{i}():\n    return {i}\n", encoding="utf-8")


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


def test_a_directory_a_reader_skips_is_never_proposed_as_a_part(tmp_path):
    """The defect the breakdown shipped with, and it is rule 13's shape.

    A plugin's `skip_dirs` is matched against the path **relative to the analysed root**, so
    a directory named there yields different files depending on where the walk started.
    `Engine/Source/ThirdParty` is 620 files seen from the top of Unreal and **57,373** walked
    as its own root: the word the C++ reader hides on is no longer in any relative path.

    Both cases were observed rather than reasoned. The breakdown proposed `Engine/Binaries`,
    and analysing it read **3,619** files where the part claimed 3,146 — 473 nobody asked
    for, silently. It proposed `Engine/Source/ThirdParty`, and that one was refused by the
    guard itself for being over the bound, which is the system catching its own advice.

    `ThirdParty` is in the C++ reader's skip list and not in `walk.SKIP_DIRS`, so Python
    files under it are admitted from the root — which is exactly why the count is non-zero
    and the directory still cannot be a part.
    """
    _tree(tmp_path, {"good/a": 6, "good/b": 6, "ThirdParty/vendored": 5})
    cut = parts_under(tmp_path, bound=8)

    assert cut.total == 17
    named = {d.name for d, _ in cut.parts}
    assert "ThirdParty" not in named, "a part must read what the breakdown says it reads"
    assert (tmp_path / "ThirdParty", 5) in cut.uncovered

    # And the arithmetic closes: every file is either in a part or stated as in none.
    assert sum(n for _, n in cut.parts) + sum(n for _, n in cut.uncovered) == cut.total
