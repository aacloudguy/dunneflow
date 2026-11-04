"""The written map.

Seven documents, ordered the way an unfamiliar program is best approached: what it is,
how you get in, what happens then, what the pieces are, what shapes move between them,
what it touches, and what the comments warn you about.

Written for someone who reads code but does not write it, so every table leads with a
name and a type and never assumes a convention is obvious.
"""

from __future__ import annotations

import os
import shutil
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .. import revisions
from ..anomalies import Report, detect
from ..detectors import rules_document
from ..docstore import DocStore
from ..resolve.cli import command_tree
from ..resolve.entrypoints import binding_note
from ..resolve.flows import Flow, boundary_index, trace_flow, ways_in
from ..schema import StructureKind
from ..store import Store
from .anomalies import render_anomalies
from .constants import render_constants
from .database import render_database
from .glossary import render_glossary
from .mermaid import command_tree_diagram, flow_diagram
from .mirror import render_mirror
from .naming import render_naming
from .network import render_network
from .page import Stamp, biggest_first, header
from .traceability import render_traceability

# How the flows page lists what each way in reaches -- the reader's choice, `--flow-inventory`.
FULL, OMITTED, COUNT = "full", "omitted", "count"
INVENTORY_MODES = (FULL, OMITTED, COUNT)

# Diagrams are bounded because a picture of 4,500 nodes conveys nothing; every
# routine a diagram omits is listed in full beneath it. Reference lists are never
# bounded -- completeness is the point of a reference.
MAX_FLOW_DIAGRAM_NODES = 45


def _esc(text: str | None, limit: int | None = None) -> str:
    """Table-safe, and complete.

    Escapes what would break a Markdown table and collapses whitespace. It does not
    truncate: a name cut off mid-way is no longer the name of anything, and a
    reference that omits rows is not a reference. `limit` is accepted so callers read
    unchanged, and ignored.
    """
    if not text:
        return ""
    return " ".join(str(text).split()).replace("|", "\\|")


# There was a `path` here, and in eight other renderers -- nine copies of the
# same four lines, each stripping the analysed root off a stored absolute path so a reader
# would not be shown one machine's directory layout. Paths are stored relative now, so
# every one of them had nothing left to strip.
#
# They were removed rather than left as harmless no-ops, because they were not harmless:
# `Path("mensores/cli.py").resolve()` resolves against the *working directory*, so run from
# anywhere inside the analysed tree the strip would succeed and silently prepend the
# intervening directories to every path on the page.
#
# **The parameters outlived the code by a month**, threaded through twenty-eight functions
# and read by none of them, and a signature that asks for a source root is a claim that one
# is needed. It is not: a map is written from the graph and the document store and nothing
# else, which is exactly what lets `dunneflow render` write the map of a sealed snapshot
# whose source tree is gone. Stating that in the signatures is the point of removing them --
# the alternative was a caller with no tree to name inventing a plausible path, which is
# rule 49 in the shape a type checker cannot see.


# --------------------------------------------------------------------------- #


