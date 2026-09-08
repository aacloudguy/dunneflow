"""A map belongs to a revision, and a second analysis must not write over the first's.

The databases have been revision-named since the temporal spine went in. The **written
map** was not: fifteen documents went flat into the program directory, so analysing a
second point in time overwrote the first one's. Nothing broke on screen, because the
dashboard reads the databases -- which is exactly why it stood on the owed list for eight
days. What it cost is the half of a sealed snapshot a reader actually reads: `CLAUDE.md`
says a sealed snapshot exists *"so it can be read after its source tree is gone"*, and its
graph survived while its documents did not.

These are about the layout and about what the index says, and the sharpest of them is not
about either: a map is a directory of Markdown **inside the output tree**, and the corpus
walk must go on refusing to read it (rule 57). That defect once had this tool claiming 942
naming rules mined from its own reports about a different program.
"""

from __future__ import annotations

import time
from pathlib import Path

from dunneflow import revisions
from dunneflow.cli import build_parser, cmd_analyze
from dunneflow.render.index import legacy_map_files, render_index

TINY = '''\
"""A program with something to map."""
import sqlite3


def open_it(path):
    """Open the database."""
    return sqlite3.connect(path)
'''


def _tree(tmp_path: Path) -> Path:
    tree = tmp_path / "src"
    tree.mkdir()
    (tree / "m.py").write_text(TINY, encoding="utf-8")
    (tree / "README.md").write_text(
        "# The program\n\nIt opens a database.\n", encoding="utf-8")
    return tree


def _analyse(tree: Path, out: Path, *extra: str) -> int:
    args = build_parser().parse_args(
        ["analyze", str(tree), "--name", "prog", "--output", str(out), "--quiet", *extra])
    return cmd_analyze(args)


def test_a_second_analysis_writes_a_second_map(tmp_path):
    """The whole item, and the shape of the promise that was half-kept.

    Sealing is what makes a second revision exist -- `open_working` reuses the one that is
    already open, so analysing twice without sealing rewrites one snapshot by design. With
    a seal between them there are two, and *both* maps have to be on disk afterwards.
    """
    tree = _tree(tmp_path)
    out = tmp_path / "out"
    assert _analyse(tree, out) == 0
    prog = out / "prog"

    first = revisions.known_maps(prog)
    assert len(first) == 1, f"the first analysis wrote {len(first)} maps: {first}"
    (rev_one, map_one), = first.items()
    assert (map_one / "01-entrypoints.md").exists(), "the map is not in its own directory"
    assert not (prog / "01-entrypoints.md").exists(), (
        "the map is still being written flat into the program directory, which is what a "
        "second analysis overwrites"
    )
    body_one = (map_one / "03-routines.md").read_text(encoding="utf-8")

    from dunneflow.sourcedb import SourceStore
    source = SourceStore(prog / "source.db")
    source.seal(label="the first one")
    source.commit()
    source.close()

    # A revision is identified to the second, and `_free_revision_id` disambiguates a
    # collision with `#2`. Both analyses landing in one second is a different test from
    # this one, so this waits rather than asserting against whichever it got.
    time.sleep(1.1)
    (tree / "second.py").write_text("def later():\n    return 1\n", encoding="utf-8")
    assert _analyse(tree, out) == 0

    maps = revisions.known_maps(prog)
    assert len(maps) == 2, f"the second analysis did not write a second map: {maps}"
    assert rev_one in maps, "the sealed revision's map is gone"
    assert (map_one / "03-routines.md").read_text(encoding="utf-8") == body_one, (
        "the sealed revision's map was rewritten by an analysis of a later one"
    )
    assert "later" not in body_one, "this test is blind -- the two maps are the same map"
    newer = maps[max(maps)]
    assert "later" in (newer / "03-routines.md").read_text(encoding="utf-8"), (
        "the newer map does not describe the newer tree"
    )


def test_the_index_names_every_revision_and_where_its_map_is(tmp_path):
    """`README.md` at the program root is the listing, and it is built from the disk.

    Every revision the directory knows about, its state, and a link into its map -- so a
    handed-over directory opens on a sentence rather than on a heap of `map@…` names.
    """
    tree = _tree(tmp_path)
    out = tmp_path / "out"
    assert _analyse(tree, out) == 0
    prog = out / "prog"

    from dunneflow.sourcedb import SourceStore
    source = SourceStore(prog / "source.db")
    source.seal(label="Society at the start")
    source.commit()
    source.close()
    # A revision is identified to the second, and `_free_revision_id` disambiguates a
    # collision with `#2`. Both analyses landing in one second is a different test from
    # this one, so this waits rather than asserting against whichever it got.
    time.sleep(1.1)
    (tree / "second.py").write_text("def later():\n    return 1\n", encoding="utf-8")
    assert _analyse(tree, out) == 0

    index = (prog / "README.md").read_text(encoding="utf-8")
    for rev, where in revisions.known_maps(prog).items():
        assert rev in index, f"the index does not name revision {rev}"
        assert f"({where.name}/README.md)" in index, (
            f"the index names {rev} and does not link to its map"
        )
    assert "Society at the start" in index, (
        "a sealed revision's label is the one thing telling a reader what it is, and the "
        "index drops it"
    )
    from dunneflow.sourcedb import STATE_FOR_COMPARISON, STATE_WORKING
    assert STATE_WORKING in index and STATE_FOR_COMPARISON in index, (
        "the index states no revision's state, so nothing says which snapshot is current "
        "and which is being held against it"
    )


