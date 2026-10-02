"""Guards for the dashboard fixes made from the 2026-10-02 retake's BACKLOG items.

Source-reading guards in `test_web_controls.py`'s idiom, and over its helpers, so a span
means the same thing here as there: `_fn` by brace depth, `_code` with comment lines
removed, because a comment naming the fix is not the fix (rule 37).
"""

from __future__ import annotations

import re

from tests.test_web_controls import _code, _fn, _read


def test_the_boundaries_note_counts_the_kinds_it_lists():
    """BACKLOG 18(a): "the nine kinds" sat over a list of seven."""
    js = _code(_read("shell.js"))
    assert "nine kinds" not in js
    assert "${BOUNDARIES.length} kind" in js


def test_the_change_group_lists_every_band_its_badge_counts():
    """BACKLOG 18(e): the badge counted the structure bands and the group listed none."""
    js = _read("shell.js")
    count, listed = _code(_fn(js, "changeCount")), _code(_fn(js, "changeList"))
    for spec in ("CHANGE_FILE_BANDS", "CHANGE_STRUCT_BANDS"):
        assert spec in count and spec in listed, spec
    # And the one band listed but not counted says so in its own title.
    assert "not in the count" in listed


def test_both_document_counts_say_which_documents():
    """BACKLOG 18(d): 52 on the glossary and 53 on the stated page, a click apart."""
    js = _code(_read("shell.js"))
    assert "distinct document" in js
    assert re.search(r"byte-identical\s+copy of another", js)


def test_the_versions_are_asked_for_with_the_cover_not_after_it():
    """BACKLOG 18(f): `/api/revisions` queued behind everything else on a cold open."""
    boot = _code(_fn(_read("shell.js"), "boot"))
    asked, cover = boot.index("loadRevisions()"), boot.index("await loadCover()")
    assert asked < cover, "the versions are requested after the cover"
    assert "await loadRevisions()" not in boot, "a second, serial request was left behind"


def test_a_fit_nobody_has_moved_follows_its_container():
    """BACKLOG 15: the graph arrived framed for a transitional size and stayed that way."""
    engine = _code(_read("graph.js"))
    fit = _fn(engine, "fitView")
    assert "g.fitKept = true" in fit and "g.fitSubset = subset" in fit
    # Cleared by the reader's gesture, which is the one path the controller prop takes.
    assert re.search(r"onViewStateChange: \(p\) => \{ g\.fitKept = false;", engine)
    mount = _fn(engine, "mount")
    assert "new ResizeObserver" in mount and "g.fitKept" in mount
    assert "g.fitSubset" in mount, "a resize would refit the whole stack over a framed selection"


def test_a_revealed_row_is_measured_again_after_the_layout_it_caused():
    """BACKLOG 16: one measurement of a `content-visibility` placeholder sent the row past
    the viewport, from the opening scroll and from Go to it alike."""
    reveal = _code(_fn(_read("shell.js"), "revealSelectedRow"))
    assert "requestAnimationFrame(settle)" in reveal
    assert "row.isConnected" in reveal, "a row the pane has replaced is chased for ever"


def test_the_loading_shell_says_what_it_is_waiting_for():
    """BACKLOG 21: twenty blank seconds on a cold open (design rule 21)."""
    html = _read("index.html")
    mount = html[html.index('id="viewMount"'):]
    assert 'id="bootNote"' in mount[:300], "the view mount starts empty again"
    boot = _code(_fn(_read("shell.js"), "boot"))
    assert boot.count("bootSay(") >= 2


def test_every_door_into_a_severity_moves_the_navigator_and_the_trail():
    """BACKLOG 22: the tab inside the page moved the view and told neither."""
    js = _code(_read("shell.js"))
    tab = js.split('$$("[data-sev]")', 1)[1][:300]
    cover = js.split('$$("[data-gosev]")', 1)[1][:300]
    for door in (tab, cover):
        assert "openSeverity(" in door and "pushTrail(" in door and "buildNav()" in door
    assert re.search(r"current: state\.view === \"anomalies\" && state\.sev === k", js)


def test_a_boundary_step_is_named_by_its_kind_and_target():
    """BACKLOG 23: the trail read `bnd:NETWO…`, a key."""
    label = _code(_fn(_read("shell.js"), "labelFor"))
    assert "bnd:" in label and "unnamed" in label


def test_the_trail_counts_the_steps_it_has_scrolled_away():
    """BACKLOG 27: steps off the left of a scrolled bar were neither shown nor counted."""
    js = _read("shell.js")
    edges = _code(_fn(js, "countTrailEdges"))
    assert "getBoundingClientRect" in edges and "dataset.window" in edges
    paint = _code(js).split('const tm = $("#trailMount");', 1)[1][:900]
    assert "countTrailEdges(tm)" in paint and '"scroll"' in paint