def render_all(store: Store, out_dir: Path, program: str,
               when: datetime | None = None, include_tests: bool = False,
               docs: DocStore | None = None,
               standards: DocStore | None = None,
               standards_note: str = "",
               report: Report | None = None,
               tick: Callable[[int, int, str], None] | None = None,
               inventory: str = FULL,
               choose: Callable[[InventoryCost], str] | None = None) -> list[Path]:
    """Write the whole map. Returns the files written.

    **`inventory` is the reader's choice of how the flows page lists what each way in
    reaches** -- `full`, `omitted` or `count` (`INVENTORY_MODES`) -- and `choose`, when
    given, is asked with what each would cost before anything is written, and its answer
    wins. The cost is measured, not estimated: every inventory is built once to be sized,
    in the same function that builds it for the page, so the figure stated in the README
    and over the flows page is the number of bytes the page holds (rule 13). On Unreal's
    Runtime the full one is 1.14 GB of a 1.14 GB page.

    `tick(done, total, what)` is called before each document and, inside the flows
    document, per way in -- the document that is 5,705 sections on Unreal's `Runtime`, and
    the one that was silent for most of a fifteen-minute phase.

    **`report` is the anomalies, detected once.** This function called `detect` twice --
    here for `09-anomalies.md` and again inside `_overview` for the headline that points
    at it -- and `cli.py` called it a third time for its own step. Three runs of one
    judgement over one unchanged store, and on `Engine/Binaries` (3,146 files, 71,306
    routines) `detect` is **306 s**: writing the map took 855.6 s and looking for
    anomalies another 306.4 s, which is **94.8% of a 1,226.6 s run** spent deciding the
    same thing three times.

    **And one of the three asked a different question**, which is worth stating exactly
    because it is a hazard today and not yet a defect. `_overview`'s call was plain
    `detect(store)` and so took `include_tests`' default rather than the run's, while the
    other two passed it. Measured rather than assumed: `include_tests` reaches only
    `_dead_code`, where it selects between two **blind-spot sentences** and changes no
    query and no count -- so the README's *"N broken"* and the `09-anomalies.md` it sends
    the reader to have always agreed. What was wrong was the *reason* they agreed, which
    was that the argument happened not to matter; the moment a detector reads it for
    anything a reader can count, the headline and its destination disagree and nothing
    anywhere says so. One report removes the question.

    `None` still detects, because this function is called from places that have no report
    to hand and a renderer that silently wrote no anomalies would be worse than a slow one
    (rule 49).

    **Written beside `out_dir` and renamed into it after the last page** (rule 109). A
    render of Unreal's `Runtime` died in `02-flows.md` and left `README.md` and
    `01-entrypoints.md` in `map@<rev>/` -- a folder with the finished map's name, a cover
    page vouching for it, and thirteen pages missing. Nothing said so, and `dunneflow
    render` counted it as a map and declined to write one. So the pages go into
    `map@<rev>.unfinished/`, which nothing counts, and become `map@<rev>/` in one rename.
    A re-render stages too: a map rewritten in place by a run that dies keeps the old
    pages it had not reached, and they would be read as the new map's.
    """
    final = out_dir
    out_dir = revisions.staging_dir(final)
    if out_dir.exists():
        # What an earlier interrupted run left. Nothing reads it (`known_maps` skips the
        # name), so it is not evidence of anything but that run, and this run replaces it.
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    stamp = Stamp.of(store, when)
    if report is None:
        report = detect(store, include_tests)
    say = tick or (lambda _done, _total, _what: None)
    # **The ways in, ranked once for the three pages that list them** -- the cover, the
    # flows and the network. Each asked for itself, and on Unreal's Runtime one asking is
    # 7.5 s warm and 19.6 s cold: the same 5,730 reach walks, three times (rule 51).
    ranked = ways_in(store)
    index = _Inventory(store)
    cost = inventory_costs(store, ranked, index,
                           tick=lambda i, n: say(i, n, "measuring the flows inventory"))
    if choose is not None:
        inventory = choose(cost)
    if inventory not in INVENTORY_MODES:
        # Refused rather than defaulted: a page written in a mode nobody chose would state
        # a choice nobody made (rule 49).
        raise ValueError(f"no flows inventory called {inventory!r}; "
                         f"the choices are {', '.join(INVENTORY_MODES)}")
    chosen = InventoryChoice(inventory, cost)

    def flows() -> Path:
        return _flows(store, out_dir, program, stamp, ranked=ranked,
                      tick=lambda i, n: say(i, n, "02-flows.md, way in"),
                      index=index, choice=chosen)

    pages: list[Callable[[], Path | None]] = [
        lambda: _overview(store, out_dir, program, stamp, report, ranked=ranked,
                          choice=chosen),
        lambda: _entrypoints(store, out_dir, program, stamp),
        flows,
        lambda: _routines(store, out_dir, program, stamp),
        lambda: _data(store, out_dir, program, stamp),
        lambda: _boundaries(store, out_dir, program, stamp),
        lambda: _governance(store, out_dir, program, stamp),
        lambda: render_database(store, out_dir, program, stamp),
        lambda: render_network(store, out_dir, program, stamp, ranked=ranked),
        lambda: render_anomalies(report, out_dir, program, stamp),
        # Documentation is a parallel input, so its two documents are written whether or
        # not any documentation was found. A glossary that says "nothing defines these
        # eleven words" is a finding; an absent glossary is a silence.
        lambda: render_glossary(store, docs, out_dir, program, stamp),
        lambda: render_naming(store, docs, out_dir, program, stamp,
                              standards=standards, standards_note=standards_note),
        lambda: render_traceability(store, docs, out_dir, program, stamp),
        lambda: render_mirror(store, docs, out_dir, program, stamp),
        lambda: render_constants(store, out_dir, program, stamp),
    ]
    written = []
    for i, page in enumerate(pages):
        say(i, len(pages), "document")
        _mark_unfinished(out_dir, final, i, len(pages), PAGE_NAMES[i])
        written.append(page())
    say(len(pages), len(pages), "document")
    (out_dir / revisions.UNFINISHED_NOTE).unlink()
    # **The swap.** `os.replace` will not put a directory over a non-empty one on any of
    # the three platforms, so the old map is removed first. Between the two statements
    # there is no map of this revision, which is a true statement -- `mapless` offers it
    # again -- where the alternative orders all leave a folder that is not what it says.
    if final.exists():
        shutil.rmtree(final)
    os.replace(out_dir, final)
    return [final / w.name for w in written if w]


