"""The local server: `dunneflow serve output/<program>`.

`http.server` from the standard library, deliberately. The dashboard is a reading tool
someone opens on their own machine, not a service, and adding a web framework to a program
whose only dependency is a YAML parser would be paying a permanent cost for a one-machine
problem. The same command works on macOS and Windows because nothing here is platform-
specific.

Both stores are opened `writable=False`. Serving must never be able to damage the map it
is showing -- see rule 20, which exists because a read command once dropped every table it
came to read.

The graph is sent **columnar**: parallel arrays rather than one object per node. At
fifteen thousand drawn nodes the difference is several megabytes of repeated key names,
and deck.gl wants flat arrays anyway, so the object form would be built only to be taken
apart again.
"""

from __future__ import annotations

import dataclasses
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import parse_qs

from .. import macapp, revisions, runstate, runtime
from ..docstore import DocStore
from ..estimate import WARN_AFTER_DEFAULT, WARN_AFTER_MAX, WARN_AFTER_MIN
from ..render.markdown import INVENTORY_MODES, human_bytes
from ..resolve import languages
from ..resolve import version as version_order
from ..resolve.macros import macro_places, macro_report
from ..runtime import resource_root
from ..sourcedb import DocSourceStore, SourceStore
from ..standards import STANDARDS_DB
from ..store import StaleGraphError, Store, UnfinishedMapError, unfinished_sentence
from . import (
    analysis,
    anomalychanges,
    changes,
    diagram,
    filediff,
    packages,
    plate,
    queries,
    roots,
    table,
)
from .code import build_file, build_files
from .corpus import build_corpus, build_document, serving
from .cover import anomalies as build_anomalies
from .cover import build as build_cover
from .curiosities import for_program
from .detail import describe, hover_card
from .detail import flow_edge as detail_flow
from .detail import fold as detail_fold
from .graph import (
    LEVELS,
    MIN_DISK_BY_LEVEL,
    MIN_DISK_CEILING,
    MIN_DISK_FLOOR,
    GraphModel,
    build,
    pkg_params,
    root_package,
)
from .layout import structural
from .plateorder import answer as plate_answer
from .related import documents_for as related_documents
from .search import search_files, search_in_file
from .shape import for_program as lanes_for_program
from .shape import outline_for
from .threads import cohort, for_node
from .vocabulary import (
    bind_glossary,
    checked_naming,
    measure_naming,
    stated_naming,
)
from .waysin import describe as describe_way_in
from .waysin import listing as ways_in_listing

# The page's own files, and the vendored engine. Through `resource_root()` rather than
# `Path(__file__)` for the reason the detectors state: frozen, `__file__` names a location
# that is not on disk, and every one of these would 404 -- a server that starts perfectly
# and serves a blank page.
STATIC = resource_root() / "web" / "static"
VENDOR = resource_root() / "web" / "vendor"

# Why a sidecar cannot answer, one sentence per corpus and one for the case that is
# neither. Constants because three readers say them -- `/api/source`, `/api/docsource`, and
# the glossary payload that decides whether a citation offers to open at all -- and rule 51
# puts the wording where all of them pass. Two spellings of "there is no sidecar here" is a
# reader being told two different things about one program.
NO_SOURCE_SIDECAR = "no source sidecar beside this map"
NO_DOC_SIDECAR = "no document sidecar beside this map (--no-doc-source)"
# Not corpus-specific, and deliberately so: `_sidecar_revision` returns `None` for exactly
# one reason in both stores, and the sentence names the version rather than the store.
SIDECAR_NO_VERSION = "this sidecar holds nothing for the version on screen"

_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
}


def _sidecar_state(sidecar: SourceStore | None, revision: str | None, *,
                   absent: str) -> dict[str, Any]:
    """Whether one sidecar can serve the version on screen, and why not when it cannot.

    `opens` is a **capability**, and it is deliberately not per path: whether this corpus
    can be read at all, which is what decides whether a citation renders a button. The
    fourth state -- a sidecar that holds bodies but not *this* path -- is per path, cannot
    be known without asking, and is stated by `_span` when the reader asks. Pre-empting it
    here would mean 235 `held_paths` lookups to grey out a button that already says what
    happened when it is pressed.

    The decision is `corpus.serving`'s, called rather than repeated. Only the two sentences
    are this corpus's own (rule 51).
    """
    store, why = serving(sidecar, revision, absent=absent, stale=SIDECAR_NO_VERSION)
    return {"opens": store is not None, "reason": why}


def glossary_sidecars(source: SourceStore | None, docsource: DocSourceStore | None,
                      source_revision: str | None,
                      docsource_revision: str | None) -> dict[str, Any]:
    """Which provenance tiers can actually open their citation, one entry per tier.

    **A capability test, not a provenance test**, which is the distinction design rule 13
    rests on here: `senseOpens()` in the shell asked `provenance === "DECLARED_CODE"` for
    as long as `source.db` was the only sidecar, so every documentation-derived definition
    rendered a dead end. The question is whether the corpus a tier quotes has a sidecar
    *this base* can read.

    Lifted out of `_r_glossary` when `dunneflow mcp` became the second caller. It is the
    same argument the route already made for not folding it into `bind_glossary` -- the
    terms belong to the base, this belongs to the process and to the version on screen --
    and a second surface answering it from its own copy is how the dashboard and the agent
    come to disagree about whether a button is live (rule 51).

    The caller holds `_Live.lock`; nothing here takes it.
    """
    return {
        "DECLARED_CODE": _sidecar_state(source, source_revision, absent=NO_SOURCE_SIDECAR),
        "DECLARED_DOCS": _sidecar_state(docsource, docsource_revision,
                                        absent=NO_DOC_SIDECAR),
    }


def columnar(model: GraphModel, clock: _Clock | None = None) -> dict[str, Any]:
    """The whole stack as parallel arrays, with every drawn thing already positioned.

    Shadows are appended after real nodes and carry `real[i]`, the index of the node they
    proxy. That is what the transposition lines are drawn from, and it means the client
    never has to build a lookup to find where a shadow's real self lives.

    `clock` is the instrument and changes nothing: this and `structural` are two of the
    five things *the 2.5D model and its payload* names, and a step label that conflates
    five things cannot say which of them costs 27.6 minutes on a map of 262,879 routines.
    """
    pos = structural(model)
    if clock is not None:
        clock.lap("· laying it out")
    index: dict[tuple[str, str], int] = {}

    ids: list[str] = []
    labels: list[str] = []
    kinds: list[str] = []
    disks: list[str] = []
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    shadow_flags: list[int] = []
    real_of: list[int] = []
    detail: list[dict[str, Any]] = []

    def emit(node_id: str, label: str, kind: str, disk: str,
             is_shadow: bool, real: int, extra: dict[str, Any]) -> int:
        x, y, z = pos.get((node_id, disk), (0.0, 0.0, 0.0))
        i = len(ids)
        index[(node_id, disk)] = i
        ids.append(node_id)
        labels.append(label)
        kinds.append(kind)
        disks.append(disk)
        xs.append(x)
        ys.append(y)
        zs.append(z)
        shadow_flags.append(1 if is_shadow else 0)
        real_of.append(real)
        detail.append(extra)
        return i

    for n in model.nodes:
        emit(n.id, n.label, n.kind, n.disk, False, -1, n.detail)

    by_id = {n.id: n for n in model.nodes}
    for s in model.shadows:
        origin = by_id.get(s.node_id)
        if origin is None:
            continue
        home = index.get((s.node_id, origin.disk), -1)
        emit(s.node_id, origin.label, origin.kind, s.disk, True, home, {})

    # Edges reference drawn-node indices, so the client draws them without a lookup.
    e_from: list[int] = []
    e_to: list[int] = []
    e_kind: list[str] = []
    e_conf: list[str] = []
    e_disk: list[str] = []
    # How many times this connection appears in the source. It is carried through to the
    # client and drives edge width, which is the whole preparation for flow replay: when
    # a profile is imported later it becomes a *second source for a channel that already
    # exists*, rather than a reason to rewrite the renderer. Reserving storage for the
    # profiler now would be building the feature, not preparing for it.
    e_weight: list[int] = []
    dropped = 0
    for e in model.edges:
        a = index.get((e.src, e.disk))
        b = index.get((e.dst, e.disk))
        if a is None or b is None:
            dropped += 1
            continue
        e_from.append(a)
        e_to.append(b)
        e_kind.append(e.kind)
        e_conf.append(e.confidence)
        e_disk.append(e.disk)
        e_weight.append(e.weight)

    stats = dict(model.stats)
    stats["edges_unplaced"] = dropped

    return {
        "nodes": {"id": ids, "label": labels, "kind": kinds, "disk": disks,
                  "x": xs, "y": ys, "z": zs, "shadow": shadow_flags, "real": real_of,
                  "detail": detail},
        "edges": {"from": e_from, "to": e_to, "kind": e_kind,
                  "confidence": e_conf, "disk": e_disk, "weight": e_weight},
        "disks": model.disks,
        "stats": stats,
        # Which altitude these arrays are. The page holds one payload per level and has to
        # be able to ask what it is holding rather than remember what it asked for -- a
        # request that was clamped or refused would otherwise leave the control naming one
        # thing while the picture drew another (rule 67).
        "level": model.level,
    }


def default_level() -> tuple[str, int]:
    """The altitude a session opens at: every thing the program declares.

    Named rather than written out, because it is the seed of the payload cache *and* the
    fallback for a request that asks for nothing, and two spellings of one default is how
    the two come apart (rule 51).
    """
    return ("routine", MIN_DISK_BY_LEVEL["routine"])


def read_level(q: dict[str, list[str]]) -> tuple[str, int]:
    """Which altitude a request is asking for, refusing anything it cannot serve.

    A level it does not know is an error rather than the default. A silent fallback here
    would answer a question nobody asked with a picture that looks exactly right -- design
    rule 16's dead control, in a query string.

    `minDisk` is clamped rather than refused, and the two are different because they are
    different mistakes: an unknown level is a caller that is wrong, a threshold of 400 is a
    reader dragging a slider. The clamp is stated in the payload the answer carries, so
    nothing on screen is a number the page cannot account for.
    """
    level = (q.get("level") or [default_level()[0]])[0]
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}; expected one of {', '.join(LEVELS)}")
    raw = (q.get("minDisk") or [""])[0]
    if not raw:
        return (level, MIN_DISK_BY_LEVEL[level])
    try:
        wanted = int(raw)
    except ValueError:
        raise ValueError(f"minDisk must be a whole number, not {raw!r}") from None
    return (level, max(MIN_DISK_FLOOR, min(MIN_DISK_CEILING, wanted)))


def build_payload(store: Store, program: str,
                  level: str = "routine", min_disk: int | None = None,
                  clock: _Clock | None = None) -> dict[str, Any]:
    """One level of the stack, positioned and columnar.

    The program's name rides with it because the browser keys stored settings per program:
    a plate order and a set of colours worked out for one codebase mean nothing in another.

    **`clock` splits the step that no evidence could name** (`BACKLOG.md` item 8). Three
    phases with quite different shapes hide behind one label: `graph.build` is six scans
    of the store, `structural` is a sort and a phyllotaxis per drawn node, and the
    transposition is ten parallel lists over nodes, shadows and edges in pure Python. A
    sub-lap is written with a leading `·` so a reader can see at a glance that it is
    inside the step above it and not a seventh one (rule 32).
    """
    model = build(store, level=level, min_disk=min_disk)
    if clock is not None:
        clock.lap("· reading the graph into a model")
    payload = columnar(model, clock)
    if clock is not None:
        clock.lap("· transposing it into the payload")
    payload["program"] = program
    return payload


def _warn_after(q: dict[str, list[str]]) -> int:
    """The reader's threshold in minutes, clamped as the terminal's is (`cli._warn_minutes`).

    An unreadable value is the default rather than an error: it came from a field in a
    dialog, and the clamp there already says what the range is."""
    try:
        n = int((q.get("warn_after") or [str(WARN_AFTER_DEFAULT)])[0])
    except ValueError:
        return WARN_AFTER_DEFAULT
    return min(WARN_AFTER_MAX, max(WARN_AFTER_MIN, n))

def _analysing(d: Path) -> dict[str, Any] | None:
    """The live run another process is making of this program, in the panel's shape, or `None`.

    See `runstate`. `None` for a sidecar whose run has gone: what that leaves behind is a
    graph marked unfinished, and `finished` already says so in the store's own words.
    """
    body = runstate.read(d)
    if body is None or not body["running"]:
        return None
    return runstate.as_progress(body)

def _unfinished_choice(q: dict[str, list[str]]) -> bool | None:
    """The page's Setting "Unfinished maps", as sent with a switch: open, refuse, or unsaid.

    Three states, because a request that does not say is not a request that chose to
    refuse: it gets the server's own default, which `--allow-unfinished` sets. Anything
    other than the two words is unsaid rather than guessed at (rule 49).
    """
    said = (q.get("unfinished") or [""])[0]
    return {"open": True, "refuse": False}.get(said)


def _relaxed(q: dict[str, list[str]]) -> bool:
    """Whether a naming request asks for a leading underscore to be allowed."""
    return (q.get("underscore") or [""])[0] == "1"


@dataclass(frozen=True)
class _Base:
    """Everything one version of the program decides, in one binding.

    Not eight attributes on `_Live`, and the reason is the whole of this chunk: a base
    switch has to replace *all* of these together, and eight places to keep in step is
    rule 51's defect with eight opportunities to make it. Frozen and swapped whole, so a
    request either sees the old version entirely or the new one entirely -- never a cover
    from one and a payload from the other.

    It is also what the guard reads: "a switch rebuilt everything" derives its list from
    `__dataclass_fields__` rather than restating it, so a field added later is covered
    without anyone remembering (rule 36 -- route from a table, never from a hand-kept
    list).
    """

    graph_db: Path
    store: Store
    # What this version is called -- the id the graph's filename claims, `""` for a legacy
    # bare `graph.db` that predates the layout. Held rather than re-derived at each use:
    # `revision_of` was called in four routes already, and a fifth caller is how a rule
    # kept at a call site starts to rot (rule 51).
    revision: str
    # **Which revision of the bodies belongs to this version**, which is a different
    # question and occasionally a different answer. There is one `source.db` per program
    # holding every revision, and its own default is the newest snapshot -- right only
    # while the newest is also the version being read. Every sidecar read in this file
    # names this rather than letting the store decide, because the store cannot know which
    # version the reader is looking at.
    #
    # `None` means the sidecar cannot serve this version at all: no sidecar, or one that
    # holds no path at this revision. That is stated, never substituted (rule 49) -- the
    # bodies of some other version under this version's map is the failure this field
    # exists to make impossible.
    source_revision: str | None
    # The same question asked of the **other** sidecar, and it is a separate field rather
    # than a reuse of the one above. `analyze` makes both stores adopt the graph's own
    # revision id, so the two agree on every program analysed in one pass -- and "agree
    # today" is exactly the kind of coincidence rule 51 is about. `--no-doc-source` on one
    # run and not the next is enough to part them, and the failure would be silent: this
    # version's headings laid over some other version's prose.
    docsource_revision: str | None
    # The 2.5D stack, columnar. Named with the program so the browser can key stored
    # settings per program: a disk order and a set of colours worked out for one codebase
    # mean nothing in another, and silently applying one to the other would be the worst
    # kind of persistence.
    payload: dict[str, Any]
    # The program's own root package, read from the data rather than assumed -- one
    # aggregate over `files`, and it is what scopes an outlier thread to the plate the
    # reader is standing on. Computed once because it cannot change while this version is
    # the base, and a per-request GROUP BY over every file would be a cost paid for
    # nothing.
    root: str
    # The file list. Its cost is all in the first touch of two databases on a slow
    # volume -- 550 ms cold against 23 ms warm -- so it is paid where a payload, a cover
    # and two vocabulary passes are already being paid for.
    files: dict[str, Any]
    # The two lanes of the naming standard. Not lazily, and the reason is where they are
    # *used*: a vocabulary thread is part of `/api/threads`, which is asked on every
    # selection, so a lazy first call would stall the reading loop on the first click of
    # every session. Measured on Lictores at 0.4 s for the naming pass and 2.1 s for the
    # glossary, which reads a 176 MB document store.
    naming: dict[str, Any]
    # The stated lane, beside the derived one rather than inside it. Two fields because
    # they are two answers to two questions -- what the code does about names, and what
    # somebody wrote down about them -- and the dashboard shows them on two pages for the
    # same reason. Folding them into one dict would make "derived" false of half of it.
    stated: dict[str, Any]
    # The comparison, and a third field for the same reason there are two above: what the
    # code does, what somebody wrote, and whether the one meets the other are three claims.
    # Folding this into `stated` would put a measurement inside the payload whose whole
    # contract is that it measures nothing.
    checked: dict[str, Any]
    glossary: dict[str, Any]
    # **This version's document store, held open.** It used to be opened for the glossary
    # and closed in the same breath, because one held across a base switch leaked a 148 MB
    # store every time the reader moved between two versions. Held *here* that argument is
    # answered rather than avoided: a base owns it and the swap closes it, so the lifetime
    # is the version's rather than the process's.
    #
    # And it has to be held, because a document list cannot be served from a store that is
    # already shut. `docs.db` is per revision -- a version's documents are that version's
    # -- which is why this is a field of `_Base` and `source`/`docsource` are not.
    #
    # `None` is a real state and not an error: design rule 11 makes documentation an
    # optional input, and a program analysed with `--no-docs` keeps a complete code map.
    docs: DocStore | None
    # **Why this map may not be trusted, or `""` when it may** -- `unfinished_sentence`,
    # set only when the reader's Setting let an unfinished map open (rule 80's third half
    # and Tom's ruling that strictness is a Setting). A sentence for the page's banner,
    # because the banner has to say which step it stopped in, and a flag cannot.
    unfinished: str
    # The first screen. 175 reachability queries on every navigation would make it the
    # slowest one.
    cover: dict[str, Any]
    # Every level of detail this version has been asked for, keyed `(level, min_disk)`.
    #
    # **`payload` is in here too, under its own key, and it is the same object** -- one
    # truth with an index over it rather than two copies that can disagree (rule 51). The
    # routine default is still built at boot, so the start cost does not move; a module
    # payload is ~120 ms and is built the first time somebody climbs to it.
    #
    # It is a field rather than a cache on `_Live` because it is a *fact about this
    # version*: a base switch must throw all of it away, and a frozen record swapped whole
    # does that for free.
    payloads: dict[tuple[str, int], dict[str, Any]] = field(default_factory=dict)
    # The plate orders, keyed on the same `(level, min_disk)` the payloads are and for the
    # same reason one line up -- an order names plates, `min_disk` decides which plates
    # exist, and an order fetched at one threshold names plates the other has merged into
    # `<small>` (rule 81: a key that decides whether to skip work must carry everything the
    # work depends on). The `grouped` flag joins the key because it is a different
    # question, not a different rendering of one answer: the two are solved separately and
    # neither can be derived from the other.
    #
    # A field rather than a cache on `_Live`, on `payloads`' argument exactly: it is a fact
    # about *this version*, and a frozen record swapped whole throws it away for free. That
    # is also why it is in neither `COMPARISON_CACHES` nor `PROGRAM_CACHES` -- being a field
    # is what clears it, and naming it there as well would be a second answer to "when does
    # this go stale" that can drift from the first.
    plate_orders: dict[tuple[str, int, bool], dict[str, Any]] = field(default_factory=dict)
    # The compartment diagrams, built once per base for the same reason the payloads are:
    # they are a fact about *this version* of the program, and a switch throws them away
    # with everything else. One pass over the model builds all fifty-three, so this is
    # keyed by nothing -- it is the whole set or it is empty.
    compartments: dict[str, Any] = field(default_factory=dict)
    # Which box each node lives in, and what each box is called -- derived from the
    # compartments above, so the second level places a crossing in exactly the box the
    # first level drew it in. Filled beside them and thrown away with them.
    box_of: dict[str, str] = field(default_factory=dict)
    box_label: dict[str, str] = field(default_factory=dict)
    # The doorway panel: twelve measured extrema over this version, held here for the same
    # reason as everything above it -- they are facts about *this* version and a switch
    # must throw them away. Not in `COMPARISON_CACHES`, because they are keyed on one
    # graph rather than on a pair; being a field is what already clears them.
    #
    # Empty rather than built at boot. Both vocabulary lanes are paid for at start
    # because a thread is asked on every selection, so a lazy first call would stall the
    # reading loop; this is a page a session either opens or never does, and 108 ms warm
    # behind the click that asked for it is the right way round (rule 45).
    curiosities: dict[str, Any] = field(default_factory=dict)
    # The loops and decisions worth reading, on the same bargain as the curiosities
    # above: one pass over this version's graph, paid on the first ask and thrown away
    # with the base. 105 ms warm on Lictores for the judgement over 9,625 control points,
    # and a cold first ask is the external volume rather than the work (rule 24).
    algorithms: dict[str, Any] = field(default_factory=dict)


# What building a base costs, in the order it is paid, so a reader watching a switch is
# told where the ten seconds are going rather than watching a bar. Named here rather than
# inside `_Live.open` because the count has to be knowable before the work starts -- "step
# 4 of 6" needs the 6 up front, and a hand-counted 6 beside a six-branch function is two
# numbers about one thing (rule 32).
class NothingOpen(RuntimeError):
    """A route that needs a version on screen was reached with none.

    Two ways now, and it used to be one. It is still a route missing from
    `_Handler.NEEDS_BASE` -- a defect with a sentence, rather than a blank page with none --
    and since `/api/close` it is **also a race a reader can win**: `opened` goes true ->
    false for the first time in this tool's life, so a request that passed the route gate
    can reach `current` a moment after the base has gone.

    The old sentence said *"never a reader's doing"*, and closing a map is now exactly a
    reader's doing. Both are answered identically, by `_refuse_without_base`, because the
    right answer to *there is no base* does not depend on whose fault it is.
    """


def why(exc: BaseException) -> str:
    """A failed build, in words a reader can act on.

    `type(exc).__name__` earns its place in front of an `OSError` or a `ValueError`, which
    say little on their own. It is **noise** in front of the two exceptions written to be
    read: `StaleGraphError` and `UnfinishedMapError` are already whole sentences aimed at
    the person on the other side of the screen, and prefixing them with a class name puts a
    Python word first in the one place where the reader is not a programmer.
    """
    if isinstance(exc, StaleGraphError | UnfinishedMapError):
        return str(exc)
    return f"{type(exc).__name__}: {exc}"


BUILD_STEPS: tuple[str, ...] = (
    "opening the graph",
    "the 2.5D model and its payload",
    "the file list",
    "the naming standard, stated and derived",
    "the glossary",
    "the cover",
)


class _Clock:
    """How long since a switch began, and what each phase of it cost.

    **One spelling of a `perf_counter` and its `ms()`** (rule 51). There were two, in
    `switch_program` and in `switch`, and a third was about to be written -- which is
    where a rule kept at call sites goes: `switch_program` would have grown per-step
    timings and `switch` would not, and the one figure a reader could get would depend on
    whether they had changed program or revision to get there.

    **Why it exists at all.** `/api/program` on `Engine.Source.Runtime` reports `done`
    after **1,659,334 ms** -- 27.6 minutes for a map of 262,879 routines -- and the only
    evidence of where that went is which step label was most recent when it finished. That
    is not evidence: the last label before `done` is simply the last one sent, and reading
    a diagnosis off it is the plausible-diagnosis-of-a-real-symptom rule 39 was minted
    from. `BACKLOG.md` item 8 says so and offers none.

    `ms()` stays **cumulative**, which is what the client draws and what every existing
    caller means by it; the two banking methods record deltas. A client that misses a
    line still has a true cumulative figure, which a stream of deltas does not survive.

    **Two cursors, because a step's own row must not be the crumbs its parts left.** A
    step is timed from the last *step*, a lap from the last *anything* -- so
    `the 2.5D model and its payload` reports the whole of itself and the four `·` rows
    under it are a breakdown of that number rather than a competitor for it. Written the
    single-cursor way first and it read **0.0s** for a step that had just taken all four
    of the laps above it, which is a report that is arithmetically true and says the
    opposite of what happened.
    """

    __slots__ = ("_at", "_step_at", "_t0", "spent")

    def __init__(self) -> None:
        self._t0 = self._at = self._step_at = time.perf_counter()
        self.spent: list[tuple[str, int]] = []

    def ms(self) -> int:
        """Milliseconds since this began."""
        return round((time.perf_counter() - self._t0) * 1000)

    def lap(self, label: str) -> None:
        """Bank a part of the step in progress. Measured from the last lap of any kind."""
        now = time.perf_counter()
        self.spent.append((label, round((now - self._at) * 1000)))
        self._at = now

    def phase(self, label: str) -> None:
        """Bank a whole step. Measured from the last step, so it *contains* its laps."""
        now = time.perf_counter()
        self.spent.append((label, round((now - self._step_at) * 1000)))
        self._at = self._step_at = now