def test_the_code_note_is_about_the_file_it_names():
    """BACKLOG 28: "357 lines" of the last file, under the next selection."""
    js = _read("shell.js")
    follow = _code(_fn(js, "followSelectionIntoCode"))
    files_first = follow.index("if (!FILES.length) return;")
    assert files_first < follow.index("codeFollowedFor = inspectorFor")
    note = _code(_fn(js, "codeNote"))
    assert "CODEFILE.file !== state.codeFile" in note


def test_a_worklist_step_carries_its_severity():
    """BACKLOG 22, as found by pointer: Suspect then Informational is one view and one
    selection, so the second step was folded into the first and Back could not return."""
    js = _read("shell.js")
    rec = _code(_fn(js, "recordSelection"))
    assert "sev:" in rec and "(at.sev || \"\") === step.sev" in rec
    assert "state.sev = step.sev" in _code(_fn(js, "goToTrailStep"))


def test_the_document_renders_the_group_it_measures():
    """BACKLOG 16, as found by pointer: a row in a skipped `content-visibility` group reports
    a stale position, so the reveal aimed at a ghost."""
    reveal = _code(_fn(_read("shell.js"), "revealSelectedRow"))
    assert reveal.index('contentVisibility = "visible"') < reveal.index("getBoundingClientRect")


def test_the_centre_fits_the_window_the_docs_are_taken_at():
    """BACKLOG 19, measured at 1,483 px: a 795 px centre, a 1,088 px table, 943 px of tabs."""
    js, css = _read("shell.js"), _read("tokens.css")
    widths = re.search(r"colWidths: \{ q: (\d+), why: (\d+), fan: (\d+), chg: (\d+) \}", js)
    assert widths and sum(map(int, widths.groups())) <= 47
    assert re.search(r"\.seg\.tabs \{[^}]*flex-wrap: wrap", css)
    adopt = _code(_fn(js, "adoptSettings"))
    assert "OLD_DEFAULT_COLS" in adopt, "a reader who never dragged a column keeps 68rem"
    folds = _code(_fn(js, "narrowFolds"))
    assert 'folds.add("legend")' in folds and "PLATES_FOLD_REM" in folds
    assert re.search(r"const paneHeld = \{[^}]*legend: false", js)



def test_a_table_repaint_keeps_the_scroll_of_the_element_that_scrolls():
    """Found retaking the tutorial: the reveal scrolled to the selection, the CHANGES
    overlay's repaint rebuilt `.tablewrap` at row 1, and the row was already marked revealed.
    Only `#viewMount`'s scroll was kept, and it is not the one that scrolls."""
    js = _read("shell.js")
    i = js.index("vp.innerHTML = viewTable();")
    block = _code(js[i - 900:i + 400])
    assert 'const was = vp.querySelector(".tablewrap")' in block
    assert "[wrap.scrollTop, wrap.scrollLeft] = kept" in block
    assert block.index("= kept") < block.index("revealSelectedRow(false)")


def test_an_opened_box_keeps_each_code_button_on_one_line():
    """Found retaking the guide: a long signature squeezed `code ▸` onto two lines and pushed
    the line number under it, on every HOLDS row of an opened box."""
    js = _read("shell.js")
    i = js.index('class="dim holds-at"')
    assert "flex:none;white-space:nowrap" in js[i:i + 120]


def test_the_navigator_is_repainted_once_the_stack_is_mounted():
    """Found retaking the guide: the fan counts are blank until the engine is mounted, and
    nothing rebuilt the navigator when it was."""
    body = _code(_fn(_read("shell.js"), "ensureGraph"))
    assert body.index("Graph.mount(") < body.rindex("buildNav()")


def test_a_usage_key_wraps_inside_its_own_column():
    """Found retaking the guide: `Naming:Underscore:Allowed` ran under the bar's dot."""
    js, css = _read("shell.js"), _read("tokens.css")
    assert '.split(":").join(":<wbr>")' in js
    assert re.search(r"\.usagebar \.usagekey \{[^}]*overflow-wrap: anywhere", css)


def test_a_picked_box_counts_as_a_selection_without_the_stack():
    """Found retaking the tutorial: straight to Diagram, pick a box, open it, and the note
    saying you are inside what you picked was wiped, because nothing mounted the stack."""
    mark = _code(_fn(_read("shell.js"), "markDiagramSelection"))
    assert "dgmSelectionNote(marked, want.size > 0 || !!state.fold)" in mark


def test_arriving_at_a_pane_forgets_the_row_it_last_revealed():
    """Found retaking the docs: leave Table and come back on the same selection, and the
    rebuilt table sat at row one -- the row had been 'revealed' a visit ago."""
    body = _code(_fn(_read("shell.js"), "render"))
    i = body.index("state.view !== lastDrawnView")
    block = body[i:i + 300]
    assert 'lastRevealedRow.row = null' in block
    assert 'lastRevealedRow.docrow = null' in block
    assert body.index("lastDrawnView = state.view") < body.index("revealSelectedRow(false)")