# The pages in the order `render_all` writes them, for the note's *which page it stopped
# on*. Positional, so `test_markdown_staging` asserts it is as long as the page list.
PAGE_NAMES = (
    "README.md", "01-entrypoints.md", "02-flows.md", "03-routines.md", "04-data.md",
    "05-boundaries.md", "06-governance.md", "07-database.md", "08-network.md",
    "09-anomalies.md", "10-glossary.md", "11-naming.md", "12-traceability.md",
    "13-mirror.md", "14-constants.md",
)


def _mark_unfinished(staging: Path, final: Path, i: int, n: int, page: str) -> None:
    """Say, inside the folder, that it is not a map yet and how far the writing got.

    Rewritten before each page, so whatever ends the run -- a crash, Ctrl-C, a full disk,
    a `kill -9` -- the folder a person opens says which page it stopped on and what writes
    it again (design rule 21, and rule 89's half about naming a command that can act).
    """
    rev = revisions.revision_of(final)
    again = (f"`dunneflow render {final.parent} --revision {rev}`" if rev
             else f"`dunneflow render {final.parent}`")
    (staging / revisions.UNFINISHED_NOTE).write_text(
        "# This map was never finished\n\n"
        f"Its writing stopped on page {i + 1} of {n}, `{page}`. The pages beside this "
        "note are the ones written before it, and they are part of a map rather than a "
        f"map: a finished one is renamed to `{final.name}/` after its last page, and this "
        f"folder never was.\n\n{again} writes it again from the graph that is already "
        "here, without reading the source.\n",
        encoding="utf-8")


# --------------------------------------------------------------------------- #


def _overview(store: Store, out: Path, program: str, stamp: Stamp,
              rep: Report, ranked: list[dict] | None = None,
              choice: InventoryChoice | None = None) -> Path:
    c = store.counts()
    bi = boundary_index(store)

    if ranked is None:
        ranked = ways_in(store)

    lines = [header(program, "Overview", stamp)]
    lines.append(
        "This is a structural map of what moves through the program: where it starts, "
        "what it runs, and where it touches anything outside itself. Internal "
        "computation and local variables are deliberately not described.\n"
    )
    lines.append("## Size\n")
    lines.append("| Measure | Count |\n|---|---:|")
    for label, key in [
        ("Source files", "files"), ("Routines", "routines"),
        ("Calls between routines", "resolved_calls"), ("Boundary touches", "boundaries"),
        ("Data structures", "structures"), ("Ways in", "entrypoints"),
        ("Comment annotations", "annotations"),
    ]:
        lines.append(f"| {label} | {c.get(key, 0):,} |")
    lines.append("")

    if ranked:
        lines.append("## Where to start\n")
        lines.append(
            "Ways in, ranked by how much of the program each one commands. The top of "
            "this list is the largest thing the program does.\n"
        )
        lines.append(
            "| Way in | Kind | Routines reached | Touches | Also detected as |"
            "\n|---|---|---:|---|---|"
        )
        for d in ranked[:15]:
            k = ", ".join(x.value for x in d["kinds"]) or "—"
            alias = ", ".join(f"`{a}`" for a in dict.fromkeys(d["aliases"]))
            lines.append(
                f"| `{_esc(d['name'])}` | {d['kind']} | {d['reach']:,} | {k} "
                f"| {_esc(alias) or '—'} |"
            )
        lines.append("")

    if bi:
        lines.append("## What it touches\n")
        lines.append("| Boundary | Touches | Most common target |\n|---|---:|---|")
        for kind, hits in bi.items():
            top = Counter(h["target"] for h in hits if h["target"]).most_common(1)
            lines.append(f"| {kind} | {len(hits):,} | {_esc(top[0][0]) if top else '—'} |")
        lines.append("")

    ac = rep.counts()
    if any(ac.values()):
        lines.append("## What looks wrong\n")
        lines.append(
            f"🔴 **{ac.get('BROKEN', 0)} broken** · 🟠 **{ac.get('SUSPECT', 0)} suspect** "
            f"· 🔵 **{ac.get('INFO', 0)} informational** — see "
            f"[09-anomalies.md](09-anomalies.md). Each finding states what would make "
            f"it a false alarm; read that before acting on it.\n"
        )

    lines.append("## The rest of the map\n")
    for name, desc in [
        ("01-entrypoints.md", "Every way in, including the full command tree."),
        ("02-flows.md", "What happens after each way in, as diagrams"
                        + (f"; {choice.short()}." if choice else ".")),
        ("03-routines.md", "Every routine, with typed signatures and its comments."),
        ("04-data.md", "The shapes that move between routines."),
        ("05-boundaries.md", "Every point where the program touches the outside world."),
        ("06-governance.md", "Plan IDs, audit locks, and warnings mined from comments."),
        ("07-database.md", "Schemas the code creates, and every read and write against them."),
        ("08-network.md", "Where the program stops being one process."),
        ("09-anomalies.md", "What looks wrong, and how sure the tool is about it."),
    ]:
        lines.append(f"- [{name}]({name}) — {desc}")
    lines.append("")

    path = out / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# `_what_this_describes` stood here: a `## What this map describes` section, on the cover