class _Live:
    """The read-only stores the dashboard queries while it is open.

    One sqlite connection per store, guarded by a lock. `ThreadingHTTPServer` hands each
    request to its own thread and a sqlite connection refuses to be used from a thread it
    was not created on, so the choice is a connection per thread or a lock -- and for a
    reading tool with one reader, contention is not a thing that happens. The lock is the
    smaller of the two mistakes to have made.

    **Every use of `current.store` happens under `self.lock`**, and that is load-bearing
    rather than tidy: it is what makes closing the outgoing store at a base switch safe.
    A request that took the store out from under the lock and used it afterwards would be
    using a connection the switch had already closed. A guard reads this off the source.

    Both stores are opened `writable=False`. Rule 20: serving may refuse, it may never
    repair, and it must never be able to damage the map it came to show.
    """

    # The caches keyed on a **pair** of versions, and therefore the ones a switch
    # invalidates: one end of every pair has just moved. Named here rather than cleared
    # one by one, so a third comparison cannot be added and half-wired (rule 36) -- both
    # `open()` and the guard that checks it read this list rather than restating it.
    #
    # What is deliberately *not* here is as load-bearing: `filepairs` and `findings` are
    # keyed on one thing each -- two snapshots of the one sidecar, and one graph file --
    # and neither becomes a different answer because a different version is on screen.
    # `findings` is also where the whole cost of the anomaly comparison lives, so
    # clearing it would make every switch pay four seconds to learn what it already knew.
    COMPARISON_CACHES: tuple[str, ...] = ("changes", "anomalypairs")

    # What a **program** switch clears, which is everything. Its own list rather than a
    # superset expression over the one above, because the two answer different questions
    # and a reader has to be able to see both answers at once: a revision switch keeps
    # `findings` and `filepairs` deliberately, and a program switch cannot.
    #
    # Not a judgement about staleness but about **keys**. `findings` is keyed on
    # `graph_db.name`, a basename that two program directories share; `filepairs` on a pair
    # of revision strings, which two unrevisioned directories both render as `("", "")`.
    # Neither collision needs a coincidence -- it is what the keys are. Rule 36 cuts both
    # ways here: a generic loop narrowed to a literal loses a feature silently, and a second
    # switch reusing the first switch's literal keeps a stale cache just as silently.
    PROGRAM_CACHES: tuple[str, ...] = ("changes", "anomalypairs", "filepairs", "findings")

    def __init__(self, source_db: Path, out_dir: Path,
                 out_root: Path | None = None, root_gone: str = "",
                 allow_unfinished: bool = False) -> None:
        self.lock = threading.Lock()
        # **The Setting "Unfinished maps", as the server's default** -- `--allow-unfinished`
        # on `serve` and `mcp`. A page sends its own on every switch, which wins; this is
        # what the boot and a request that says nothing get. Refusing is the default.
        self.allow_unfinished = allow_unfinished
        # **Why the root on screen is not the root the reader chose**, or `""` when it is.
        # A sentence rather than a flag, for the reason every refusal here is a sentence:
        # the page has to *say* which disk, and a boolean cannot (rule 89). Set once at
        # boot and never after -- reconnecting the disk is a restart, because the root is
        # the server's state and re-pointing it under a live reader is what `POST /api/root`
        # is for.
        self.root_gone = root_gone
        # The program directory, so a second point in time can be found. The graph being
        # served is one revision of it; every other revision is a file beside this one.
        self.out_dir = out_dir
        # **The output root, as a thing rather than as a derivation.** Three routes worked
        # it out for themselves as `out_dir.parent` -- the program list, the program
        # switch and the analysis -- which is right for as long as there is an `out_dir`
        # to take the parent of. A server opened on the root itself, with nothing yet to
        # serve, has none; and three copies of one derivation is where rule 51 says the
        # drift starts. Derived once here when nobody says, read everywhere.
        self.out_root = out_root or out_dir.parent
        # One computed diff per pair, keyed by (before, after). Lazily, unlike the two
        # vocabulary lanes: a thread is asked on every selection and a change list is
        # opened deliberately, so paying for it at boot would add seconds to a start that
        # is already 10 s and buy nothing for a reader who never opens the view.
        self.changes: dict[tuple[str, str], dict[str, Any]] = {}
        # The same, over the findings rather than over the facts, and cleared beside it
        # for the same reason. Note that the *expensive* half is not here: running the
        # detectors is held per graph in `findings` below, which a switch does not touch,
        # so re-pairing after one costs the pairing alone.
        self.anomalypairs: dict[tuple[str, str], dict[str, Any]] = {}
        # The file-level pairing, per pair of revisions. **Not cleared on a base switch**,
        # unlike `changes` above, and the difference is worth stating: a diff is keyed on
        # two graphs, which a switch replaces one of, while this is keyed on two snapshots
        # of the one sidecar -- and `source.db` is the store that is never rebuilt (rule
        # 25). The pairing of two revisions is the same fact before and after a switch.
        self.filepairs: dict[tuple[str, str], dict[str, Any]] = {}
        # The findings of one graph, keyed by that graph's filename. **Not cleared on a
        # base switch**, for `filepairs`' reason rather than `changes`': a diff is keyed
        # on two graphs and a switch replaces one of them, while this is keyed on one
        # graph -- and a graph file's findings are a property of the file. Switching away
        # and back re-serves them rather than recomputing.
        #
        # It exists because the findings are *computed*, not stored: thirteen detectors
        # over the graph, every time they are asked for. On the served graph, whose pages
        # the boot has already warmed, that is **62 ms** per request against 0.9 ms held
        # -- worth having and not the reason. The reason is the other end of a
        # comparison, which is a 31 MB file this process has never opened: **1.3 s to
        # 4.1 s** for the first pairing on Lictores, stated as a range because that is
        # what it is -- two runs of identical work, differing by how much of the file the
        # operating system still had. It is the disk as much as the work, which is the
        # caveat every other cold row in this project carries. Bounded by the number of
        # revisions a reader visits, which is the number of graphs in one directory.
        self.findings: dict[str, list[dict[str, Any]]] = {}
        # Both naming lanes read with a leading underscore allowed, which is a reader's
        # Setting rather than the default the base is built with. Keyed by revision and
        # lane, and filled the first time the page asks: a reader who never turns the
        # Setting on pays nothing for it.
        self.relaxed: dict[tuple[str, str], dict[str, Any]] = {}
        # A sidecar is optional by design -- `--no-source`, or a map handed over without
        # it. Absent is a state the inspector states plainly, never one it hides.
        #
        # It survives a base switch untouched: there is **one** `source.db` per program
        # directory holding every revision's bodies, content-addressed, so it is not a
        # thing a version owns. That is also why it is not a field of `_Base`.
        self.source: SourceStore | None = None
        self.source = self._open_source(source_db)

        # The **document** bodies, and the same posture for the same reasons: optional,
        # read-only, one per program, and outside `_Base` because it is not a thing a
        # version owns. Its own store rather than a lane in `source.db`, because design
        # rule 14 turns on documentation and source being separately handable -- a map can
        # arrive with either, both or neither, and each absence is stated.
        #
        # `DocSourceStore` rather than `SourceStore`, and that is load-bearing rather than
        # decorative: the two have identical schemas, so nothing but the kind stamp could
        # tell this open from opening `source.db` by mistake, and rule 16 refuses it by
        # name.
        self.docsource: DocSourceStore | None = None
        self.docsource = self._open_docsource(out_dir / "docsource.db")

        # **The imported standard, per program and not per revision.** `standards.db` sits
        # beside `docsource.db` for the same reason and with the same lifetime: it belongs
        # to the program, not to a point in its history. Absent is the ordinary case -- most
        # maps are made without `--standards` -- and the difference between *absent* and
        # *present but empty* is carried to the page rather than inferred there.
        self.standards: DocStore | None = self._open_standards(out_dir / STANDARDS_DB)

        # Filled by `open()`, which every caller goes through -- boot included. **`None`
        # is now a real state**, and it is the state a packaged application starts in: a
        # double-clicked DunneFlow has no argument and, on a fresh machine, no map, so the
        # server binds a port and serves the start page instead of refusing to exist.
        #
        # Reached through `current` rather than directly, and that is the whole of how
        # sixty use sites stayed as they were. The property **raises** with nothing open,
        # because with the start page in front of a reader the shell never boots without a
        # base -- so a route asking is a defect and gets a sentence, where a `None` handed
        # back would arrive as an `AttributeError` several frames later, or worse, as an
        # empty payload that looks exactly like a version with nothing in it (rule 49).
        self._base: _Base | None = None

        # What a switch is doing, for the reader watching it. Behind its own lock, never
        # `self.lock`: the whole point of a progress report is answering *while* the big
        # work runs, and a poll that queued behind the rebuild would report nothing until
        # there was nothing left to report.
        self.build_lock = threading.Lock()
        self.build: dict[str, Any] = {"state": "idle"}

        # **A second slot, and it is not the build slot.** A switch replaces what is on
        # screen; an analysis replaces nothing -- it reads some other tree into some other
        # directory, and every number the reader is looking at stays true throughout. So
        # the two must not contend: one slot would mean a ninety-second read of an
        # unrelated program locking a reader out of changing versions, for no reason
        # anybody could state.
        #
        # Its own pair of fields rather than a second key in `build`, for `PROGRAM_CACHES`'
        # reason (rule 36): the two answer different questions and a reader has to be able
        # to see both answers at once. Behind its own lock, for `build_lock`'s -- a poll
        # that queued behind the work would report nothing until there was nothing left to
        # report.
        self.analysis_lock = threading.Lock()
        self.analysis: dict[str, Any] = {"state": "idle"}
        # **The running child itself, because a label is not a fact (rule 30).** The slot
        # used to be held by `analysis["state"] == "working"` alone, which is true for ever
        # if the watching thread dies without saying so -- and there was no way to stop a
        # run either, because the handle was a local inside `analysis.run`. Holding it
        # answers both: the claim asks whether anything is actually alive, and `stop` has
        # something to signal.
        self.analysis_proc: Any = None
        # **And whether the slot is claimed at all, because the child is not the first
        # thing that exists.** `analysis_running` asked `analysis_proc.poll()` and nothing
        # else, so between `claim_analysis` returning and `on_start` handing the child over
        # -- a thread start and a `Popen`, but a window all the same -- the slot read as
        # free and a second analysis claimed it too. Measured, not feared: two
        # `claim_analysis` calls in a row both return `True`, the report ends up describing
        # the second, and the first child is then unreachable because `analysis_proc` has
        # been overwritten -- so it cannot be stopped and it is writing into the same
        # output root as the one that displaced it.
        #
        # **This is a claim and not a label, which is the distinction rule 30 draws here.**
        # A label is set by somebody describing the work; this is released by the watching
        # thread *ending*, in a `finally` it cannot skip, so it cannot outlive the thing it
        # names -- including when that thread dies without noting, which is the jam the
        # process question was added for. The process question stays beside it: claimed
        # with a child that has exited is still a stale lock and is still cleared.
        self.analysis_claimed = False
        # The program directory whose terminal-started run the panel is following.
        self.terminal_dir: Path | None = None

    # -- the one door onto a version -------------------------------------- #

    def open(self, graph_db: Path,
             step: Any = None, clock: _Clock | None = None,
             allow_unfinished: bool | None = None) -> None:
        """Make `graph_db` the base: build everything from it, then swap it in.

        The same method at boot and at a switch, deliberately. A second builder would be
        two ways to produce one thing, and the day they disagree the map on screen after a
        switch is not the map `serve` would have shown for that version (rule 51).

        **Built outside the lock, committed inside it.** Nothing here touches the live
        base until the last three statements, so the ten seconds of work cost other
        requests nothing and a failure costs them nothing at all: the new store is private
        to this thread until it is committed, and on any exception it is closed and the
        reader keeps the map they had. That is rule 20's shape applied to a swap -- a
        switch may refuse, it may never leave a broken base behind.
        """
        # **The one choke point all six steps pass through, so the timing is here.** The
        # step *before* this one is what has just finished, which is the only phase whose
        # cost is known at the moment a label changes; the last one is banked at the end.
        # Six numbers instead of a label, which is the whole of `BACKLOG.md` item 8's
        # *what would settle it*.
        clock = clock or _Clock()

        def _step(i: int) -> None:
            if i:
                clock.phase(BUILD_STEPS[i - 1])
            if step is not None:
                step(BUILD_STEPS[i], i, len(BUILD_STEPS))

        _step(0)
        # A graph written by an older DunneFlow refuses to open rather than being
        # repaired (rule 20), and `revisions.known` will list it as comparable regardless
        # -- so this is a real outcome of a real switch, not a defensive branch.
        store = Store(graph_db, writable=False, shared=True)
        # **A map that never finished being written is refused here**, before anything is
        # built from it and before anything is swapped. It opens perfectly -- that is the
        # whole problem: one killed twelve seconds into the Comitia tree reports 4,786
        # routines and *no internal calls at all*, over a timestamp and a determinism
        # guarantee. Closed by hand rather than by the `try` below, which does not start
        # until the build does.
        #
        # **Unless the reader's Setting says to open it with a warning.** `None` is "the
        # request did not say", which is the server's default and not a choice. The
        # sentence is read either way, before anything can close the store it comes from.
        allowed = self.allow_unfinished if allow_unfinished is None else allow_unfinished
        unfinished = ""
        try:
            if allowed and store.finished() == "":
                unfinished = unfinished_sentence(self.out_dir.name,
                                                 store.get_meta("step") or "")
            else:
                store.refuse_if_unfinished(self.out_dir.name)
        except BaseException:
            store.close()
            raise
        revision = revisions.revision_of(graph_db) or ""
        source_revision = self._sidecar_revision(self.source, revision)
        docsource_revision = self._sidecar_revision(self.docsource, revision)
        # Named before the `try` so the failure path can close it. It is opened inside,
        # several steps in, and a build that raises after that point must not leave a 148
        # MB store behind for a switch the reader never got.
        docs: DocStore | None = None
        try:
            _step(1)
            payload = build_payload(store, self.out_dir.name, clock=clock)
            root = root_package(store)
            clock.lap("· the root package")

            _step(2)
            files = build_files(store, self.source, revision=source_revision)

            _step(3)
            # Documentation is optional by design (design rule 11): with no `docs.db` the
            # glossary keeps every code-derived term and loses only the tier that quotes a
            # document. It is never a prerequisite for a code-derived fact. Per revision,
            # because a version's documents are that version's.
            #
            # **It used to be closed right here, and now the base holds it.** The close was
            # not caution: one held across a switch leaked a 148 MB store every time the
            # reader moved between two versions, which is a thing they do often. Held on
            # `_Base` the leak is answered rather than avoided -- the swap below closes the
            # outgoing one, and the failure path a few lines down closes this one -- and
            # the document list has the live handle it cannot be served without.
            #
            # **Opened a step earlier than it used to be**, because the naming standard has
            # two lanes and one of them is quoted out of these documents. Building the
            # derived lane under a step called "the naming standard" while the stated lane
            # waited for the glossary's store would be a step that names one thing and does
            # half of it (rule 32) -- and the reader watches these go past.
            docs = self._docs_for(graph_db)
            naming = measure_naming(store)
            stated = stated_naming(docs)
            checked = checked_naming(store, docs, self.standards)

            _step(4)
            glossary = bind_glossary(store, docs)

            _step(5)
            defined, total = glossary["coverage"]
            cover = build_cover(store, self.source, self.out_dir.name,
                                revision=source_revision, vocabulary={
                                    "conventions": len(naming["conventions"]),
                                    "stated": len(stated["rules"]),
                                    # How many rules were actually *measured*, not how many
                                    # exist: the navigator row is a count of answers, and a
                                    # row reading 16 beside a page that could check 4 would
                                    # promise twelve findings that are not there (rule 32).
                                    "checked": checked["summary"]["checked"],
                                    "terms": total,
                                    "defined": defined,
                                })
        except BaseException:
            store.close()
            if docs is not None:
                docs.close()
            raise

        fresh = _Base(graph_db=graph_db, store=store, revision=revision,
                      source_revision=source_revision,
                      docsource_revision=docsource_revision, payload=payload, root=root,
                      files=files, naming=naming, stated=stated, checked=checked,
                      glossary=glossary,
                      docs=docs,
                      unfinished=unfinished,
                      cover=cover,
                      # The default under its own key, and the *same object*: `payload` and
                      # `payloads[default_level()]` are one truth with an index over it.
                      payloads={default_level(): payload},
                      # Empty, for the diagrams' reason on the next line: the solve is about
                      # a second and a reader who never leaves *by size* must never pay it
                      # (rule 45). The route fills one key on first ask.
                      plate_orders={},
                      # Empty rather than built: fifty-three diagrams cost a model build,
                      # and a session that never opens Diagram mode must not pay for it at
                      # every switch. The route fills all three on first ask, together --
                      # the index is derived from the compartments, so a base carrying one
                      # without the other would place this version's crossings in the last
                      # version's boxes.
                      compartments={}, box_of={}, box_label={}, curiosities={}, algorithms={})
        # The sixth, which no later `_step` can bank. Before the swap rather than after
        # it: what the reader waited for is the build, and the swap is three statements
        # under a lock.
        clock.phase(BUILD_STEPS[-1])
        with self.lock:
            outgoing = self._base
            self._base = fresh
            # Every cached diff is keyed on a pair one end of which has just moved. Not a
            # stale copy of this answer -- an answer to a different question (rule 51).
            for cache in self.COMPARISON_CACHES:
                getattr(self, cache).clear()
            # Safe here and nowhere else: every use of a base's store is under this lock,
            # so no request can be holding this connection.
            if outgoing is not None:
                outgoing.store.close()
                # The document store goes with it, for the same reason and under the same
                # lock. A version's documents are that version's, so leaving this open
                # would be the 148 MB per-switch leak the old close was written against --
                # moved, not removed.
                if outgoing.docs is not None:
                    outgoing.docs.close()

    def _sidecar_revision(self, sidecar: SourceStore | None,
                          revision: str) -> str | None:
        """Which revision of one sidecar's bodies this version can be read at, or nothing.

        The graph's own revision when the sidecar holds it. A legacy bare `graph.db` has
        no revision to claim, and a sidecar written before revisions existed maps its
        paths under the empty id -- so falling through to `current_revision()` there is
        the *same* answer arrived at honestly, not a substitute for one we could not get.

        A named revision the sidecar does not hold is `None`, and every reader shows that
        as an absence. It is the one case where guessing would be silent and wrong: the
        newest snapshot's bytes under an older version's map look exactly like a file, and
        the marks in the margin land on whatever line has since moved under them.

        **Takes the store rather than reading `self.source`**, because there are two of
        them now and this is the whole of the rule for both. Left at the call site it
        would have been copied for the document sidecar, and the copy would have been
        right on the day it was written -- rule 51's shape exactly. The two stores answer
        differently often enough to matter: `--no-doc-source` on one run and not the next
        parts them.
        """
        if sidecar is None:
            return None
        if revision and sidecar.holds_revision(revision):
            return revision
        if revision:
            return None
        return sidecar.current_revision()

    def _docs_for(self, graph_db: Path) -> DocStore | None:
        """The document store captured beside this graph, or nothing at all."""
        rev = revisions.revision_of(graph_db)
        docs_db = (revisions.db_path(self.out_dir, revisions.DOCS, rev) if rev
                   else revisions.newest(self.out_dir, revisions.DOCS))
        if docs_db is None or not docs_db.exists():
            return None
        try:
            # `shared`, like every other store this server holds: the base keeps this one
            # alive and `ThreadingHTTPServer` reads it from a request thread, where sqlite
            # refuses a connection made on another one -- from the request, by name, and
            # only for the routes that touch it. Every read is under `_Live.lock`, which
            # is the lock the flag makes the caller responsible for.
            return DocStore(docs_db, writable=False, shared=True)
        except (ValueError, OSError):
            return None

    # -- what a switch is doing, for whoever is watching ------------------- #

    def claim(self, revision: str) -> bool:
        """Take the build slot, or say it is taken.

        Test and set inside one hold of the lock. Two requests arriving together must not
        both start a ten-second rebuild -- and the second one must be *told* it was
        refused rather than appearing to have worked (design rule 1).
        """
        with self.build_lock:
            if self.build.get("state") == "working":
                return False
            self.build = {"state": "working", "revision": revision,
                          "step": BUILD_STEPS[0], "done_steps": 0,
                          "steps": len(BUILD_STEPS), "ms": 0}
            return True

    @staticmethod
    def _open_source(path: Path) -> SourceStore | None:
        """The code sidecar, or nothing. Absent is a real state, never an error.

        Lifted out of `__init__` when a **program** switch arrived, because a program's
        sidecars are that program's: the boot and the switch have to open them the same
        way or the two paths drift, and the way that drifts first is the `try` (rule 51).
        """
        if not path.exists():
            return None
        try:
            return SourceStore(path, writable=False, shared=True)
        except (ValueError, OSError):
            return None

    @staticmethod
    def _open_standards(path: Path) -> DocStore | None:
        """The imported standard, or nothing at all.

        A `DocStore` because a standard *is* documents -- the same scanner read it, and a
        second store type would be a second answer to what a document is (rule 51). What
        keeps it from being mistaken for the corpus is the file it lives in, never a flag.
        """
        if not path.exists():
            return None
        try:
            return DocStore(path, writable=False, shared=True)
        except (ValueError, OSError):
            return None

    @staticmethod
    def _open_docsource(path: Path) -> DocSourceStore | None:
        """The document sidecar. `DocSourceStore`, never `SourceStore` -- see rule 16."""
        if not path.exists():
            return None
        try:
            return DocSourceStore(path, writable=False, shared=True)
        except (ValueError, OSError):
            return None

    def switch_program(self, out_dir: Path, name: str,
                       allow_unfinished: bool | None = None) -> None:
        """Serve a different **program**. Runs on its own thread, like `switch`.

        The same shape as a revision switch and a wider blast radius, and the difference is
        the whole of this method. A revision switch replaces the base; the sidecars, the
        output directory and two of the four caches survive it because they belong to the
        *program* rather than to the version. A program switch is the case where that stops
        being true.

        **Every cache goes**, and the two that survive a revision switch are the reason this
        cannot reuse `COMPARISON_CACHES`:

        * `findings` is keyed on `graph_db.name` -- a **basename**. `output/lictores/
          graph@X.db` and `output/dunneflow/graph@X.db` key identically, so one program's
          anomaly findings would be served for the other, confidently and wrongly.
        * `filepairs` is keyed on a pair of revision strings, and an unrevisioned program
          directory yields `("", "")`. Two of those key identically as well.

        Neither collision needs an unlikely coincidence; both are what the keys *are*.

        **The old program stays whole if this fails.** Nothing is closed or repointed until
        `open()` has returned a base built from the new directory -- so a stale program, a
        missing graph or a schema bump leaves the reader looking at what they had, with the
        store's own sentence in the progress report. That is `open()`'s own rule (20) and
        the reason the build happens before the swap rather than after it.
        """
        clock = _Clock()
        ms = clock.ms

        def step(label: str, i: int, n: int) -> None:
            self.note(state="working", revision=name, program=name, step=label,
                      done_steps=i, steps=n, ms=ms(), spent=list(clock.spent))

        graph_db = revisions.newest(out_dir, revisions.GRAPH)
        if graph_db is None:
            self.note(state="failed", revision=name, program=name, steps=len(BUILD_STEPS),
                      ms=ms(), reason=f"{name} holds no graph to read")
            return

        # Opened before anything is closed, and *not* stored on `self` until it succeeds.
        # A sidecar opened into the field and then abandoned by a failed build is a handle
        # on a program nobody is serving.
        source = self._open_source(out_dir / "source.db")
        docsource = self._open_docsource(out_dir / "docsource.db")
        standards = self._open_standards(out_dir / STANDARDS_DB)
        was = (self.out_dir, self.source, self.docsource, self.standards)
        try:
            (self.out_dir, self.source, self.docsource,
             self.standards) = out_dir, source, docsource, standards
            self.open(graph_db, step, clock, allow_unfinished)
        except Exception as exc:                  # noqa: BLE001 -- a report, not a swallow
            (self.out_dir, self.source, self.docsource, self.standards) = was
            # **All three, and `standards` was missing from both of these lists.** It was
            # added to `was` and to the swap when `--standards` arrived and to neither of
            # the closes, so every program switch leaked one `standards.db` handle on the
            # way past -- silently, because a leaked read-only SQLite handle costs nothing
            # a reader can see until the process has done it a few hundred times. The
            # sidecars are a set of three; anything that enumerates two of them is a list
            # that has fallen behind the tuple above it (rule 36).
            for opened in (source, docsource, standards):
                if opened is not None:
                    opened.close()
            # **Which failure it is, as a field.** The page offers *Analyse it again* on
            # this one and nothing on the others, and deciding that by reading the reason
            # would make a sentence written for a reader into a wire format (rule 30).
            self.note(state="failed", revision=name, program=name, steps=len(BUILD_STEPS),
                      ms=ms(), reason=why(exc),
                      unfinished=isinstance(exc, UnfinishedMapError))
            return

        # After the swap, never before: a failed build above must leave the outgoing
        # program's sidecars open, because it is still the one being served.
        with self.lock:
            for cache in self.PROGRAM_CACHES:
                getattr(self, cache).clear()
        for old in was[1:]:
            if old is not None:
                old.close()
        self.note(state="done", revision=name, program=name, step="",
                  done_steps=len(BUILD_STEPS), steps=len(BUILD_STEPS), ms=ms(),
                  spent=list(clock.spent))

    def close_program(self) -> None:
        """Put the server back to having nothing open, so `/` is the start page again.

        **`switch_program` with no destination**, and that framing decides everything below.
        A program switch repoints `out_dir`, swaps three sidecars and empties every cache
        that is keyed on something a program owns; this does the same, to nothing. So it
        clears `PROGRAM_CACHES` for exactly `switch_program`'s stated reasons -- `findings`
        keyed on a **basename** and `filepairs` on `("", "")` -- because after a close the
        next thing opened may be any program under the root, including one whose graph file
        is named identically to the one just closed.

        **Named `close_program`, never `close`.** `_Live.close` is the process going away
        and leaves an object nobody may use again; this leaves one that is fully usable and
        merely empty. Two methods of one name where only one of them is recoverable is
        rule 16's mistake -- opening a thing as the wrong kind -- moved onto a lifetime.

        **Rule 20 applies, but not in its usual direction, and the difference is worth
        stating.** `open()` builds before it swaps so that a failure leaves the reader with
        what they had. Closing builds nothing and cannot fail, so what survives of that rule
        is the other half: *unpublish before you shut*. `_base` is dropped and the fields
        are emptied **before** any handle is closed, so no request can ever reach a store
        that is reachable and shut -- which is the one race this method could otherwise
        introduce, and it is why the whole swap is a single hold of `self.lock` rather than
        `switch_program`'s two. That method closes outside the lock because it has just
        spent ten seconds building and has already repointed; four `close()` calls are
        microseconds and buy nothing by being let out.

        **The analysis is not touched -- not the process, not the slot, not the report.**
        Rule 82: a slot names what is being replaced, and an analysis of some other tree
        into some other directory replaces nothing here. A reader going back to the start
        page has not cancelled their ninety-second read, and `start.js` already carries the
        panel across by asking `/api/analysis` at boot.
        """
        t = time.perf_counter()
        with self.lock:
            # Unpublished first. Everything below this line is unreachable by any request
            # that is not already inside `self.lock`, which is the invariant the class
            # docstring names and `tests/test_base_switch.py` guards.
            outgoing, self._base = self._base, None
            was = (self.source, self.docsource, self.standards)
            self.source = self.docsource = self.standards = None
            # `out_dir == out_root` is what `where()` returns for a directory holding no
            # map, and what `serve()` tests to decide it is cold. Restoring it is what makes
            # this a *return* to the start state rather than a base-shaped hole.
            self.out_dir = self.out_root
            for cache in self.PROGRAM_CACHES:
                getattr(self, cache).clear()
            if outgoing is not None:
                outgoing.store.close()
                if outgoing.docs is not None:
                    outgoing.docs.close()
            for old in was:
                if old is not None:
                    old.close()
        # **`steps=0`, not `len(BUILD_STEPS)`.** A close pays none of the six build steps,
        # and six-of-six would be a count of work that never happened (rule 32). `_r_base`
        # already answers `base: ""` honestly from here -- no version is on screen.
        self.note(state="done", revision="", program="", step="",
                  done_steps=0, steps=0, ms=round((time.perf_counter() - t) * 1000))

    def switch(self, graph_db: Path, revision: str,
               allow_unfinished: bool | None = None) -> None:
        """Make `graph_db` the base, reporting each step. Runs on its own thread.

        A failure is **reported**, never raised into a thread nobody is reading. The
        reader asked for a switch and is watching a progress report; a rebuild that ends
        by writing a traceback to the terminal and leaving the report saying "working"
        for ever is the same defect as a spinner that never stops.
        """
        clock = _Clock()
        ms = clock.ms

        def step(name: str, i: int, n: int) -> None:
            self.note(state="working", revision=revision, step=name,
                      done_steps=i, steps=n, ms=ms(), spent=list(clock.spent))

        try:
            self.open(graph_db, step, clock, allow_unfinished)
        except Exception as exc:                  # noqa: BLE001 -- see the docstring:
            self.note(state="failed", revision=revision,   # this is a report, not a swallow
                      steps=len(BUILD_STEPS), ms=ms(), reason=why(exc))
            return
        self.note(state="done", revision=revision, step="",
                  done_steps=len(BUILD_STEPS), steps=len(BUILD_STEPS), ms=ms(),
                  spent=list(clock.spent))

    def analysis_running(self) -> bool:
        """Is an analysis *actually* running -- asked of the claim and of the child.

        `state == "working"` is a **label**, and a label outlives the thing it names: a
        watcher that dies without noting leaves it true for ever, and nothing short of
        restarting the server could then start another analysis. So the report's own word
        is not consulted here at all (rule 30).

        **Two questions, and either one alone gets a real case wrong.** *Is the slot
        claimed* is the only thing true from the instant somebody takes it -- the child
        does not exist yet, and asking the child alone let a second analysis in through
        that window. *Has the child exited* is the only thing that clears a claim whose
        watcher died. `claimed and (no child yet or the child is alive)` is the conjunction
        that answers both, and it is not a superset of either (rule 36).

        The claim is released by the watching thread's own `finally`, so *no child yet* is
        bounded by a thread start rather than by hope -- see `start_analysis`, which is the
        only place a claim is taken and the only place one is released.

        Caller holds `analysis_lock`.
        """
        if not self.analysis_claimed:
            return False
        proc = self.analysis_proc
        return proc is None or proc.poll() is None

    def claim_analysis(self, name: str) -> bool:
        """Take the analysis slot, or say it is taken. `claim`'s shape, its own slot.

        One analysis at a time, because two reading into the same output root can collide
        on a directory -- and because the panel shows one. The loser is **told**, never
        answered as though its own run were the one now going (design rule 1).

        **The refusal is the process's, not the report's.** A report still saying `working`
        over a child that has gone is a stale lock, and it is *cleared here* rather than
        left for somebody to notice -- which is the difference between a slot and a jam.

        **Rule 82** — a long job is not a switch. This slot sits beside `claim` rather than
        sharing it because a base switch replaces what is on screen and an analysis of some
        other tree replaces nothing; the map stays true for the whole run. And it asks the
        process rather than a label (rule 30), which is the *"or locked"* half.
        """
        with self.analysis_lock:
            if self.analysis_running():
                return False
            self.analysis_claimed = True
            self.analysis_proc = None
            self.terminal_dir = None    # a run started here replaces any ending on show
            self.analysis = {"state": "working", "program": name, "step": "",
                             "done_steps": 0, "steps": 0, "detail": "",
                             # Both stamped now and only `moved` bumped afterwards, so the
                             # panel can say *how long it has been running* and *how long it
                             # has been silent* -- two different questions, and the second is
                             # the one that tells a hang from a long step.
                             "began": time.time(), "moved": time.time()}
            return True

    def start_analysis(self, name: str, *, source: Path, out_root: Path, docs: bool,
                       run: Any = analysis.run, inventory: str | None = None) -> bool:
        """Claim the slot and start the run. `False` means the slot was taken.

        **One place, because there were two and they were the same eleven lines** -- the
        dialog's `_p_analyze` and the MCP session's `analyze`, each claiming the slot,
        each defining its own `hold`, each starting its own thread on `analysis.run`. Two
        copies of one procedure is where rule 51 says the drift starts, and the drift that
        was already there is the point: whatever either of them did about a claim that
        never became a child, it had to do twice.

        **The claim is released in a `finally` around the whole run**, which is what makes
        `analysis_running`'s *claimed* half safe to trust. Every exit from `analysis.run`
        already ends in a terminal report -- it reports rather than raising, deliberately
        -- but *already* is not *always*, and a claim released by anything less than the
        thread ending is a claim that can outlive it. That is the jam, and the whole reason
        the slot asks the process at all (rule 30).

        `run` is an argument on `analysis.run`'s own precedent, so a test can hold a slot
        open without racing a real analysis.
        """
        if not self.claim_analysis(name):
            return False

        def hold(proc: Any) -> None:
            with self.analysis_lock:
                self.analysis_proc = proc

        def work() -> None:
            try:
                run(source=source, name=name, out_root=out_root, docs=docs,
                    note=self.note_analysis, on_start=hold, inventory=inventory)
            finally:
                with self.analysis_lock:
                    self.analysis_claimed = False

        thread = threading.Thread(target=work, name=f"dunneflow-analyze-{name}",
                                  daemon=True)
        try:
            thread.start()
        except RuntimeError:
            # A thread that could not be started is a claim nobody will ever release, and
            # it would hold the slot for the life of the server. Given back here rather
            # than reported: the caller is about to say the analysis did not start, and it
            # did not.
            with self.analysis_lock:
                self.analysis_claimed = False
            raise
        return True

    def stop_analysis(self) -> tuple[bool, str]:
        """End the running analysis. Returns whether there was one, and what happened.

        The map it was writing marked itself unfinished as it started, so there is nothing
        to clean up here and nothing this process could write if there were (rule 20).

        **Three answers rather than two**, because *nothing is running* and *it is running
        and I stopped it* do not cover the instant between a claim and its child. Signalling
        a `None` would be an exception where a sentence belongs, and reporting *nothing is
        running* over a claimed slot would be a refusal the reader can see is false --
        there is a panel on their screen saying it started (design rule 21).
        """
        with self.analysis_lock:
            own = self.analysis_running()
        if not own:
            other = runstate.running_under(revisions.programs_under(self.out_root))
            if other is None:
                return False, "no analysis is running"
            # Outside the lock for the reason given below: up to six seconds of waiting.
            said = analysis.stop_pid(int(other.get("pid") or 0))
            return True, f"{other.get('program', '')}: {said}"
        with self.analysis_lock:
            if not self.analysis_running():
                return False, "no analysis is running"
            if self.analysis_proc is None:
                return False, ("the analysis is still starting — ask again in a moment")
            proc, name = self.analysis_proc, self.analysis.get("program", "")
        # Outside the lock: `terminate` then up to six seconds of waiting, and a progress
        # poll must not queue behind it -- the reader pressed Stop and is watching to see
        # whether it worked.
        said = analysis.stop(proc)
        return True, f"{name}: {said}"

    def note_analysis(self, **fields: Any) -> None:
        """Replace the analysis report. Whole, never field by field -- see `note`.

        **`began` and `moved` are carried across, and `moved` only bumps when something
        actually changed.** A timestamp refreshed on every identical report would say a run
        was moving because it was being watched, which is the one thing a silence detector
        must not do -- and silence is exactly what tells a hang from a long step. Resolution
        on the Comitia tree is quiet for tens of seconds and is perfectly healthy.

        **`residue` is carried across too, and that is a term of `--progress-json`'s
        contract rather than a convenience here.** The child sends what the walk left out
        **once**, the moment it knows, because the fact is fixed and the steps after it are
        many; replacing the report whole would then wipe it on the very next line and the
        panel would show it for a fraction of a second. Carried, it is still there when the
        run says `done`, which is when a reader actually reads it. A fresh claim replaces
        `self.analysis` outright, so a new run starts with no residue rather than
        inheriting the last one's.
        """
        with self.analysis_lock:
            was = self.analysis
            fresh = dict(fields)
            fresh["began"] = was.get("began", time.time())
            if "residue" not in fresh and "residue" in was:
                fresh["residue"] = was["residue"]
            # `residue` is in the list because its *arrival* is something happening --
            # and only its arrival, since it compares equal on every line it is carried
            # across. Left out, the one moment the walk reports what it left out would
            # register as silence.
            #
            # **`ms` is deliberately not in it and must never be added.** The child stamps
            # every line with how long the run has taken, so `ms` differs on every line by
            # construction -- putting it here would make `moved` bump because a clock
            # moved, and a run would report itself as progressing for as long as it was
            # being watched. That is the exact failure this list exists to prevent, and
            # silence is what tells a hang from a long step.
            changed = any(was.get(k) != fresh.get(k)
                          for k in ("state", "step", "done_steps", "detail", "residue"))
            fresh["moved"] = time.time() if changed else was.get("moved", time.time())
            self.analysis = fresh

    def analysis_progress(self) -> dict[str, Any]:
        """The report, plus the two elapsed times, plus whether it is *really* running.

        `running` is the process's answer beside the report's own word, deliberately: they
        agree until a watcher dies, and the pane that has to explain a refusal is the one
        that needs to know they have stopped agreeing.
        """
        with self.analysis_lock:
            own = self.analysis_running()
            out = dict(self.analysis)
        if not own:
            # **A run this server did not start**, found by the sidecar it writes (see
            # `runstate`). Asked only while this server's own slot is idle, so a run the
            # reader started here is never displaced by one somebody started in a terminal,
            # and kept on once it is being shown, so the panel watching it sees it end --
            # `done`, or stopped without finishing -- rather than the idle report replacing
            # it mid-poll.
            other = self._terminal_run()
            if other is not None:
                return other
        with self.analysis_lock:
            now = time.time()
            if "began" in out:
                out["running_for"] = round(now - float(out["began"]), 1)
                out["silent_for"] = round(now - float(out.get("moved", now)), 1)
            out["running"] = own
            return out

    def _terminal_run(self) -> dict[str, Any] | None:
        """The live run in this root that some other process started, in the panel's shape.

        **Once one has been shown, its ending is shown too, for `runstate.ENDED_S`.** A panel
        polls for the end, and the end has to still be there when it asks. This reported the
        ending *once*, and the browser found what that costs: pressing Stop holds the stop
        route for its grace period while the panel keeps polling, so the one report of
        *stopped* went to a poll the panel was not listening to, and every poll after it got
        the idle report -- a panel stuck on *"asking the server…"* over a run that had
        ended. A window rather than a count, then. It cannot re-raise a panel on a reload,
        because `resumeAnalysis` only picks up a run that is running, and a claim here clears
        it (see `claim_analysis`).
        """
        watching = self.terminal_dir
        if watching is not None:
            body = runstate.read(watching)
            if body is not None and (body["running"]
                                     or time.time() - float(body.get("beat") or 0)
                                     <= runstate.ENDED_S):
                return runstate.as_progress(body)
            self.terminal_dir = None
        body = runstate.running_under(revisions.programs_under(self.out_root))
        if body is None:
            return None
        self.terminal_dir = self.out_root.resolve() / str(body.get("program") or "")
        return runstate.as_progress(body)

    def note(self, **fields: Any) -> None:
        """Replace the progress report. Whole, never field by field.

        A half-updated report is a state the reader can be shown -- "the glossary" beside
        a step count from the previous step -- and it costs one dict to make impossible.
        """
        with self.build_lock:
            self.build = dict(fields)

    @property
    def opened(self) -> bool:
        """Is there a version on screen at all?

        The one question a server with nothing open can answer about itself, and the one
        the route gate asks. Separate from `current` on purpose: *is there a base* and
        *give me the base* are different questions, and a single accessor answering both
        with `None` is how the second one gets asked by accident.
        """
        return self._base is not None

    @property
    def current(self) -> _Base:
        """The version everything on screen is about. **Raises with nothing open.**

        Sixty-odd routes read this, every one of them behind the gate in `_Handler` that
        refuses before they are reached -- so arriving here with no base is a defect in
        that list rather than a state a reader can produce. Refusing loudly is what makes
        the gate's list checkable: an empty `_Base` handed back instead would let a route
        drop off the list and answer with a confident, empty, entirely wrong page.
        """
        base = self._base
        if base is None:
            raise NothingOpen(
                "nothing is open — this server was started on an output root rather than "
                "on a program, and no program has been opened yet")
        return base

    def progress(self) -> dict[str, Any]:
        with self.build_lock:
            return dict(self.build)

    def close(self) -> None:
        if self._base is not None:
            self._base.store.close()
            if self._base.docs is not None:
                self._base.docs.close()
        if self.source is not None:
            self.source.close()
        if self.docsource is not None:
            self.docsource.close()
        if self.standards is not None:
            self.standards.close()


