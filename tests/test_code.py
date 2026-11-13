"""The code browser's backend: a file, its links, and where a link may not be drawn."""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow.schema import hash_source
from dunneflow.sourcedb import SourceStore
from dunneflow.store import Store
from dunneflow.web.code import _link_spans, _margin, _place, build_file, build_files


@pytest.fixture
def sidecar(analyzed: Store, sample_tree: Path, tmp_path: Path) -> SourceStore:
    """A sidecar holding every file the sample program was analysed from.

    Two spellings, as `capture` itself has: the stored key is relative, and the tree is
    joined onto it to find the bytes. The fixture needs `sample_tree` for exactly the
    reason `capture` needs a root -- reading a body is the one step that touches the disk.
    """
    src = SourceStore(tmp_path / "source.db")
    for row in analyzed.query("SELECT path FROM files", ()):
        rel = str(row["path"])
        body = (sample_tree / rel).read_text(encoding="utf-8")
        h = hash_source(body)
        src.add_blob(body, h)
        src.map_path(rel, h, lang="python")
    src.commit()
    return src


# There was a `_root(store)` here, reading `source_root` out of the graph's meta and
# falling back to the first file's parent. Nothing records a root any more and no reader
# needs one: paths are stored relative to the tree they were read from, which is the
# spelling the screen wants and the spelling that pairs a file with itself across two
# revisions read from two different trees.


# ------------------------------------------------------------------ the list --- #

def test_the_file_list_is_every_analysed_file(
        analyzed: Store, sidecar: SourceStore) -> None:
    out = build_files(analyzed, sidecar)
    in_store = analyzed.query("SELECT COUNT(*) AS n FROM files", ())[0]["n"]
    assert out["total"] == in_store == len(out["files"])
    assert all(f["held"] for f in out["files"])


def test_the_file_list_is_not_bounded(tmp_path: Path) -> None:
    """Rule 8, and it needs a list long enough to be worth truncating.

    Written against a store built here rather than against the sample program, which has
    exactly one file -- so the obvious version of this guard passed against a `[:2]` that
    would have hidden 624 of Lictores' 626. A guard whose fixture is smaller than the bound
    it is checking for has not checked anything.
    """
    store = Store(tmp_path / "many.db")
    for i in range(200):
        store.conn.execute(
            "INSERT INTO files(path, lang, module, content_hash) VALUES(?,?,?,?)",
            (f"pkg/mod{i:03d}.py", "python", f"pkg.mod{i:03d}", f"h{i}"))
    store.conn.commit()
    out = build_files(store, None)
    assert out["total"] == 200 == len(out["files"])
    assert out["files"][0]["path"] == "pkg/mod000.py"


def test_the_list_survives_a_map_handed_over_without_its_source(analyzed: Store) -> None:
    """Design rule 11 in miniature: what was analysed is answerable with no sidecar at all.

    "This map has no source" and "this map has no files" are opposite claims, and a list
    that went empty without one would state the wrong one.
    """
    out = build_files(analyzed, None)
    assert out["total"] > 0
    assert out["sidecar"] is False
    assert all(f["held"] is False for f in out["files"])
    assert all(f["lines"] == 0 for f in out["files"])


def test_a_path_is_stored_relative_to_the_tree_that_was_analysed(
        analyzed: Store, sidecar: SourceStore) -> None:
    """Relative in the **store**, not merely on the screen — and that is the change.

    It used to be shortened for display over an absolute path in the store, which read the
    same on this page and was wrong underneath it in three ways: it leaked one machine's
    layout to anyone the map was handed to, it broke when the tree moved, and it gave the
    same file two unrelated keys across two revisions read from two different trees.

    Asserted over **every** row rather than the first, because a shortening that worked on
    one path and not another is exactly what a spot check misses (rule 18: assert the
    total, not the case).
    """
    out = build_files(analyzed, sidecar)
    assert out["files"]
    assert all(not f["path"].startswith("/") for f in out["files"])
    # Nothing hands back an absolute spelling beside it any more. `full` was that spelling.
    assert all("full" not in f for f in out["files"])
    stored = [str(r["path"]) for r in analyzed.query("SELECT path FROM files", ())]
    assert stored and all(not p.startswith("/") for p in stored)


# --------------------------------------------------------- placing a link --- #

