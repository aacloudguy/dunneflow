"""The text lane of a comparison: the file pairing, and one file's line difference.

Every test here is a way this can be wrong while looking right, which for an overlay is
the normal case: marked lines look exactly like marked lines whatever they are marking.

Two of them are about the defect that made this chunk necessary at all -- the code browser
read the sidecar's *newest* snapshot whatever version the map was showing, so serving
Lictores' older graph returned `_queue.py` at 674 lines with the 595-line version's marks
laid over it. Nothing raised, and the page looked like a page that worked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow.schema import hash_source
from dunneflow.sourcedb import SourceStore
from dunneflow.store import Store
from dunneflow.web import filediff
from dunneflow.web.code import build_file, build_files

A = "2026-01-01T00:00:00Z"
B = "2026-02-02T00:00:00Z"


def _sidecar(tmp_path: Path, at: dict[str, dict[str, str]]) -> SourceStore:
    """A sidecar holding `{revision: {path: body}}`, content-addressed as the real one is."""
    s = SourceStore(tmp_path / "source.db")
    for rev, files in at.items():
        s.conn.execute(
            "INSERT OR REPLACE INTO revisions (revision, state, captured_at) "
            "VALUES (?, 'FOR_COMPARISON', ?)", (rev, rev))
        for path, body in files.items():
            h = hash_source(body)
            s.add_blob(body, h)
            s.map_path(path, h, revision=rev)
    s.commit()
    return s


# --------------------------------------------------------------- the pairing --- #

def test_the_four_states_are_told_apart(tmp_path: Path) -> None:
    """Same, modified, and one side only each way. `same` is an answer, not an omission.

    613 of Lictores' 628 files are unchanged, and a list holding only the exceptions
    cannot be told from a list that lost some.
    """
    s = _sidecar(tmp_path, {
        A: {"same.py": "x = 1\n", "mod.py": "x = 1\n", "gone.py": "x = 1\n"},
        B: {"same.py": "x = 1\n", "mod.py": "x = 2\n", "new.py": "x = 1\n"},
    })
    out = filediff.pair(s, A, B)
    assert out["available"]
    assert out["counts"] == {"same": 1, "modified": 1,
                             "only_in_base": 1, "only_in_compared": 1}
    by = {r["path"]: r["status"] for r in out["rows"]}
    assert by == {"same.py": "same", "mod.py": "modified",
                  "gone.py": "only_in_base", "new.py": "only_in_compared"}
    assert out["total"] == 4


def test_two_paths_with_one_body_are_the_same_file(tmp_path: Path) -> None:
    """Equal hashes are equal bytes, and that is what makes the pairing free.

    Not "probably equal": the hash is what the store keyed the body by, so the whole
    file-level diff is a string comparison over an indexed column. If this ever stops
    holding, the cheap lane is unsound and the expensive one has to run on everything.
    """
    s = _sidecar(tmp_path, {A: {"p.py": "same bytes\n"}, B: {"p.py": "same bytes\n"}})
    assert s.hash_of("p.py", revision=A) == s.hash_of("p.py", revision=B)
    assert filediff.pair(s, A, B)["counts"]["same"] == 1


def test_the_pairing_never_names_what_happened(tmp_path: Path) -> None:
    """Rule 65: the bands say **where** a thing is, never what befell it.

    Asserted over the keys the answer carries rather than over this module's source,
    because what misleads a reader is what reaches them. And over the *parts* of each
    key -- `routines_after` contains a forbidden word rather than equalling one, and a
    whole-key test lets exactly that through (rule 59's companion).
    """
    s = _sidecar(tmp_path, {A: {"a.py": "1\n"}, B: {"b.py": "1\n"}})
    out = filediff.pair(s, A, B)
    keys = set(out) | set(out["counts"]) | {r["status"] for r in out["rows"]}
    keys |= set(filediff.STATUSES)
    banned = {"added", "removed", "deleted", "new", "old", "before", "after",
              "earlier", "later", "newer", "older"}
    for key in keys:
        parts = set(str(key).replace("-", "_").split("_"))
        assert not (parts & banned), (
            f"`{key}` names what happened rather than where the thing is. Which version is "
            "newer is the reader's assumption, stated on the strip — a store that bakes it "
            "in is confidently wrong the moment an older copy is analysed second"
        )


@pytest.mark.parametrize("base,compared,expect", [
    (A, A, "itself"),
    (A, "2099-01-01T00:00:00Z", "holds no source"),
    ("", B, "two versions"),
])
def test_every_refusal_says_which_one_it_is(tmp_path: Path, base: str,
                                            compared: str, expect: str) -> None:
    """Design rule 1: "there is no comparison" and "the comparison found nothing" are
    opposite claims, and a reader must not have to guess which one they got."""
    s = _sidecar(tmp_path, {A: {"p.py": "1\n"}, B: {"p.py": "2\n"}})
    out = filediff.pair(s, base, compared)
    assert out["available"] is False
    assert expect in out["reason"]


def test_no_sidecar_is_a_stated_absence(tmp_path: Path) -> None:
    """A map handed over without its bodies cannot be compared, and says so."""
    out = filediff.pair(None, A, B)
    assert out["available"] is False and "sidecar" in out["reason"]


# ------------------------------------------------------------ one file's lines --- #

def test_a_deleted_line_is_a_base_line_number_and_an_added_one_carries_its_text(
        tmp_path: Path) -> None:
    """The two halves are shaped by what the code browser already is.

    The client holds the base's lines, so a line only the base has is a *number*. A line
    only the compared has is not in the file on screen at all, so its **text** has to
    travel -- there is nothing there to mark.
    """
    s = _sidecar(tmp_path, {
        A: {"p.py": "one\ntwo\nthree\n"},
        B: {"p.py": "one\nthree\nfour\n"},
    })
    out = filediff.lines(s, "p.py", A, B)
    assert out["available"] and out["status"] == "modified"
    assert out["base_only"] == [2]                     # "two" is in the base only
    assert out["counts"]["base_only"] == 1
    texts = [t for ins in out["inserts"] for t in ins["lines"]]
    assert texts == ["four"]
    assert out["counts"]["compared_only"] == 1


def test_an_insert_is_anchored_where_the_matcher_puts_it_and_keeps_its_own_number(
        tmp_path: Path) -> None:
    """`after` is a base line and `first` is the compared version's own number.

    Renumbering the other version's lines into this file would invent a position for
    lines that have none here (rule 1); dropping the number would throw away the one
    thing that says where they actually are.
    """
    s = _sidecar(tmp_path, {
        A: {"p.py": "a\nb\n"},
        B: {"p.py": "a\nX\nY\nb\n"},
    })
    out = filediff.lines(s, "p.py", A, B)
    assert out["base_only"] == []
    assert len(out["inserts"]) == 1
    ins = out["inserts"][0]
    assert ins["after"] == 1                           # after the base's line 1
    assert ins["first"] == 2                           # their line 2
    assert ins["lines"] == ["X", "Y"]


def test_an_insert_before_the_first_line_anchors_at_zero(tmp_path: Path) -> None:
    """`0` is genuinely "before line one", not a sentinel — the client draws it there."""
    s = _sidecar(tmp_path, {A: {"p.py": "b\n"}, B: {"p.py": "a\nb\n"}})
    ins = filediff.lines(s, "p.py", A, B)["inserts"]
    assert [i["after"] for i in ins] == [0]
    assert ins[0]["lines"] == ["a"]


def test_a_rewritten_line_is_a_deletion_and_an_insertion_and_not_a_third_thing(
        tmp_path: Path) -> None:
    """A `replace` is recorded as both halves.

    Two rewritten lines are not "one changed line" in any way this can defend -- their
    contents may share nothing -- and pairing them would invent an identity (rule 30's
    shape in a diff). The reader sees the old line struck and the new one beside it,
    which is what actually happened.
    """
    s = _sidecar(tmp_path, {A: {"p.py": "a\nOLD\nc\n"}, B: {"p.py": "a\nNEW\nc\n"}})
    out = filediff.lines(s, "p.py", A, B)
    assert out["base_only"] == [2]
    assert [t for i in out["inserts"] for t in i["lines"]] == ["NEW"]
    # **The anchor, and only a `replace` can test it.** A pure insert has a zero-width
    # base range, so `i1` and `i2` are equal there and an anchor taken from either passes
    # — which is how a mutation swapping them survived the two tests above. Here the
    # ranges differ: the new line belongs *before* the old one it replaces, at the base
    # line above, not after the line it is replacing.
    assert out["inserts"][0]["after"] == 1


def test_an_unchanged_file_is_answered_from_the_hashes(tmp_path: Path) -> None:
    """`same` is stated, never returned as an empty diff.

    No marks and no reason reads as a comparison that failed rather than as one that
    succeeded and found nothing -- the same argument `changes.py` makes for `identical`.
    """
    s = _sidecar(tmp_path, {A: {"p.py": "x\ny\n"}, B: {"p.py": "x\ny\n"}})
    out = filediff.lines(s, "p.py", A, B)
    assert out["status"] == "same"
    assert out["base_only"] == [] and out["inserts"] == []
    # Three, not two: a trailing newline makes an empty final line, and the store keeps it
    # rather than trimming (rule 8 -- nothing is shortened on the way in). The gutter
    # numbers it, so counting it here is the same count the reader sees.
    assert out["counts"]["same"] == 3


def test_a_file_on_one_side_only_says_which_side(tmp_path: Path) -> None:
    """Stated here rather than left for a caller to infer from an absence.

    The code browser is showing the base: a file the base does not have has no lines to
    overlay at all, and a file the compared does not have is entirely one side's.
    """
    s = _sidecar(tmp_path, {A: {"gone.py": "1\n2\n"}, B: {"new.py": "1\n"}})
    gone = filediff.lines(s, "gone.py", A, B)
    # Every line of it, including the empty one a trailing newline leaves.
    assert gone["status"] == "only_in_base" and gone["base_only"] == [1, 2, 3]
    new = filediff.lines(s, "new.py", A, B)
    assert new["status"] == "only_in_compared"
    assert new["base_only"] == [] and new["counts"]["compared_only"] == 2


def test_a_path_neither_version_holds_refuses_rather_than_answering_empty(
        tmp_path: Path) -> None:
    """`(no rows)` and "no such file" are different answers (rule 20's argument)."""
    s = _sidecar(tmp_path, {A: {"p.py": "1\n"}, B: {"p.py": "2\n"}})
    out = filediff.lines(s, "nowhere.py", A, B)
    assert out["available"] is False and "neither version" in out["reason"]


def test_the_matcher_does_not_treat_repeated_source_lines_as_junk(
        tmp_path: Path) -> None:
    """`autojunk=False`, asserted by the answer rather than by the flag.

    `SequenceMatcher`'s heuristic calls a line appearing in more than 1% of a sequence
    longer than 200 lines junk -- which in source is every blank line, every bare `)` and
    every `return`, so it aligns worst exactly where source is most repetitive. On
    Lictores' twelve modified files it reported three removals that are not removals.

    Written first as a grep for `autojunk=False` in this module's source, and that guard
    was worthless twice over: the string is in the docstring as well as the code, so a
    mutation flipping the *call* left it passing (rule 37 -- check that it catches, not
    that it mentions). This is 480 lines of the repetition source actually has, with
    scattered edits. With the heuristic on it reports **13 removals where there are 10**.
    """
    body = []
    for i in range(80):
        body += [f"def f{i}():", "    x = (", "        1,", "    )", "    return x", ""]
    edited = []
    for i, line in enumerate(body):
        if i % 37 == 0:
            edited.append(f"    # inserted {i}")
        if i % 53 == 0:
            continue                      # a line genuinely removed
        edited.append(line)
    removed = sum(1 for i in range(len(body)) if i % 53 == 0)

    s = _sidecar(tmp_path, {A: {"p.py": "\n".join(body)},
                            B: {"p.py": "\n".join(edited)}})
    out = filediff.lines(s, "p.py", A, B)
    assert out["counts"]["base_only"] == removed, (
        f"{out['counts']['base_only']} lines are reported as being in the base only and "
        f"{removed} actually are — difflib's junk heuristic is on, and it mis-aligns "
        "exactly where source is most repetitive"
    )


# --------------------------------------- the defect this chunk was built over --- #

def test_the_code_browser_reads_the_version_it_was_asked_for(tmp_path: Path) -> None:
    """The defect, made into a check.

    One sidecar holds every revision, so its own default is the newest snapshot -- right
    only while the newest is also the version being read. Serving Lictores' older graph
    returned `_queue.py` at 674 lines with the 595-line version's marks over it: every
    link past the first divergence underlining the wrong characters, nothing raised.

    Both directions are asserted. Asking for the older version must give the older bytes
    **and** asking for the newer must still give the newer -- a fix that pinned everything
    to one end would pass half of this.
    """
    s = _sidecar(tmp_path, {A: {"p.py": "old\n"}, B: {"p.py": "new\nlines\n"}})
    assert s.text("p.py", revision=A) == "old\n"
    assert s.text("p.py", revision=B) == "new\nlines\n"
    # And with nothing named it is the newest, which is what made the defect invisible.
    assert s.text("p.py") == "new\nlines\n"


def test_a_sidecar_says_whether_it_holds_a_version_rather_than_substituting_one(
        tmp_path: Path) -> None:
    """`holds_revision` is a bool, and the two outcomes are not interchangeable.

    Rule 49: a fallback yielding a plausible value hides the failure it was written for.
    The newest snapshot's bytes under an older version's map look exactly like a file.
    """
    s = _sidecar(tmp_path, {A: {"p.py": "1\n"}})
    assert s.holds_revision(A) is True
    assert s.holds_revision(B) is False


def test_the_file_list_counts_lines_from_the_version_it_names(
        analyzed: Store, sample_tree: Path, tmp_path: Path) -> None:
    """A file list built from one snapshot beside a map of another states line counts for
    bytes nobody is looking at -- two versions in one row, agreeing about nothing."""
    from dunneflow.sourcedb import capture
    src = SourceStore(tmp_path / "source.db")
    hashes = {str(r["path"]): str(r["content_hash"])
              for r in analyzed.query("SELECT path, content_hash FROM files", {})}
    capture(hashes, src, root=sample_tree, revision=A)
    # A second revision holding a longer body for the same path, so the two disagree.
    body = "\n".join(f"line {i}" for i in range(50))
    h = hash_source(body)
    src.conn.execute("INSERT OR REPLACE INTO revisions (revision, state, captured_at) "
                     "VALUES (?, 'WORKING', ?)", (B, B))
    src.add_blob(body, h)
    for path in hashes:
        src.map_path(path, h, revision=B)
    src.commit()

    at_a = build_files(analyzed, src, revision=A)
    at_b = build_files(analyzed, src, revision=B)
    assert at_a["revision"] == A and at_b["revision"] == B
    lines_a = {f["path"]: f["lines"] for f in at_a["files"]}
    lines_b = {f["path"]: f["lines"] for f in at_b["files"]}
    assert lines_a != lines_b, (
        "the file list gave the same line counts for two different snapshots — it is "
        "reading whichever the sidecar defaults to rather than the version it names"
    )
    assert set(lines_b.values()) == {50}

    # And the same for one file's body: the map's marks are the graph's, the lines are
    # this revision's, and the payload names which revision it read.
    one = next(iter(hashes))
    at = build_file(analyzed, src, one, revision=B)
    assert at["available"] and at["revision"] == B
    assert len(at["lines"]) == 50

    # **And against the older revision, which is the half that matters.** Asking for `B`
    # alone proves nothing: `B` is the newest snapshot, so a `build_file` that dropped the
    # revision entirely and fell back to the sidecar's default would answer identically.
    # That is exactly the defect — and a first version of this guard passed over a
    # mutation that reintroduced it (rule 59's companion: when a mutation survives, ask
    # whether the guard is weak before deciding the mutation was).
    older = build_file(analyzed, src, one, revision=A)
    assert older["available"] and older["revision"] == A
    assert len(older["lines"]) != 50, (
        "asking for the older revision returned the newest snapshot's body — one version's "
        "bytes under another version's map, which raises nothing and looks like a file"
    )
    assert older["lines"] != at["lines"]
    src.close()