def said_residue(stored: str | None) -> dict[str, Any]:
    """`said()`'s three states for a field that holds a **list**.

    Its own function rather than a branch inside `said`, because the two differ in what
    *nothing* looks like: a scalar's nothing is a word this layer knows (`none`, or
    blank), and a list's is an empty list. One function testing both would be answering
    two questions with one shape, and the day a third field arrives it would answer a
    third.

    **Refused rather than guessed when the stored text will not parse.** A key that
    holds something other than a JSON list was written by something this build does not
    understand, and reporting it as *nothing was left out* would be a plausible value
    standing in for a failure (rule 49). It reads as *not recorded*, which is the true
    statement: this map cannot say.
    """
    if stored is None:
        return {"recorded": False, "lines": [], "none": False}
    try:
        lines = json.loads(stored)
    except ValueError:
        return {"recorded": False, "lines": [], "none": False}
    if not isinstance(lines, list) or not all(isinstance(x, str) for x in lines):
        return {"recorded": False, "lines": [], "none": False}
    return {"recorded": True, "lines": lines, "none": not lines}


CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self' data:; worker-src 'self' blob:; "
    # `data:` and `blob:` under connect-src are deck.gl's: it reads its own generated
    # textures back through `fetch`, and the graph drew nothing selected without them.
    "connect-src 'self' data: blob:; object-src 'none'; base-uri 'none'; form-action 'none'; "
    "frame-ancestors 'none'"
)