def test_a_span_is_placed_only_where_the_expression_occurs_exactly_once() -> None:
    """The rule the whole inline layer rests on, both ways.

    `calls` records a line and the expression written at the call site and **no column**.
    Once on the line is a position we know; twice is a position we would be guessing, and
    a guessed column is an invented position -- rule 1, and the same argument `queries.py`
    makes about inventing an id to make a row clickable.
    """
    assert _place("    self._emit(x)", "self._emit") == 5
    assert _place("    self._emit(self._emit(x))", "self._emit") is None
    assert _place("    other(x)", "self._emit") is None
    # Columns are one-based, matching every line number the graph records.
    assert _place("f(x)", "f") == 1


def test_an_unplaceable_call_is_counted_rather_than_dropped_silently() -> None:
    """Design rule 1: a link that could not be drawn is not a link that is missing."""
    lines = ["go(go(x))", "go(x)"]
    calls = [{"line": 1, "expr": "go", "id": "n1", "confidence": "CERTAIN"},
             {"line": 2, "expr": "go", "id": "n1", "confidence": "CERTAIN"}]
    placed, dropped = _link_spans(lines, calls, [])
    assert [p["line"] for p in placed] == [2]
    assert dropped == 0                      # line 1 was never a candidate, not an overlap


def test_two_spans_claiming_the_same_characters_do_not_both_get_drawn() -> None:
    """A link whose text belongs to another link is a click landing where nobody aimed.

    Rule 47's argument about two pickable layers reporting through one handler, one layer
    down: overlapping spans are one region with two answers.
    """
    lines = ["    self._emit(x)"]
    calls = [{"line": 1, "expr": "self._emit", "id": "outer", "confidence": "CERTAIN"},
             {"line": 1, "expr": "_emit", "id": "inner", "confidence": "CERTAIN"}]
    placed, dropped = _link_spans(lines, calls, [])
    assert len(placed) == 1
    assert dropped == 1
    assert placed[0]["id"] == "outer"        # the longer span, taken first


def test_a_call_that_resolved_to_nothing_local_is_never_a_link() -> None:
    """Rule 26: external is not inferred. We are certain the call happens and cannot see
    the other end, which is a mark rather than a link to nowhere."""
    lines = ["    requests.post(url)"]
    calls = [{"line": 1, "expr": "requests.post", "id": None, "confidence": "INFERRED"}]
    placed, dropped = _link_spans(lines, calls, [])
    assert placed == [] and dropped == 0


def test_a_line_number_outside_the_file_places_nothing() -> None:
    """A fact whose line is past the end is a defect upstream, not a crash here."""
    placed, _ = _link_spans(["one line"], [
        {"line": 99, "expr": "x", "id": "n", "confidence": "CERTAIN"}], [])
    assert placed == []


# ------------------------------------------------------------------ one file --- #

def _sample(analyzed: Store) -> str:
    return str(analyzed.query(
        "SELECT path FROM files WHERE path LIKE '%sample.py'", ())[0]["path"])


def test_a_file_comes_back_whole_with_its_lines_in_order(
        analyzed: Store, sidecar: SourceStore) -> None:
    """Whole, never a window -- the client bounds what it draws (rule 8)."""
    d = build_file(analyzed, sidecar, _sample(analyzed))
    assert d["available"] is True
    assert d["first"] == 1
    body = sidecar.text(_sample(analyzed))
    assert body is not None
    assert d["lines"] == body.split("\n")


def test_every_link_carries_an_id_the_graph_actually_holds(
        analyzed: Store, sidecar: SourceStore) -> None:
    """Rule 30 from the other side: a control that emits no identity cannot act, and one
    that emits an identity nothing holds is a link to nothing."""
    d = build_file(analyzed, sidecar, _sample(analyzed))
    assert d["links"], "the sample program has resolvable calls"
    known = {str(r["id"]) for r in analyzed.query("SELECT id FROM routines", ())}
    known |= {str(r["id"]) for r in analyzed.query("SELECT id FROM structures", ())}
    for link in d["links"]:
        assert link["id"] in known, f"{link['label']} points at nothing"


def test_a_link_sits_exactly_on_the_text_it_names(
        analyzed: Store, sidecar: SourceStore) -> None:
    """The claim a span makes about itself, checked against the line it was placed on.

    A column that is merely plausible looks identical to a correct one, and every guard
    that reads markup would pass on either.
    """
    d = build_file(analyzed, sidecar, _sample(analyzed))
    for link in d["links"]:
        line = d["lines"][link["line"] - 1]
        a = link["col"] - 1
        assert line[a:a + link["len"]] == link["label"]


