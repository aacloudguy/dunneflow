"""Search inside source: one matcher, an answer that says its size, and a named refusal.

Every test here was run against the defect it is written from *and* against a version where
only half the feature works (rule 37). Where that took a fixture larger than the one-file
sample program, one is built here -- rule 8's guard passed against a `[:2]` once because
its corpus had one file in it, and a guard whose fixture is smaller than the bound it
checks has not checked anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow.schema import hash_source
from dunneflow.sourcedb import INFLATE_BUDGET_BYTES, SourceStore
from dunneflow.store import Store
from dunneflow.walk import analyze_tree
from dunneflow.web.code import build_file
from dunneflow.web.search import (
    BadPattern,
    containing_routine,
    matcher,
    search_files,
    search_in_file,
)


@pytest.fixture
def sidecar(analyzed: Store, tmp_path: Path) -> SourceStore:
    """A sidecar holding every file the sample program was analysed from."""
    src = SourceStore(tmp_path / "source.db")
    for row in analyzed.query("SELECT path FROM files", ()):
        body = Path(str(row["path"])).read_text(encoding="utf-8")
        h = hash_source(body)
        src.add_blob(body, h)
        src.map_path(str(row["path"]), h, lang="python")
    src.commit()
    return src


def _root(store: Store) -> str:
    recorded = store.get_meta("source_root")
    if recorded:
        return recorded
    paths = [str(r["path"]) for r in store.query("SELECT path FROM files", ())]
    return str(Path(paths[0]).parent) if paths else ""


# Two things this fixture must have that the sample program does not, and each is a claim
# a guard here would otherwise pass without testing.
#
# A **closure**, so "innermost" can fail: the middle of `outer` is inside `inner`, and a
# version answering with the first containing span looks right on any program without one.
#
# And an **affix family** -- `emit`, `_emit_all`, `reemit` -- so whole-word has something to
# exclude. The sample program has `widgets` and `save_widget` and no bare `widget` at all,
# so the obvious assertion there is `0 > 0`: a needle that matches nothing under either
# rule proves neither rule.
NESTED = '''
"""A program with a closure, so `innermost` is a claim that can fail."""
import os

LIMIT = 3  # module level, so the module scope exists to be an answer


def emit() -> int:
    return len(os.environ)


def _emit_all() -> int:
    return emit() + reemit()


def reemit() -> int:
    return 1


def outer(n: int) -> int:
    total = 0

    def inner(k: int) -> int:
        # emit is named here and is not the routine this line is in
        return emit() + k

    for i in range(n):
        total += inner(i)
    return total
'''


@pytest.fixture
def nested(tmp_path: Path) -> tuple[Store, SourceStore, str]:
    """A program with a nested function, and a sidecar holding it."""
    root = tmp_path / "nested"
    root.mkdir()
    (root / "prog.py").write_text(NESTED, encoding="utf-8")
    store = Store(tmp_path / "graph.db")
    analyze_tree(root, store)
    src = SourceStore(tmp_path / "source.db")
    for row in store.query("SELECT path FROM files", ()):
        body = Path(str(row["path"])).read_text(encoding="utf-8")
        h = hash_source(body)
        src.add_blob(body, h)
        src.map_path(str(row["path"]), h, lang="python")
    src.commit()
    return store, src, str(root)


# ---------------------------------------------------------------- the matcher --- #

def test_the_row_count_and_the_lines_beneath_it_come_from_one_matcher(
        analyzed: Store, sidecar: SourceStore) -> None:
    """Rule 13, and it is the reason `matcher()` exists at all.

    The count printed on a file row and the lines drawn under it are one claim. The easiest
    way to make them disagree is to let the cheap pass and the detailed pass each decide
    what "matches" means -- `str.lower()` and `re.IGNORECASE` differ on a handful of
    characters, and the row would then print a number the lines beneath it cannot produce.

    Asserted for every row of every query rather than in total, because a total can agree
    while two files are wrong in opposite directions.
    """
    root = _root(analyzed)
    for q, kw in [("conn", {}), ("WIDGET", {}), ("widget", {"case": True}),
                  ("execute", {"word": True}), (r"def\s+\w+", {"regex": True})]:
        out = search_files(analyzed, sidecar, q, source_root=root, **kw)
        assert out["ok"], out.get("reason")
        assert sum(int(r["n"]) for r in out["rows"]) == out["total"]
        for row in out["rows"]:
            one = search_in_file(analyzed, sidecar, q, str(row["path"]),
                                 source_root=root, **kw)
            assert one["ok"] and one["n"] == row["n"], (q, kw, row["path"])
            assert one["hits"][0]["line"] == row["first"]


def test_a_whole_word_search_does_not_match_inside_a_longer_name(
        nested: tuple[Store, SourceStore, str]) -> None:
    """Rule 5 in the search box: a marker must sit at an edge of the name.

    Run against plain-substring matching, which reports the wider number and looks right.
    Both bounds matter: the tight answer must be smaller than the loose one *and* must not
    be empty, or a needle nothing matches under either rule would pass this.
    """
    store, src, root = nested
    loose = search_files(store, src, "emit", source_root=root)
    tight = search_files(store, src, "emit", word=True, source_root=root)
    assert loose["total"] > tight["total"] > 0

    one = search_in_file(store, src, "emit", "prog.py", word=True, source_root=root)
    lines = {str(h["text"]).strip() for h in one["hits"]}
    assert "def _emit_all() -> int:" not in lines
    assert "def reemit() -> int:" not in lines
    assert "def emit() -> int:" in lines
    # A line naming both is a hit for the bare one, and the marks say which.
    for hit in one["hits"]:
        text = str(hit["text"])
        assert hit["at"], "a hit with nothing to mark is a highlight over nothing"
        for col, length in hit["at"]:
            assert text[col - 1:col - 1 + length] == "emit"
            before = text[col - 2:col - 1]
            after = text[col - 1 + length:col + length]
            assert not before or not (before.isalnum() or before == "_")
            assert not after or not (after.isalnum() or after == "_")


def test_a_needle_that_can_never_sit_at_a_word_edge_says_so(
        analyzed: Store, sidecar: SourceStore) -> None:
    """`\\b` sits between a word character and a non-word one, so whole-word `()` matches
    nothing however much of it there is. Told apart from a real empty result, because
    "nothing here" and "this question cannot be asked" are different answers.
    """
    root = _root(analyzed)
    impossible = search_files(analyzed, sidecar, "()", word=True, source_root=root)
    assert impossible["ok"] and impossible["total"] == 0
    assert impossible["wordable"] is False
    real = search_files(analyzed, sidecar, "widget", word=True, source_root=root)
    assert real["wordable"] is True


def test_a_regex_turns_whole_word_off_rather_than_composing_with_it() -> None:
    """Rule 46: two controls answering one question is how one gets answered by accident.

    A regex writes its own `\\b`. Wrapping one in another pair would change what the reader
    typed -- `a|b` becomes `\\ba|b\\b`, which is `\\ba` or `b\\b` and is not the question.
    """
    assert matcher("a|b", regex=True, word=True).pattern == "a|b"
    assert matcher("a|b", word=True).pattern == r"\ba\|b\b"


def test_an_unusable_pattern_is_named_and_never_answered_with_no_rows(
        analyzed: Store, sidecar: SourceStore) -> None:
    """Rule 20's `(no rows)` argument, in a search box.

    A bad pattern silently returning nothing is indistinguishable from a good pattern
    matching nothing, and they are opposite claims. Run against a version that caught
    `re.error` and returned an empty answer -- which passes every other test here.
    """
    root = _root(analyzed)
    for q, kw in [("[unclosed", {"regex": True}), ("*", {"regex": True}), ("", {})]:
        out = search_files(analyzed, sidecar, q, source_root=root, **kw)
        assert out["ok"] is False
        assert out["reason"]
        assert "rows" not in out and "total" not in out
        one = search_in_file(analyzed, sidecar, q, "sample.py", source_root=root, **kw)
        assert one["ok"] is False and one["reason"]
    with pytest.raises(BadPattern):
        matcher("[unclosed", regex=True)


# ------------------------------------------------------------- what a hit says --- #

def test_a_hits_margin_and_links_are_the_code_browsers_own(
        analyzed: Store, sidecar: SourceStore) -> None:
    """Rule 51: one truth, one place that owns it.

    A second implementation agrees with the first until the day one of them is edited, and
    a margin disagreeing with the code browser's for the same line is two answers to one
    question. Run against a copy of `_margin` with rule 40's anti-join left out, which is
    exactly the drift this is written to catch.
    """
    root = _root(analyzed)
    out = search_files(analyzed, sidecar, "conn", source_root=root)
    assert out["rows"], "the sample program must contain the needle"
    for row in out["rows"]:
        whole = build_file(analyzed, sidecar, str(row["path"]), root)
        marks: dict[int, list[dict[str, object]]] = {}
        for m in whole["marks"]:
            marks.setdefault(int(m["line"]), []).append(m)
        links: dict[int, list[dict[str, object]]] = {}
        for s in whole["links"]:
            links.setdefault(int(s["line"]), []).append(s)
        one = search_in_file(analyzed, sidecar, "conn", str(row["path"]), source_root=root)
        for hit in one["hits"]:
            assert hit["marks"] == marks.get(int(hit["line"]), [])
            assert hit["links"] == links.get(int(hit["line"]), [])


def test_a_hit_keeps_its_whole_line(analyzed: Store, sidecar: SourceStore) -> None:
    """Rule 8: never truncate at ingest. A line cut to fit a pane is a value shortened
    before it reaches the reader, and the pane can scroll."""
    root = _root(analyzed)
    out = search_in_file(analyzed, sidecar, "conn", "sample.py", source_root=root)
    body = sidecar.path_lines(
        [str(r["path"]) for r in analyzed.query("SELECT path FROM files", ())][0])
    assert body is not None
    for hit in out["hits"]:
        assert hit["text"] == body[int(hit["line"]) - 1]


def test_where_a_hit_sits_is_a_line_range_and_never_a_name(
        nested: tuple[Store, SourceStore, str]) -> None:
    """Rules 5 and 10.

    Two claims in one, and each fails a different wrong implementation. The line inside
    `inner` names `helper` and nothing else, so a name-matching version answers `helper`;
    and `inner` is nested inside `outer`, so a version taking the first containing span
    answers `outer`. Both look plausible on a program with no closures in it.
    """
    store, src, root = nested
    out = search_in_file(store, src, "emit() + k", "prog.py", source_root=root)
    assert out["ok"] and out["n"] == 1
    where = out["hits"][0]["in"]
    assert where is not None
    assert where["name"] == "inner"
    assert str(where["qualname"]).endswith("outer.inner")

    # And the module scope is a real answer, not a gap. Rule 18: it owns what no function
    # does, so a line at module level genuinely sits in it.
    #
    # Found writing this: **the module scope is created only when something needs an owner**
    # (`_owner()` in the extractor), so a file with nothing at module level has none, and a
    # module-level line there honestly answers "nowhere". Two fixtures in a row lacked one
    # -- an import alone does not make one; `LIMIT` does, because a constant is a name
    # (rule 19). Worth writing down rather than working around: a routine list with no
    # `<module>` in it is a real state of a real file, not a defect.
    top = search_in_file(store, src, "LIMIT = 3", "prog.py", source_root=root)
    assert top["ok"] and top["n"] == 1
    assert top["hits"][0]["in"] is not None
    assert top["hits"][0]["in"]["name"] == "<module>"


def test_the_innermost_span_wins_at_every_line_of_a_nested_program(
        nested: tuple[Store, SourceStore, str]) -> None:
    """Asserted over every line rather than at a chosen one.

    A midpoint is not a safe probe: the middle of `outer` is inside `inner`, which is the
    right answer and looks like a failure. The invariant is what to assert -- whatever
    comes back contains the line, and nothing that also contains it starts later.
    """
    from dunneflow.web import queries
    store, _src, _root = nested
    path = [str(r["path"]) for r in store.query("SELECT path FROM files", ())][0]
    defs = [{"id": r["id"], "name": r["name"], "qualname": r["qualname"],
             "line": r["line"], "line_end": r["line_end"]}
            for r in store.query(queries.CODE_DEFS_ROUTINES, {"file": path})]
    assert any(str(d["qualname"]).endswith("outer.inner") for d in defs), \
        "this fixture has no nested routine; the test would pass on anything"
    end = max(int(d["line_end"]) for d in defs)
    for n in range(1, end + 1):
        got = containing_routine(defs, n)
        rivals = [d for d in defs if int(d["line"]) <= n <= int(d["line_end"])]
        if not rivals:
            assert got is None
            continue
        assert got is not None
        assert int(got["line"]) == max(int(d["line"]) for d in rivals)


# ------------------------------------------------------- what the answer states --- #

def test_the_file_answer_is_not_bounded(tmp_path: Path) -> None:
    """Rule 8, on a corpus long enough to be worth truncating.

    Three hundred files, every one of them holding the needle. A `[:50]` anywhere in the
    answer fails here and passes on the one-file sample program.
    """
    root = tmp_path / "many"
    root.mkdir()
    for i in range(300):
        (root / f"m{i:03d}.py").write_text(f"NEEDLE = {i}\n", encoding="utf-8")
    store = Store(tmp_path / "graph.db")
    analyze_tree(root, store)
    src = SourceStore(tmp_path / "source.db")
    for row in store.query("SELECT path FROM files", ()):
        body = Path(str(row["path"])).read_text(encoding="utf-8")
        h = hash_source(body)
        src.add_blob(body, h)
        src.map_path(str(row["path"]), h, lang="python")
    src.commit()
    out = search_files(store, src, "NEEDLE", source_root=str(root))
    assert out["files"] == out["total"] == len(out["rows"]) == 300
    assert out["broad"] is True


def test_the_answer_says_what_it_looked_at_and_not_only_what_it_found(
        analyzed: Store, sidecar: SourceStore) -> None:
    """Design rule 1: what is not on screen is stated, in counts.

    `scanned` and `lines` are what was searched; `analysed` is what the map holds. Without
    them a search that quietly covered 620 of 626 files reads exactly like one that covered
    all of them.
    """
    root = _root(analyzed)
    out = search_files(analyzed, sidecar, "widget", source_root=root)
    held = analyzed.query("SELECT COUNT(*) AS n FROM files", ())[0]["n"]
    assert out["analysed"] == held
    assert out["scanned"] == held and out["unheld"] == 0
    assert out["lines"] > 0 and out["bodies"] > 0


def test_a_file_the_sidecar_cannot_open_is_counted_rather_than_passed_over(
        analyzed: Store, tmp_path: Path) -> None:
    """A search that silently covered fewer files than the map holds is a silent filter."""
    empty = SourceStore(tmp_path / "empty.db")
    empty.open_working()
    empty.commit()
    out = search_files(analyzed, empty, "widget", source_root=_root(analyzed))
    assert out["ok"] and out["scanned"] == 0
    assert out["unheld"] == out["analysed"] > 0


def test_one_body_at_two_paths_is_one_body_and_says_so(tmp_path: Path) -> None:
    """Content addressing, stated. A vendored copy is one search, not two.

    `bodies` and `scanned` are different numbers and the answer reports both, because a
    reader told "626 files searched" on a program holding one file at fifty paths has been
    told something true about paths and misleading about work.
    """
    root = tmp_path / "twice"
    (root / "a").mkdir(parents=True)
    (root / "b").mkdir()
    body = "NEEDLE = 1\n"
    (root / "a" / "same.py").write_text(body, encoding="utf-8")
    (root / "b" / "same.py").write_text(body, encoding="utf-8")
    store = Store(tmp_path / "graph.db")
    analyze_tree(root, store)
    src = SourceStore(tmp_path / "source.db")
    for row in store.query("SELECT path FROM files", ()):
        text = Path(str(row["path"])).read_text(encoding="utf-8")
        h = hash_source(text)
        src.add_blob(text, h)
        src.map_path(str(row["path"]), h, lang="python")
    src.commit()
    out = search_files(store, src, "NEEDLE", source_root=str(root))
    assert out["scanned"] == 2 and out["files"] == 2
    assert out["bodies"] == 1


def test_the_three_absences_are_told_apart(
        analyzed: Store, sidecar: SourceStore, tmp_path: Path) -> None:
    """The same three `/api/file` and `/api/source` keep apart, in the same words."""
    root = _root(analyzed)
    no_sidecar = search_in_file(analyzed, None, "x", "sample.py", source_root=root)
    unknown = search_in_file(analyzed, sidecar, "x", "nowhere.py", source_root=root)
    empty = SourceStore(tmp_path / "empty.db")
    empty.open_working()
    empty.commit()
    unheld = search_in_file(analyzed, empty, "x", "sample.py", source_root=root)
    reasons = {no_sidecar["reason"], unknown["reason"], unheld["reason"]}
    assert len(reasons) == 3, reasons
    assert all(r["ok"] is False for r in (no_sidecar, unknown, unheld))


def test_a_file_with_no_hits_is_an_answer_and_not_a_failure(
        analyzed: Store, sidecar: SourceStore) -> None:
    """`ok: False` is "I cannot answer"; zero hits is an answer. Never the same field."""
    out = search_in_file(analyzed, sidecar, "zzz_not_in_this_program",
                         "sample.py", source_root=_root(analyzed))
    assert out["ok"] is True and out["n"] == 0 and out["hits"] == []


# --------------------------------------------------------------- reading bodies --- #

def test_inflated_bodies_are_kept_within_a_stated_budget(tmp_path: Path) -> None:
    """The bound is the honest half of holding source in memory at all.

    Asserted against the accounting rather than against a number of files, because the
    defect this guards is a cache that grows without limit -- which passes any test that
    only searches twice.
    """
    src = SourceStore(tmp_path / "source.db")
    for i in range(50):
        body = f"# file {i}\n" + ("x = 1\n" * 200)
        src.add_blob(body, f"h{i:03d}")
        src.map_path(f"/p/{i}.py", f"h{i:03d}")
    src.commit()
    for i in range(50):
        assert src.body_lines(f"h{i:03d}") is not None
    assert src._inflated_bytes <= INFLATE_BUDGET_BYTES
    assert src._inflated_bytes == sum(
        sum(len(ln) for ln in v) + len(v) for v in src._inflated.values())


def test_a_body_read_three_ways_is_the_same_body(tmp_path: Path) -> None:
    """`text`, `lines` and `path_lines` are one inflation now; they must also be one answer."""
    src = SourceStore(tmp_path / "source.db")
    body = "alpha\nbeta\ngamma\n"
    src.add_blob(body, "h1")
    src.map_path("/p/x.py", "h1")
    src.commit()
    rows = src.path_lines("/p/x.py")
    assert rows is not None
    assert src.text("/p/x.py") == body
    assert "\n".join(rows) == body
    assert src.lines("/p/x.py", 2, 3) == [(2, "beta"), (3, "gamma")]
    assert src.path_lines("/p/missing.py") is None
    assert src.text("/p/missing.py") is None