class _Handler(BaseHTTPRequestHandler):
    """Static files and the JSON endpoints, routed from a table.

    A table rather than an `if`/`elif` chain, because design rule 16 was written after
    eight of eleven controls silently did the wrong thing: a chain ends in a fallback,
    and a fallback that looks deliberate is indistinguishable from a route that works.
    An unknown path here fails loudly and by name.
    """

    server_version = "DunneFlow"
    # The interpreter's version is nobody's business who has not opened the page.
    sys_version = ""

    def __init__(self, *args: Any, live: _Live, **kw: Any) -> None:
        # The base is not held here. It used to be -- the payload arrived as a
        # constructor argument, from a local in `serve()` -- and that was one truth in two
        # places the moment a base could be switched. `_Live.current` owns every part of
        # a version and is swapped whole, so a handler reads it and never caches it.
        self._live = live
        super().__init__(*args, **kw)

    def log_message(self, fmt: str, *args: Any) -> None:
        return                                    # a reading tool is not a web log

    # -- the table --------------------------------------------------------- #

    def _r_index(self, q: dict[str, list[str]]) -> None:
        """The page, and **which page depends on whether there is anything to show.**

        The shell is an application about one version of one program: a navigator counting
        its routines, a cover, a stack, an inspector. There is no honest way to draw it
        over nothing, and drawing it empty would be forty panes each having to say why they
        are blank -- design rule 21 in the place it applies least well, because the answer
        is the same for all of them and the reader has not asked any of the questions yet.

        So a server with nothing open serves a page whose *whole job* is to say there is
        nothing yet, and to offer the two things that can be done about it: open one of the
        programs that are here, or read a new tree. Once a base exists the shell is what
        `/` means, and it never has to boot without one.
        """
        self._file(STATIC / ("index.html" if self._live.opened else "start.html"))

    def _r_start(self, q: dict[str, list[str]]) -> None:
        """The start page, whatever is open. **A second address, never a second answer.**

        `_r_index` decides *which page is `/`*, and its docstring plus `start.js`' own
        comment insist that decision lives on the server and nowhere else. This does not
        duplicate it -- it declines to make it. Asked for the start page, it serves the
        start page; `/` is untouched, so there is still exactly one place deciding what a
        reader sees when a base is open (rule 51).

        **Why it earns a route.** Design rule 20's closing line -- *nothing may strand the
        reader off-screen with no way back* -- and the way back has to survive the shell
        being unusable. A control inside `shell.js` cannot help a reader whose `shell.js`
        has thrown; a URL they can type can. That is the whole justification, and it is why
        this is four words long and reads no state at all.

        **It does not close anything.** The temptation is real -- an escape hatch reads as
        *get me out* -- but a GET that tears down the base is precisely what `POST_ROUTES`
        exists to prevent: a prefetch, a bookmark reload or a link preview would drop the
        reader's map, and unlike a switch there would be nothing left on screen to show that
        anything had happened. This page *shows* the state and offers the gesture; the
        reader performs it, as a POST.
        """
        self._file(STATIC / "start.html")

    def _r_graph(self, q: dict[str, list[str]]) -> None:
        """The stack, at the altitude asked for.

        Two levels of one model, never two models: `?level=module` folds each file into one
        node and each boundary kind into one, which takes Lictores from 10,015 nodes to 578
        without dropping a single fact -- every folded node says what it stands for. It is a
        second way to look at the same program, so both are cached side by side and the
        reader moves between them.

        Built **under the lock**, unlike a base switch, and the difference is which store it
        reads. A switch opens its own private connection and can therefore build outside the
        lock; this one reads `current.store`, and every use of that is under the lock or a
        request could be querying a connection a switch has already closed. So the first
        climb to a level holds the lock for the ~120 ms it takes -- worth writing down as
        the cost it is rather than leaving as a claim the code contradicts.
        """
        try:
            key = read_level(q)
        except ValueError as exc:
            # A status rather than a JSON body with a reason in it, which is what the
            # routes that can partly answer do. There is no partial stack: a payload the
            # page cannot draw is worse than none, and `ensureGraph` reads this message.
            self.send_error(400, str(exc))
            return
        with self._live.lock:
            base = self._live.current
            payload = base.payloads.get(key)
            if payload is None:
                level, min_disk = key
                payload = build_payload(base.store, self._live.out_dir.name,
                                        level=level, min_disk=min_disk)
                base.payloads[key] = payload
        self._json(payload)

    def _r_plate(self, q: dict[str, list[str]]) -> None:
        """One plate of the stack, described as the thing it is.

        **The same level the picture is at.** A plate that exists at routine level may be
        merged into `<small>` at module level, and vice versa, so answering from the
        default payload would describe a plate the reader is not looking at -- and would
        do it plausibly, which is the expensive kind of wrong. `read_level` is `/api/graph`'s
        own reader, so an unknown level is refused here exactly as it is there rather than
        quietly defaulted (design rule 16 in a query string).

        Built under the lock and cached beside the others, for `_r_graph`'s reason: this
        reads `current.store`, and every use of that is under the lock or a request could
        be querying a connection a switch has already closed. A plate asked for at a level
        nobody has drawn yet pays that climb once and the picture that follows is free,
        which is the right way round: the reader who asks about a plate is about to look
        at it.

        **The climb is not `_r_graph`'s ~120 ms on a program this size.** Measured on
        Lictores, 2026-09-05: `build_payload` takes **1.31 s** for 15,870 drawn nodes over
        53 plates on a warm store, and 10.0 s on the first open of a cold one -- the
        external volume and nothing else, per `PERFORMANCE.md`. Written down rather than
        inherited, because a figure taken on a smaller program and repeated here would be
        a claim nobody had measured.
        """
        plate_id = (q.get("id") or [""])[0]
        if not plate_id:
            self._json({"found": False, "reason": "no id asked for"})
            return
        try:
            key = read_level(q)
        except ValueError as exc:
            self.send_error(400, str(exc))
            return
        with self._live.lock:
            base = self._live.current
            payload = base.payloads.get(key)
            if payload is None:
                level, min_disk = key
                payload = build_payload(base.store, self._live.out_dir.name,
                                        level=level, min_disk=min_disk)
                base.payloads[key] = payload
            # `waysin.listing()` rather than a query of this route's own, because there is
            # one answer to what a way in is and four surfaces read it (rule 51). Asked
            # here rather than cached on `_Base`: it is fourteen rows on the largest
            # program measured, the compartments already pay for it separately, and a
            # third cache of the same list is a third thing a switch has to remember.
            body = plate.describe(base.store, payload, plate_id,
                                  ways_in_listing(base.store))
        self._json(body)

    def _compartments(self) -> dict[str, Any]:
        """Every compartment of the base, built once and cached whole.

        One owner, because there are two routes into it now -- the drawing and the box a
        reader clicked -- and the list of callers is the thing that grows (rule 51). A
        second copy of this would build the model twice on a cold base and, worse, could
        answer the two routes from two different passes.
        """
        with self._live.lock:
            base = self._live.current
            if not base.compartments:
                level, min_disk = default_level()
                model = build(base.store, level=level, min_disk=min_disk)
                # Filled in place, never reassigned: `_Base` is frozen so that a switch
                # replaces every field together, and the payload cache above earns its
                # mutability the same way.
                # **The ways in, folded in on the way past.** `waysin.listing()` is the
                # one place that question is asked (rule 51) -- the cover row, the way-in
                # pane and the diagram all read the same answer, so a way in cannot be
                # declared on one surface and guessed on another. Built here rather than
                # held on `_Base`, because the compartments are the only thing that wants
                # it and they are already cached whole.
                entered: dict[str, list[str]] = {}
                for w in ways_in_listing(base.store):
                    for node_id in w["nodes"]:
                        names = entered.setdefault(node_id, [])
                        if w["name"] not in names:
                            names.append(w["name"])
                base.compartments.update(diagram.build(model, entered))
                by_node, by_box = diagram.box_index(base.compartments)
                base.box_of.update(by_node)
                base.box_label.update(by_box)
            return base.compartments

    def _r_fold(self, q: dict[str, list[str]]) -> None:
        """One box of a diagram, described as the thing it stands for.

        **A box is a fold, not a node**, and that distinction is the defect this route
        exists to fix. Clicking one used to select `members[0]` and let `/api/node` answer,
        so a box labelled `KernelDecl` holding sixty-one methods filled the inspector with
        `KernelDecl._profile_name_or_none` -- a true answer about something nobody clicked
        (rule 32: the answer must be about the thing that was asked).

        The stack has always been honest about this: picking a *plate* clears the selection
        rather than nominating a member of it. What was missing was not honesty but an
        answer, and `detail.fold` gives one in the same shape every other specimen uses, so
        the inspector renders it through the path that already exists.

        A port is refused rather than described. It is a place, not a thing in this
        compartment -- a click on one flips the book, which is a different act with its own
        handler, and describing it here would be inventing a subject for a stand-in
        (rule 23).
        """
        box_id = (q.get("id") or [""])[0]
        if not box_id:
            self._json({"found": False, "reason": "no id asked for"})
            return
        found = diagram.find_box(self._compartments(), box_id)
        if found is None:
            self._json({"found": False, "id": box_id,
                        "reason": "no such box in this diagram"})
            return
        comp, box = found
        if box.kind == "port":
            self._json({"found": False, "id": box_id,
                        "reason": "a port stands for another compartment, not for "
                                  "anything in this one"})
            return
        with self._live.lock:
            base = self._live.current
            body = detail_fold(base.store, diagram.box_payload(box),
                               diagram.flow_of(comp, box_id),
                               self._live.source, revision=base.source_revision)
        self._json(body)

    def _inside_compartment(self, box_id: str, box: diagram.Box) -> diagram.Compartment:
        """A fold's own routines as a compartment. **The one place that builds one.**

        Two routes want it now -- the drawing of the second level, and the flow behind an
        arrow on that drawing -- and a second copy of these five queries would be a second
        answer to what is inside a box the moment either is edited (rule 51).

        Not cached, and that is rule 45's own argument: a compartment is fifty-three
        drawings from one pass and is built with the others, a box is one of nine thousand
        and is built when someone opens it. Three grouped queries over indexed columns,
        measured at 15 ms for eighteen routines and 170 ms for sixty-one.
        """
        args = {"ids": json.dumps(list(box.members))}
        with self._live.lock:
            base = self._live.current
            rows = base.store.query
            members = [dict(r) for r in rows(queries.FOLD_MEMBERS, args)]
            inner = [dict(r) for r in rows(queries.FOLD_INNER_CALLS, args)]
            out = [dict(r) for r in rows(queries.FOLD_CALLS_OUT, args)]
            into = [dict(r) for r in rows(queries.FOLD_CALLS_IN, args)]
            touches = [dict(r) for r in rows(queries.FOLD_BOUNDARIES, args)]
            box_of, box_label = dict(base.box_of), dict(base.box_label)
        for t in touches:
            t["weight"] = 1
        return diagram.build_inside(box_id, box, members, inner, out, into, touches,
                                    box_of, box_label)

    def _r_flow(self, q: dict[str, list[str]]) -> None:
        """One arrow, opened: what actually passes between two boxes.

        `from` and `to` are box ids; `inside` names the fold when the arrow is on the
        second level, and is absent on the first. The two levels are two different
        compartments and an edge id alone cannot say which -- a routine box id is a node
        id and a first-level box id is `plate|kind|key`, so guessing from the shape would
        be reading an identity out of a string (rule 30).

        Answered on demand, which is rule 45 where it belongs: the cost is bounded by the
        reader opening **one** arrow, not by the picture drawing a hundred and fifteen of
        them.

        An arrow that is not in the compartment is `found: false` and says so. An empty
        panel would claim the arrow carries nothing, which is a different and false thing.
        """
        src_id = (q.get("from") or [""])[0]
        dst_id = (q.get("to") or [""])[0]
        inside = (q.get("inside") or [""])[0]
        if not src_id or not dst_id:
            self._json({"found": False, "reason": "an edge has two ends and needs both"})
            return

        comps = self._compartments()
        if inside:
            found = diagram.find_box(comps, inside)
            if found is None or found[1].kind == "port" or not found[1].members:
                self._json({"found": False, "id": inside,
                            "reason": "no such box to be inside of"})
                return
            comp = self._inside_compartment(inside, found[1])
        else:
            comp = comps.get(src_id.partition("|")[0])  # type: ignore[assignment]
            if comp is None:
                self._json({"found": False, "reason": "no such compartment"})
                return

        by_id = {b.id: b for b in (*comp.boxes, *comp.ports, *comp.entries)}
        src, dst = by_id.get(src_id), by_id.get(dst_id)
        if src is None or dst is None:
            self._json({"found": False, "id": diagram.edge_id(src_id, dst_id),
                        "reason": "one end of that arrow is not in this drawing"})
            return
        edge = diagram.edge_flow(comp, src_id, dst_id)
        if edge is None:
            self._json({"found": False, "id": diagram.edge_id(src_id, dst_id),
                        "reason": "there is no arrow between those two boxes"})
            return
        kinds, weight = edge

        # **An entry arrow has no call sites, and says so rather than answering emptily.**
        # `/api/flow` opens an arrow by listing every call site with the arguments as
        # written; a way in is started by the operating system, so there is no caller in
        # this program to list. An empty panel would read as *"this arrow carries nothing"*,
        # which is a different and false claim (design rule 21, and the same distinction
        # `edge_flow` draws between no arrow and an empty one).
        if src.kind == "wayin":
            self._json({
                "found": False, "id": diagram.edge_id(src_id, dst_id),
                "reason": f"{src.label} is a way in — the program is started here, so there "
                          f"is no call site to open. It starts {weight} routine"
                          f"{'' if weight == 1 else 's'} in "
                          f"{dst.label}; open the way in to see everything it can run.",
                "wayin": src.label,
            })
            return

        with self._live.lock:
            store = self._live.current.store
            body = detail_flow(store, edge=diagram.edge_id(src_id, dst_id),
                                    src=diagram.box_payload(src),
                                    dst=diagram.box_payload(dst),
                                    kinds=kinds, weight=weight)
        body["found"] = True
        body["inside_of"] = inside
        self._json(body)

    def _r_inside(self, q: dict[str, list[str]]) -> None:
        """One box, opened: the routines it holds and the flow among them.

        **The second level of the same picture, not a second picture.** It comes back in
        exactly the shape `/api/diagram` returns -- `dot`, `mermaid`, `by_id`, `names` and
        the same stats -- so the page draws it with the code that already draws a
        compartment, and a fix to one is a fix to both.

        Asked on demand and never cached. A compartment is fifty-three drawings built in one
        pass, so building them together is the cheap way round; a *box* is one of nine
        thousand, and building all of them to answer a double-click would be rule 45 exactly.
        Three grouped queries over indexed columns is what it costs instead.

        A box holding nothing the store has a routine for -- a boundary cylinder -- is
        refused rather than drawn empty: a blank picture is indistinguishable from a thing
        that genuinely holds nothing, and this level has none of those.
        """
        box_id = (q.get("id") or [""])[0]
        if not box_id:
            self._json({"found": False, "reason": "no id asked for"})
            return
        found = diagram.find_box(self._compartments(), box_id)
        if found is None:
            self._json({"found": False, "id": box_id,
                        "reason": "no such box in this diagram"})
            return
        _, box = found
        if box.kind == "port" or not box.members:
            self._json({"found": False, "id": box_id,
                        "reason": "a port stands for another compartment, and a boundary "
                                  "is the bottom of the flow -- neither opens"})
            return

        c = self._inside_compartment(box_id, box)
        ports = (q.get("ports") or ["0"])[0] == "1"
        roles = c.roles()
        self._json({
            "id": c.id, "name": c.name, **c.stats,
            "inside_of": box_id, "plate": box_id.partition("|")[0],
            "dot": diagram.dot(c, ports=ports),
            "portsDrawn": ports,
            "mermaid": diagram.mermaid(c),
            # `role` rides here so a hover card can say it in words -- the drawing already
            # carries it as a class, and a colour a reader cannot name is one they have to
            # guess at (design rule 1). **Boxes only**: a port stands for another
            # compartment and a way in is the world outside reaching in, so neither has a
            # part in this compartment's own flow. Taken once rather than per box, because
            # `roles()` walks four lanes and a comprehension would walk them per row.
            "by_id": {b.id: {"label": b.label, "kind": b.kind, "holds": b.holds,
                             "members": b.members,
                             **({"role": roles[b.id]} if b.id in roles else {}),
                             **b.detail}
                      for b in c.boxes + c.ports + c.entries},
            # Every arrow, keyed by the id `dot()` wrote on it, so a hover over one costs
            # no request. Rule 45's own argument in the other direction: the answer rides
            # with the picture because it is already computed, and only the *contents* of
            # an arrow -- the call sites and their arguments -- wait to be asked for.
            "edges": diagram.edge_payload(c),
            "names": {nid: lbl
                      for b in c.boxes
                      for nid, lbl in zip(b.members, b.labels, strict=True)},
            "found": True,
        })

    def _r_diagram(self, q: dict[str, list[str]]) -> None:
        """A compartment as a diagram, or the list of compartments there are.

        With no `id`, the index: every compartment and what it holds, so the reader can
        choose one without fetching fifty-three diagrams to find out. With an `id`, that
        compartment's **DOT** -- which is what the browser draws, with Graphviz -- and its
        **Mermaid**, which is the same graph in a form a reader can paste into another tool.
        Both come from one `Compartment`, so the picture and the export cannot describe
        different graphs (rule 13).

        An unknown id is a 404 and never an empty diagram. `graph.py` merges small packages
        into `pkg:<small>`, so an id that is a real package and not a real plate exists; a
        blank picture would be indistinguishable from a compartment that genuinely holds
        nothing, and this program has none of those.

        Built once per base and cached whole. The fold is a single pass over a model that
        costs a couple of seconds to construct, and every compartment comes out of that one
        pass -- so building "just this one" would be building all of them and throwing
        fifty-two away.
        """
        comps = self._compartments()

        wanted = (q.get("id") or [""])[0]
        if not wanted:
            self._json({"compartments": [
                {"id": c.id, "name": c.name, **c.stats}
                for c in sorted(comps.values(), key=lambda c: (-c.stats["boxes"], c.name))]})
            return
        c = comps.get(wanted)
        if c is None:
            self.send_error(404, f"no compartment {wanted!r}")
            return
        roles = c.roles()
        self._json({
            "id": c.id, "name": c.name, **c.stats,
            # Ports off unless asked for: see `diagram.dot` for the measurement. The page
            # states the crossing count either way, so what is not drawn is never silent.
            "dot": diagram.dot(c, ports=(q.get("ports") or ["0"])[0] == "1"),
            "portsDrawn": (q.get("ports") or ["0"])[0] == "1",
            "mermaid": diagram.mermaid(c),
            # What each box stands for, so a click on the drawing resolves to something this
            # program knows about rather than to a shape (rule 30). Keyed by the id Graphviz
            # writes into the SVG, which is the box id itself.
            #
            # **`by_id`, not `boxes`.** It was `boxes` for one run, and `**c.stats` already
            # carries a `boxes` *count* -- so the map silently overwrote the number and the
            # page would have read a count off an object. One key meaning two things is
            # rule 32 in a payload, and it is invisible because both halves are real.
            # `role` rides here so a hover card can say it in words -- the drawing already
            # carries it as a class, and a colour a reader cannot name is one they have to
            # guess at (design rule 1). **Boxes only**: a port stands for another
            # compartment and a way in is the world outside reaching in, so neither has a
            # part in this compartment's own flow. Taken once rather than per box, because
            # `roles()` walks four lanes and a comprehension would walk them per row.
            "by_id": {b.id: {"label": b.label, "kind": b.kind, "holds": b.holds,
                             "members": b.members,
                             **({"role": roles[b.id]} if b.id in roles else {}),
                             **b.detail}
                      for b in c.boxes + c.ports + c.entries},
            # What each member is called, so a hover card can name what a box holds rather
            # than counting it. Sent with the diagram rather than fetched per hover: it is a
            # few hundred short strings against a request per box, and a card that is
            # complete the moment it appears has nothing to wait for.
            #
            # `strict=True`: the two lists are appended in one place in one loop, so a
            # mismatch is impossible today and would silently truncate every box after it
            # if that ever stopped being true.
            # Every arrow, keyed by the id `dot()` wrote on it, so a hover over one costs
            # no request. Rule 45's own argument in the other direction: the answer rides
            # with the picture because it is already computed, and only the *contents* of
            # an arrow -- the call sites and their arguments -- wait to be asked for.
            "edges": diagram.edge_payload(c),
            "names": {nid: lbl
                      for b in c.boxes
                      for nid, lbl in zip(b.members, b.labels, strict=True)},
        })

    def _r_packages(self, q: dict[str, list[str]]) -> None:
        """The overview altitude: every package as a box, and what passes between them.

        Built per request rather than at startup. It is two aggregations over indexed
        columns, the payload is a few kilobytes, and most sessions never open it -- caching
        it would trade a measurable startup cost for a saving nobody can perceive.
        """
        with self._live.lock:
            self._json(packages.build(self._live.current.store))

    def _r_cover(self, q: dict[str, list[str]]) -> None:
        """The first screen. Built once per base -- see `cover.py`."""
        with self._live.lock:
            self._json(self._live.current.cover)

    def _r_routines(self, q: dict[str, list[str]]) -> None:
        """Every routine and every structure, with the package the stack puts each on.

        The navigator used to read this off `/api/document?id=routines`, which was right
        while a routine row needed only a name and an id. Grouping the list by package needs
        the package, and there are two expressions for one in this dashboard -- so it comes
        from the one the *plates* use, and a package heading in the list is the plate in the
        picture rather than a second thing spelled the same way.

        On demand rather than with the cover: 4,734 rows is a real payload and a session
        that reads only the overview never asks for it.
        """
        # Both under one lock, and one read of `current`: the rows and the plates are two
        # halves of one answer, so taking them from two different bases -- which is what a
        # switch landing between them would do -- is rule 13 in a payload.
        with self._live.lock:
            base = self._live.current
            rows = [dict(r) for r in base.store.query(
                queries.NAV_ROUTINES, pkg_params(base.root))]
            # The structures, riding with the routines because both are wanted at the same
            # moment: the navigator lists them and the topbar search filters them, and both
            # happen at boot. 671 rows against 4,786 is a seventh of the weight, where a
            # second request would be a whole second round trip for it.
            structures = [dict(r) for r in base.store.query(
                queries.NAV_STRUCTURES, pkg_params(base.root))]
            # Which packages actually have a plate. `graph.py` merges any package below
            # `MIN_DISK` into `pkg:<small>`, so 47 packages become 45 plates -- and a list
            # row offering `pkg:_version` would be selecting a plate that is not in the
            # stack. `queries.py` wrote down why that is the wrong fix before anything
            # needed it: inventing an id to make a row clickable is a link to nothing.
            plates = [d["id"] for d in base.payload["disks"]
                      if d["id"].startswith("pkg:")]
        self._json({"routines": rows, "structures": structures, "plates": plates})

    def _r_anomalies(self, q: dict[str, list[str]]) -> None:
        """The worklist. Separate from the cover, which carries only the counts.

        The findings are large -- every one carries its detail and its blind spot -- and
        most sessions read the counts without ever opening the list. Sending them with
        the cover would put that weight behind the first paint of every map.

        Held per graph rather than recomputed. This route ran all thirteen detectors on
        every request, under the lock, for an answer that cannot change while the served
        file does not: 62 ms a time on Lictores, against 0.9 ms held. Small, and the same
        cache is what makes the comparison affordable, where the other end is a graph
        nothing has opened.
        """
        rows, reason = self._findings(self._live_graph())
        if rows is None:
            self._json({"findings": [], "available": False, "reason": reason})
            return
        self._json({"findings": rows})

    def _live_graph(self) -> Path:
        """Which graph is being served, read once under the lock.

        A switch landing between two reads would have one caller asking about two
        different versions, which is the trap `_r_changes` names at its own first read.
        """
        with self._live.lock:
            return self._live.current.graph_db

    def _findings(self, graph_db: Path) -> tuple[list[dict[str, Any]] | None, str]:
        """One graph's findings, from the cache or by running the detectors.

        `None` and a reason, never an empty list, when the graph cannot be read: a stale
        or wrong-kind store **refuses** (rules 16 and 20), and "no findings" and "we could
        not look" are opposite claims that render identically (rules 49 and 63).

        Two paths, and the difference is rule 58. Where this is the graph the dashboard is
        serving, the detectors run on the connection already holding it open -- a second
        read-only handle to a file this process has open in WAL mode cannot share the
        `-shm` index and re-derives it per query. Where it is not, it is a file nothing
        here holds, so an ordinary read-only open is the cheap path and it is closed
        again. The lock is held across the served build for the reason `_r_changes` holds
        it: that connection belongs to every other request too. Measured on Lictores: 62
        ms on the served graph, 1.3-4.1 s on the other one, which is a 31 MB file being
        read for the first time -- a range, because it is mostly the disk.
        """
        key = graph_db.name
        with self._live.lock:
            held = self._live.findings.get(key)
        if held is not None:
            return held, ""

        rows: list[dict[str, Any]]
        with self._live.lock:
            if graph_db == self._live.current.graph_db:
                rows = build_anomalies(self._live.current.store)
                self._live.findings[key] = rows
                return rows, ""
        try:
            other = Store(graph_db, writable=False)
        except (StaleGraphError, ValueError, OSError) as exc:
            return None, str(exc)
        try:
            rows = build_anomalies(other)
        finally:
            other.close()
        with self._live.lock:
            self._live.findings[key] = rows
        return rows, ""

    def _r_documents(self, q: dict[str, list[str]]) -> None:
        """What document mode can show."""
        from .documents import index
        self._json({"documents": index()})

    def _r_document(self, q: dict[str, list[str]]) -> None:
        """One document, whole, every row carrying its graph node id."""
        from .documents import build as build_doc
        doc_id = (q.get("id") or [""])[0]
        with self._live.lock:
            self._json(build_doc(self._live.current.store, doc_id))

    def _r_node(self, q: dict[str, list[str]]) -> None:
        """Everything the inspector shows about one node."""
        node_id = (q.get("id") or [""])[0]
        if not node_id:
            self._json({"found": False, "reason": "no id asked for"})
            return
        with self._live.lock:
            base = self._live.current
            body = describe(base.store, node_id, self._live.source,
                            revision=base.source_revision)
        self._json(body)

    def _r_hover(self, q: dict[str, list[str]]) -> None:
        """The compact card behind the pop-up.

        Separate from `/api/node` rather than a slice of it, because the two answer
        different questions and cost different amounts. `/api/node` returns every caller,
        every callee, every comment and a span of source -- right for something the reader
        has chosen, wildly wrong for something the cursor is passing over on its way
        somewhere else.
        """
        node_id = (q.get("id") or [""])[0]
        if not node_id:
            self._json({"found": False, "reason": "no id asked for"})
            return
        with self._live.lock:
            body = hover_card(self._live.current.store, node_id)
        self._json(body)

    def _r_threads(self, q: dict[str, list[str]]) -> None:
        """The reasons a neighbour is worth a detour, for one node.

        The subject's module comes out of the store here rather than being asked for by
        the client: an outlier thread is scoped to the package the reader is standing on,
        and a module supplied from outside is a parameter that can disagree with the id
        beside it. There is one right answer and the store has it.
        """
        node_id = (q.get("id") or [""])[0]
        if not node_id:
            self._json({"found": False, "reason": "no id asked for", "threads": []})
            return
        with self._live.lock:
            row = self._live.current.store.query(
                "SELECT module, name FROM routines WHERE id = :id", {"id": node_id})
            module = str(row[0]["module"]) if row else ""
            name = str(row[0]["name"]) if row else ""
            body = for_node(self._live.current.store, node_id,
                            module=module, root=self._live.current.root, name=name,
                            naming=self._live.current.naming, glossary=self._live.current.glossary)
        self._json(body)

    def _r_thread(self, q: dict[str, list[str]]) -> None:
        """What one thread's subject resolves to.

        Only cohorts come here. A thread whose subject is already a node needs nothing
        resolved -- it is selected as itself -- and asking the server about it would be
        a round trip to be told what the client already knew.
        """
        kind = (q.get("kind") or [""])[0]
        key = (q.get("key") or [""])[0]
        if not kind or not key:
            self._json({"found": False, "nodes": [],
                        "reason": "a thread needs both a kind and a key"})
            return
        with self._live.lock:
            body = cohort(self._live.current.store, kind, key)
        self._json(body)

    def _r_curiosities(self, q: dict[str, list[str]]) -> None:
        """The doorway panel: what came out furthest from the middle, program-wide.

        Held on the base and computed on the first ask. 140 ms warm on Lictores for all
        twelve measures -- 106 ms when there were ten; the first ask of a session is the
        external volume reading a 28 MB graph and is 1.7 s, which is the caveat every
        other cold row in this product carries and not a property of the queries.

        `/api/threads` answers the same family of questions about *one node's* package.
        This is the whole program, which is a different panel and a different bargain:
        that one is asked on every selection and so is paid for at boot, this one is
        asked when a reader opens it.
        """
        with self._live.lock:
            base = self._live.current
            if not base.curiosities:
                # Filled in place rather than reassigned, exactly as the compartments and
                # the payloads are: `_Base` is frozen so a switch replaces every field
                # together, and these have to go with it.
                base.curiosities.update(for_program(base.store))
            body = base.curiosities
        self._json(body)

    def _r_algorithms(self, q: dict[str, list[str]]) -> None:
        """ALGORITHMS: the loops and decisions this program is worth reading for.

        Held on the base and computed on the first ask, for `_r_curiosities`' reason and
        with the same arithmetic behind it: a session either opens this page or never
        does, and 96 ms behind the click that asked for it is the right way round
        (rule 45).
        """
        with self._live.lock:
            base = self._live.current
            if not base.algorithms:
                # Filled in place rather than reassigned: `_Base` is frozen so a switch
                # replaces every field together, and this has to go with it.
                base.algorithms.update(lanes_for_program(base.store))
            body = base.algorithms
        self._json(body)

    def _r_shape(self, q: dict[str, list[str]]) -> None:
        """One routine's whole shape: every span it holds, and what moves inside them.

        **Answered on demand and held on nothing**, which is `/api/flow`'s bargain one
        subject over (rule 45): the bound is the reader opening one routine. The whole
        program's judgement is a base-held page (`/api/algorithms`); this is 9,625 points
        narrowed to the twenty in front of somebody, and caching it would be keeping an
        answer that costs less to make than to remember.

        A node that is not a routine is a **refusal with a sentence**, not an empty
        ribbon: a fold, a boundary and a table are all selectable and none of them has a
        shape of its own, and a blank pane would say the routine had none (design
        rule 21).
        """
        node = (q.get("node") or [""])[0]
        if not node:
            self._json({"found": False, "reason": "nothing is selected"})
            return
        with self._live.lock:
            self._json(outline_for(self._live.current.store, node))

    def _r_plateorder(self, q: dict[str, list[str]]) -> None:
        """Which order to stack the plates in, so a crossing does not have to travel far.

        **On demand, and held on the base** -- `/api/graph`'s bargain rather than
        `/api/shape`'s. The two halves of rule 45 pull opposite ways here: the solve is a
        second of work, so it must not be at boot for a reader who never asks; and the
        answer is a fact about *this version at this altitude*, identical for everyone who
        asks it, so throwing it away would charge the second again on every toggle between
        two orders the reader is comparing.

        **The model is rebuilt rather than read off the payload**, which looks like waste
        and is not. `build()` at a level costs ~120 ms against the ~1,000 ms solve, and the
        payload is columnar with edges as *indices* -- so deriving the plate pairs from it
        means a second reading of what an edge is, in a second place, for a number printed
        beside the first (rule 51). `plateorder.weights()` reads `GraphModel` and nothing
        else, and is the one place a crossing is counted.

        `read_level` is `/api/graph`'s own, so an unknown level is refused with a 400 here
        exactly as it is there and `minDisk` is clamped the same way -- one reading of the
        question, not two that can drift (rule 51). `grouped` defaults to false because the
        interleaved order is the one that answers the question asked; a reader who wants the
        bands held says so.
        """
        try:
            level, min_disk = read_level(q)
        except ValueError as exc:
            self.send_error(400, str(exc))
            return
        grouped = (q.get("grouped") or [""])[0] in ("1", "true", "yes")
        key = (level, min_disk, grouped)
        with self._live.lock:
            base = self._live.current
            answer = base.plate_orders.get(key)
            if answer is None:
                model = build(base.store, level=level, min_disk=min_disk)
                answer = plate_answer(model, grouped=grouped)
                base.plate_orders[key] = answer
        self._json(answer)

    def _r_macros(self, q: dict[str, list[str]]) -> None:
        """What the program's macros do, and with `?def=` one definition's places. Built once
        per revision: the report is several scans of the larger tables, on a route a reader
        returns to, and it cannot change under a revision."""
        with self._live.lock:
            live = self._live
            wanted = (q.get("def") or [""])[0]
            if wanted:
                self._json(macro_places(live.current.store, wanted))
                return
            key = (live.current.revision, "macros")
            if key not in live.relaxed:
                live.relaxed[key] = macro_report(live.current.store)
            self._json(live.relaxed[key])

    def _r_naming(self, q: dict[str, list[str]]) -> None:
        """The Form lane: what this program does about names, counted.

        `?underscore=1` is the reader's Setting that a leading underscore marks privacy
        rather than breaking a spelling. Answered from its own memo, never by rebuilding
        the base, so the default the navigator counted stays the default."""
        with self._live.lock:
            if _relaxed(q):
                self._json(self._relaxed_lane("naming"))
            else:
                self._json(self._live.current.naming)

    def _relaxed_lane(self, lane: str) -> dict[str, Any]:
        """One naming lane with a leading underscore allowed, built once per revision.

        Called under `self._live.lock`, which is what makes the memo safe to fill."""
        live = self._live
        key = (live.current.revision, lane)
        if key not in live.relaxed:
            live.relaxed[key] = (
                measure_naming(live.current.store, private_prefix=True) if lane == "naming"
                else checked_naming(live.current.store, live.current.docs, live.standards,
                                    private_prefix=True))
        return live.relaxed[key]

    def _r_reldocs(self, q: dict[str, list[str]]) -> None:
        """Which of the program's own documents have anything to do with this node.

        **On demand, per selection.** `traceability.measure()` answers the same question for
        the whole program in 4.7 s, which is right for a report and wrong for a click; this
        pair of queries is 6.8 ms, measured over 100 routines. It borrows that module's
        `normalise` and nothing else (rule 51).

        A node that carries no governance id gets `ids: []` and a sentence -- 59% of
        Lictores' routines, so it is the common case rather than the edge, and an empty list
        with no reason would read as *"nothing was found"* instead of *"there is nothing to
        find"* (design rule 21).
        """
        node = (q.get("node") or [""])[0]
        if not node:
            self._json({"found": False, "reason": "no node was named"})
            return
        with self._live.lock:
            base = self._live.current
            self._json({**related_documents(base.store, base.docs, node), "node": node})

    def _r_wayin(self, q: dict[str, list[str]]) -> None:
        """One way in, opened: what starts it, and everything it can run.

        **Answered on demand, because a way in is only sometimes a tree.** A single-routine
        way in needs nothing this does not already have on the cover; a command tree costs a
        recursive walk per mounted sub-application -- 22 of them on Lictores -- and a reader
        who never clicks one must not pay for it at every boot (rule 45).

        The name is the identity because the name is what the row printed and the cover has
        no other. A name that matches nothing is a refusal with a sentence, never an empty
        tree: an empty tree reads as an application with no commands, which is a different
        and false claim (design rule 21).
        """
        name = (q.get("name") or [""])[0]
        if not name:
            self._json({"found": False, "reason": "no way in was named"})
            return
        # `inside` names a sub-application to open instead of the whole tree. Refused by
        # `describe` unless it is genuinely mounted under this way in -- an id from the page
        # is a parameter, not a permission, and one taken as given would render any app
        # object in the store under any way in's heading.
        inside = (q.get("inside") or [""])[0]
        with self._live.lock:
            self._json(describe_way_in(self._live.current.store, name, inside))

    def _r_stated(self, q: dict[str, list[str]]) -> None:
        """The stated lane: the naming rules this project's documents contain.

        Its own route rather than a key on `/api/naming`, because it is its own page: what
        the code was found to do and what somebody wrote down about it are two claims, and
        the one word that keeps them apart on the derived page is *derived*. A reader who
        never opens this page should not pay for it either.

        **`corpus` is what makes "Read it in the document" a capability rather than a
        hope.** Every rule here names a document and a line, and the hop into that document
        needs `docsource.db` to hold the version on screen -- which is a fact about this
        process and this base, not about the rules, so it rides on the route exactly as the
        glossary's `sidecars` block does and for the same stated reason. Without it the
        button would render on a map with no document sidecar and do nothing, which is
        design rule 16's defect with a citation attached.
        """
        with self._live.lock:
            base = self._live.current
            self._json({**base.stated, "corpus": _sidecar_state(
                self._live.docsource, base.docsource_revision,
                absent=NO_DOC_SIDECAR)})

    def _r_checked(self, q: dict[str, list[str]]) -> None:
        """The comparison: every stated rule, against the population it governs.

        Its own route for the reason `_r_stated` is its own route, one step further on. The
        derived page counts and quotes nobody; the stated page quotes and counts nothing;
        this one does both and is *labelled* as doing both, which is the only arrangement
        that keeps a measured number from being read as somebody's rule or the reverse.

        Built at boot with the other two rather than on demand, and for the same reason:
        it is the same two stores already open, and a lazy first call would put a full
        population scan in the reading loop the first time anyone opened the page.
        """
        with self._live.lock:
            if _relaxed(q):
                self._json(self._relaxed_lane("checked"))
            else:
                self._json(self._live.current.checked)

    def _r_glossary(self, q: dict[str, list[str]]) -> None:
        """The Vocabulary lane: the program's words and who says what they mean.

        **The `sidecars` block is what makes a citation's button a capability test rather
        than a provenance test.** Design rule 13 says every reported meaning must carry its
        provenance and the provenance must open; which of them *can* open is a fact about
        this program's directory and this base's revision, and the page has no other way to
        learn it -- `/api/docs` carries the document half but is a 546 KB list a reader who
        never leaves the glossary should not be made to fetch to find out whether a button
        is live.

        Sent from here rather than folded into `bind_glossary`, because the two are
        answers with different lifetimes: the terms belong to the base and are built once,
        the sidecars belong to the *process* and to which version the base is on. A shallow
        copy, so the cached payload is never mutated by the route that serves it.

        The block itself is `glossary_sidecars` above, shared with the MCP server.
        """
        with self._live.lock:
            base = self._live.current
            self._json({**base.glossary, "sidecars": glossary_sidecars(
                self._live.source, self._live.docsource,
                base.source_revision, base.docsource_revision)})

    def _r_table(self, q: dict[str, list[str]]) -> None:
        """The routines that touch one table.

        A table is not a node in the graph, so selecting one means selecting the code
        that reads and writes it. Answered on demand rather than shipped with the cover:
        Lictores has 1,042 operations across its tables and most sessions never click a
        table at all.
        """
        name = (q.get("name") or [""])[0]
        if not name:
            self._json({"found": False, "reason": "no table asked for", "nodes": []})
            return
        with self._live.lock:
            store = self._live.current.store
            rows = store.query(queries.TABLE_ROUTINES, {"name": name})
            specimen = table.describe(store, name)
        nodes = [r["node"] for r in rows]
        # `found: False` for a real table nothing touches would read as "no such table".
        # They are different answers and the client shows different things for each.
        #
        # **The specimen rides beside the nodes rather than replacing them**, because the
        # three doors into this route ask two questions: the navigator row, the document
        # row and the ribbon all want the table *selected*, which lights its routines in
        # the stack, and the inspector wants the table *described*. Serving one and making
        # the caller derive the other is how the table came to be thrown away.
        self._json({"found": True, "table": name, "nodes": nodes,
                    "specimen": specimen})

    def _r_files(self, q: dict[str, list[str]]) -> None:
        """Every analysed file, complete. Rule 8: a reference list is never bounded."""
        with self._live.lock:
            self._json(self._live.current.files)

    def _r_file(self, q: dict[str, list[str]]) -> None:
        """One file, whole, with what the map knows about every line of it.

        Separate from `/api/source`, which serves a *span* and is what a citation and a
        definition open. This answers a different question -- what is this file, all of it,
        and what is on each line -- and sending the margin with every citation would put a
        file's worth of facts behind a click that wanted fifteen lines.
        """
        path = (q.get("path") or [""])[0]
        with self._live.lock:
            base = self._live.current
            self._json(build_file(base.store, self._live.source, path,
                                  revision=base.source_revision))

    def _r_search(self, q: dict[str, list[str]]) -> None:
        """Search the text of the source, which is the one thing the graph cannot do.

        Two answers behind one route, and the difference is `path`. Without it: which files
        hold a match and how many lines each -- complete, and cheap enough to run on a
        keystroke (20-30 ms over all 184,722 of Lictores' lines). With it: that one file's
        hits, each carrying its margin, its links and the routine it sits in.

        Split that way because the expensive half is the margin -- ten queries per file --
        and a broad search touches 166 files. Building it for all of them behind a keystroke
        would be rule 45 exactly; building it for the one file a reader opened is what
        `/api/file` already costs.
        """
        term = (q.get("q") or [""])[0]
        path = (q.get("path") or [""])[0]
        flag = lambda k: (q.get(k) or ["0"])[0] in ("1", "true", "on")  # noqa: E731
        case, word, regex = flag("case"), flag("word"), flag("regex")
        with self._live.lock:
            base = self._live.current
            if path:
                self._json(search_in_file(
                    base.store, self._live.source, term, path,
                    case=case, word=word, regex=regex, revision=base.source_revision))
            else:
                self._json(search_files(
                    base.store, self._live.source, term,
                    case=case, word=word, regex=regex, revision=base.source_revision))

    def _r_source(self, q: dict[str, list[str]]) -> None:
        """A span of one file, straight out of the source sidecar.

        Separate from `/api/node` because the inspector opens a definition first and the
        surrounding file only if asked. Sending a whole file with every selection would
        put a megabyte behind every click for a view most clicks never open.
        """
        self._span(q, self._live.source, "source_revision", absent=NO_SOURCE_SIDECAR)

    def _r_docsource(self, q: dict[str, list[str]]) -> None:
        """The same span of one document, out of the **document** sidecar.

        Its own route rather than a `corpus=` parameter on `/api/source`, and the reason
        is rule 16's: two stores, two routes, nothing guessed. A parameter would put the
        choice of *which database* behind a query string a caller can omit, and the
        default would be right until the day somebody forgot it -- at which point a
        citation into `docs/glossary.md` would be answered out of the code sidecar, which
        holds no such path and would report the document as missing.

        This is what chunk 5 opens a `DECLARED_DOCS` citation against.
        """
        self._span(q, self._live.docsource, "docsource_revision", absent=NO_DOC_SIDECAR)

    def _span(self, q: dict[str, list[str]], sidecar: SourceStore | None,
              revision_field: str, *, absent: str) -> None:
        """Lines `first` to `last` of one path out of one sidecar, or why not.

        One implementation for both corpora, because the *rule* is the same and only the
        store and the revision differ -- and a second copy would have been correct on the
        day it was written (rule 51). The four refusals are the ones that were already
        here: no path, no sidecar, line numbers that are not numbers, and a sidecar that
        does not hold the path. Each is stated; none is a blank (rule 49).

        `revision_field` is a name rather than a value because the base can move between
        this call and the read, and the answer must come from the base the read is made
        against -- resolved under the lock, beside the store it is a revision *of*.

        **A `None` revision refuses rather than falling through**, and that is not
        defensiveness. `_sidecar_revision` returns it for "this sidecar cannot serve the
        version on screen"; every store below reads `revision=None` as "the current one".
        Passed on, the newer meaning wins and the newest snapshot's bytes are served under
        this version's line numbers -- which is rule 70 exactly, and is what the document
        sidecar did on Lictores' older base before anybody looked.
        """
        path = (q.get("path") or [""])[0]
        if not path:
            self._json({"available": False, "reason": "no path asked for"})
            return
        if sidecar is None:
            self._json({"available": False, "file": path, "reason": absent})
            return
        try:
            first = int((q.get("first") or ["1"])[0])
            last = int((q.get("last") or ["0"])[0])
        except ValueError:
            self._json({"available": False, "file": path,
                        "reason": "line numbers must be numbers"})
            return
        with self._live.lock:
            rev = getattr(self._live.current, revision_field)
            if rev is None:
                self._json({"available": False, "file": path,
                            "reason": SIDECAR_NO_VERSION})
                return
            if last <= 0:
                whole = sidecar.text(path, revision=rev)
                lines = list(enumerate((whole or "").split("\n"), 1)) if whole else []
            else:
                lines = sidecar.lines(path, first, last, revision=rev)
        if not lines:
            self._json({"available": False, "file": path,
                        "reason": "the sidecar does not hold this file"})
            return
        self._json({"available": True, "file": path,
                    "first": lines[0][0], "last": lines[-1][0],
                    "lines": [{"n": n, "text": t} for n, t in lines]})

    def _r_docs(self, q: dict[str, list[str]]) -> None:
        """Every document the scan read, complete and unbounded (rule 8).

        Cheap enough to be whole: 2,064 rows and three grouped counts over a store this
        process already holds open. What makes it affordable is that the bodies are not in
        it -- 38.7 MB of prose stays in the sidecar until somebody opens a document.
        """
        with self._live.lock:
            base = self._live.current
            self._json(build_corpus(base.docs, self._live.docsource,
                                    revision=base.docsource_revision))

    def _r_doc(self, q: dict[str, list[str]]) -> None:
        """One document: its row, its headings with their lines, and its text.

        Whole, like `/api/source` and for the same reason: a reference is never bounded,
        and the client bounds what it *draws* rather than being handed a slice it cannot
        tell from the document (rules 8 and 55). The largest here is 1.33 MB.
        """
        with self._live.lock:
            base = self._live.current
            self._json(build_document(base.docs, self._live.docsource,
                                      (q.get("path") or [""])[0],
                                      revision=base.docsource_revision))

    def _r_about(self, q: dict[str, list[str]]) -> None:
        """What read this map, and whether anything in it was guessed.

        **Every row is a recorded fact or a stated absence**, and the two are never blurred:
        a key that is *missing* means this map predates the question, a key that is *blank*
        means the answer is nothing. Design rule 21 says a blank must say why it is blank,
        and here there are two different whys.

        The two rows this exists for are the last two, and they are a **standing guarantee**
        rather than a placeholder waiting for a model. Nothing on the analysis path calls a
        model or touches a network -- the extractors are stdlib `ast` and `tokenize`, the
        document scanner is hand-written, and `Provenance`'s two paid tiers are declared and
        unbuilt. A reader handed a map is entitled to know that in as many words, and to be
        told plainly when an older map cannot say.

        **Design rule 28** is what these two rows are: inference is voluntary and secondary,
        and a map states whether any was used. One step over from design rule 14, which
        scopes what may *leave* the machine -- this scopes whether a fact was **guessed**.

        **The fingerprint is not offered as a comparison, and that was a correction.** The
        obvious row is *"would a newer DunneFlow read this differently?"* -- and for the map
        on screen it can only ever answer no, because `Store` opened read-only calls
        `_refuse_if_stale` and a mismatched graph never becomes the base at all. So what is
        stated is the guarantee that produces: this map was read by the build serving it,
        necessarily. The honest *"should I read this again?"* signal is the date beside it
        and the tree it was read from, which have moved on and say nothing about it.
        """
        with self._live.lock:
            base = self._live.current
            meta = {k: base.store.get_meta(k) for k in (
                "program", "revision", "analysed_at", "tool_version", "extractor",
                "schema_version", "inference", "model", "analysis_args",
                "walk_residue")}
            counts = base.store.counts()
            # Where the map stops, and why, over every call (schema 17). Only readers that
            # say fill it; `unsaid` counts the calls whose reader said nothing.
            frontier = base.store.frontier_of_map()
            # Commands sent by name between two languages (`resolve/ipc.py`).
            by_name = base.store.ipc_of_map()
            # Calls dispatched to several bodies, crossed by every walk (`resolve/dispatch.py`).
            by_dispatch = base.store.dispatch_of_map()
            # **What this map was read from, not what this build can read** (rule 24).
            # The dialog's subject is the map on screen, and the same claim the mirror
            # page makes in prose is the one this row states as a count.
            # The stored key **and** the word for it: `files.lang` holds `python` and a
            # sentence a reader reads says `Python`, and the page owns neither spelling
            # (rule 51 -- the same argument `none` is decided here rather than there).
            langs = [{"lang": k, "display": languages.display(k), "files": n}
                     for k, n in languages.counts(base.store).items()]
            docs = base.docs.counts() if base.docs is not None else None
            source_revision = base.source_revision
            out_name = self._live.out_dir.name
            # `""` unless this map never finished and the reader's Setting opened it
            # anyway -- the banner's sentence, naming the step it stopped in (rule 80).
            unfinished = base.unfinished

            # The leaf of the tree this snapshot was read from -- a name, never a path
            # (rule 60). Only the sidecar knows it, and a map handed over without one
            # simply cannot say, which is a different answer from a map read from a tree
            # with no name.
            #
            # **Read under the lock, and that placement is the fix rather than tidiness.**
            # The sidecar is opened `shared=True`, which is `check_same_thread=False` and
            # a lock owed by the caller (`sourcedb.py`). This held the store *outside* the
            # block and called `revisions()` there, so `/api/about` and `/api/revisions` --
            # which the shell fires back to back at boot -- read one connection at once.
            # The rows came back wrong, no row matched, and the topbar stated *"no sidecar
            # here to ask"* over a map whose sidecar holds the name: rule 49 exactly, a
            # plausible answer that consumed the evidence on its way past. Measured before
            # the move: 0 of 30 serial reads wrong, 2 of 60 concurrent ones, and one
            # connection dropped. `_r_revisions` asks the same question the right way.
            sidecar = self._live.source
            tree = None
            if sidecar is not None and source_revision is not None:
                for row in sidecar.revisions():
                    if row.get("revision") == source_revision:
                        tree = str(row.get("tree") or "")
                        break

        # What a value meaning *nothing* looks like in the store. Two spellings because two
        # fields chose differently and both are right where they are: `inference` says
        # `none` so `dunneflow query` over `meta` reads as prose, and `model` is blank
        # because there is no word for the model that did not run.
        NOTHING = {"", "none"}

        def said(key: str) -> dict[str, Any]:
            """One recorded field: its value, whether it was recorded, and what it means.

            **`none` is decided here rather than on the page**, because this is the layer
            that knows what `analyze` writes. A renderer testing for the literal `"none"`
            would be a second reading of a value it does not own, and it would go on
            looking right on the day the word changed (rule 51).

            Three states, never two: not recorded, recorded as nothing, recorded as
            something. The first two are the distinction the whole guarantee rests on --
            *this map cannot say* and *nothing was inferred* are different claims.
            """
            v = meta.get(key)
            return {"recorded": v is not None, "value": (v or ""),
                    "none": v is not None and v.strip().lower() in NOTHING}

        self._json({
            "program": meta.get("program") or out_name,
            "revision": meta.get("revision") or "",
            "unfinished": unfinished,
            "analysed_at": meta.get("analysed_at") or "",
            "tree": tree,
            "tool_version": said("tool_version"),
            "extractor": said("extractor"),
            "schema_version": said("schema_version"),
            "analysis_args": said("analysis_args"),
            # **What the walk left out, and it is three answers rather than a list.** A map
            # written before `analyze` recorded this cannot say; one recording an empty
            # list is saying *nothing was left out*, which is a real and different answer;
            # and one recording lines is saying which. Collapsing the first two would turn
            # a silence into a promise, which is the failure every other field here is
            # shaped to avoid (design rule 21).
            #
            # The panel says the same thing while a run is going, off the same sentences
            # -- `walk_residue` is the one place they are worded (rule 51) -- and this is
            # what a reader gets once the panel is dismissed and next week when they open
            # the map again.
            "walk_residue": said_residue(meta.get("walk_residue")),
            # The two the dialog exists for.
            "inference": said("inference"),
            "model": said("model"),
            "counts": {"files": counts.get("files", 0),
                       "routines": counts.get("routines", 0),
                       # `None`, not 0: a corpus nobody scanned and a corpus with nothing
                       # in it are different facts (design rule 11 -- documentation is
                       # optional, and its absence is stated rather than shown as zero).
                       "documents": (docs or {}).get("documents") if docs else None},
            "languages": langs,
            "frontier": frontier,
            "by_name": by_name,
            "by_dispatch": by_dispatch,
        })

    def _version_of(self, graph: Path) -> dict[str, Any]:
        """What one version says its own version is, or nothing at all.

        Three meta keys, written by `analyze` from `resolve/version.py`. Absent is a real
        answer -- most programs assert no version, and an empty string here means the page
        shows nothing rather than an empty box beside a label (rule 44).

        The served graph is read off the connection this process already holds. Rule 58:
        a second read-only handle to a database open in WAL mode cannot join the
        shared-memory WAL index and re-derives it per query -- 36x on a real comparison.
        Three rows is not 36x of anything, but the rule is about the *habit*, and the
        cheap path is also the shorter code.
        """
        keys = ("program_version", "program_version_tier", "program_version_where",
                # **Every declaration, where there is more than one.** Written by
                # `analyze` only when two root manifests state different versions, so a
                # program that declares one has exactly the `meta` it always had. The
                # strip draws one value because a strip has room for one; this is what
                # lets it say *and one other* rather than quietly showing whichever
                # `manifests.PROVIDERS` happened to order first.
                "program_versions")
        # One read of `current` and one decision from it. Asking "is this the served
        # graph?" outside the lock and then reading the store inside it is two questions
        # about a thing that can move between them -- which is the whole failure mode a
        # base switch introduces.
        with self._live.lock:
            base = self._live.current
            got = ({k: base.store.get_meta(k) for k in keys}
                   if graph == base.graph_db else None)
        if got is None and graph.exists():
            try:
                other = Store(graph, writable=False)
            except Exception:                       # noqa: BLE001 -- a version is not
                return {}                           # worth failing the whole listing for
            try:
                got = {k: other.get_meta(k) for k in keys}
            finally:
                other.close()
        elif got is None:
            return {}
        out: dict[str, Any] = {
            k.replace("program_", ""): (v or "") for k, v in got.items() if v
        }
        # How this version sorts, and against what it may be sorted. Computed here rather
        # than in the page for two reasons: `1.10.0` sorts *below* `1.2.0` as a string,
        # which is the oldest version-sorting bug there is; and a date and a release
        # number are both orderable and are not orderable against **each other**, so the
        # kind has to travel with the key or the page will happily rank them.
        key = version_order.order_key(out.get("version", ""))
        if key is not None:
            out["version_kind"], out["version_key"] = key[0], list(key[1])
        # JSON on the way out rather than a string the page has to parse. A map written
        # before this key existed has no `versions` at all, which is the *not recorded*
        # state and not an empty list (rule 30).
        if out.get("versions"):
            try:
                out["versions"] = json.loads(str(out["versions"]))
            except ValueError:               # a value this build cannot read is not a
                out.pop("versions")          # reason to fail a listing
        return out

    def _r_revisions(self, q: dict[str, list[str]]) -> None:
        """Every point in time this program directory holds, newest first.

        The sidecar is the authority on *what a revision is* -- its state, when it was
        captured, what it was labelled -- and the directory is the authority on whether
        a **graph** exists to read it with. A revision whose bodies are held but whose
        graph was never written cannot be compared, and saying so is the difference
        between an empty answer and an honest one (rule 20).
        """
        rows: list[dict[str, Any]] = []
        with self._live.lock:
            serving = self._live.current.graph_db
            listed = (self._live.source.revisions()
                      if self._live.source is not None else [])
        for r in listed:
            rev = str(r.get("revision") or "")
            graph = revisions.db_path(self._live.out_dir, revisions.GRAPH, rev)
            rows.append({
                "revision": rev,
                "state": r.get("state", ""),
                "captured": r.get("captured_at", ""),
                "label": r.get("label", ""),
                # The leaf of the directory this version was read from. Two versions of a
                # program are two directories, so this is what the strip names them by --
                # an instant says when we read the bytes and nothing about which tree.
                "tree": r.get("tree", ""),
                **self._version_of(graph),
                "files": r.get("paths", r.get("files", 0)),
                "comparable": graph.exists(),
                "serving": graph == serving,
                # No `source_root`. It used to ride here so the toolbar could name the tree
                # each revision was read from -- which was a real observation, two points in
                # play and one path shown implying it was both. The answer turned out to be
                # that the path should not be stored at all: it is one machine's layout,
                # wrong the moment anything moves, and a revision is identified by its label
                # and its instant rather than by where it happened to sit. See `migrate.py`.
            })
        # With no sidecar there is still a directory, and it may hold graphs. Never
        # answer "no revisions" out of a store that simply was not asked.
        if not rows:
            for g in revisions.known(self._live.out_dir, revisions.GRAPH):
                rows.append({
                    "revision": revisions.revision_of(g) or "",
                    "state": "", "captured": "", "label": "", "tree": "", "files": 0,
                    "comparable": True, "serving": g == serving,
                })
        self._json({"revisions": rows,
                    "comparable": sum(1 for r in rows if r["comparable"])})

    def _r_changes(self, q: dict[str, list[str]]) -> None:
        """What differs between two versions of this program.

        `base` is the version the map is showing and `compared` is the one it is held
        against. **Neither is claimed to be older** -- the only instant this tool records
        is when the bytes were read, which says nothing about when the code is from.

        The defaults are the served graph as the base and the next comparable one as the
        compared end, because that is the question someone opening this view is asking.
        That the second happens to be the next one *captured* is a convenience for
        picking a default and is not a claim about it; the strip names both ends and
        states the reader's own assumption about which is newer, so nobody can be looking
        at a comparison without knowing which one and which way round.
        """
        graphs = revisions.known(self._live.out_dir, revisions.GRAPH)
        if len(graphs) < 2:
            self._json({
                "available": False,
                "reason": ("this program has one version — analyse another copy of the "
                           "source after sealing this one, and there will be two"),
                "revisions": len(graphs),
            })
            return

        def _pick(name: str, default: Path) -> Path | None:
            asked = (q.get(name) or [""])[0]
            if not asked:
                return default
            p = revisions.db_path(self._live.out_dir, revisions.GRAPH, asked)
            return p if p.exists() else None

        # The base defaults to the graph actually being served rather than to
        # `graphs[0]`: the map and the comparison must never disagree about which version
        # is on screen (rule 51). Read once, because a switch can land between two reads
        # and then the default base and the `rode` decision below would be about two
        # different versions.
        with self._live.lock:
            serving = self._live.current.graph_db
        base = _pick("base", serving)
        compared = _pick("compared", next(
            (g for g in graphs if g != serving), graphs[1]))
        if base is None or compared is None:
            self._json({"available": False,
                        "reason": "no graph for one of the versions asked for"})
            return
        if base == compared:
            self._json({"available": False,
                        "reason": "a version compared with itself has nothing to say"})
            return

        key = (compared.name, base.name)
        with self._live.lock:
            built = self._live.changes.get(key)
        if built is None:
            t = time.perf_counter()
            # Ride the connection that already holds the served graph open when it is one
            # end of the pair. A second read-only handle to a database this process has
            # open in WAL mode cannot share the `-shm` WAL index and re-derives it per
            # query: 8,855 ms against 137 ms on one `calls` comparison. The lock is held
            # for the build because that connection belongs to every other request too.
            # Decided under the lock and acted on under the same one, so a base switch
            # cannot land between "is this the served graph?" and the connection the
            # answer licenses -- which would hand `changes.build` a connection that has
            # just been closed.
            built = None
            with self._live.lock:
                rode = base == self._live.current.graph_db
                if rode:
                    built = changes.build(base, compared,
                                          serving=self._live.current.store.conn)
            if built is None:
                built = changes.build(base, compared)
            built["ms"] = round((time.perf_counter() - t) * 1000)
            # Which path produced the number beside it. Rule 13: a measurement that does
            # not say how it was taken cannot be checked, and these two differ by 36x.
            built["rode_serving_connection"] = rode
            with self._live.lock:
                self._live.changes[key] = built
        self._json({
            "available": True,
            "base": revisions.revision_of(base),
            "compared": revisions.revision_of(compared),
            **built,
        })

    def _r_anomalychanges(self, q: dict[str, list[str]]) -> None:
        """What the comparison says about each finding.

        The same two ends as `/api/changes`, picked the same way and meaning the same
        thing, because a reader holding one pair in mind must not find a second one here
        (rule 51). `base` is the version the map is showing; neither end is claimed to be
        older.

        Where this differs from every other comparison in the dashboard is the cost, and
        it is inherent rather than an oversight: findings are not rows to be joined, they
        are what thirteen detectors conclude, so the compared version's findings mean
        running the detectors over the compared version's graph. Held per graph in
        `_Live.findings`, so a reader who switches back and forth pays once each.
        """
        graphs = revisions.known(self._live.out_dir, revisions.GRAPH)
        if len(graphs) < 2:
            self._json({
                "available": False,
                "reason": ("this program has one version — analyse another copy of the "
                           "source after sealing this one, and there will be two"),
                "revisions": len(graphs),
            })
            return

        def _pick(name: str, default: Path) -> Path | None:
            asked = (q.get(name) or [""])[0]
            if not asked:
                return default
            p = revisions.db_path(self._live.out_dir, revisions.GRAPH, asked)
            return p if p.exists() else None

        serving = self._live_graph()
        base = _pick("base", serving)
        compared = _pick("compared", next(
            (g for g in graphs if g != serving), graphs[1]))
        if base is None or compared is None:
            self._json({"available": False,
                        "reason": "no graph for one of the versions asked for"})
            return
        if base == compared:
            self._json({"available": False,
                        "reason": "a version compared with itself has nothing to say"})
            return

        key = (compared.name, base.name)
        with self._live.lock:
            built = self._live.anomalypairs.get(key)
        if built is None:
            t = time.perf_counter()
            base_rows, why = self._findings(base)
            compared_rows, why_other = self._findings(compared)
            if base_rows is None or compared_rows is None:
                # Stated, never an empty list: a graph this version of DunneFlow refuses
                # to read and a program with nothing wrong with it are opposite claims
                # (rules 49 and 63), and the reader is owed which one they are looking at.
                self._json({"available": False,
                            "reason": why or why_other})
                return
            built = anomalychanges.build(base_rows, compared_rows)
            built["ms"] = round((time.perf_counter() - t) * 1000)
            with self._live.lock:
                self._live.anomalypairs[key] = built
        self._json({
            "available": True,
            "base": revisions.revision_of(base),
            "compared": revisions.revision_of(compared),
            **built,
        })

    def _r_filechanges(self, q: dict[str, list[str]]) -> None:
        """Which files differ between two versions, and where inside one of them.

        Two answers behind one route, and the difference is `path` -- the same shape
        `/api/search` has, for the same reason. Without it: every file with its status,
        complete, and it costs **no body reads at all**, because the sidecar is
        content-addressed and equal hashes are equal bytes. With it: that one file's
        lines, which is the only place `difflib` ever runs.

        Split that way because the cheap half says which files the expensive half is
        worth running on: twelve of Lictores' 628. Running the text lane over all of them
        behind one request would be rule 45 exactly -- work proportional to the whole
        program for an answer about one file.

        **The base end is the server's, not the caller's.** Every other pair in this
        dashboard is two arguments, but this one is drawn *over the bytes on screen*, and
        those are the base's. A caller free to name a base the code browser is not showing
        could put one version's difference marks on another version's lines, which is the
        defect the revision pinning above exists to remove -- so the parameter does not
        exist rather than being validated (rule 51: one truth, one place that owns it).
        """
        compared = (q.get("compared") or [""])[0]
        path = (q.get("path") or [""])[0]
        with self._live.lock:
            base = self._live.current.source_revision
            source = self._live.source
        if path:
            # Uncached, deliberately. The worst file in the corpus is 40 ms and every
            # body it reads is already in the sidecar's inflate cache from having been
            # opened; holding the compared version's text for every file a reader visits
            # would be a second copy of the program in memory to save that.
            with self._live.lock:
                self._json(filediff.lines(source, path, base, compared))
            return
        key = (base or "", compared)
        with self._live.lock:
            built = self._live.filepairs.get(key)
            if built is None:
                built = filediff.pair(source, base, compared)
                self._live.filepairs[key] = built
            self._json(built)

    def _r_base(self, q: dict[str, list[str]]) -> None:
        """Which version is the base, and what a switch to another one is doing.

        Two answers in one place on purpose. A page that has just loaded needs the first
        -- the **server** is the truth about which version is on screen, not a value the
        browser stored in a previous session -- and a page watching a switch needs the
        second. Splitting them would mean two requests to answer "what am I looking at,
        and is it about to change".

        It never takes `live.lock` for the progress: that is the whole point of a separate
        one. A poll that queued behind the rebuild would report nothing until there was
        nothing left to report.
        """
        # **It answers with nothing open**, because that is when it is asked hardest: the
        # start page polls this while the first program is being built, and until that build
        # lands there is no base to name. `""` here is the honest answer -- *no version is
        # on screen* -- and it is the same word this route already uses for an unrevisioned
        # graph, which is the one place the two could be confused and are not: the state
        # beside it says which (design rule 21).
        base = ""
        if self._live.opened:
            with self._live.lock:
                base = revisions.revision_of(self._live.current.graph_db) or ""
        self._json({
            "base": base,
            "open": self._live.opened,
            "steps": list(BUILD_STEPS),
            **self._live.progress(),
        })

    def _r_programs(self, q: dict[str, list[str]]) -> None:
        """Every program beside this one, and which is being read.

        The siblings come from `revisions.program_dirs(out_dir.parent)` -- *which
        directories under this root hold a map* -- so `serve` keeps taking a program
        directory and needs no new argument. A program served from somewhere with no
        siblings gets a list of one, which is the honest answer rather than an empty
        control.

        **The union below is a union of keys, and it only works because both sides are
        resolved.** `here` has always been `out_dir.resolve()` and the listing was not, so
        where the root arrives unresolved the two are unequal `Path` objects naming a
        single directory: the open program came back **twice**, and the copy that was not
        marked as serving was the one the listing supplied. `/tmp` and `/var/folders` are
        both symlinks on macOS, so a maps root in a temporary directory is already this
        shape.

        **Which callers were exposed is worth stating, because it is not this route's
        own.** `cmd_serve` and the MCP session both reach `_Live` through `serve.where`,
        which resolves both halves, so the application a reader runs was never wrong here;
        what is exposed is `_Live`'s two-argument form, where `out_root` is derived as
        `out_dir.parent` and keeps whatever spelling the caller had. `tools/ordering.py`
        is such a caller and is how this was found. `program_dirs` resolves now, which is
        where that has to happen (rule 51) -- the line below asks for nothing and depends
        on it entirely.

        **Named but not opened.** Whether a program's stores are readable by *this* build of
        DunneFlow is a question that costs a graph open and a document-store open apiece,
        and this route is behind a `<select>` the reader clicks. The switch answers it, with
        the store's own sentence, and refuses (rule 20). Listing a program that turns out to
        be stale is not a lie; hiding it, or stalling the toolbar to find out, would be
        worse.

        `files` is `None` for every program but the served one, for the same reason -- see
        `PERFORMANCE.md`. The served one is free: the base already knows. `revisions` is a
        count for every row, because that one is a directory listing rather than an open --
        the bargain above is about *reading* a store, not about naming its files.

        **It answers with nothing open, and that is what the start page is built on.** A
        second route listing programs would be a second answer to one question (rule 51),
        so this is the only one: `serving` is `""` from cold, `files` is `None` for every
        row including the root's own, and `root` rides along because a reader looking at an
        empty list needs to know *where* it was empty.
        """
        opened = self._live.opened
        with self._live.lock:
            here = self._live.out_dir.resolve()
            served_files = (int(self._live.current.cover.get("stats", {}).get("files", 0))
                            if opened else None)
        found = revisions.program_dirs(self._live.out_root)
        # The served program is in the list whatever the walk found -- it is being read
        # right now, so a list without it would be a control that cannot name the thing it
        # is showing. From cold there is nothing being read and `here` is the root itself,
        # which is not a program; adding it would invent a row for a directory that holds
        # no map (rule 30). Sorted by name so the order is total and does not move between
        # polls — and **total means the spelling too**, because `found` is a set and
        # `.lower()` alone ties `Lictores` against `lictores`, which are two directories on
        # a case-sensitive volume and one hash seed's opinion apart in this list (rule 105).
        rows = []
        for d in sorted(found | ({here} if opened else set()),
                        key=lambda p: (p.name.lower(), p.name)):
            is_here = opened and d == here
            rows.append({
                "name": d.name,
                "serving": is_here,
                # A directory with no graph is **listed and marked**, never dropped: a
                # program that cannot be opened and a program that does not exist are
                # different facts, and only one of them is worth a sentence (design rule 1).
                "openable": revisions.newest(d, revisions.GRAPH) is not None,
                # **Listed and marked, never dropped** -- design rule 1, and the same
                # bargain `openable` makes one column over. A directory whose analysis was
                # stopped is a real thing a reader made and will look for; hiding it would
                # leave them hunting for a program they know they started. The switch
                # refuses it with the store's own sentence.
                "finished": self._finished(d, is_here),
                # **Unfinished and still being worked on** is the third answer the graph
                # cannot give, and the start page said *"never finished — analyse it again"*
                # over a run two hours into finishing it. The sidecar is a file read, not
                # an open, so it keeps the bargain above.
                "analysing": _analysing(d),
                "files": served_files if is_here else None,
                # A glob, not an open -- see the note above. It is what tells a reader on
                # the start page that a program has more than one point in time in it.
                "revisions": len(revisions.known(d, revisions.GRAPH)),
            })
        self._json({"programs": rows,
                    "serving": here.name if opened else "",
                    "root": str(self._live.out_root),
                    # Empty unless the reader's chosen maps directory is on a disk that is
                    # not connected, in which case `root` above is the fallback and this
                    # says so. It rides here rather than on a route of its own because it
                    # is a fact *about the root*, and this is the one route that answers
                    # where maps are (rule 51) -- the same bargain `root` itself makes.
                    "root_gone": self._live.root_gone})

    def _finished(self, d: Path, is_here: bool) -> bool:
        """Did the analysis that wrote this program's newest map finish?

        **One meta read, and only one**, against `_r_programs`' standing bargain: that route
        names programs without opening them, because whether a map is readable costs a graph
        open apiece behind a `<select>` the reader clicks. This is the exception, and it
        earns it -- an unopenable program wastes a click, an *unfinished* one is read as a
        program that calls nothing. `True` on any failure to say otherwise: this column
        marks a row, it does not decide whether the switch may happen, and the switch asks
        the store itself.
        """
        if is_here:
            return True             # it is being served, so it passed the check to get here
        graph = revisions.newest(d, revisions.GRAPH)
        if graph is None:
            return True             # `openable` already says this row has nothing to read
        try:
            store = Store(graph, writable=False)
        except Exception:           # noqa: BLE001 -- stale, wrong kind, unreadable: all
            return True             # `openable`'s business, and none of this column's
        try:
            return store.finished() != ""
        finally:
            store.close()

    def _p_program(self, q: dict[str, list[str]]) -> None:
        """Serve a different program. A POST, for `_p_base`'s reason.

        Refuses by name in the same four shapes: nothing named, no such directory beside
        this one, already being read, and a switch already running. A reader must never
        have to guess which of those they got.

        **The first open and a switch are one route**, and that is deliberate. From the
        start page there is nothing to switch *from*, but `switch_program` already builds
        the new base before it closes anything and restores what it had on failure -- with
        nothing to restore, that is exactly a cold open. A second route would be a second
        copy of the widest blast radius in this file (rule 51). What changes with nothing
        open is only what can be refused: *that is already what you are reading* has no
        subject, and the root itself is not one of the choices.
        """
        asked = (q.get("name") or [""])[0]
        if not asked:
            self._started(False, "no program was named")
            return
        opened = self._live.opened
        with self._live.lock:
            here = self._live.out_dir.resolve()
        # Resolved against the siblings rather than joined onto the parent, so a name
        # carrying `..` or a separator cannot address a directory outside the output root.
        # The list is the authority on what may be switched to (rule 30: a label is not an
        # identity, and this turns one into the other by lookup).
        candidates = {d.name: d for d in revisions.program_dirs(self._live.out_root)}
        if opened:
            candidates[here.name] = here
        target = candidates.get(asked)
        if target is None:
            where_ = "beside this one" if opened else f"under {self._live.out_root}"
            self._started(False, f"there is no program called {asked} {where_}")
            return
        if opened and target == here:
            self._started(False, f"{asked} is already the program being read")
            return
        if not self._live.claim(asked):
            running = self._live.progress().get("revision", "")
            self._started(False, f"a switch to {running} is already running")
            return
        threading.Thread(target=self._live.switch_program,
                         args=(target, asked, _unfinished_choice(q)),
                         name=f"dunneflow-program-{asked}", daemon=True).start()
        self._started(True, "")

    def _p_close(self, q: dict[str, list[str]]) -> None:
        """Close the map, so the reader is back at the start page. `_p_program`, one out.

        The two belong side by side: `_p_program` moves the base sideways and this removes
        it. **There has to be a way back** -- until this route existed, `/` was the shell
        for as long as the process lived and nothing could return a reader to the start
        page, so the maps-directory control there was unreachable the moment a map opened.

        **Not in `POST_WITHOUT_BASE`, and the frozenset's direction is the argument.** That
        list names *exceptions*; closing with nothing open has no subject, so leaving it off
        is the answer rather than an omission. The reader who produces that 409 is racing
        themselves -- two tabs, one close -- and it is read as *already closed*.

        **Synchronous, unlike both switches.** They run on a thread because they build a
        base and that takes ten seconds; this closes four handles and clears four dicts, so
        a thread would buy nothing and cost the caller the ability to know it was done. The
        reply already carries the terminal report, so the shell's `pollBase` and the start
        page's `watch` both settle on it without a line of new watching.
        """
        if not self._live.claim("closing"):
            # A switch is mid-flight and holds `was`; closing under it would have the
            # failing switch restore handles this method had already shut. One `claim` makes
            # that impossible, and it is the build slot rather than a third one because a
            # close is a thing that replaces the base (rule 82).
            running = self._live.progress().get("revision", "")
            self._started(False, f"a switch to {running} is still running", steps=())
            return
        self._live.close_program()
        self._started(True, "", steps=())

    def _r_root(self, q: dict[str, list[str]]) -> None:
        """The pre-flight for a maps-directory change, live, for whoever is typing.

        The same function the POST calls, so the warning under the field and the refusal at
        the button are one sentence from one place and cannot drift (rule 41) --
        `_r_analysis` does exactly this for the analyse dialog, and this is that arrangement
        one subject over.

        A GET because it reads and decides nothing; `_p_root` is the POST that acts.
        """
        asked = (q.get("path") or [""])[0]
        carry = (q.get("move") or ["1"])[0] != "0"
        if not asked:
            self._json({"ok": False, "refusal": "", "note": ""})
            return
        v = roots.check(asked, self._live.out_root)
        body = {"ok": v.ok, "refusal": v.refusal, "note": v.note}
        if v.ok and carry:
            # Only when it is going to be used. A reader who unticked the box must not be
            # shown a shortfall for space they are not going to need (rule 32).
            room = roots.will_fit(self._live.out_root,
                                  Path(asked.strip()).expanduser().resolve())
            body["ok"] = room.ok
            body["refusal"] = room.refusal
            body["note"] = " ".join(x for x in (v.note, room.note) if x)
        self._json(body)

    def _p_root(self, q: dict[str, list[str]]) -> None:
        """Keep maps somewhere else, optionally carrying the existing ones there.

        **In `POST_WITHOUT_BASE`, and only reachable with nothing open.** Choosing where maps
        live precedes having any map, exactly as `/api/pickdir` does -- but re-pointing under
        a *live* reader would mean tearing down a base, repointing three sidecars and
        rebuilding, which is `switch_program`'s blast radius for a gesture nobody performs
        mid-read. So it refuses while something is open and names the way out (rule 89); the
        start page's control closes the map first.

        **A POST, and blocking.** Rule 82's test is not how long a job takes but what the
        reader loses while it runs: an analysis replaces nothing on screen and gets a
        dismissible panel, but this replaces *the list this page is showing* and moves the
        files underneath it. So it takes the build slot -- the one that names what is being
        replaced -- rather than a third one, and the page waits.

        **Synchronous and in-process, unlike an analysis.** An analysis is exiled to a
        subprocess because the serving process must never become a writer to the tree it is
        serving (rule 20). Nothing is being served here: that is the precondition, not a
        coincidence, which is why the same argument does not reach this.
        """
        if self._live.opened:
            self._started(False, "a map is open — close it first, then move the maps "
                                 "directory", steps=())
            return
        asked = (q.get("path") or [""])[0]
        # `0` and only `0` is off, on `_p_analyze`'s precedent: an absent parameter means
        # the caller did not say, and carrying the maps across is what a reader means by
        # moving them.
        carry = (q.get("move") or ["1"])[0] != "0"

        verdict = roots.check(asked, self._live.out_root)
        if not verdict.ok:
            self._started(False, verdict.refusal, steps=())
            return
        target = Path(asked.strip()).expanduser().resolve()
        if carry:
            room = roots.will_fit(self._live.out_root, target)
            if not room.ok:
                self._started(False, room.refusal, steps=())
                return
        if not self._live.claim("moving the maps"):
            running = self._live.progress().get("revision", "")
            self._started(False, f"{running} is already running", steps=())
            return
        try:
            moved: list[str] = []
            if carry:
                moved = roots.move(self._live.out_root, target, step=lambda label, i, n:
                                   self._live.note(state="working", revision="moving",
                                                   program="", step=label,
                                                   done_steps=i, steps=n, ms=0))
            runtime.write_root_pointer(target)
            with self._live.lock:
                # Nothing is open, so this is a field rather than a teardown -- which is the
                # whole reason the control lives on the start page. `out_dir` follows it for
                # `close_program`'s reason: cold means the two are equal, and a root change
                # that moved only one of them would leave `analysis.check` measuring a name
                # against a root nobody is reading.
                self._live.out_root = target
                self._live.out_dir = target
                # The reader's chosen root is now the one being served, whatever the boot
                # had to say about a disk that was missing then.
                self._live.root_gone = ""
                for cache in self._live.PROGRAM_CACHES:
                    getattr(self._live, cache).clear()
        except Exception as exc:                  # noqa: BLE001 -- a report, not a swallow
            # The pointer is written only after a successful move, so a failure here leaves
            # both the maps and the recorded location exactly as they were.
            self._live.note(state="failed", revision="moving", program="", steps=0,
                            ms=0, reason=why(exc))
            self._started(False, why(exc), steps=())
            return
        self._live.note(state="done", revision="", program="", step="",
                        done_steps=0, steps=0, ms=0)
        self._json({"started": True, "reason": "", "root": str(target), "moved": moved})

    def _r_analysis(self, q: dict[str, list[str]]) -> None:
        """What an analysis is doing, or that none is. `_r_base`'s half about a switch.

        Its own route rather than a field on `/api/base`, because the two are watched by
        different things for different lengths of time: a switch is ten seconds behind a
        scrim, an analysis is a minute and a half behind nothing, and a page reads one
        without reading the other.

        Never takes `live.lock`, for the reason `_r_base` states.
        """
        body: dict[str, Any] = {"analysis": self._live.analysis_progress()}
        # The pre-flight, live, for whoever is typing into the dialog. Answered here as
        # well as at the POST so the warning under the name field and the refusal at the
        # button are the same sentence from the same function (rule 41).
        asked = (q.get("path") or [""])[0]
        if asked:
            v = analysis.check(asked, (q.get("name") or [""])[0],
                               self._live.out_root, self._serving_dir())
            body["check"] = {"ok": v.ok, "refusal": v.refusal, "note": v.note}
            # What each flows inventory took the last time this name was analysed, for the
            # choice under it. Only a name that is a program here is asked (rule 30).
            name = ((q.get("name") or [""])[0]
                    or Path(asked.strip()).expanduser().name).strip()
            here = {d.name: d for d in revisions.program_dirs(self._live.out_root)}
            last = analysis.inventory_for(here[name]) if name in here else None
            # Worded here, by the function the map's own pages use, so the dialog and the
            # page say one size in one spelling (rule 51).
            body["inventory"] = ({m: human_bytes(n) for m, n in last.items()}
                                 if last else None)
        self._json(body)

    def _serving_dir(self) -> Path | None:
        """The program directory being read, or **`None` when none is** — `analysis.check`'s
        fourth argument, answered in one place because two call sites got it wrong the same
        way (rule 51).

        `check` has always documented the contract: *"`serving` is `None` when nothing is
        open… Passed as `None` rather than as some stand-in path, because a stand-in would
        have to be a directory name, and a name that accidentally matched would refuse the
        first analysis a reader ever asks for (rule 30)."* Both callers passed
        `out_dir.resolve()` unconditionally, and from cold `out_dir` **is** the output root —
        precisely the stand-in that docstring forbids, and its basename is a real name.

        So the refusal fired on the root's own name with nothing open, claiming *"X is the
        program being read — its graph is open here"* over a server holding no graph at all.
        Reproduced against the signed build: a cold root called `render`, analysing any
        directory called `render`, refused. **And the frozen default root is called
        `DunneFlow`**, so the reader this refusal was most likely to meet is somebody who has
        just double-clicked the application and pointed it at their own checkout — the first
        analysis they ever ask for, refused by the sentence written to stop that happening.

        The docstring was right and unenforced, which is the shape rule 30 keeps taking: a
        label — here a directory's basename — got read as an identity. `opened` is the fact,
        never the path.
        """
        if not self._live.opened:
            return None
        with self._live.lock:
            return self._live.out_dir.resolve()

    def _p_pickdir(self, q: dict[str, list[str]]) -> None:
        """Ask the operating system for a directory, and hand back an absolute path.

        **`analysis.check` refuses a relative path**, deliberately: the server's working
        directory is not the reader's, so half a path is a different directory to each of
        them. That leaves *type the whole path* as the way in, which is a poor first
        instruction for somebody who has just double-clicked an application -- and a
        browser cannot hand a server what a folder picker chose, by design.

        So the picker is the operating system's, run by this process -- `osascript` on
        macOS, a Windows Forms folder dialog through `powershell` on Windows, neither of
        which is a dependency. **Which one, and the whole business of making it open in
        front, is `pick_folder`'s** (rule 51): this route is the same three answers on every
        platform, and a handler that knew one of them would be the place a second platform
        got added by copying it.

        **The typed field stays**, and that is the whole posture: this is a convenience over
        a control that still works, never a replacement for one (design rule 2). Cancelling
        is not an error, and says so.

        A POST for `_p_analyze`'s reason and a sharper one: it puts a modal window on the
        reader's screen, which is not a thing a prefetch may do.
        """
        picked, reason = pick_folder()
        self._json({"picked": picked, "reason": reason})

    def _p_reveal(self, q: dict[str, list[str]]) -> None:
        """Show a directory in the file manager. **Only ever one inside the output root.**

        The root in a packaged build is the platform's own answer for an application's data
        -- `~/Library/Application Support/DunneFlow`, `%LOCALAPPDATA%\\DunneFlow`, or
        `$XDG_DATA_HOME/DunneFlow` -- chosen because none of the three is swept into a sync
        folder, and invisible in all three cases to a reader who wants to hand a colleague a
        map or delete one. A page that names a place the reader cannot reach is rule 89's
        shape, so it opens.

        **Bounded to the root and its programs**, because this hands a path to the shell and
        a localhost POST is a thing a page in another tab can send. A path outside is refused
        by name rather than sanitised into one that is inside (rule 30). The bound is judged
        **here and before anything is spawned**; which file manager to hand it to is
        `reveal_dir`'s question and it asks nothing about permission.
        """
        root = self._live.out_root.resolve()
        asked = (q.get("path") or [""])[0].strip()
        target = Path(asked).resolve() if asked else root
        if target != root and not target.is_relative_to(root):
            self._json({"revealed": False,
                        "reason": f"{target} is not inside {root}"})
            return
        if not target.is_dir():
            self._json({"revealed": False, "reason": f"{target} is not there"})
            return
        shown, why = reveal_dir(target)
        self._json({"revealed": shown, "reason": why})

    def _p_stop_analysis(self, q: dict[str, list[str]]) -> None:
        """Stop the running analysis. A POST, for `_p_analyze`'s reason and its own.

        The reader may want this because the run has hung, because they changed their mind,
        or because they need the slot for a different tree -- and the server cannot tell
        those apart and does not try. **What it does not do is judge**: a run that is
        genuinely healthy and one that is wedged look identical from here, so the panel
        states how long it has been silent and the person decides.

        Answered with `started` like every other control-the-server route, so one client
        function reads them all -- and with the outcome in words, because *asked to stop*
        and *had to be killed* are different facts about the child.
        """
        stopped, said = self._live.stop_analysis()
        self._json({"started": stopped, "reason": said, "steps": [],
                    **({} if not stopped else self._live.analysis_progress())})

    def _p_analyze(self, q: dict[str, list[str]]) -> None:
        """Read a directory into a new program. **A POST, and the sharpest case for one.**

        `_p_base` is a POST because a GET that swaps the map is one a prefetch fires by
        itself. This one starts work on the filesystem, so the same argument applies with
        nothing left to argue about.

        Every refusal comes from `analysis.check`, which is the same function the dialog
        asked while the reader was typing -- so the button never refuses something the
        field said was fine (rule 41). The two answers this adds are about the *server*
        rather than the request: an analysis already running, and nothing to run it with.
        """
        out_root = self._live.out_root
        verdict = analysis.check((q.get("path") or [""])[0],
                                 (q.get("name") or [""])[0], out_root,
                                 self._serving_dir())
        if not verdict.ok:
            self._started(False, verdict.refusal, steps=())
            return
        source = Path((q.get("path") or [""])[0].strip()).expanduser().resolve()
        name = ((q.get("name") or [""])[0] or source.name).strip()
        # `0` and only `0` is off. An absent parameter means the caller did not say, and
        # documentation is an input this tool reads by default (design rule 11).
        docs = (q.get("docs") or ["1"])[0] != "0"
        # **Asked before it starts, and only asked once.** `any_size=1` is the reader's yes
        # to the confirm box below; without it, a run estimated past the reader's own
        # threshold -- or past the largest tree known to finish -- is put to them first.
        if (q.get("any_size") or ["0"])[0] != "1":
            cost = analysis.estimate_for(source, out_root, name)
            if cost.over_bound or cost.high_s > _warn_after(q) * 60:
                self._json({"started": False, "reason": "", "steps": [],
                            "confirm": dataclasses.asdict(cost)})
                return
        # The flows page's inventory, as the dialog chose it. A word it does not offer is
        # the dialog not having said, which leaves the child's own default (rule 49).
        said = (q.get("inventory") or [""])[0]
        inventory = said if said in INVENTORY_MODES else None
        if not self._live.start_analysis(name, source=source, out_root=out_root,
                                         docs=docs, inventory=inventory):
            # **The refusal carries the running job, so the reader can act on it.** It used
            # to be a sentence and nothing else -- true, and a dead end: the one thing they
            # might want to do about it is stop it, and nothing on the page offered that.
            live = self._live.analysis_progress()
            running = live.get("program", "")
            self._started(False, f"an analysis of {running} is already running", steps=())
            return
        self._started(True, verdict.note, progress=self._live.analysis_progress, steps=())

    def _p_base(self, q: dict[str, list[str]]) -> None:
        """Make another version the base. **A POST, and that is not ceremony.**

        Every other route on this server is a read. A GET that swaps the whole map is one
        a browser prefetch, a bookmark reload or a link preview fires by itself -- and
        this codebase spends rule 20 on a *read* that repaired. The one route that
        replaces what is on screen is the one route that is not a GET.

        Refuses by name in four cases, because "nothing happened" and "that is already
        what you are looking at" are different answers and a reader must not have to guess
        which one they got.
        """
        asked = (q.get("revision") or [""])[0]
        if not asked:
            self._started(False, "no version was named")
            return
        graph = revisions.db_path(self._live.out_dir, revisions.GRAPH, asked)
        if not graph.exists():
            self._started(False, f"there is no graph for {asked} in this program directory")
            return
        with self._live.lock:
            already = graph == self._live.current.graph_db
        if already:
            self._started(False, f"{asked} is already the version being read")
            return
        # Claimed before the thread is started, so two requests arriving together cannot
        # both begin a rebuild -- and the loser is told, rather than being answered as
        # though its own switch were the one now running.
        if not self._live.claim(asked):
            running = self._live.progress().get("revision", "")
            self._started(False, f"a switch to {running} is already running")
            return
        threading.Thread(target=self._live.switch,
                         args=(graph, asked, _unfinished_choice(q)),
                         name=f"dunneflow-base-{asked}", daemon=True).start()
        self._started(True, "")

    def _started(self, ok: bool, reason: str,
                 progress: Callable[[], dict[str, Any]] | None = None,
                 steps: tuple[str, ...] = BUILD_STEPS) -> None:
        """The answer to a switch request, and the progress **only when one started**.

        200 either way, with one field saying whether anything started. Not a 409 for the
        refusal: the client has to render the *reason* in both cases, and a status code
        beside a reason is two ways to say one thing -- one of which nothing reads.

        The progress rides only on the `started` answer, and that is rule 13 rather than
        neatness. A refusal used to carry it too, so declining a switch to a version with
        no graph replied `started: false` beside `state: "done"` and the *previous*
        switch's revision -- three fields about three different things under one answer.
        A refusal is about the request; it has no progress, because nothing is running.

        **Which slot it reports is the caller's**, and the default is the build one so
        the two switch routes read as they always did. An analysis has its own slot and
        its own steps -- the child names those, so it passes an empty list and the panel
        draws no bar until the first line arrives, which is the same honesty
        `rebuildPanel` already keeps about a total it has not been told (rule 44).
        """
        body: dict[str, Any] = {"started": ok, "reason": reason, "steps": list(steps)}
        if ok:
            body.update((progress or self._live.progress)())
        self._json(body)

    def _r_favicon(self, q: dict[str, list[str]]) -> None:
        # Browsers always ask. Answering "nothing here" is quieter than a 404 in
        # everyone's console.
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    ROUTES: dict[str, str] = {
        "/": "_r_index",
        "/index.html": "_r_index",
        "/api/graph": "_r_graph",
        "/api/diagram": "_r_diagram",
        "/api/fold": "_r_fold",
        "/api/plate": "_r_plate",
        "/api/inside": "_r_inside",
        "/api/flow": "_r_flow",
        "/api/cover": "_r_cover",
        "/api/routines": "_r_routines",
        "/api/packages": "_r_packages",
        "/api/anomalies": "_r_anomalies",
        "/api/documents": "_r_documents",
        "/api/document": "_r_document",
        "/api/node": "_r_node",
        "/api/hover": "_r_hover",
        "/api/curiosities": "_r_curiosities",
        "/api/algorithms": "_r_algorithms",
        "/api/shape": "_r_shape",
        "/api/plateorder": "_r_plateorder",
        "/api/threads": "_r_threads",
        "/api/thread": "_r_thread",
        "/api/naming": "_r_naming",
        "/api/macros": "_r_macros",
        "/api/stated": "_r_stated",
        "/api/checked": "_r_checked",
        "/api/wayin": "_r_wayin",
        "/api/reldocs": "_r_reldocs",
        "/api/glossary": "_r_glossary",
        "/api/table": "_r_table",
        "/api/source": "_r_source",
        "/api/docs": "_r_docs",
        "/api/doc": "_r_doc",
        "/api/docsource": "_r_docsource",
        "/api/files": "_r_files",
        "/api/file": "_r_file",
        "/api/search": "_r_search",
        "/api/revisions": "_r_revisions",
        "/api/changes": "_r_changes",
        "/api/filechanges": "_r_filechanges",
        "/api/anomalychanges": "_r_anomalychanges",
        "/api/base": "_r_base",
        "/api/programs": "_r_programs",
        "/start": "_r_start",
        "/api/root": "_r_root",
        "/api/analysis": "_r_analysis",
        "/api/about": "_r_about",
        "/favicon.ico": "_r_favicon",
    }

    # The one route that changes what this server is showing. Its own table for the same
    # reason `ROUTES` is one (design rule 16): an unhandled path fails by name rather than
    # through a default that looks deliberate. Kept separate from `ROUTES` rather than
    # flagged inside it, so "does a GET ever swap the base" is a question about a list.
    POST_ROUTES: dict[str, str] = {
        "/api/base": "_p_base",
        "/api/program": "_p_program",
        # Not a switch, and the odd one out in this table: it changes nothing this server
        # is showing. It is here because it is the other thing a GET must never start --
        # a prefetch that reads a source tree into a new directory is worse than one that
        # swaps the map, not better.
        "/api/analyze": "_p_analyze",
        # The way out of the one above. A POST for the same reason and a sharper one: it
        # ends a process, which is not a thing a prefetch may do.
        "/api/analyze/stop": "_p_stop_analysis",
        "/api/close": "_p_close",
        "/api/root": "_p_root",
        # Two gestures that reach outside the browser, and both are POSTs for the reason
        # above and a sharper one: one puts a modal window on the reader's screen and the
        # other brings the Finder forward. Neither is a thing a prefetch may do.
        "/api/pickdir": "_p_pickdir",
        "/api/reveal": "_p_reveal",
    }

    # Served directories, checked in order. Kept beside the route table rather than
    # inside the dispatch so both are readable as one list of what this server answers.
    TREES: tuple[tuple[str, Path], ...] = (("/static/", STATIC), ("/vendor/", VENDOR))

    # **What a server with nothing open can still answer.** Everything else needs a
    # version on screen and is refused before it is reached.
    #
    # Two lists for the two tables, on `POST_ROUTES`' own argument: `/api/base` is a
    # readout from cold and a base *switch* when it is posted to, and one list covering
    # both would exempt the second by accident. Kept apart so "may this be asked with
    # nothing open" is a question about a list rather than about a shared name.
    #
    # Each list is of the *exceptions*, and that direction is the whole guard: a route added
    # tomorrow needs a base by default, so from cold it refuses visibly rather than
    # answering out of nothing. Named the other way round -- every route that needs one --
    # a new route would default to *works without a base* and would fail the way rule 49
    # describes, with a plausible empty answer nobody can tell from a real one.
    GET_WITHOUT_BASE: frozenset[str] = frozenset({
        "/", "/index.html", "/favicon.ico",
        "/api/programs",        # the list, and the root it was empty in
        "/api/base",            # what is being built, asked hardest while there is no base
        "/api/analysis",        # a run outlives the page, and starts before any base
        "/api/root",            # the pre-flight for moving them, asked while typing
        # The way back, and it has to work from cold as well -- where it is the common case
        # and `/` already agrees with it. Never a base's business (rule 20's neighbourhood:
        # this reads a file and decides nothing).
        "/start",
    })

    POST_WITHOUT_BASE: frozenset[str] = frozenset({
        "/api/program",         # opening the first one is the same route as a switch
        "/api/analyze",
        "/api/analyze/stop",
        "/api/pickdir",         # choosing a directory precedes having any map
        "/api/reveal",          # the root is exactly what a cold reader asks about
        # Where maps are kept precedes having any map, exactly as `pickdir` does — and it
        # refuses while a map *is* open, so it can only ever act from cold anyway.
        "/api/root",
    })

    def _refuse_without_base(self, raw: str) -> None:
        """Say what is not open, rather than answering as though something were.

        Mostly a defect -- a route that ought to be in `WITHOUT_BASE`, or a page asking too
        early -- and it gets a status and a sentence, which is a thing that can be found. An
        empty payload would be indistinguishable from a version with nothing in it (rule
        49), and that is the failure this whole gate exists to make impossible.

        **It said *"a reader cannot reach this"*, and since `/api/close` they can.** Load
        `/start` while a map is open, close the map in another tab, then press *Close it*:
        that is a race, not a defect, and the 409 is still exactly the right answer -- the
        base really is gone, and the page reads the refusal as *already closed* and reloads
        its list. `NothingOpen` arriving from inside a handler is routed here too, so one
        sentence covers the defect and the race (rule 41).
        """
        # **The reason goes in `explain`, never in the message.** `send_error`'s second
        # argument is the HTTP *status line*, which `http.server` encodes as latin-1 -- so a
        # sentence written for a reader, with the em dash this project writes everywhere,
        # raises `UnicodeEncodeError` from inside the error handler and the socket closes
        # with nothing on it at all. A refusal that cannot be delivered is worse than the
        # confident empty answer this gate exists to prevent, and it was found by pressing
        # the route rather than by any test. `explain` is encoded UTF-8 and is where the
        # sentence belongs.
        self.send_error(
            409, "nothing is open",
            f"This server was started on an output root rather than on a program, and no "
            f"program has been opened yet — so {raw} has nothing to answer about. Open a "
            f"program first.")

    # -- who may ask ------------------------------------------------------- #
    #
    # **Bound to loopback is not the same as answering only this machine's reader.** The
    # reader's browser is on this machine too, and it runs every page they have open. Two
    # things were confirmed with `curl` on 2026-11-12, against a server that checked neither:
    #
    # - a request whose `Host` was `evil.example:8787` was answered in full, which is all
    #   DNS rebinding needs: a page on a name its author controls re-points that name at
    #   127.0.0.1 and is then *same-origin* with this server, free to read every route
    #   (the source of the program, its documents, the maps root's path on this disk);
    # - a `POST` carrying `Origin: http://evil.example` was acted on, and the POSTs here
    #   take their parameters in the query string, so any page could start an analysis of
    #   any directory, move the maps root, or put a folder picker on the screen.
    #
    # So every request passes here first (rule 51: one place, not one per route). A `Host`
    # that is not this server's own address is refused, which is what defeats rebinding: the
    # browser sends the name the page was loaded by. A `POST` must also say it came from this
    # page -- no foreign `Origin`, no cross-site `Sec-Fetch-Site`, and the `X-DunneFlow`
    # header, which a cross-origin page cannot send without a preflight this server never
    # answers.

    MAX_BODY = 1 << 20

    def _own_hosts(self) -> set[str]:
        port = self.connection.getsockname()[1]
        return {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}

    def _refuse(self, why: str) -> None:
        self.send_error(403, "refused", why)

    def _may_ask(self, *, acting: bool) -> bool:
        host = (self.headers.get("Host") or "").strip().lower()
        if host not in self._own_hosts():
            self._refuse(
                "This server answers only as 127.0.0.1 or localhost on its own port, and "
                "this request named another host. Open the address `dunneflow serve` printed.")
            return False
        if not acting:
            return True
        origin = (self.headers.get("Origin") or "").strip().lower()
        site = (self.headers.get("Sec-Fetch-Site") or "").strip().lower()
        own = {f"http://{h}" for h in self._own_hosts()}
        if (origin and origin not in own) or site in ("cross-site", "same-site") \
                or self.headers.get("X-DunneFlow") != "1":
            self._refuse(
                "This request would change something, and it did not come from the "
                "DunneFlow page this server served. Nothing was done.")
            return False
        return True

    def end_headers(self) -> None:
        # On every answer, the refusals included: what a browser is told about this page.
        # Nothing may frame it, nothing may guess a type, nothing leaves in a Referer, and
        # the page loads script, style and data from this server alone. `wasm-unsafe-eval`
        # is Graphviz, which is WebAssembly; `unsafe-inline` for style is the `style=`
        # attributes the views are drawn with. No script is ever inline.
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        super().end_headers()

    def do_GET(self) -> None:                     # noqa: N802  (stdlib's spelling)
        if not self._may_ask(acting=False):
            return
        raw, _, query = self.path.partition("?")
        handler = self.ROUTES.get(raw)
        if handler is not None:
            if not self._live.opened and raw not in self.GET_WITHOUT_BASE:
                self._refuse_without_base(raw)
                return
            # **The gate is a check and the handler is a later moment**, and `/api/close`
            # is the first thing in this codebase that makes `opened` go true -> false. So
            # a request can pass the gate and reach `current` after the base has gone, and
            # an escaping `NothingOpen` goes to `socketserver.handle_error` -- which closes
            # the connection with **nothing on it at all**, rule 91's symptom reached by a
            # different door. Answered as the gate would have answered it, from the same
            # function, so the race and the defect give one sentence (rule 41).
            try:
                getattr(self, handler)(parse_qs(query))
            except NothingOpen:
                self._refuse_without_base(raw)
            return
        for prefix, root in self.TREES:
            if raw.startswith(prefix):
                self._file(root / raw[len(prefix):])
                return
        self.send_error(404, f"no route for {raw}")

    def do_POST(self) -> None:                    # noqa: N802  (stdlib's spelling)
        raw, _, query = self.path.partition("?")
        # Drained whether or not anything is sent. An unread body sits in the socket and
        # the next request on a kept-alive connection starts reading in the middle of it.
        # **Bounded, and a number**: no route here reads a body, so one that claims to be
        # larger than `MAX_BODY`, or whose length is not a count, is refused unread and the
        # connection closed rather than held open reading it (rule 55).
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > self.MAX_BODY:
            self.close_connection = True
            self.send_error(413, "too large", "No request to this server carries a body.")
            return
        if length:
            self.rfile.read(length)
        if not self._may_ask(acting=True):
            return
        handler = self.POST_ROUTES.get(raw)
        if handler is None:
            self.send_error(404, f"nothing here takes a POST: {raw}")
            return
        if not self._live.opened and raw not in self.POST_WITHOUT_BASE:
            self._refuse_without_base(raw)
            return
        # The same race, on the table that can cause it. See `do_GET`.
        try:
            getattr(self, handler)(parse_qs(query))
        except NothingOpen:
            self._refuse_without_base(raw)

    def _json(self, obj: dict[str, Any]) -> None:
        body = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path) -> None:
        # A served path must stay inside the directory it was resolved against, or a
        # request for ../../ walks the disk. Cheap to check, expensive to omit.
        try:
            resolved = path.resolve(strict=True)
            root = (STATIC if str(path).startswith(str(STATIC)) else VENDOR).resolve()
            resolved.relative_to(root)
        except (OSError, ValueError):
            self.send_error(404)
            return
        body = resolved.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", _TYPES.get(resolved.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def already_serving(port: int, out_root: Path) -> str | None:
    """The URL of a DunneFlow already serving **this same root**, or `None`.

    **The application has no way to say "I am already running", so it has to ask.** A
    double-clicked application gets no Dock running-indicator -- the bundle is a command
    line tool that never becomes a foreground process -- so a reader who does not see a
    window appear fast enough launches it again. Before this, every launch took a fresh
    port: three double-clicks left **three servers** on 8787, 50595 and 50596, three browser
    tabs, and three sets of SQLite handles, with nothing on any screen saying so. Measured,
    not supposed.

    That is `_free_port`'s wander, which is right for its own case and wrong for this one.
    A port held by something that is not DunneFlow is a reason to move; a port held by
    **DunneFlow reading the same maps** is the reader's own application, and the useful
    thing to do is show it to them.

    **The same root, and not merely the same program.** A developer serving two output
    roots wants two servers and would be badly served by the second launch silently opening
    the first; a reader double-clicking twice wants one. The root is what tells those apart,
    so it is what is asked -- `/api/programs` carries it for the start page already, and
    this needs no route of its own (rule 51).

    Answers `None` on anything unexpected. This runs before a server exists and its only job
    is to decide whether to make one; a probe that raised would turn a stale socket into an
    application that will not start.
    """
    url = f"http://127.0.0.1:{port}/"
    try:
        with urllib.request.urlopen(f"{url}api/programs", timeout=1.5) as r:  # noqa: S310
            # **The header, before the body.** Another program on 8787 could answer JSON
            # with a `root` in it, and joining that would send the reader somewhere else
            # entirely. `server_version` is this handler's own name (rule 30 -- what is
            # asked is identity, never a shape that resembles one).
            if not str(r.headers.get("Server", "")).startswith("DunneFlow"):
                return None
            said = json.loads(r.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    try:
        theirs = Path(str(said.get("root", ""))).resolve()
    except OSError:
        return None
    return url if theirs == out_root.resolve() else None


def _free_port(preferred: int) -> int:
    """Take the asked-for port, or any free one, rather than failing on a stale server."""
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _run(live: _Live, port: int, open_browser: bool, emit: Any) -> None:
    """Bind, open a browser, and answer until interrupted.

    Its own function because there are two ways to arrive here -- with a version built, and
    with nothing open at all -- and the second one exists so a packaged application can
    start on a fresh machine. Two copies of a bind, a timer and a `finally` that closes the
    stores is two places to forget one of them (rule 51).
    """
    port = _free_port(port)
    handler = partial(_Handler, live=live)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/"
    dock = macapp.available()
    # **Both, where both are true.** The packaged build takes this path whether it was
    # double-clicked or run from a shell, and Ctrl-C still ends it — the signal is handed
    # back to the operating system precisely so that it does (`macapp.run_as_application`).
    # Naming only the Dock would be false to whoever is reading this line, since the only
    # people who ever see it are at a terminal.
    emit(f"serving {url}  ({'quit from the Dock, or ctrl-c' if dock else 'ctrl-c'} to stop)")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    def shut() -> None:
        httpd.server_close()
        live.close()

    # **The packaged application takes the main thread; everything else keeps it.**
    # A bundle whose process never touches AppKit gets no Dock running-indicator -- no dot
    # under the icon -- so a reader who does not see a window fast enough launches it again.
    # `already_serving` stops that becoming three servers; this is the other half, and it is
    # the half that answers the question the reader actually asked.
    #
    # `run_as_application` returns `False` where there is no window server to connect to,
    # and then this falls through to the loop it always ran. A Dock icon is a nicety; a
    # server that would not start without one would be the tail wagging the dog.
    if dock and macapp.run_as_application(httpd.serve_forever, shut):
        return
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        emit("stopped")
    finally:
        shut()


def _serve_cold(live: _Live, out_root: Path, port: int,
                open_browser: bool, emit: Any) -> None:
    """Serve the start page: no base, and the terminal told what is here.

    The same sentence the page will show, said where somebody running this from a shell can
    read it. A server that binds a port and says nothing about *why* it has nothing to show
    is design rule 21's failure one surface over from where that rule was written.
    """
    found = [d.name for d in revisions.programs_under(out_root)]
    emit(f"no program is open; reading {out_root}")
    if found:
        emit(f"{len(found)} here: {', '.join(found)} — pick one on the page, "
             "or analyse a new tree")
    else:
        emit("nothing here yet — the page offers to analyse a directory")
    _run(live, port, open_browser, emit)


def where(given: Path) -> tuple[Path, Path]:
    """Which program this is, and which root it sits under. **Either is accepted.**

    `serve` has always taken a program directory and worked the root out as its parent.
    A packaged application has no working directory to resolve a relative default against
    and, on a fresh machine, no program either -- so the root has to be something it can
    be handed directly.

    The two are told apart by the same question `analyze` asks to keep a program's own
    output out of its own corpus: **does this directory hold a map**. A directory holding
    a `graph@….db` is a program; one holding directories that do is a root. Never by name,
    for `program_dirs`' own reason -- `output/` is a fine name for a directory of
    hand-written prose, and nothing here may claim a directory because of what it is
    called (rule 30).

    It is asked by calling `revisions.holds_a_map` rather than by spelling the glob out,
    and that is the point of the sentence above: this said it was asking the same question
    as `analyze` while asking it separately, which is three copies of one rule waiting to
    disagree (rule 51).

    A root is returned as `(root, root)`, its own program directory, which is what makes
    the refusal below able to say what *is* there. The caller decides what that means.
    """
    given = given.resolve()
    if revisions.holds_a_map(given):
        return given, given.parent
    return given, given


# **A folder picker and a reveal are the two things this server asks the operating system
# for, and they are the only two places in `web/` that are not portable by construction.**
# Each is a *convenience over a control that still works* (design rule 2) -- the typed field
# and the stated path are the controls -- so a platform with no answer refuses in a sentence
# and nothing else changes.
#
# **Getting a dialog in front is most of the code here, and it only works on two of three.**
# The process holding these has no window of its own, so its dialog is placed behind whatever
# does -- which here is always the reader's browser, since that is where they just clicked.
# macOS needs `activate`; Linux's dialogs come forward by themselves, measured. Rule 90, one
# process over from where it was first paid for.
#
# **Windows asks and is refused, and that is documented rather than fixed** (`875499c`, Tom's
# call). The topmost owner form below is the right request and a *server* has no foreground
# rights to spend on it, so the chooser opens behind the browser and `01-installing.md` tells
# the reader to Alt-Tab. Every measurement that said otherwise was taken from an interactive
# shell, which does have those rights: rule 24, three times over, with numbers.

# Windows' folder picker, as one line for `powershell -Command`. `-STA` is required: a
# Windows Forms dialog will not open on a multi-threaded apartment, and the failure is a
# refusal on stderr rather than a hang. `ShowNewFolderButton` is off because this chooses a
# tree to *read*, and an empty new directory is never the answer to that.
_WINDOWS_PICKER = (
    "Add-Type -AssemblyName System.Windows.Forms;"
    "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
    "$d.Description = 'Choose a directory for DunneFlow to read';"
    "$d.ShowNewFolderButton = $false;"
    "$t = New-Object System.Windows.Forms.Form;"
    "$t.TopMost = $true;"
    "if ($d.ShowDialog($t) -eq [System.Windows.Forms.DialogResult]::OK)"
    " { [Console]::Out.Write($d.SelectedPath) };"
    "$t.Dispose()"
)

# So the helper process does not flash a console window over the page. Windows-only, and
# read through `getattr` because the constant does not exist in `subprocess` anywhere else.
_NO_CONSOLE = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# **Linux ships no one dialog, so it has a short list of them and a fixed order.** macOS and
# Windows each have exactly one thing that can ask a person for a folder and it is always
# there; a Linux desktop has whichever its toolkit brought, and plenty have both or neither.
# So this is the one list (rule 51), tried in order, and a machine with none of them refuses
# in a sentence naming what would give it one (rule 89) rather than pretending. That refusal
# is affordable for the reason the whole family is: the typed field is the control and the
# picker is a convenience over it (design rule 2).
#
# **Both spell the outcome the same way**, which is what lets one reader serve two commands:
# exit 0 with the path on stdout, exit 1 for a cancel. Measured on zenity 3.44.2 -- a dialog
# closed from the window manager's own button exits 1 with **nothing at all on stderr**.
#
# `org.freedesktop.portal.FileChooser` is the modern answer and is deliberately not here: it
# returns its result over a signal on a Request object, so reading it means subscribing to
# the session bus, which means a D-Bus binding this tool does not have and will not grow for
# a convenience. Under a portal-backed desktop `zenity` opens the portal's own dialog anyway.
_PICK_PROMPT = "Choose a directory for DunneFlow to read"
_LINUX_PICKERS: tuple[tuple[str, list[str]], ...] = (
    ("zenity", ["zenity", "--file-selection", "--directory", "--title", _PICK_PROMPT]),
    ("kdialog", ["kdialog", "--title", _PICK_PROMPT,
                 "--getexistingdirectory", str(Path.home())]),
)

# **Two rungs for the reveal, and the first is the standards-track one.**
# `org.freedesktop.FileManager1.ShowFolders` is the desktop's own *reveal*: an activatable
# D-Bus service every major file manager implements, so it starts one that is not already
# running, and it consults no MIME default at all. `xdg-open` is the second rung and is the
# one everybody reaches for first -- it works, and it is not quite this question. It hands the
# directory to whatever the desktop says opens `inode/directory`, and **measured on the
# machine this was written on that is `org.gnome.baobab.desktop`**, a disk usage analyser. It
# opened Thunar regardless, because XFCE's `xdg-open` routes through `exo-open` and never
# reads that default -- so one rung is right by construction and the other was right by luck,
# and they are in that order for that reason.
#
# **`--print-reply` is load-bearing.** Without it `dbus-send` does not wait, and exits 0 for
# having sent a message nobody may be listening for -- so a desktop with no file manager on
# the bus would report a successful reveal and never reach the second rung (rule 76: an echo
# is not an act). With it the exit code is the call's own answer. Its timeout is set inside
# the one this process applies, so the rung reports rather than being killed mid-ladder.
_REVEAL_BUS = [
    "dbus-send", "--session", "--print-reply", "--reply-timeout=6000",
    "--dest=org.freedesktop.FileManager1", "/org/freedesktop/FileManager1",
    "org.freedesktop.FileManager1.ShowFolders",
]

NO_PICKER = ("the folder picker is not available on this platform — "
             "type the whole path instead")
NO_REVEAL = "showing a directory in a file manager is not available on this platform"
NO_LINUX_PICKER = ("no folder picker is installed — zenity or kdialog would give you one; "
                   "type the whole path instead")
NO_SESSION = ("there is no desktop session here to open a window in — "
              "type the whole path instead")
NO_SESSION_REVEAL = "there is no desktop session here to show a directory in"


def _desktop_session() -> bool:
    """Is there a screen to put a window on?

    Asked of the environment rather than of a platform, which is the honest question (rule
    30): a Linux build serving over SSH with no forwarding is the same state as one on a
    headless box, and the reader in both cases is looking at a browser somewhere else.

    **It is asked before anything is spawned, and that is what makes the cancel readable.**
    Measured on zenity 3.44.2: a cancel exits **1 with an empty stderr**, and a failure to
    open the display exits **1 with a line on stderr** -- the same code, told apart only by
    text that a perfectly healthy desktop also writes for its own harmless reasons. Ruling
    out the failure that actually happens, in advance and by name, is what leaves exit 1
    meaning one thing.
    """
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _picker_order() -> tuple[tuple[str, list[str]], ...]:
    """Which dialog to try first, which is a question about the desktop and not the folder.

    A GTK dialog on Plasma and a Qt dialog on GNOME both *work*; each simply looks like it
    came from somewhere else, and this is the one window in the tool a reader navigates
    rather than reads. `XDG_CURRENT_DESKTOP` is the standard way to ask and every session
    manager sets it.

    `sorted` is stable, so this promotes one entry and leaves the rest in the order declared
    above -- rather than expressing a two-element preference as a reversal that a third
    picker would silently break.
    """
    kde = "kde" in os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    first = "kdialog" if kde else "zenity"
    return tuple(sorted(_LINUX_PICKERS, key=lambda entry: entry[0] != first))


def pick_folder() -> tuple[str, str]:
    """Ask the operating system for a directory. Returns `(path, reason)`.

    **Three outcomes and not two.** A path is a choice; an empty path with an empty reason
    is a *cancel*, which is the ordinary way out of a dialog and not a failure; an empty
    path with a reason is something that went wrong and that the reader is told about.
    Collapsing the last two would report every cancel as an error in the panel.

    Bounded on both platforms, because this blocks on a person: a dialog left open must not
    hold a server thread for ever. Three minutes is long enough to go and find a folder and
    short enough to recover from one nobody ever saw.
    """
    if sys.platform == "darwin":
        script = ('activate\n'
                  'POSIX path of (choose folder with prompt '
                  '"Choose a directory for DunneFlow to read")')
        try:
            done = subprocess.run(["osascript", "-e", script], capture_output=True,
                                  text=True, timeout=180)
        except (OSError, subprocess.TimeoutExpired):
            return "", "the picker did not answer — type the whole path instead"
        if done.returncode != 0:
            # Cancelling is the ordinary way out of a dialog, and is not a failure. Told
            # apart from a real one by AppleScript's own words rather than by assuming
            # every non-zero exit is a cancel (rule 30).
            said = (done.stderr or "").strip()
            cancelled = "-128" in said or "canceled" in said.lower()
            return "", ("" if cancelled else (said or "the picker failed"))
        # A trailing separator is how `POSIX path of` spells a directory; `analysis.check`
        # takes either, and the field shows what a person would write.
        return done.stdout.strip().rstrip("/") or "", ""

    if sys.platform == "win32":
        try:
            done = subprocess.run(
                ["powershell", "-NoProfile", "-STA", "-Command", _WINDOWS_PICKER],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=180, creationflags=_NO_CONSOLE)
        except (OSError, subprocess.TimeoutExpired):
            return "", "the picker did not answer — type the whole path instead"
        # **A cancel is silence here, not an exit code**, which is the other half of the
        # same rule 30 the macOS branch states: the script writes a path only on `OK`, so
        # nothing on stdout *is* the cancel and there is no code to read it out of. A
        # non-zero exit is therefore always a real failure -- PowerShell absent, the
        # assembly unavailable, `-STA` refused -- and says so in its own words.
        if done.returncode != 0:
            said = (done.stderr or "").strip().splitlines()
            return "", (said[0] if said else "the picker failed")
        return done.stdout.strip() or "", ""

    if sys.platform == "linux":
        if not _desktop_session():
            return "", NO_SESSION
        for name, argv in _picker_order():
            try:
                done = subprocess.run(argv, capture_output=True, text=True,
                                      encoding="utf-8", errors="replace", timeout=180)
            except FileNotFoundError:
                # Not installed. **The one failure that is not this picker's answer**, so it
                # is the one that falls through to the next rather than being reported: a
                # reader on Plasma with no zenity must not be told the picker failed when
                # kdialog is sitting right there.
                continue
            except (OSError, subprocess.TimeoutExpired):
                return "", "the picker did not answer — type the whole path instead"
            if done.returncode == 0:
                # `rstrip` and then *the path back again*, because `/` is a directory whose
                # whole spelling is its separator -- stripped, it becomes the empty string,
                # which this function already spends three outcomes distinguishing from a
                # path. Absurd as a source tree and cheap to not get wrong.
                picked = done.stdout.strip()
                return (picked.rstrip("/") or picked), ""
            if done.returncode == 1:
                # A cancel. **The residue is stated rather than hidden**: a dialog that
                # opened and then broke exits this way too and is reported as a cancel. That
                # is the trade `_desktop_session` buys -- the failure that actually happens
                # is refused before anything is spawned, and what remains has no measured
                # discriminator, only stderr text a healthy desktop also writes.
                return "", ""
            said = (done.stderr or "").strip().splitlines()
            return "", (said[0] if said else f"{name} failed")
        # Every picker tried and none of them installed. Rule 89: the sentence names the two
        # packages that would answer, because the reader's alternative is to type a path and
        # they may prefer to fix it once.
        return "", NO_LINUX_PICKER

    return "", NO_PICKER


def _reveal_linux(target: Path) -> tuple[bool, str]:
    """Show one directory on a Linux desktop, by the two means a desktop offers.

    The rungs and why they are in this order are stated at `_REVEAL_BUS` above. What is
    worth saying here is what happens when they run out.

    **The last rung's reason is the one reported, not the first.** A ladder that kept its
    earliest complaint would answer *"dbus-send is not installed"* on a machine where the
    interesting fact is what `xdg-open` said -- and `xdg-open` is the rung every desktop has,
    so its refusal is the one a reader can act on (rule 89). The first rung failing is
    ordinary: plenty of sessions have no file manager on the bus, and that is precisely the
    case the second rung exists for.

    Permission is not asked about here, exactly as on the other two platforms: `_p_reveal`
    bounds the path to the output root before anything is spawned, because this hands a path
    to the desktop and a localhost POST is a thing a page in another tab can send.
    """
    if not _desktop_session():
        return False, NO_SESSION_REVEAL
    # `as_uri` percent-encodes, which the bus requires and a space in a directory name would
    # otherwise break; the plain path is what a command line wants. Two spellings of one path
    # because the two rungs are genuinely different interfaces, not one with a flag. Both are
    # POSIX by construction, since this branch only ever talks to a Linux desktop: spelt from
    # the native `Path` instead, the tests that drive it under a patched `sys.platform` raised
    # on Windows, where `/tmp/maps` is a relative path and has no URI.
    posix = PurePosixPath(target.as_posix())
    rungs = [
        [*_REVEAL_BUS, f"array:string:{posix.as_uri()}", "string:"],
        ["xdg-open", str(posix)],
    ]
    why = NO_REVEAL
    for argv in rungs:
        try:
            done = subprocess.run(argv, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=10)
        except FileNotFoundError:
            why = f"{argv[0]} is not installed"
            continue
        except (OSError, subprocess.TimeoutExpired) as exc:
            why = str(exc)
            continue
        if done.returncode == 0:
            return True, ""
        said = (done.stderr or "").strip().splitlines()
        why = said[-1] if said else f"{argv[0]} exited {done.returncode}"
    return False, why


def reveal_dir(target: Path) -> tuple[bool, str]:
    """Show one directory in the platform's file manager. Returns `(shown, reason)`.

    **Whether the directory may be shown at all is the caller's question, not this one's**
    -- `_p_reveal` bounds it to the output root before anything is spawned, because this
    hands a path to a shell and a localhost POST is a thing a page in another tab can send.

    Windows' `explorer` **exits 1 on success**, which is long-standing and documented
    nowhere useful, so its return code is deliberately not read: treating it as a failure
    would report every successful reveal as a broken one, and there is no code it gives that
    means anything else (rule 30 -- this is not a status, whatever its shape).
    """
    # Linux is a ladder rather than one command, so it answers for itself; see
    # `_reveal_linux`. The two that *are* one command keep the shape below.
    if sys.platform == "linux":
        return _reveal_linux(target)
    # Bound before the branches rather than in an `else`, so the refusal is one statement
    # on every platform and mypy can check all three of them from any one of them.
    argv: list[str] = []
    if sys.platform == "darwin":
        argv = ["open", str(target)]
    elif sys.platform == "win32":
        argv = ["explorer", str(target)]
    if not argv:
        return False, NO_REVEAL
    try:
        subprocess.run(argv, capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    return True, ""


def no_map_here(out_dir: Path, out_root: Path, revision: str | None) -> str:
    """Why there is nothing to serve, and what to do about it.

    Three sentences rather than one, because *you named a version that is not here*,
    *this directory holds nothing*, and *this root holds programs and you named none of
    them* are different facts and the thing to do about each is different (design rule 21).
    The third lists what it found: a refusal has to name something that can act on it, and
    the reader's next move is a program name they cannot guess (rule 89).
    """
    if revision:
        return f"no graph for {revision} in {out_dir}"
    found = [d.name for d in revisions.programs_under(out_root)]
    if found:
        return (f"{out_dir} holds no map of its own. Under this root: "
                f"{', '.join(found)} — name one of those, or run `dunneflow analyze` "
                f"to read a new tree into it.")
    return f"no graph in {out_dir} -- run `dunneflow analyze` first"


def serve(out_dir: Path, *, port: int = 8787, open_browser: bool = True,
          revision: str | None = None, emit: Any = print, root_gone: str = "",
          allow_unfinished: bool = False) -> None:
    """Open one version of a program and serve it until interrupted.

    `revision` chooses which one, defaulting to the newest -- never a fixed `graph.db`
    name, because a program written in the revision layout has none at all and answering
    "no graph" for it would be rule 20's failure, a reader confidently reporting nothing
    is there.

    It exists because **the base is the server's state, not the browser's.** The reader
    can switch it from the page, and that choice survives a reload; without this flag it
    could not survive a restart of `serve`, and the alternative -- a server reading the
    browser's stored settings -- does not exist.

    `root_gone` is a sentence, empty unless the reader's chosen maps directory is on a disk
    that is not connected. It is carried rather than re-derived because only `cli` knows
    that a fallback happened -- by the time a path arrives here it is just a path, and a
    server that re-read the pointer would be a second place deciding where maps live
    (rule 51). Passed to the page, which is where the reader who has no terminal reads it.
    """
    out_dir, out_root = where(out_dir)
    graph_db = revisions.resolve(out_dir, revisions.GRAPH, revision)
    # **A root with nothing in it is served, not refused.** A directory that is a program
    # and has no map is still a mistake worth a sentence -- the reader named that one --
    # but a root is what a packaged application opens on, and on a fresh machine it holds
    # nothing at all. That is the state the start page exists for.
    #
    # A named `--revision` is always a refusal, whichever kind of directory it is: the
    # reader asked for a version by name, and quietly opening a chooser instead would be
    # answering a question nobody asked.
    cold = out_dir == out_root and not revision
    if (graph_db is None or not graph_db.exists()) and not cold:
        raise FileNotFoundError(no_map_here(out_dir, out_root, revision))

    live = _Live(out_dir / "source.db", out_dir, out_root, root_gone=root_gone,
                 allow_unfinished=allow_unfinished)
    # The same door a base switch goes through, and the whole reason it takes a `step`
    # callback: the terminal gets the boot, a watching page gets a switch, and neither is
    # a second way of building a version (rule 51).
    #
    # Naming the cost of each step here rather than only in the browser, because someone
    # who runs this on a large program and waits ten seconds at a prompt is entitled to
    # the same answer as someone watching the overlay.
    t0 = time.perf_counter()
    if graph_db is None or not graph_db.exists():
        _serve_cold(live, out_root, port, open_browser, emit)
        return
    # **The cost of each step, not only its name.** A step label said what the build was
    # doing and never what it had cost, which is survivable at ten seconds and is not at
    # 27.6 minutes -- and the terminal is the surface where somebody diagnosing that will
    # actually be standing. Printed as each step *ends*, so a run still going has already
    # told the reader everything it knows.
    boot = _Clock()
    # A cursor, not `spent[-1]`: step 1 banks four laps of its own -- the model, the
    # layout, the transposition and the root package -- and a printer that shows only the
    # most recent would drop three of the five numbers the whole instrument is for. Rule
    # 32 one more time: a report must account for what it counts.
    said = 0

    def _drain() -> None:
        nonlocal said
        for was, took in boot.spent[said:]:
            emit(f"      {was} — {took / 1000:.1f}s")
        said = len(boot.spent)

    def _boot_step(name: str, i: int, n: int) -> None:
        _drain()
        emit(f"  [{i + 1}/{n}] {name}…")

    live.open(graph_db, _boot_step, boot)
    _drain()
    if live.current.unfinished:
        emit(f"warning: {live.current.unfinished}")

    files = live.current.files
    naming = live.current.naming
    glossary = live.current.glossary
    emit(f"{files['total']:,} files listed for the code browser")
    emit(f"{len(naming['conventions'])} naming conventions measured; "
         f"{glossary['coverage'][0]:,} of {glossary['coverage'][1]:,} "
         f"terms defined somewhere")

    st = live.current.payload["stats"]
    # Shadows are never drawn -- they are placement devices, standing in on a plate so its
    # layout feels the pull of something living elsewhere. Reporting them as drawn would
    # overstate the picture by half.
    emit(f"{st['nodes']:,} nodes across {st['disks']} plates "
         f"(largest {st['largest_disk']:,}), {st['edges']:,} edges, "
         f"{st['shadows']:,} shadows for placement only")
    emit(f"{revisions.revision_of(graph_db) or 'this version'} is the base, "
         f"built in {time.perf_counter() - t0:.1f} s")

    _run(live, port, open_browser, emit)