# only, stating the snapshot, when its source was read, and when the documents were
# written. All three facts survive -- they are in `page.header` now, and so on every page
# of the map rather than on one of fifteen. Keeping the section as well would have made
# the cover state the same three instants twice, which is the shape rule 51 warns about
# arriving through its own fix. Tom's call, 2026-09-09.


def _entrypoints(store: Store, out: Path, program: str, stamp: Stamp) -> Path:
    eps = store.entrypoints()
    lines = [header(program, "Ways in", stamp)]
    lines.append(
        "How this program gets started or woken up. Entries declared in packaging "
        "metadata are contractual; the rest are detected from decorators and "
        "conventional names.\n"
    )

    by_kind: dict[str, list] = defaultdict(list)
    for e in eps:
        by_kind[e.kind.value].append(e)

    # **`declared`, and `target_expr`.** This was `"[project.scripts]" in e.evidence` and
    # `e.evidence.rsplit("= ", 1)[-1]` -- a substring test and a parse against a sentence
    # written for a person, which a `package.json` `bin` can never match (rule 30).
    scripts = [e for e in eps if e.declared]
    if scripts:
        lines.append("## Executables\n")
        # **A reason in the last column, never a bare *no*.** *no* over a Rust binary
        # this build has no reader for is a claim that the program is broken; what
        # happened is that the map holds none of that language. `binding_note` words it
        # in one place (rule 51) and `anomalies` decides on the same answer (rule 98).
        lines.append("| Command | Target | Resolved |\n|---|---|---|")
        for e in scripts:
            tgt = e.target_expr or "—"
            if e.routine_id or e.parent_id:
                ok = "yes"
            else:
                ok = f"not bound — {binding_note(store, e.id).sentence}"
            lines.append(f"| `{_esc(e.name)}` | `{_esc(tgt)}` | {_esc(ok)} |")
        lines.append("")

        for e in scripts:
            if not e.parent_id:
                continue
            tree = command_tree(store, e.parent_id)
            if not tree:
                continue
            total = _count_commands(tree)
            lines.append(f"### `{e.name}` command tree ({total} commands)\n")
            lines.append("```mermaid")
            lines.append(command_tree_diagram(tree))
            lines.append("```\n")
            lines.append("The complete tree, including every command the diagram "
                         "above abbreviates:\n")
            lines.append(_tree_list(tree))
            lines.append("")

    for kind in sorted(by_kind):
        items = [e for e in by_kind[kind] if not e.declared]
        if not items:
            continue
        lines.append(f"## {kind} ({len(items)})\n")
        lines.append("| Name | Module | Detected from |\n|---|---|---|")
        for e in sorted(items, key=lambda x: (x.name, x.module, x.evidence)):
            lines.append(f"| `{_esc(e.name)}` | `{_esc(e.module)}` | {_esc(e.evidence)} |")
        lines.append("")

    lines.extend(_unclaimed_marks(store, program))

    path = out / "01-entrypoints.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _unclaimed_marks(store: Store, program: str) -> list[str]:
    """What is marked as a way in by the language and deliberately not claimed as one.

    A directive prologue -- `"use server"` -- marks a module whose exports are called
    across the wire, which is what HTTP_ROUTE means. They are not claimed, because nothing
    in the tree says which of a module's exports a client actually calls and claiming every
    one would put names in "Where to start" that no request reaches (rule 1). **A hole a
    reader can act on is stated; one that is merely absent is a false claim of
    completeness**, and this is design rule 13's shape: the count, and the query that
    returns exactly it.

    **The words are the language's and not this renderer's.** Which marks exist, whether
    each is claimed, and the sentence printed about it all come from
    `detectors/<lang>.yaml` -- the same document the reader was handed (rule 51). A
    sentence about React written into this file would be a claim no language could edit,
    and a second place to edit it.
    """
    langs = [str(r["lang"]) for r in
             store.query("SELECT DISTINCT lang FROM files WHERE lang <> '' ORDER BY lang")]
    out: list[str] = []
    for lang in langs:
        declared = rules_document(lang).get("directives") or {}
        for mark, block in sorted(declared.items()):
            if not isinstance(block, dict) or block.get("claimed", True):
                continue
            rows = store.query(
                "SELECT count(*) AS n, count(DISTINCT file) AS files FROM routines "
                "WHERE lang = ? AND decorators LIKE ?", (lang, f'%"{mark}"%'))
            n = int(rows[0]["n"]) if rows else 0
            if not n:
                continue
            files = int(rows[0]["files"])
            if not out:
                out.append("## Not claimed as a way in\n")
            out.append(
                f"**{n} routine{'' if n == 1 else 's'} in {files} "
                f"{'file' if files == 1 else 'files'}** "
                f"{'is' if n == 1 else 'are'} marked `{mark}`, which "
                f"{str(block.get('says', '')).strip()}\n"
            )
            out.append("```")
            out.append(f'dunneflow query <dir> --sql "SELECT file, name FROM routines '
                       f"WHERE lang = '{lang}' AND decorators LIKE '%{mark}%'\"")
            out.append("```\n")
    return out