def test_the_margin_does_not_state_one_act_twice(
        analyzed: Store, sidecar: SourceStore) -> None:
    """Rule 40. A DATABASE boundary already named by a `sql_ops` row on the same line is
    the same act seen by two detectors -- two correct numbers, neither saying what it
    counted."""
    d = build_file(analyzed, sidecar, _sample(analyzed))
    sql_lines = {m["line"] for m in d["marks"] if m["kind"] == "sql"}
    assert sql_lines, "the sample program runs SQL"
    doubled = [m for m in d["marks"]
               if m["kind"] == "boundary" and m["label"] == "DATABASE"
               and m["line"] in sql_lines]
    assert doubled == []


def test_a_boundary_no_other_detector_saw_keeps_its_mark(tmp_path: Path) -> None:
    """Rule 40's companion, and the half its first fix got wrong.

    Excluding the general record must not lose what only the general record saw. Two cases
    the sample program cannot produce -- every DATABASE boundary in it sits on a SQL line,
    and no other kind does -- so the rows are written here. 43 of Lictores' routines open a
    connection and run nothing, and a coarser rule blanks every one of their cards.
    """
    store = Store(tmp_path / "b.db")
    f = "/tree/x.py"
    store.conn.execute(
        "INSERT INTO files(path, lang, module, content_hash) VALUES(?,?,?,?)",
        (f, "python", "x", "h"))
    store.conn.executemany(
        "INSERT INTO boundaries(file, routine_id, kind, direction, target, line, "
        "evidence, salience) VALUES(?,?,?,?,?,?,?,?)",
        [(f, "r1", "DATABASE", "BOTH", "conn", 10, "connect()", 1),  # nothing else saw this
         (f, "r1", "DATABASE", "BOTH", "conn", 20, "execute()", 1),  # the SQL reader saw it
         (f, "r1", "ENV", "IN", "TOKEN", 20, "environ[]", 1)])       # ...on the same line
    store.conn.execute(
        "INSERT INTO sql_ops(file, routine_id, operation, direction, tbl, sql, line) "
        "VALUES(?,?,?,?,?,?,?)",
        (f, "r1", "SELECT", "READ", "widgets", "SELECT 1", 20))
    store.conn.commit()

    marks = _margin(store, f)
    db_lines = {m["line"] for m in marks if m["kind"] == "boundary" and m["label"] == "DATABASE"}
    env_lines = {m["line"] for m in marks if m["kind"] == "boundary" and m["label"] == "ENV"}
    assert db_lines == {10}, "the one nothing else recorded is kept, the doubled one is not"
    assert env_lines == {20}, "a different kind on a SQL line is a different act"


def test_only_a_real_library_call_is_marked_as_leaving(
        analyzed: Store, sidecar: SourceStore) -> None:
    """`calls.external` covers three different things and only one earns a mark.

    Found by reading the margin rather than by any check: `int` sat on its own line labelled
    *leaves the program*. A builtin is not rule 26's case -- we can see exactly where `len`
    goes -- and `len(x)` is internal computation, which this tool exists not to report.
    Boundary touches are the third, and marking them here states one act a third time beside
    the boundary and the SQL rows for it (rule 40).

    The first segment must be a name the file imported, or `out.append` and `payload.get`
    read as libraries. Rule 5: match on something pinned, never on a bare name.
    """
    d = build_file(analyzed, sidecar, _sample(analyzed))
    lib = {m["label"] for m in d["marks"] if m["kind"] == "library"}

    # Exactly one, and every exclusion is visible in what is missing beside it.
    assert lib == {"typer.Typer"}, lib

    # `requests.post` and `subprocess.run` are real calls out of the program, and each is
    # already a boundary on its own line. Stating them here is the same act a second time,
    # so they are absent here and present there -- both halves asserted, because dropping
    # them from both would pass the first half alone.
    assert not any(x.startswith(("requests.", "subprocess.", "conn.")) for x in lib)
    kinds = {(m["kind"], m["label"]) for m in d["marks"]}
    assert ("boundary", "PROCESS") in kinds
    # And NETWORK is *not* a boundary mark: `net_calls` recorded the same act with its
    # protocol and its timeout, so rule 40 gives it the more specific row and drops the
    # general one. Asserted rather than assumed, because the first version of this guard
    # expected a boundary and would have been "fixed" by weakening the dedup.
    assert ("boundary", "NETWORK") not in kinds
    assert ("net", "HTTP") in kinds

    # `app.add_typer` is a method on a local variable, and nothing but the import test
    # tells it apart from `typer.Typer` one line above it.
    assert "app.add_typer" not in lib

    # And no bare name: a builtin, or a call the resolver lost, and neither is a library.
    assert all("." in x for x in lib)


