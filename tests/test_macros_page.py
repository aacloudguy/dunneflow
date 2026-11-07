"""The macros page, the fold, and the agent's answer: what a reader sees of the facts."""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow import ingest
from dunneflow.ingest.contract import ToolchainMissing
from dunneflow.render.macros import render_macros
from dunneflow.render.markdown import _routines
from dunneflow.render.page import Stamp
from dunneflow.resolve.macros import macro_places, macro_report
from dunneflow.store import Store
from dunneflow.walk import analyze_tree


def _why() -> str:
    plugin = ingest.PLUGINS.get("cpp")
    if plugin is None:
        return "this build ships no C and C++ reader"
    try:
        plugin.probe()
    except ToolchainMissing as exc:
        return str(exc)
    return ""


WHY = _why()
pytestmark = pytest.mark.skipif(bool(WHY), reason=WHY or "-")

TREE = """\
extern "C" { int connect(int, const void *, int); int system(const char *); }
#define NOTHING 0
#define SEND(a) connect(a, 0, 0)
#define MANY(n) void n##_a() {} void n##_b() {}
#define ENTRY int main() { return 0; }
#include "not_here.h"
#ifdef NEVER
void not_read() {}
#endif
MANY(tree)
ENTRY
void hand() { SEND(NOTHING); }
"""


@pytest.fixture
def store(tmp_path):
    (tmp_path / "m.cpp").write_text(TREE, encoding="utf-8")
    st = Store(tmp_path / "g.db")
    analyze_tree(tmp_path, st)
    yield st
    st.close()


def _page(store: Store, out: Path, render) -> str:
    return render(store, out, "p", Stamp.of(store)).read_text(encoding="utf-8")


def test_the_report_leads_with_what_reaches_something(store):
    rows = macro_report(store)["definitions"]
    assert rows[0]["name"] == "SEND"
    assert rows[0]["kinds"] == ["NETWORK"] and rows[0]["boundaries"] == 1
    assert rows[0]["statement"] == 1 and rows[0]["uses"] == 1
    many = next(d for d in rows if d["name"] == "MANY")
    assert many["routines_written"] == 2


def test_a_summary_counts_what_it_says_and_its_numbers_open(store):
    report = macro_report(store)
    s = report["summary"]
    assert s["routines_written"] == 3 and s["routines"] == 4
    # Rule 13: the number beside a definition is the rows behind it.
    send = next(d for d in report["definitions"] if d["name"] == "SEND")
    places = macro_places(store, send["id"])
    assert len(places["uses"]) == send["uses"]
    assert [b["evidence"] for b in places["boundaries"]] == ["connect"]
    assert [c["callee"] for c in places["callees"]] == ["connect"]


def test_what_was_not_read_is_said_and_is_not_called_absent(store, tmp_path):
    report = macro_report(store)
    assert report["unread"]["lines"] > 0
    assert report["unread"]["headers"] == [{"header": "not_here.h", "files": 1}]
    page = _page(store, tmp_path, render_macros)
    assert "not read, rather than absent" in page
    assert "`not_here.h`" in page
    assert "in `#if` arms this configuration does not take" in page
    assert "One hop" in page


def test_the_page_leads_with_what_leaves(store, tmp_path):
    page = _page(store, tmp_path, render_macros)
    assert "What leaves the program through a macro" in page
    assert page.index("`SEND`") < page.index("`NOTHING`")
    assert "3 are written by macros" in page


def test_routines_fold_to_one_row_per_definition_and_a_way_in_never_does(store, tmp_path):
    page = _page(store, tmp_path, _routines)
    assert "2 written by `MANY`" in page
    assert "`tree_a`" not in page and "`tree_b`" not in page
    # `main` is written by a macro and is what somebody came for.
    assert "`main`" in page
    assert "`hand`" in page
    assert "4, 2 written by macros" in page


def test_a_routine_says_who_wrote_it(store):
    from dunneflow.web.detail import written_by

    ids = {r["name"]: r["id"] for r in store.query("SELECT id, name FROM routines")}
    got = written_by(store, ids["tree_a"])
    assert got["body"]["name"] == "MANY" and got["name"]["name"] == "MANY"
    assert got["body"]["file"] == "m.cpp"
    assert written_by(store, ids["hand"]) == {}


def test_a_language_without_macros_has_a_page_that_says_so(tmp_path):
    (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    st = Store(tmp_path / "g.db")
    try:
        analyze_tree(tmp_path, st)
        page = _page(st, tmp_path, render_macros)
    finally:
        st.close()
    assert "that is not a finding" in page
    assert "What this page cannot see" not in page


def test_the_cover_counts_say_how_many_routines_nobody_typed(store, tmp_path):
    from dunneflow.anomalies import detect
    from dunneflow.render.markdown import _overview, ways_in

    page = _overview(store, tmp_path, "p", Stamp.of(store), detect(store),
                     ranked=ways_in(store)).read_text(encoding="utf-8")
    assert "| of which written by macros | 3 |" in page
    counts = store.counts()
    assert counts["routines_by_macro"] == 3
    assert counts["macro_sites"] >= 4


def test_the_diagram_gives_what_a_macro_wrote_one_box_and_a_way_in_stays_itself(store):
    from dunneflow.web.diagram import build as diagram
    from dunneflow.web.graph import build as model

    comps = diagram(model(store, level="routine"), ways={
        r["routine_id"]: ["main"] for r in store.query(
            "SELECT routine_id FROM entrypoints WHERE routine_id IS NOT NULL")})
    boxes = [b for c in comps.values() for b in c.boxes]
    macro = [b for b in boxes if b.kind == "macro"]
    assert [(b.label, b.holds) for b in macro] == [("MANY", 2)]
    assert sorted(macro[0].labels) == ["tree_a", "tree_b"]
    # `main` is written by a macro and is on the same file box as what somebody typed.
    files = [b for b in boxes if b.kind == "file"]
    assert sorted(x for b in files for x in b.labels) == ["hand", "main"]


def test_the_navigator_rows_say_who_wrote_each_routine_and_which_are_ways_in(store):
    from dunneflow.web import queries
    from dunneflow.web.graph import pkg_params

    rows = {r["name"]: dict(r) for r in store.query(
        queries.NAV_ROUTINES, pkg_params(str(Path(store.path).parent)))}
    assert rows["tree_a"]["by_macro"] == "MANY" and not rows["tree_a"]["way_in"]
    assert rows["main"]["by_macro"] == "ENTRY" and rows["main"]["way_in"]
    assert rows["hand"]["by_macro"] == ""


def test_a_macro_box_is_drawn_as_what_it_is_and_counts_what_it_holds(store):
    from dunneflow.web.diagram import build as diagram
    from dunneflow.web.diagram import dot as to_dot
    from dunneflow.web.graph import build as model

    comps = diagram(model(store, level="routine"))
    comp = next(c for c in comps.values() if any(b.kind == "macro" for b in c.boxes))
    dot = to_dot(comp)
    line = next(x for x in dot.splitlines() if 'label="MANY' in x)
    assert "2 functions" in line and "dashed" in line and "cylinder" not in line


def test_a_file_box_is_named_after_the_file_in_any_language(store):
    from dunneflow.web.diagram import build as diagram
    from dunneflow.web.graph import build as model

    comps = diagram(model(store, level="routine"))
    assert {b.label for c in comps.values() for b in c.boxes if b.kind == "file"} == {"m.cpp"}