def _count_commands(tree: dict) -> int:
    return len(tree.get("commands", [])) + sum(
        _count_commands(c) for c in tree.get("children", [])
    )


def _tree_list(tree: dict, depth: int = 0) -> str:
    pad = "  " * depth
    label = tree.get("mounted_as") or tree.get("var", "")
    out = [f"{pad}- **{label}** (`{tree.get('module','')}`)"]
    for c in tree.get("commands", []):
        out.append(f"{pad}  - `{c['name']}`")
    for ch in tree.get("children", []):
        out.append(_tree_list(ch, depth + 1))
    return "\n".join(out)


def _flows(store: Store, out: Path, program: str, stamp: Stamp,
           tick: Callable[[int, int], None] | None = None,
           ranked: list[dict] | None = None,
           index: _Inventory | None = None,
           choice: InventoryChoice | None = None) -> Path:
    if ranked is None:
        ranked = ways_in(store)
    if index is None:
        index = _Inventory(store)
    if choice is None:
        choice = InventoryChoice(FULL, inventory_costs(store, ranked, index))

    path = out / "02-flows.md"
    lines = _Stream(path)
    try:
        _flows_into(lines, store, program, stamp, ranked, tick, index, choice)
    finally:
        lines.close()
    return path


class _Stream:
    """A page written as it is built, byte for byte what `"\n".join(lines)` wrote.

    **The flows page is the one page that can be larger than memory should hold.** On
    Unreal's Runtime it was 1.14 GB, joined into one string before a single byte reached
    the disk, beside a Python process already at 1.5 GB on an 8 GB machine. Written as it
    goes, the page costs one section at a time. `append` keeps the list's spelling so the
    builder above reads exactly as it did.
    """

    def __init__(self, path: Path) -> None:
        self._f = path.open("w", encoding="utf-8")
        self._first = True

    def append(self, text: str) -> None:
        self._f.write(text if self._first else "\n" + text)
        self._first = False

    def close(self) -> None:
        self._f.close()


def _flows_into(lines: _Stream, store: Store, program: str, stamp: Stamp,
                ranked: list[dict], tick: Callable[[int, int], None] | None,
                index: _Inventory, choice: InventoryChoice) -> None:
    lines.append(header(program, "Flows", stamp))
    lines.append(
        "What each way in sets in motion. Solid arrows are calls; dotted arrows are "
        "the program reading from or writing to the world outside itself. Diagrams are "
        "capped so they stay readable — the caption says what was left out.\n"
    )
    lines.append(choice.statement())

    # **A declared way in that bound nothing sets nothing in motion here**, so there is no
    # flow to draw -- and that is a different page's subject, not a silence (design
    # rule 1). It is stated at the foot rather than dropped: `dunnenote-host` is a real
    # front door of that application, and a Flows page that mentions none of its four
    # would read as a program with nothing to trace.
    unbound = [d for d in ranked if not d["roots"]]
    rooted = [d for d in ranked if d["roots"]]
    for n, (d, flow) in enumerate(_traced(store, rooted)):
        if tick is not None:
            tick(n, len(rooted))
        lines.append(f"## {d['name']}\n")
        summary = ", ".join(f"{k} ×{v}" for k, v in flow.boundary_summary().items())
        lines.append(
            f"`{d['kind']}` · reaches **{d['reach']:,}** routines · "
            f"touches: {summary or 'nothing outside itself'}\n"
        )
        if len(d["roots"]) > 1:
            lines.append(
                f"> Built from a command tree of {len(d['roots'])} commands; the "
                f"diagram follows the first.\n"
            )
        if flow.truncated:
            # What is said about the list depends on which list was written (rule 13):
            # "listed in full below" over a count would be a sentence the page breaks.
            below = {
                FULL: "**Every routine this way in reaches is listed in full below the "
                      "diagram** — nothing is omitted from the record, only from the "
                      "drawing.",
                OMITTED: "**Every routine the drawing leaves out is listed below it**, so "
                         "the diagram and the list together are the whole of what this "
                         "way in reaches.",
                COUNT: "The routines it reaches are counted below rather than listed, by "
                       "the choice this map was written with.",
            }[choice.mode]
            lines.append(
                f"> The diagram shows the first {len(flow.nodes)} routines by call "
                f"depth, because a picture of {d['reach']:,} nodes conveys nothing. "
                f"{below}\n"
            )
        lines.append("```mermaid")
        lines.append(flow_diagram(flow))
        lines.append("```\n")
        lines.append(_flow_inventory(store, d, index, choice.mode, flow))


    if unbound:
        lines.append(f"## Declared, and not traced here ({len(unbound)})\n")
        lines.append(
            "These are declared ways into this program that this map cannot follow. "
            "Each one is a real front door; what is missing is the code behind it.\n"
        )
        lines.append("| Way in | Kind | Why |\n|---|---|---|")
        for d in unbound:
            lines.append(f"| `{_esc(d['name'])}` | {_esc(d['kind'])} | "
                         f"{_esc(d.get('why', ''))} |")
        lines.append("")