def test_a_definition_is_a_link_and_the_module_scope_is_not(
        analyzed: Store, sidecar: SourceStore, tmp_path: Path) -> None:
    """`<module>` is the synthetic scope that owns what no function does (rule 18).

    It is a real node the reader can select, and it has no `def` line to underline -- so it
    belongs in `defs`, where the pane can list it, and never in `links`.

    **Read against a body whose first line contains the text `<module>`**, because the
    obvious version of this guard passed against a build that had stopped filtering: the
    string never appears in ordinary source, so `_place` found nothing and the assertion
    held for a reason that had nothing to do with the rule. Rule 42 -- check that the guard
    catches, not that it mentions.
    """
    d = build_file(analyzed, sidecar, _sample(analyzed))
    assert any(x["kind"] == "module" for x in d["defs"])
    assert any(x["kind"] == "def" and x["label"] == "load_config" for x in d["links"])

    path = _sample(analyzed)
    body = sidecar.text(path)
    assert body is not None
    doctored = "# <module> level handling\n" + body.split("\n", 1)[1]
    trap = SourceStore(tmp_path / "trap" / "source.db")
    trap.add_blob(doctored, hash_source(doctored))
    trap.map_path(path, hash_source(doctored), lang="python")
    trap.commit()

    d = build_file(analyzed, trap, path)
    assert "<module>" in d["lines"][0], "the trap is on the line the module scope claims"
    assert all(x["label"] != "<module>" for x in d["links"])


def test_a_definition_span_is_the_whole_routine(
        analyzed: Store, sidecar: SourceStore) -> None:
    """The pane scrolls to a selection and shades its extent, so it needs both ends."""
    d = build_file(analyzed, sidecar, _sample(analyzed))
    load = next(x for x in d["defs"] if x["name"] == "load_config")
    assert load["line_end"] > load["line"]
    assert "def load_config" in d["lines"][load["line"] - 1]


# ------------------------------------------------------------------ absences --- #

def test_the_three_absences_are_told_apart(
        analyzed: Store, sidecar: SourceStore, tmp_path: Path) -> None:
    """No sidecar, a sidecar without this file, and a file the map never read.

    Blurring them is how "we cannot show you this" becomes indistinguishable from "there
    is nothing here", which are opposite claims about the map.
    """
    assert "no path asked for" in build_file(analyzed, sidecar, "")["reason"]
    assert "did not analyse" in build_file(analyzed, sidecar, "nope.py")["reason"]
    assert "no source sidecar" in build_file(analyzed, None, _sample(analyzed))["reason"]

    empty = SourceStore(tmp_path / "empty" / "source.db")
    d = build_file(analyzed, empty, _sample(analyzed))
    assert d["available"] is False
    assert "does not hold this file" in d["reason"]


def test_there_is_one_spelling_of_a_path_and_an_absolute_one_is_not_it(
        analyzed: Store, sidecar: SourceStore, sample_tree: Path) -> None:
    """This replaces a test that two spellings reconciled, because now there is one.

    `_resolve_path` existed to take either the short path the browser hands out or the
    absolute one the store recorded, and ask the store which was meant. With paths stored
    relative there is nothing to reconcile — and the guard that matters is the opposite
    one: an absolute path must be **honestly refused**, not quietly re-joined. A lookup
    that accepted both spellings again would be the same defect returning by the door it
    left through.
    """
    rel = _sample(analyzed)
    assert not rel.startswith("/")
    assert build_files(analyzed, sidecar)["files"][0]["path"] == rel

    ok = build_file(analyzed, sidecar, rel)
    assert ok["available"] and ok["file"] == rel

    absolute = build_file(analyzed, sidecar, str(sample_tree / rel))
    assert absolute["available"] is False
    assert "did not analyse" in absolute["reason"]
