"""The written map.

Seven documents, ordered the way an unfamiliar program is best approached: what it is,
how you get in, what happens then, what the pieces are, what shapes move between them,
what it touches, and what the comments warn you about.

Written for someone who reads code but does not write it, so every table leads with a
name and a type and never assumes a convention is obvious.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from ..anomalies import Report, detect
from ..detectors import rules_document
from ..docstore import DocStore
from ..resolve.cli import command_tree
from ..resolve.entrypoints import binding_note
from ..resolve.flows import boundary_index, trace_flow, ways_in
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
               tick: Callable[[int, int, str], None] | None = None) -> list[Path]:
    """Write the whole map. Returns the files written.

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
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = Stamp.of(store, when)
    if report is None:
        report = detect(store, include_tests)
    say = tick or (lambda _done, _total, _what: None)

    def flows() -> Path:
        return _flows(store, out_dir, program, stamp,
                      tick=lambda i, n: say(i, n, "02-flows.md, way in"))

    pages: list[Callable[[], Path | None]] = [
        lambda: _overview(store, out_dir, program, stamp, report),
        lambda: _entrypoints(store, out_dir, program, stamp),
        flows,
        lambda: _routines(store, out_dir, program, stamp),
        lambda: _data(store, out_dir, program, stamp),
        lambda: _boundaries(store, out_dir, program, stamp),
        lambda: _governance(store, out_dir, program, stamp),
        lambda: render_database(store, out_dir, program, stamp),
        lambda: render_network(store, out_dir, program, stamp),
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
        written.append(page())
    say(len(pages), len(pages), "document")
    return [w for w in written if w]


# --------------------------------------------------------------------------- #


def _overview(store: Store, out: Path, program: str, stamp: Stamp,
              rep: Report) -> Path:
    c = store.counts()
    bi = boundary_index(store)

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
        ("02-flows.md", "What happens after each way in, as diagrams."),
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
           tick: Callable[[int, int], None] | None = None) -> Path:
    ranked = ways_in(store)

    lines = [header(program, "Flows", stamp)]
    lines.append(
        "What each way in sets in motion. Solid arrows are calls; dotted arrows are "
        "the program reading from or writing to the world outside itself. Diagrams are "
        "capped so they stay readable — the caption says what was left out.\n"
    )

    # **A declared way in that bound nothing sets nothing in motion here**, so there is no
    # flow to draw -- and that is a different page's subject, not a silence (design
    # rule 1). It is stated at the foot rather than dropped: `dunnenote-host` is a real
    # front door of that application, and a Flows page that mentions none of its four
    # would read as a program with nothing to trace.
    unbound = [d for d in ranked if not d["roots"]]
    rooted = [d for d in ranked if d["roots"]]
    for n, d in enumerate(rooted):
        if tick is not None:
            tick(n, len(rooted))
        flow = trace_flow(store, d["roots"][0], d["name"], d["kind"])
        if not flow.nodes:
            continue
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
            lines.append(
                f"> The diagram shows the first {len(flow.nodes)} routines by call "
                f"depth, because a picture of {d['reach']:,} nodes conveys nothing. "
                f"**Every routine this way in reaches is listed in full below the "
                f"diagram** — nothing is omitted from the record, only from the "
                f"drawing.\n"
            )
        lines.append("```mermaid")
        lines.append(flow_diagram(flow))
        lines.append("```\n")
        lines.append(_flow_inventory(store, d))


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

    path = out / "02-flows.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _flow_inventory(store: Store, way_in: dict) -> str:
    """Every routine one way in reaches, and every boundary it ends up touching.

    The diagram above is bounded; this is not. A reader who wants the complete answer
    to "what does starting this actually run?" finds it here.
    """
    reached = sorted(store.reachable_from_many(way_in["roots"]))
    if not reached:
        return ""
    ids = (json.dumps(reached),)
    rows = store.query(
        "SELECT id, qualname, module, file, line_start FROM routines"
        " WHERE id IN (SELECT value FROM json_each(?))"
        " ORDER BY module, qualname, file, line_start",
        ids,
    )
    bounds: dict[str, list[str]] = {}
    for b in store.query(
        "SELECT routine_id, kind, direction, target FROM boundaries"
        " WHERE routine_id IN (SELECT value FROM json_each(?)) ORDER BY kind, direction, target",
        ids,
    ):
        label = f"{b['kind']}{'→' if b['direction'] == 'OUT' else '←'}{b['target'] or '?'}"
        entries = bounds.setdefault(b["routine_id"], [])
        if label not in entries:
            entries.append(label)

    out = [
        f"<details><summary>Every routine reachable from <code>{way_in['name']}</code>"
        f" ({len(rows):,})</summary>\n",
        "| Routine | Touches | Where |\n|---|---|---|",
    ]
    for r in rows:
        touches = "; ".join(bounds.get(r["id"], [])) or "—"
        where = f"{r['file']}:{r['line_start']}"
        out.append(f"| `{_esc(r['qualname'])}` | {_esc(touches)} | {_esc(where)} |")
    out.append("\n</details>\n")
    return "\n".join(out)


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