class _Inventory:
    """What every way in's inventory is made of, read once per render rather than per way in.

    **Each inventory asked the graph twice**, once for its routines and once for their
    boundaries, and on Unreal's Runtime that was 11,410 queries over 11.3 M rows: 9,032 s
    of a 9,649 s profiled render, at about 0.8 ms a row on an external disk. What a row
    says depends only on its routine, and where it goes in the table depends only on the
    routine's place in one fixed order, so both are taken once: the order as a rank, and
    the row's text the first time a way in reaches it.

    The order is the one the per-way-in query wrote -- module, qualname, file, line --
    with the id last, which breaks the tie that query left to the engine (rule 66).
    """

    def __init__(self, store: Store) -> None:
        self._rank: dict[str, int] = {}
        self._where: list[tuple[str, str, str]] = []
        for i, r in enumerate(store.query(
                "SELECT id, qualname, file, line_start FROM routines"
                " ORDER BY module, qualname, file, line_start, id")):
            self._rank[r["id"]] = i
            self._where.append((r["id"], r["qualname"], f"{r['file']}:{r['line_start']}"))
        self._bounds: dict[str, list[str]] = {}
        for b in store.query(
                "SELECT routine_id, kind, direction, target FROM boundaries"
                " ORDER BY kind, direction, target"):
            label = f"{b['kind']}{'→' if b['direction'] == 'OUT' else '←'}{b['target'] or '?'}"
            entries = self._bounds.setdefault(b["routine_id"], [])
            if label not in entries:
                entries.append(label)
        self._line: dict[int, str] = {}

    def rows(self, reached: set[str]) -> list[str]:
        """The table rows for these routines, in the fixed order. An id the routines
        table does not hold has no row, exactly as the join it replaces had none."""
        out = []
        for i in sorted(self._rank[r] for r in reached if r in self._rank):
            line = self._line.get(i)
            if line is None:
                rid, qualname, where = self._where[i]
                touches = "; ".join(self._bounds.get(rid, [])) or "—"
                line = f"| `{_esc(qualname)}` | {_esc(touches)} | {_esc(where)} |"
                self._line[i] = line
            out.append(line)
        return out


def _flow_inventory(store: Store, way_in: dict, index: _Inventory | None = None,
                    mode: str = "full", flow: Flow | None = None) -> str:
    """What one way in reaches, as the reader chose to have it listed.

    * `full` -- every routine it reaches, and every boundary each one touches. The diagram
      above is bounded; this is not, and it is the complete answer to "what does starting
      this actually run?".
    * `omitted` -- only the routines the diagram leaves out, which is rule 8 read
      literally: the drawing is bounded, so the record of what it bounded off is owed and
      nothing else is.
    * `count` -- how many it reaches, and where the list can be had.

    **One function builds the block for the page and for `inventory_costs`**, so a stated
    size is the size of what is written (rule 13). `index` is the render's one
    `_Inventory`; without it, one is read for this call.
    """
    reached = store.reachable_from_many(way_in["roots"])
    if not reached:
        return ""
    index = index or _Inventory(store)
    name = way_in["name"]
    if mode == COUNT:
        n = len(index.rows(set(reached)))
        return (f"<details><summary>Every routine reachable from <code>{name}</code>"
                f" ({n:,}) — counted, not listed</summary>\n\n"
                "Not listed, because this map was written with `--flow-inventory count`. "
                "Open this way in in the dashboard to walk what it reaches, or write the "
                "map again with `--flow-inventory full`.\n\n</details>\n")
    if mode == OMITTED:
        drawn = {node.routine_id for node in flow.nodes} if flow is not None else set()
        rows = index.rows(set(reached) - drawn)
        if not rows:
            return (f"<details><summary>Every routine reachable from <code>{name}</code>"
                    " is in the diagram</summary>\n\nNothing was left out of the "
                    "drawing, so there is nothing to list.\n\n</details>\n")
        summary = (f"What the diagram of <code>{name}</code> leaves out "
                   f"({len(rows):,} of {len(reached):,})")
    else:
        rows = index.rows(set(reached))
        summary = f"Every routine reachable from <code>{name}</code> ({len(rows):,})"
    out = [
        f"<details><summary>{summary}</summary>\n",
        "| Routine | Touches | Where |\n|---|---|---|",
        *rows,
        "\n</details>\n",
    ]
    return "\n".join(out)


