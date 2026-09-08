"""What a program directory holds, and which map describes which point in time.

The fifteen documents of a map used to be written flat into the program directory, so a
second analysis wrote over the first one's map. The databases never had that problem --
they are revision-named, and a sealed snapshot exists precisely so it can be read after
its source tree is gone -- which left the promise half-kept: the graph survived and the
*written map*, the thing the reader this tool is for actually reads, did not.

Maps are `map@<revision>/` now. That makes the program directory a list of points in time
rather than a map, and this is the sentence that says so: what is here, which revision each
one describes, and what state that revision is in.

**It states an absence rather than leaving one** (design rule 1, and design rule 21 one
surface over). Three of them, and they are different answers with different things to do
about each:

* a revision whose map was never written -- `--no-render`, or an analysis that predates
  this layout. The graph is there and the map is not; re-rendering it is not something
  this tool offers yet, and saying so beats an empty cell.
* a map on disk for a revision no graph in this directory claims. A snapshot whose stores
  were dropped by hand -- the recipe in `CLAUDE.md` says to do exactly that -- and its map
  is a real document about a version nothing here can answer questions about.
* the older flat map, still lying in the program directory. It is left where it is: it is
  a real map of *some* revision, and which one is not recorded anywhere in it (rule 30 --
  a name is not an identity, and here there is not even a name). Deleting a reader's
  documents to tidy up a listing is not this tool's decision.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .. import revisions
from .markdown import _stamp

# The map's own first document. Its presence directly in the program directory is what
# says an older, un-named map is lying there -- `README.md` is not, because this file
# writes that one.
LEGACY_MARKER = "01-entrypoints.md"


def legacy_map_files(out_dir: Path) -> list[str]:
    """The flat map left over from before maps were revision-named, if there is one.

    Recognised by `01-entrypoints.md` and reported whole, because half a list is a worse
    answer than none: a reader deciding whether to delete these needs to see all of them.
    """
    if not (out_dir / LEGACY_MARKER).exists():
        return []
    return sorted(p.name for p in out_dir.glob("*.md") if p.name != "README.md")


def render_index(out_dir: Path, program: str, stamp: str | None = None,
                 rows: Sequence[Mapping[str, Any]] = ()) -> Path:
    """Write `README.md`: every revision in this directory and where its map is.

    `rows` are `SourceStore.revisions()` -- state, label, capture instant, file count. They
    are the sidecar's answer and this asks for nothing else: a directory analysed with
    `--no-source` has none, and the listing is then what the filenames say and no more,
    which is the honest amount.

    Built from what is **on disk** rather than from what this run wrote, so a map written
    by an earlier build, and a revision whose stores someone removed by hand, both appear.
    """
    stamp = stamp or _stamp()
    graphs = {}
    for p in revisions.known(out_dir, revisions.GRAPH):
        graphs[revisions.revision_of(p)] = p
    legacy_graph = out_dir / f"{revisions.GRAPH}.db"
    if legacy_graph.exists():
        graphs.setdefault(None, legacy_graph)
    maps = revisions.known_maps(out_dir)
    said = {r["revision"]: r for r in rows}

    # Newest first, and every revision anything here knows about -- a map with no graph is
    # as much a row as a graph with no map. `None` is the legacy bare `graph.db`, which
    # sorts last because it has no instant to sort by.
    named = sorted({r for r in (set(graphs) | set(maps)) if r}, reverse=True)
    order: list[str | None] = [*named]
    if None in graphs:
        order.append(None)

    lines = [
        f"# {program} — the maps in this directory\n",
        f"*Written {stamp} by DunneFlow.*\n",
        "Each analysis writes its map into a directory of its own, named for the revision "
        "it describes, so a second analysis never writes over the first one's. Open the "
        "`README.md` inside a map to start reading it.\n",
    ]

    if not order:
        # Design rule 21: a blank listing says why it is blank. Reaching here means the
        # directory holds neither a graph nor a map, which is a directory nothing has
        # analysed into yet -- not an empty program.
        lines.append("Nothing has been analysed into this directory yet.\n")
    else:
        lines.append("| Revision | State | Captured | Files | Map |")
        lines.append("|---|---|---|---:|---|")
        for rev in order:
            said_row = said.get(rev) if rev else None
            state = str(said_row["state"]) if said_row else "—"
            captured = (str(said_row["captured_at"]) or "—") if said_row else "—"
            files = f"{said_row['files']:,}" if said_row else "—"
            where = maps.get(rev) if rev else None
            if where is not None:
                cell = f"[`{where.name}/`]({where.name}/README.md)"
            elif rev in graphs:
                cell = "*not written — `--no-render`, or analysed before maps were named*"
            else:
                cell = "*no graph here — its stores were removed*"
            label = str(said_row["label"]) if said_row and said_row["label"] else ""
            name = f"`{rev}`" if rev else "*un-named — a map from before revisions*"
            lines.append(f"| {name} | {state} | {captured} | {files} | {cell} |")
            if label:
                lines.append(f"| | | | | “{label}” |")
        lines.append("")

    legacy = legacy_map_files(out_dir)
    if legacy:
        lines.append("## An older map, still here\n")
        lines.append(
            f"{len(legacy)} documents were written into this directory before maps were "
            "revision-named. **Which revision they describe is not recorded** — not in "
            "their text and not in their names — so they are left where they are rather "
            "than filed under a revision this file would have to guess. Delete them when "
            "you no longer want them.\n"
        )
        for name in legacy:
            lines.append(f"- `{name}`")
        lines.append("")

    path = out_dir / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