def test_a_revision_with_no_map_says_so_rather_than_showing_a_blank(tmp_path):
    """Design rule 21, and rule 32's neighbour: an empty cell is not an answer.

    `--no-render` writes a graph and no map, which is also the shape of every revision
    analysed before this layout existed. The row has to say which of those it is rather
    than leave a reader to guess that the map failed.
    """
    tree = _tree(tmp_path)
    out = tmp_path / "out"
    assert _analyse(tree, out, "--no-render") == 0
    prog = out / "prog"
    assert not revisions.known_maps(prog), "--no-render wrote a map"

    index = render_index(prog, "prog")
    text = index.read_text(encoding="utf-8")
    graph = revisions.newest(prog, revisions.GRAPH)
    assert graph is not None, "--no-render wrote no graph either"
    rev = revisions.revision_of(graph)
    assert rev and rev in text, "a revision with no map is missing from the listing"
    assert "not written" in text, (
        "the row for a revision with no map is blank, which reads as a map that failed "
        "rather than one nobody asked for"
    )


def test_the_older_flat_map_is_named_and_left_alone(tmp_path):
    """It is a real map of a revision nothing records, so the reader decides its fate.

    Recognising it costs one `exists()` and reporting it costs a section. Deleting it would
    be this tool tidying away a reader's documents to make its own listing neat, and there
    is nothing in any of the fifteen files that says which revision they describe -- not in
    the text and not in the names (rule 30, with not even a name to go on).
    """
    prog = tmp_path / "prog"
    prog.mkdir()
    for name in ("01-entrypoints.md", "03-routines.md", "09-anomalies.md"):
        (prog / name).write_text(f"# old {name}\n", encoding="utf-8")
    (prog / "README.md").write_text("# an old overview\n", encoding="utf-8")

    assert legacy_map_files(prog) == ["01-entrypoints.md", "03-routines.md",
                                      "09-anomalies.md"], (
        "the older map is not recognised, or `README.md` is being counted as one of its "
        "documents -- it is the file the index itself writes"
    )
    render_index(prog, "prog")
    text = (prog / "README.md").read_text(encoding="utf-8")
    for name in ("01-entrypoints.md", "03-routines.md", "09-anomalies.md"):
        assert name in text, f"the index does not name the leftover {name}"
        assert (prog / name).exists(), f"the index deleted {name}"
    assert "not recorded" in text, (
        "the index files the older map under some revision, which it cannot know"
    )


def test_a_map_is_not_read_as_documentation(tmp_path):
    """Rule 57, one directory deeper than it was minted.

    A map is fifteen Markdown documents written **inside the output tree**, and the corpus
    walk prunes by directory: `analyze` passes the program directory in `exclude`, so
    everything beneath it goes -- the new `map@…/` included. This asserts that rather than
    trusting it, because the same mistake once had DunneFlow reading 46 of 54 documents out
    of its own `output/` and claiming all 942 naming rules it found in them.

    Driven through a **second** analysis, which is the only run where a map already exists
    on disk while the corpus is being scanned.
    """
    tree = _tree(tmp_path)
    out = tmp_path / "out"
    assert _analyse(tree, out) == 0
    prog = out / "prog"
    (map_one,) = revisions.known_maps(prog).values()
    assert (map_one / "03-routines.md").exists(), "there is no map to be misread"

    assert _analyse(tree, out) == 0

    from dunneflow.docstore import DocStore
    doc_db = revisions.newest(prog, revisions.DOCS)
    assert doc_db is not None, "no document store was written"
    docs = DocStore(doc_db, writable=False)
    try:
        paths = {r["path"] for r in docs.conn.execute("SELECT path FROM documents")}
    finally:
        docs.close()
    assert paths, "no documents were read at all, so this test proves nothing"
    offenders = sorted(p for p in paths if "01-entrypoints" in p or "map@" in p
                       or "03-routines" in p)
    assert not offenders, (
        f"the corpus read the map back in as documentation: {offenders} -- a program's own "
        "output is not evidence about the program (rule 57)"
    )


def test_the_walk_prunes_the_output_directory_it_is_writing_into(tmp_path):
    """The mechanism behind the test above, asserted where it can be seen directly.

    `discover_docs` prunes an excluded directory out of `dirnames`, so excluding a program
    directory excludes everything beneath it. That is what makes a map safe *without* the
    exclusion list having to learn a new name -- and it is worth one test, because the
    alternative reading (exclude matches only the directory itself) is equally plausible
    from the call site and would let every map be read as prose.
    """
    from dunneflow.walk import discover_docs

    root = tmp_path
    prog = root / "out" / "prog"
    (prog / "map@2026-01-01T00-00-00Z").mkdir(parents=True)
    (prog / "map@2026-01-01T00-00-00Z" / "01-entrypoints.md").write_text("# generated\n")
    (root / "README.md").write_text("# real prose\n")

    found = {p.relative_to(root).as_posix()
             for p in discover_docs(root, exclude=frozenset({prog}))}
    assert found == {"README.md"}, (
        f"excluding a program directory did not prune what is under it: {sorted(found)}"
    )