def _traced(store: Store, rooted: list[dict]) -> Iterator[tuple[dict, Flow]]:
    """Every way in that has a flow to draw, with its flow -- one walk, for the page and
    for its measurement, so both see the same ways in in the same order."""
    for d in rooted:
        flow = trace_flow(store, d["roots"][0], d["name"], d["kind"])
        if flow.nodes:
            yield d, flow


_SAYS = {FULL: "every routine each way in reaches",
         OMITTED: "only what each diagram leaves out",
         COUNT: "how many each reaches, not which"}


@dataclass(frozen=True)
class InventoryCost:
    """The bytes the flows page's inventories take in each mode, measured by building them."""

    bytes: dict[str, int]

    def words(self, mode: str) -> str:
        return f"`{mode}` ({_SAYS[mode]}), {human_bytes(self.bytes[mode])}"


@dataclass(frozen=True)
class InventoryChoice:
    mode: str
    cost: InventoryCost

    def short(self) -> str:
        return (f"its inventories list {_SAYS[self.mode]} "
                f"({human_bytes(self.cost.bytes[self.mode])})")

    def statement(self) -> str:
        """The paragraph over the flows page: which choice, and what the others cost."""
        others = "; ".join(self.cost.words(m) for m in INVENTORY_MODES if m != self.mode)
        return (f"> **Under each diagram: {_SAYS[self.mode]}** — `--flow-inventory "
                f"{self.mode}`, {human_bytes(self.cost.bytes[self.mode])} of this page. "
                f"The other choices would have taken {others}.\n")


def human_bytes(n: int) -> str:
    """`1.14 GB`, `830 KB`, `412 bytes` -- decimal units, as a file manager shows them."""
    if n < 1000:
        return f"{n:,} bytes"
    for unit, size in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if n >= size:
            return f"{n / size:.3g} {unit}" if n < size * 100 else f"{n / size:,.0f} {unit}"
    return f"{n:,} bytes"


def inventory_costs(store: Store, ranked: list[dict], index: _Inventory | None = None,
                    tick: Callable[[int, int], None] | None = None) -> InventoryCost:
    """What the flows page's inventories take in each mode, in bytes, before one is written.

    Built and measured rather than estimated, because the figure is printed beside the
    choice and a claim must be what is printed (rule 13). It costs one more reach walk and
    trace per way in; the rows themselves are cached in `index`, so the page that follows
    builds no row twice.
    """
    index = index or _Inventory(store)
    rooted = [d for d in ranked if d["roots"]]
    total = dict.fromkeys(INVENTORY_MODES, 0)
    for n, (d, flow) in enumerate(_traced(store, rooted)):
        if tick is not None:
            tick(n, len(rooted))
        for m in INVENTORY_MODES:
            total[m] += len(_flow_inventory(store, d, index, m, flow).encode("utf-8"))
    return InventoryCost(total)


