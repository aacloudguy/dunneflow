"""The map of one named revision, written from the graph it already has.

A sealed snapshot exists to be readable after its source tree is gone. Until maps were
revision-named that promise was half-kept: the graph and the document store survived under
their own names and the *written map* -- the half a reader who does not write code actually
reads -- went flat into the program directory and was overwritten by the next analysis.
Naming maps fixed it going forward and could not reach backwards, so `output/lictores` was
left holding two sealed graphs and no map of either.

**This is not analysis, and that is the whole of why it is allowed.** Nothing is extracted,
no fingerprint is re-stamped and no store this reads is opened for writing: a graph and a
document store are opened read-only and fifteen Markdown documents are written into a
directory beside them. Rules 25 and 62 are about re-analysing a sealed snapshot in place and
are untouched; rule 20 is satisfied by never writing to the store it reads.

It is possible at all because a map needs neither the source tree nor the documentation
tree -- see the comment in `markdown.py` about the twenty-eight signatures that claimed
otherwise for a month.

**Three things this refuses, each with its own sentence** (design rule 21):

* a revision with no graph here. Its stores were dropped by hand -- the recipe in
  `CLAUDE.md` says to do exactly that -- and there is nothing left to render from.
* a graph whose analysis never finished. It opens perfectly and lies (rule 80), and a map
  written out of one would be a lie with fifteen documents behind it.
* a graph this build cannot read. `Store` refuses a stale one on open and this does not
  catch that to carry on regardless (rule 20).

**And one thing it states rather than refusing.** `standards.db` is one file per program
holding one revision's standard, so rendering an older snapshot finds a standard that is
not about it. Measuring one version's rules against another version's code is rule 70 one
store over -- the same shape as `revision=None` meeting the sidecar's `None` and serving
one version's prose under another's headings. So the standard is withheld from the
comparison and the naming page says which snapshot it does describe, because "no standard
was read" and "a standard is here and it is not this one's" are different answers that look
identical on a blank section.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from .. import revisions
from ..docstore import DocStore
from ..store import StaleGraphError, Store, unfinished_sentence
from .index import render_index
from .markdown import FULL, InventoryCost, render_all


@dataclass
class Rendered:
    """What one attempt produced: a map, or the sentence saying why not."""

    revision: str
    program: str = ""
    map_dir: Path | None = None
    files: list[Path] = field(default_factory=list)
    rewritten: bool = False
    refusal: str = ""
    notes: list[str] = field(default_factory=list)


def mapless(out_dir: Path) -> list[str]:
    """Every revision in this directory that has a graph and no map, newest first.

    The default population, because it is the job this was built for: a directory whose
    maps were overwritten before they had names, opened and given back what it lost. A
    revision that already has a map is left alone unless it is named, so running this
    twice writes nothing the second time.
    """
    graphs = {
        rev for p in revisions.known(out_dir, revisions.GRAPH)
        if (rev := revisions.revision_of(p))
    }
    return sorted(graphs - set(revisions.known_maps(out_dir)), reverse=True)


def _standard_for(out_dir: Path, revision: str) -> tuple[DocStore | None, str]:
    """The standard this snapshot was measured against, or the sentence saying it is not.

    `standards.db` records one revision, and the comparison it feeds is the only section of
    the naming page that puts a number beside a quotation. Handing it a standard captured
    against a different snapshot would produce exactly the confident wrong answer the
    population rule was written to prevent -- so the page is told, in the section where the
    comparison would have been.
    """
    path = out_dir / "standards.db"
    if not path.exists():
        return None, ""
    try:
        store = DocStore(path, writable=False)
    except OSError:
        return None, ""
    held = store.get_meta("revision") or ""
    if held == revision:
        return store, ""
    store.close()
    # Rule 89's shape, with the honest amount to say: there is no command that can make a
    # sealed snapshot's standard exist -- re-analysing it is what rules 25 and 62 forbid --
    # so what is named is the map that *does* carry the comparison.
    which = f"`{held}`" if held else "an unrecorded revision"
    # **It says what is held out, never that nothing is checked.** The section below still
    # checks the rules this program's *own* documents state -- those travel in `docs@<rev>`
    # and are this snapshot's -- so a sentence reading "nothing here is checked" would
    # contradict the verdicts printed under it (rule 13).
    return None, (
        "> **A naming standard is present in this program directory and it is not this "
        f"snapshot's.** `standards.db` was captured against {which}; this map describes "
        f"`{revision}`. Its rules are held out of the comparison below, because measuring "
        "one version's rules against another version's code would put a number beside a "
        "quotation that was never about it. What *is* checked below comes from this "
        f"program's own documents, which are this snapshot's. The map of {which} is the "
        "one whose naming page checks the outside standard as well."
    )


def render_snapshot(out_dir: Path, revision: str, *,
                    include_tests: bool = False,
                    inventory: str = FULL,
                    choose: Callable[[InventoryCost], str] | None = None) -> Rendered:
    """Write `map@<revision>/` from the stores this directory already holds.

    Everything is opened **read-only**. `Store` refuses a stale graph on open and that
    refusal is passed on rather than caught: a read may refuse, but it may never repair.
    """
    out = Rendered(revision=revision)
    graph = revisions.db_path(out_dir, revisions.GRAPH, revision)
    if not graph.exists():
        out.refusal = (
            f"no graph for {revision} in {out_dir} — its stores were removed, and a map "
            f"cannot be written from a snapshot that is not here"
        )
        return out

    try:
        store = Store(graph, writable=False)
    except StaleGraphError as exc:
        out.refusal = str(exc)
        return out

    if store.finished() == "":
        # Read before anything closes, for `_open_store`'s reason: `check` once died on a
        # closed connection while explaining why it was refusing.
        said = unfinished_sentence(store.get_meta("program") or out_dir.name,
                                   store.get_meta("step") or "")
        store.close()
        out.refusal = said
        return out

    program = store.get_meta("program") or out_dir.name
    out.program = program
    doc_path = revisions.db_path(out_dir, revisions.DOCS, revision)
    # **Named, never newest.** A document store resolved by falling back to the newest is
    # rule 70 exactly: one version's prose under another version's headings, and nothing on
    # the page to say so.
    doc_store: DocStore | None = None
    if doc_path.exists():
        try:
            doc_store = DocStore(doc_path, writable=False)
        except OSError as exc:
            out.notes.append(f"the document store for {revision} could not be read: {exc}")
    else:
        out.notes.append(
            f"no document store for {revision} — analysed with `--no-docs`, or its "
            f"`docs@` file was removed; the four documentation pages say so themselves")

    standards, note = _standard_for(out_dir, revision)
    if note:
        out.notes.append("its naming standard describes another snapshot, and the naming "
                         "page says so")

    map_out = revisions.map_dir(out_dir, revision)
    out.rewritten = map_out.exists()
    try:
        store.warm()
        out.files = render_all(store, map_out, program,
                               include_tests=include_tests,
                               docs=doc_store, standards=standards,
                               standards_note=note,
                               inventory=inventory, choose=choose)
        out.map_dir = map_out
    finally:
        store.close()
        if doc_store is not None:
            doc_store.close()
        if standards is not None:
            standards.close()
    return out


def render_maps(out_dir: Path, wanted: Iterable[str] | None = None, *,
                include_tests: bool = False,
                inventory: str = FULL,
                choose: Callable[[InventoryCost], str] | None = None,
                rows: Iterable[dict] = (),
                emit: Callable[[str], None] | None = None) -> list[Rendered]:
    """Render the named revisions, or every one that has a graph and no map.

    The listing is rewritten once at the end rather than after each map, because it is one
    statement about the whole directory and writing it five times would be five readings of
    the same disk (rule 51's shape, one file over).
    """
    say = emit or (lambda _: None)
    chosen = list(wanted) if wanted is not None else mapless(out_dir)
    if not chosen:
        # Design rule 21: an empty run says which empty it is. "Every revision here already
        # has a map" and "there is nothing here" are different answers.
        graphs = revisions.known(out_dir, revisions.GRAPH)
        say("nothing to render: every revision in this directory already has a map"
            if graphs else f"nothing to render: no graph in {out_dir}")
        return []

    done: list[Rendered] = []
    for rev in chosen:
        r = render_snapshot(out_dir, rev, include_tests=include_tests,
                            inventory=inventory, choose=choose)
        done.append(r)
        if r.refusal:
            say(f"{rev}: refused — {r.refusal}")
            continue
        verb = "rewrote" if r.rewritten else "wrote"
        say(f"{rev}: {verb} {len(r.files)} documents to {r.map_dir}")
        for n in r.notes:
            say(f"        {n}")

    if any(r.map_dir for r in done):
        index = render_index(out_dir, _program_of(done, out_dir), rows=list(rows))
        say(f"{index} lists this directory's maps")
    return done


def _program_of(done: list[Rendered], out_dir: Path) -> str:
    """The program the listing is titled with.

    The graph's own answer, carried back by the render that read it, rather than the
    directory's name: a name is a convenience and the file is the authority (rule 30). It
    is asked of a map that was actually written, so a directory of refusals falls back to
    the name rather than opening a second handle to say the same thing (rule 58).
    """
    for r in done:
        if r.map_dir is not None and r.program:
            return r.program
    return out_dir.name
