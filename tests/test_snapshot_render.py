"""Rendering the map of a snapshot from the graph it already has.

The feature exists because a sealed snapshot kept its graph and lost its map, and the
promise a sealed snapshot makes -- *readable after its source tree is gone* -- is about the
half a reader who does not write code actually reads. So the tests that matter here are not
"did fifteen files appear": they are about the four ways this could quietly say something
untrue.

* **It must not be analysis.** Every store it opens is opened read-only, and nothing it
  reads may be different afterwards. That is rules 25, 62 and 20 in one assertion.
* **It must not borrow another snapshot's inputs.** A document store resolved by falling
  back to the newest is rule 70 exactly, and a standard captured against a different
  revision is the same defect one store over.
* **A refusal must be a refusal.** An unfinished graph opens perfectly and lies (rule 80);
  a map written out of one would be a lie with fifteen documents behind it.
* **The sentence must match the page.** The standards note says what is *held out*, never
  that nothing is checked -- there are verdicts printed directly beneath it (rule 13).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from dunneflow import revisions
from dunneflow.docstore import DocStore
from dunneflow.render.snapshot import mapless, render_maps, render_snapshot
from dunneflow.resolve.calls import resolve_calls
from dunneflow.store import Store
from dunneflow.walk import analyze_tree

MODULE = (
    "import os\n\n\n"
    "def read_it(name: str) -> str:\n"
    "    # AC-1: the one boundary this fixture needs\n"
    "    return os.getenv(name, '')\n"
)

REV_A = "2026-01-01T00:00:00Z"
REV_B = "2026-02-02T00:00:00Z"


def _graph(out_dir: Path, revision: str, tmp_path: Path, *, finished: bool = True) -> Path:
    """A real graph for one revision, written the way `analyze` writes one."""
    tree = tmp_path / f"src{revisions.as_filename(revision)}"
    tree.mkdir(parents=True, exist_ok=True)
    (tree / "reader.py").write_text(MODULE, encoding="utf-8")
    path = revisions.db_path(out_dir, revisions.GRAPH, revision)
    store = Store(path)
    store.set_meta("revision", revision)
    store.set_meta("program", "fixture")
    store.set_meta("analysed_at", "2026-01-01 00:00 UTC")
    store.set_meta("complete", "")
    store.set_meta("step", "resolving calls")
    analyze_tree(tree, store)
    resolve_calls(store)
    if finished:
        store.set_meta("complete", "yes")
    store.close()
    return path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_snapshot_gets_its_map_and_the_graph_is_untouched(tmp_path: Path) -> None:
    """The whole feature, and the reason it is allowed to exist.

    Writing a map must leave every store it read byte-identical. That is what separates
    this from analysis, and it is the assertion rules 25 and 62 are actually about.
    """
    out_dir = tmp_path / "prog"
    graph = _graph(out_dir, REV_A, tmp_path)
    before = _digest(graph)

    r = render_snapshot(out_dir, REV_A)

    assert not r.refusal, r.refusal
    assert r.map_dir == revisions.map_dir(out_dir, REV_A)
    # Thirteen rather than fifteen, and the two absences are the renderers' own rule:
    # `render_database` and `render_network` return `None` where a program touches neither,
    # and this fixture touches neither. Naming the thirteen rather than counting them, so a
    # renderer that silently stopped writing one is caught rather than absorbed.
    assert {f.name for f in r.files} == {
        "README.md", "01-entrypoints.md", "02-flows.md", "03-routines.md", "04-data.md",
        "05-boundaries.md", "06-governance.md", "09-anomalies.md", "10-glossary.md",
        "11-naming.md", "12-traceability.md", "13-mirror.md", "14-constants.md",
    }, f"got {sorted(f.name for f in r.files)}"
    assert _digest(graph) == before, \
        "rendering a map read the graph and must not have changed one byte of it"


def test_every_page_states_the_snapshot_and_both_instants(tmp_path: Path) -> None:
    """`Generated` is not `analysed`, and a re-rendered map is where they come apart.

    **Every page, and that is the assertion.** The cover said this and the other fourteen
    pages said only `Generated <now>`, so a reader arriving at `07-database.md` from a link
    had the whole problem the cover had just solved. It was not fixed in passing because
    eight renderers each built that line inline -- rule 51 -- so this is asserted over the
    *files written*, never over one renderer, because eight copies is exactly how it drifted.
    """
    out_dir = tmp_path / "prog"
    _graph(out_dir, REV_A, tmp_path)
    r = render_snapshot(out_dir, REV_A)

    assert not r.refusal, r.refusal
    for page in r.files:
        text = page.read_text(encoding="utf-8")
        assert f"Snapshot `{REV_A}`" in text, \
            f"{page.name} does not name the snapshot, so its date reads as today's"
        assert "source read 2026-01-01 00:00 UTC" in text, \
            f"{page.name} must carry the graph's own analysis instant, never now"
        assert "these documents written" in text, \
            f"{page.name} must keep the two instants apart -- that is the whole point"


def test_a_map_written_before_a_revision_was_recorded_keeps_its_old_line(
        tmp_path: Path) -> None:
    """Missing and blank are different answers, and neither is a guess (rule 30).

    A graph that predates both keys is a real state. Handing it `Snapshot: unknown` would
    be a claim about a map that never had one; the line it always carried is the fact.
    """
    from dunneflow.render.page import Stamp, header

    undated = Stamp(generated="2026-01-01 00:00 UTC", revision="", analysed="")
    said = header("fixture", "Database", undated)

    assert "*Generated 2026-01-01 00:00 UTC by DunneFlow.*" in said
    assert "Snapshot" not in said, "a map with no revision must not be given one"


def test_a_half_recorded_map_says_which_half_is_missing(tmp_path: Path) -> None:
    """Three states per instant, and the pair does not collapse to two.

    A graph recording a revision but no analysis instant is not the same as one recording
    neither, and answering both with the pre-revision line would lose the revision it does
    have.
    """
    from dunneflow.render.page import Stamp, header

    said = header("fixture", "Database",
                  Stamp(generated="now", revision=REV_A, analysed=""))

    assert f"Snapshot `{REV_A}`" in said
    assert "when that source was read is not recorded" in said
    assert "these documents written now" in said


def test_an_unfinished_graph_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    """Rule 80: a killed analysis leaves a graph that opens perfectly and lies."""
    out_dir = tmp_path / "prog"
    _graph(out_dir, REV_A, tmp_path, finished=False)

    r = render_snapshot(out_dir, REV_A)

    assert r.refusal, "an unfinished graph must be refused"
    assert "never finished" in r.refusal
    assert r.map_dir is None
    assert not revisions.map_dir(out_dir, REV_A).exists(), \
        "a refusal that has already written half a map is not a refusal"


def test_a_revision_with_no_graph_says_so_rather_than_rendering_the_newest(
        tmp_path: Path) -> None:
    """The recipe in `CLAUDE.md` says to drop a superseded snapshot's stores by hand.

    Asking for its map afterwards must name that, not quietly render whichever graph is
    newest -- which is the fallback rule 70 was paid for.
    """
    out_dir = tmp_path / "prog"
    _graph(out_dir, REV_A, tmp_path)

    r = render_snapshot(out_dir, REV_B)

    assert "no graph for" in r.refusal and REV_B in r.refusal
    assert not revisions.map_dir(out_dir, REV_B).exists()


def test_documents_are_read_from_this_revisions_store_and_no_other(
        tmp_path: Path) -> None:
    """A `docs@` store is resolved by name, never by newest.

    Two revisions, and only the newer has a corpus. Rendering the older must report having
    read no documentation rather than serving one snapshot's prose under another's map.
    """
    out_dir = tmp_path / "prog"
    _graph(out_dir, REV_A, tmp_path)
    _graph(out_dir, REV_B, tmp_path)
    docs = DocStore(revisions.db_path(out_dir, revisions.DOCS, REV_B))
    docs.close()

    older = render_snapshot(out_dir, REV_A)

    assert not older.refusal, older.refusal
    assert any("no document store" in n for n in older.notes), \
        f"the absence must be stated, not filled from {REV_B}; got {older.notes}"


def test_a_standard_for_another_snapshot_is_held_out_and_said_so(
        tmp_path: Path) -> None:
    """Rule 70, one store over -- and the sentence must not overstate what it withheld.

    `standards.db` holds one revision. Rendering a different one must keep its rules out of
    the comparison **and** must not claim nothing is checked, because the rules the program's
    own documents state are still checked directly beneath the sentence (rule 13).
    """
    out_dir = tmp_path / "prog"
    _graph(out_dir, REV_A, tmp_path)
    standards = DocStore(out_dir / "standards.db")
    standards.set_meta("revision", REV_B)
    standards.close()

    r = render_snapshot(out_dir, REV_A)
    page = (revisions.map_dir(out_dir, REV_A) / "11-naming.md").read_text(encoding="utf-8")

    assert not r.refusal, r.refusal
    assert REV_B in page and "held out of the comparison" in page, \
        "the page must say which snapshot the standard does describe"
    assert "nothing here is checked" not in page, \
        "the note sits above real verdicts and must not contradict them"


def test_a_standard_for_this_snapshot_is_used_without_a_caveat(tmp_path: Path) -> None:
    """The other half: a matching standard is admitted and says nothing about itself."""
    out_dir = tmp_path / "prog"
    _graph(out_dir, REV_A, tmp_path)
    standards = DocStore(out_dir / "standards.db")
    standards.set_meta("revision", REV_A)
    standards.close()

    render_snapshot(out_dir, REV_A)
    page = (revisions.map_dir(out_dir, REV_A) / "11-naming.md").read_text(encoding="utf-8")

    assert "held out of the comparison" not in page, \
        "a standard captured against this very snapshot is not a caveat"


def test_mapless_is_the_default_population_and_leaves_finished_ones_alone(
        tmp_path: Path) -> None:
    """Running it twice must write nothing the second time.

    The default is *every revision with a graph and no map*, so a re-render is always
    something the reader asked for by name.
    """
    out_dir = tmp_path / "prog"
    _graph(out_dir, REV_A, tmp_path)
    _graph(out_dir, REV_B, tmp_path)

    assert mapless(out_dir) == [REV_B, REV_A], "newest first, and both are mapless"

    said: list[str] = []
    first = render_maps(out_dir, emit=said.append)
    assert [r.revision for r in first] == [REV_B, REV_A]
    assert mapless(out_dir) == [], "both have maps now"

    said.clear()
    second = render_maps(out_dir, emit=said.append)
    assert second == [], "a second run must write nothing"
    assert any("already has a map" in s for s in said), \
        "design rule 21: an empty run says which empty it is"


def test_the_listing_names_the_command_for_a_revision_with_no_map(
        tmp_path: Path) -> None:
    """Rule 89: a refusal names a command that can act on what it is refusing.

    The cell said *"not something this tool offers yet"* until this feature existed, which
    is the sentence a feature has to come back and correct.
    """
    out_dir = tmp_path / "prog"
    _graph(out_dir, REV_A, tmp_path)
    _graph(out_dir, REV_B, tmp_path)

    render_maps(out_dir, [REV_A])
    listing = (out_dir / "README.md").read_text(encoding="utf-8")

    assert "dunneflow render" in listing, \
        f"the mapless revision {REV_B} must be told how to get a map"
    assert f"map@{revisions.as_filename(REV_A)}/" in listing


def test_a_graph_this_build_cannot_read_is_refused_not_repaired(tmp_path: Path) -> None:
    """Rule 20: a read may refuse, but it may never repair.

    `Store` refuses a stale graph on open, and this passes that refusal on rather than
    catching it to render anyway. Re-rendering a map from a graph this build reads
    differently would produce documents that look exactly right.
    """
    out_dir = tmp_path / "prog"
    graph = _graph(out_dir, REV_A, tmp_path)
    stale = Store(graph)
    stale.set_meta("extractor", "0:notthisbuild")
    stale.close()

    r = render_snapshot(out_dir, REV_A)

    assert r.refusal, "a stale graph must be refused"
    assert r.map_dir is None
    assert not revisions.map_dir(out_dir, REV_A).exists()