def _routines(store: Store, out: Path, program: str, stamp: Stamp) -> Path:
    rows = store.query(
        "SELECT module, COUNT(*) n FROM routines WHERE name != '<module>'"
        " GROUP BY module ORDER BY n DESC, module"
    )
    lines = [header(program, "Routines", stamp)]
    lines.append(
        "Every routine, with what goes in and what comes out. `WHY` is the comment or "
        "docstring attached to it — the part the code itself cannot tell you.\n"
    )
    lines.append(f"Modules: **{len(rows)}**\n")

    for r in rows:
        module = r["module"]
        rts = [x for x in store.routines(module) if x.name != "<module>"]
        if not rts:
            continue
        lines.append(f"## `{module}` ({len(rts)})\n")
        lines.append("| Routine | Signature | WHY | Where |\n|---|---|---|---|")
        for rt in rts:
            # The whole WHY: the docstring's opening line plus every comment attached
            # to the routine. Nothing is dropped -- the comments are the part the code
            # cannot tell you, and a half-shown caveat is worse than none.
            why_parts: list[str] = []
            if rt.docstring:
                why_parts.append(rt.docstring.strip().split("\n")[0])
            why_parts.extend(c.text for c in rt.comments if c.text)
            why = " · ".join(dict.fromkeys(p for p in why_parts if p))
            marker = "async " if rt.is_async else ""
            where = f"{rt.file}:{rt.line_start}"
            lines.append(
                f"| `{_esc(rt.name)}` | `{marker}{_esc(rt.signature())}` "
                f"| {_esc(why)} | {_esc(where)} |"
            )
        lines.append("")

    path = out / "03-routines.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _data(store: Store, out: Path, program: str, stamp: Stamp) -> Path:
    structs = store.structures()
    lines = [header(program, "Data structures", stamp)]
    lines.append(
        "The named shapes that move between routines. Fields carry their declared "
        "types where the code declares them.\n"
    )
    by_kind = Counter(s.kind.value for s in structs)
    lines.append("| Kind | Count |\n|---|---:|")
    for k, n in by_kind.most_common():
        lines.append(f"| {k} | {n} |")
    lines.append("")

    by_mod: dict[str, list] = defaultdict(list)
    for s in structs:
        by_mod[s.module].append(s)

    for module in sorted(by_mod):
        lines.append(f"## `{module}`\n")
        for s in by_mod[module]:
            base = f" — extends `{', '.join(s.bases)}`" if s.bases else ""
            lines.append(f"### {s.name} · {s.kind.value}{base}\n")
            if s.docstring:
                lines.append(f"{_esc(s.docstring)}\n")
            if s.kind is StructureKind.TYPE_ALIAS:
                # A `Literal` alias has members, not fields. Rendering them in a
                # Field / Type / Default / Note table put the members under the wrong
                # heading and filled three columns with em-dashes.
                if s.fields:
                    members = " · ".join(f"`{_esc(f.name)}`" for f in s.fields)
                    lines.append(f"One of: {members}\n")
            elif s.fields:
                lines.append("| Field | Type | Default | Note |\n|---|---|---|---|")
                for f in s.fields:
                    lines.append(
                        f"| `{_esc(f.name)}` | `{_esc(f.type) or '—'}` "
                        f"| {_esc(f.default) or '—'} | {_esc(f.comment)} |"
                    )
            lines.append(f"\n`{s.file}:{s.line}`\n")

    path = out / "04-data.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _boundaries(store: Store, out: Path, program: str, stamp: Stamp) -> Path:
    bi = boundary_index(store, min_salience="low")
    lines = [header(program, "Boundaries", stamp)]
    lines.append(
        "Every point where the program touches something outside itself. This is the "
        "complete inventory of what moves in and what moves out.\n"
    )
    for kind, hits in bi.items():
        lines.append(f"## {kind} ({len(hits):,})\n")
        targets = Counter(h["target"] for h in hits if h["target"])
        if targets:
            lines.append("| Target | Touches | Direction |\n|---|---:|---|")
            # `most_common()` breaks a tie by insertion order, which here is row order.
            for tgt, n in sorted(targets.items(), key=lambda kv: (-kv[1], kv[0])):
                dirs = {h["direction"] for h in hits if h["target"] == tgt}
                lines.append(f"| `{_esc(tgt)}` | {n} | {'/'.join(sorted(dirs))} |")
            lines.append("")
        lines.append("<details><summary>Routines involved</summary>\n")
        lines.append("| Routine | Target | Via | Where |\n|---|---|---|---|")
        for h in hits:
            where = f"{h['file']}:{h['line']}"
            lines.append(
                f"| `{_esc(h['qualname'])}` | `{_esc(h['target'])}` "
                f"| `{_esc(h['evidence'])}` | {_esc(where)} |"
            )
        lines.append("\n</details>\n")

    path = out / "05-boundaries.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _governance(store: Store, out: Path, program: str, stamp: Stamp) -> Path:
    rows = store.query(
        """SELECT a.kind, a.value, a.text, a.line, a.owner_kind,
                  COALESCE(r.qualname, s.name) AS owner, COALESCE(r.file, s.file) AS file
             FROM annotations a
             LEFT JOIN routines r ON a.owner_id = r.id
             LEFT JOIN structures s ON a.owner_id = s.id
            ORDER BY a.kind, a.value, file, a.line, owner, a.text"""
    )
    lines = [header(program, "Governance and caveats", stamp)]
    lines.append(
        "Structured markers mined out of comments and docstrings. These are the things "
        "the code cannot say about itself: which decision governs a routine, what is "
        "locked, and what will bite you.\n"
    )
    if not rows:
        lines.append("*No annotations found.*\n")
        path = out / "06-governance.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    by_kind: dict[str, list] = defaultdict(list)
    for r in rows:
        by_kind[r["kind"]].append(r)

    lines.append("| Marker | Occurrences | Distinct values |\n|---|---:|---:|")
    for marker in sorted(by_kind, key=biggest_first(by_kind)):
        vals = {r["value"] for r in by_kind[marker]}
        lines.append(f"| {marker} | {len(by_kind[marker]):,} | {len(vals):,} |")
    lines.append("")

    for marker in sorted(by_kind, key=biggest_first(by_kind)):
        items = by_kind[marker]
        lines.append(f"## {marker} ({len(items):,})\n")
        grouped: dict[str, list] = defaultdict(list)
        for r in items:
            grouped[r["value"]].append(r)
        for value in sorted(grouped):
            hits = grouped[value]
            lines.append(f"### {value} — {len(hits)} place(s)\n")
            lines.append("| Where | Says |\n|---|---|")
            for h in hits:
                where = f"{h['file'] or ''}:{h['line']}"
                lines.append(f"| `{_esc(h['owner'])}` <br>{_esc(where)} "
                             f"| {_esc(h['text'])} |")
            lines.append("")

    path = out / "06-governance.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
