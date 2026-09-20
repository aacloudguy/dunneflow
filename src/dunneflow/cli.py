"""Command line.

    dunneflow analyze <path> --name mensores    extract, resolve, and write the map
    dunneflow touches <path> --routine save     what does this reach?
    dunneflow impact <path> --routine save      what breaks if I change it?
    dunneflow query <path> --sql "..."          ask the graph directly

`analyze` is incremental: run it again after editing and only the changed files are
re-read.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import multiprocessing
import sqlite3
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from . import ingest, revisions
from .anomalies import BROKEN, INFO, SUSPECT, detect
from .docstore import DocStore
from .ingest.contract import PluginRefused
from .lookup import find_routine, search_said
from .migrate import MigrationRefused, migrate_program
from .render.index import legacy_map_files, render_index
from .render.markdown import render_all
from .render.snapshot import mapless, render_maps
from .resolve import languages, manifests
from .resolve import version as program_version
from .resolve.calls import resolve_calls
from .resolve.cli import resolve_cli
from .resolve.entrypoints import (
    binding_note,
    collisions,
    entrypoints_from_manifests,
    record_manifests,
)
from .resolve.flows import entry_reach, governance_over, ways_in_affected
from .resolve.glossary import bind
from .resolve.mirror import BANDS as MIRROR_BANDS
from .resolve.mirror import measure as measure_mirror
from .resolve.naming import measure
from .resolve.typescript import calls as ts_edges
from .runtime import (
    MapsRootGone,
    default_output_root,
    platform_output_root,
    tool_version,
)
from .sourcedb import STATE_FOR_COMPARISON, DocSourceStore, SourceStore
from .sourcedb import capture as capture_source
from .standards import STANDARDS_DB, standards_refusal
from .store import StaleGraphError, Store, UnfinishedMapError, unfinished_sentence
from .walk import (
    TOO_BIG,
    Breakdown,
    analyze_docs_tree,
    analyze_tree,
    parts_under,
    walk_languages,
    walk_residue,
)


def _default_paths(target: Path, name: str | None, out_root: Path) -> tuple[str, Path]:
    program = name or target.resolve().name
    return program, out_root / program


def _emit(msg: str) -> None:
    print(msg, file=sys.stderr)


def speak_utf8() -> None:
    """Say what this program's own channels are encoded in, rather than letting a locale.

    **Everything else about this tool already settled on UTF-8 and only the two streams were
    left to chance.** Every file it writes names `encoding="utf-8"`, every source and every
    document it reads is decoded as UTF-8, and `hash_source` hashes the UTF-8 encoding -- so
    a map is a UTF-8 artefact by construction. `print`, alone, went to whatever
    `locale.getpreferredencoding()` said, which on a Windows machine in most of the world is
    `cp1252`: 256 characters, and this program's own sentences are outside them.

    Two ways that bites, and the first is a crash rather than a blemish. `render/anomalies`
    writes its badges with 🔴 and the naming report writes `\u2192`; neither is in cp1252, so a
    command whose output was **redirected or piped** -- which is exactly how `--progress-json`
    is read, and how a reader captures a report -- ended in a `UnicodeEncodeError` raised from
    inside `print`, several frames from anything that could say what had gone wrong. The
    second is quieter: the em dash and the middle dot that every summary line uses *are* in
    cp1252, so those runs did not fail, they simply wrote a different byte than the one the
    reader's terminal was reading, and the sentence arrived broken.

    **Only where it is not already right, and never on a stream that cannot answer.** A
    console on Windows is UTF-16 through its own API and needs nothing; macOS is UTF-8
    already, so this is a no-op there and the platform is not tested for -- what is tested
    for is the encoding actually in force, which is the honest question (rule 30). A stream
    that pytest or a caller has replaced may have no `reconfigure` at all and is left exactly
    as it was: this decides an encoding, and may not decide who owns the stream.
    """
    for stream in (sys.stdout, sys.stderr):
        if (getattr(stream, "encoding", "") or "").lower().replace("-", "") == "utf8":
            continue
        # A replaced or non-reconfigurable stream is left exactly as it is. Nothing here is
        # worth failing a command over, and doing nothing is the behaviour every earlier
        # build had.
        with contextlib.suppress(AttributeError, OSError, ValueError):
            stream.reconfigure(encoding="utf-8")       # type: ignore[union-attr]


def _out_root(args: argparse.Namespace) -> Path:
    """Where this run's maps go, and **said out loud when nobody chose it.**

    `--output` used to default to the literal `output`, relative to whatever working
    directory the command was run from. That is right for a checkout and meaningless for a
    double-clicked application, which has no working directory worth the name -- so the
    default now comes from `runtime.default_output_root()`, which answers differently in
    the two worlds.

    Two answers to one question is a thing this project distrusts on sight, so the fallback
    **names the directory it chose**. A default that quietly moves between a terminal run
    and an application is exactly the sort of silence that costs a session hunting for a map
    that was written somewhere else.
    """
    if args.output:
        return Path(args.output)
    root = default_output_root()
    _emit(f"no --output given; maps go to {root}")
    return root


def _args_said(args: argparse.Namespace) -> str:
    """What this run was told, as a short readable phrase.

    Only what **removes** something. A map with no documents and a map analysed
    `--no-docs` look identical from the inside, and only one of them is a program that has
    no documentation -- design rule 1 again, one store over.
    """
    said = []
    # **The purest case of this docstring's own argument.** A map analysed
    # `--without typescript` and a map of a tree with no TypeScript in it hold exactly the
    # same rows, and only one of them is a program written in one language. It is what the
    # run was *told* rather than what it found, so there is no count here — the walk says
    # that, on the terminal and in the progress stream.
    for lang in sorted(getattr(args, "without", []) or []):
        said.append(f"{lang.strip().lower()} not read")
    # **A part, and where in its tree it sits.** It belongs here on the docstring's own
    # test -- judging from the tree is what *removes* the files the tree was hiding, which
    # is why `Engine/Binaries` is 3,146 with it and 3,619 without. And it belongs here for
    # a second reason the others do not have: a figure taken off a part cannot be
    # reproduced by anybody who does not know it was read as one (rule 24).
    #
    # The part's path **relative to the tree**, never the tree's own path: an absolute path
    # is one machine's directory layout written into a map built to be handed over
    # (rule 60), and the relative position is the whole of what a reader needs to run the
    # command again.
    #
    # A tree given as its own `--part-of` is the ordinary whole-program case spelled the
    # long way and removes nothing, so it says nothing (rule 13).
    #
    # `relative_to` cannot raise here because `cmd_analyze` refuses a `--part-of` that does
    # not contain the target before anything is opened, several hundred lines above. Said
    # out loud because that is this function's one precondition and a new caller would not
    # find it -- and because catching the error instead would turn a build defect into a
    # map that quietly does not say how it was read (rule 49).
    if getattr(args, "part_of", None):
        where = Path(args.path).resolve().relative_to(Path(args.part_of).resolve())
        if where != Path("."):
            said.append(f"read as a part of its tree, at {where.as_posix()}")
    if args.include_tests:
        said.append("tests included")
    if args.no_docs:
        said.append("documentation not read")
    elif args.docs:
        said.append(f"documentation from {Path(args.docs).name}")
    if args.no_source:
        said.append("source bodies not kept")
    if args.no_doc_source:
        said.append("document bodies not kept")
    if args.no_render:
        said.append("map not written")
    return "; ".join(said)


# -- what an analysis is doing, for whoever is watching it ------------------ #
#
# The dashboard runs `analyze` as a subprocess and draws a bar against these. The labels
# and the count both come from here and are **printed as sent** all the way to the screen,
# so there is one answer to "what does an analysis involve" and no copy of it downstream to
# fall behind (rule 51). `serve.py`'s `BUILD_STEPS` is the same shape one subject over.

STEP_EXTRACT = "reading the source tree"
STEP_DOCS = "reading the documents"
STEP_DOC_BODIES = "capturing the document bodies"
STEP_STANDARDS = "reading the standards"
STEP_RESOLVE = "resolving calls and command trees"
STEP_BODIES = "capturing the source bodies"
STEP_RENDER = "writing the map"
STEP_ANOMALIES = "looking for anomalies"

# Every label that exists, so a step advanced under a name nobody declared is caught here
# rather than becoming a bar that silently never moves.
ALL_STEPS = frozenset({
    STEP_EXTRACT, STEP_DOCS, STEP_DOC_BODIES, STEP_STANDARDS, STEP_RESOLVE,
    STEP_BODIES, STEP_RENDER, STEP_ANOMALIES,
})

# **Not a step, and deliberately not in `ALL_STEPS`.** Nothing advances to it and no bar
# draws it: it is the name the timings table gives to everything that happens before the
# first step, which is where a refusal is decided, a tree is walked to size it, a package
# root is found and three stores are opened. A run reports progress from its first step
# and always has; what it could not do was say what the run had already spent getting
# there, which on a small part is most of it.
STEP_BEFORE = "before the first step"


def analysis_steps(args: argparse.Namespace) -> tuple[str, ...]:
    """The steps *this* run will take, in order.

    **Computed for the run, never a constant**, and that is rule 32 rather than
    fastidiousness: four flags remove work. `--no-docs` drops two of these, `--no-source`
    and `--no-render` one each. A fixed tuple would put a total on the bar that a
    `--no-docs` run can never reach -- and a progress bar that stops at five of seven is
    indistinguishable from a run that died at step five.
    """
    steps = [STEP_EXTRACT]
    if not args.no_docs:
        steps.append(STEP_DOCS)
        if not args.no_doc_source:
            steps.append(STEP_DOC_BODIES)
    # A step the reader *adds* rather than one a flag removes, which is the same argument
    # from the other side: a run given no standard must not show a step it will never take.
    if getattr(args, "standards", None):
        steps.append(STEP_STANDARDS)
    steps.append(STEP_RESOLVE)
    if not args.no_source:
        steps.append(STEP_BODIES)
    # **Anomalies before the map**, because the map is written out of the report and was
    # detecting it twice more to get one. Order follows work; the set and the count are
    # unchanged.
    steps.append(STEP_ANOMALIES)
    if not args.no_render:
        steps.append(STEP_RENDER)
    return tuple(steps)


class _Progress:
    """`--progress-json`: one JSON object per line on **stdout**, or nothing at all.

    Two channels, and keeping them apart is the whole point. stdout is the machine
    channel; stderr keeps the prose it has always printed and stays governed by
    `--quiet`, which is where a failure's reason comes from. Scraping the prose instead
    would make a sentence written for a human into a contract (rule 30).

    Flushed every line. A buffered pipe reports nothing for ninety seconds and then
    everything at once, which is a progress report that is only correct after it stops
    being needed.

    **The step label is asserted against the list**, because a step advanced under a name
    `analysis_steps` did not produce is a bar that silently never moves -- the shape of
    rule 44, arriving from the other end.

    **It times what it announces**, and that is why the timing lives here rather than in
    eight places. `analyze` has had three `perf_counter` spans for a year -- extraction,
    resolution, rendering -- and between them they cover about half of what a run does:
    the size guard's walk, the store and sidecar opens, the documents, the document
    bodies, the standards, the source bodies and the anomalies were all untimed. That was
    survivable until a part of **fifteen files cost 110-400 seconds** on Unreal, at which
    point the only instrument anybody had was a stopwatch against a total (`BACKLOG.md`
    item 9). A step is the one thing every phase already passes through, so timing it here
    costs one `perf_counter` and cannot fall behind the list (rule 51).

    The clock starts when the reporter is built, which is before the graph is opened,
    because the first thing worth timing is the opening.
    """

    def __init__(self, steps: tuple[str, ...], on: bool) -> None:
        self.steps = steps
        self.on = on
        self.i = 0
        self.label = steps[0] if steps else ""
        # **The pre-step region is a phase with no name and it was the suspect**, so it is
        # timed like the others and reported under one: everything from the first argument
        # to the first `step()` -- the size guard's `discover`, the manifest walk-up, the
        # standards refusals, the source store and the graph.
        self._t0 = time.perf_counter()
        self._at = self._t0
        # **Milliseconds, as `web.serve._Clock` records them.** Two instruments and one
        # unit: they are separate classes because they time separate things on separate
        # surfaces, and the one way that costs a session is for the number to mean
        # seconds in one of them.
        self.spent: list[tuple[str, int]] = []
        # Where a step is also **recorded**, so a map that never finished can name where it
        # stopped. Wired to the store once there is one -- the reporter is built before the
        # graph is opened, because it has to be able to report the opening.
        #
        # `None` until then, and nothing here fills it in: a `_Progress` with no store has
        # nothing to record into, and a fallback that wrote somewhere plausible instead
        # would hide exactly the run this exists for (rule 49).
        self.mark: Callable[[str, str], None] | None = None

    def _say(self, **fields: object) -> None:
        if not self.on:
            return
        print(json.dumps(fields), flush=True)

    def _close(self, label: str) -> None:
        """Bank what the phase just finishing cost. Called on every advance, and at the end."""
        now = time.perf_counter()
        self.spent.append((label, round((now - self._at) * 1000)))
        self._at = now

    def step(self, label: str) -> None:
        """Advance to a named step. A step this run is not taking is not an error here."""
        assert label in ALL_STEPS, f"unknown analysis step {label!r}"
        if label not in self.steps:
            return
        # The first advance closes the region *before* any step, which has no label of
        # its own and was the untimed half of the run.
        self._close(self.label if self.spent else STEP_BEFORE)
        self.i = self.steps.index(label)
        self.label = label
        # Committed as it goes, so a killed run leaves a map that can say *"stopped while
        # reading the documents"* rather than only *"stopped"*. Seven commits over a
        # ninety-second run.
        if self.mark is not None:
            self.mark("step", label)
        self._say(state="working", step=label, done_steps=self.i,
                  steps=len(self.steps), detail="", ms=self.ms())

    def ms(self) -> int:
        """Milliseconds since the run began.

        **On every object, because the stream had none at all.** `dunneflow serve` runs its
        child `--progress-json --quiet`, so the three timings `analyze` printed went to a
        stderr nobody was reading and the application could say how far a run had got but
        never how long it had taken. A cumulative figure rather than a delta: a client that
        misses a line still has a true number, which a delta does not survive.
        """
        return round((time.perf_counter() - self._t0) * 1000)

    def detail(self, done: int, total: int) -> None:
        """Restate the current step with a count. The step is unchanged; only the inside."""
        self._say(state="working", step=self.label, done_steps=self.i,
                  steps=len(self.steps), detail=f"{done:,}/{total:,}", ms=self.ms())

    def residue(self, lines: list[str]) -> None:
        """What the walk left out, once, as its own object on the machine channel.

        **Design rule 1 on the surface this tool is actually for.** These sentences have
        always been written -- `walk_residue` computes them and `_emit` prints them -- but
        `_emit` is stderr and `dunneflow serve` runs its child `--quiet`, so *unread: 4,120
        `.go`*, *left out as tests: 315 typescript* and *declined by you* reached a terminal
        and never the application. A reader who analyses from the dialog got the bar and the
        map and no account of what was filtered out of them.

        **Sent once, when the walk knows, and not repeated.** The stream is one object per
        line and the steps after this one are many; carrying the residue on every line
        would multiply a fixed fact by however long resolution takes. The *watcher* is what
        makes it survive to the end -- `_Live.note_analysis` replaces the report whole, so
        `residue` is carried across there exactly as `began` is, and that stickiness is a
        term of this contract rather than an accident of it.

        **The current step is restated with it**, so a client that reads this object like
        any other does not see the bar jump to a step-less record. Same fields as `detail`,
        one key more.
        """
        self._say(state="working", step=self.label, done_steps=self.i,
                  steps=len(self.steps), detail="", residue=lines, ms=self.ms())

    def done(self, **fields: object) -> None:
        self._say(state="done", step="", done_steps=len(self.steps),
                  steps=len(self.steps), ms=self.ms(), **fields)

    def timings(self) -> list[str]:
        """The phase table, in the order the run took them.

        Chronological rather than by size, because a reader comparing two runs of the same
        tree needs the rows to line up, and because the order is itself a fact about the
        run -- an ordering by cost would hide that the documents come after the source.

        **The gap is the finding and the total is not.** A part of fifteen files costing
        two hundred seconds is not slow at reading fifteen files; what the table has to
        show is which phase is indifferent to how much there is to do. So every phase is
        listed, including the ones that cost nothing -- a phase absent from a table is
        indistinguishable from a phase that was instant, and only one of those is news
        (design rule 21).
        """
        now = time.perf_counter()
        total = now - self._t0
        # **The phase still running is one of them**, computed here rather than banked by
        # whoever happens to call this. `done()` is only reached on the machine channel --
        # the prose path prints a summary instead -- so a table built from `spent` alone
        # is a table with its last phase missing, and the last phase is the anomalies.
        # Rule 32: a count must say what it counts, and a row that is simply absent says
        # nothing at all.
        rows = [*self.spent, (self.label, round((now - self._at) * 1000))]
        width = max(len(n) for n, _ in rows)
        lines = [f"  {name:<{width}}  {took / 1000:7.1f}s  {took / 10 / total:5.1f}%"
                 for name, took in rows]
        lines.append(f"  {'the whole run':<{width}}  {total:7.1f}s")
        return lines


# How many parts a refusal prints before it stops and says how many are left. A tree splits
# the way its own directories do, not evenly: Unreal comes out as 86 parts of which 18 hold
# 90% of the files and 50 hold 1.5% between them. Printing all 86 into a terminal -- or into
# the application's analysis pane, which is narrower than prose (rule 91) -- buries the ones
# that matter under the ones that do not. The bound is stated when it bites and `--parts`
# prints the whole list, so nothing is hidden (design rule 1).
PARTS_SHOWN = 12


def part_name(part: Path, root: Path) -> str:
    """What a part of `root` is called.

    The part's path under the root, dotted -- `Engine.Source.Runtime` -- because that is
    what tells two parts apart when a reader is looking at a list of them, and a bare leaf
    name does not: this tree holds two directories called `Runtime`.
    """
    rel = part.relative_to(root)
    return ".".join(rel.parts) if rel.parts else root.name


def part_argv(part: Path, root: Path, out_root: Path) -> list[str]:
    """The one spelling of the command that reads a part of a tree (rule 51).

    Two things wrote this command independently until 2026-09-20 -- the refusal that prints
    it and `tools/ingest_parts.py`, which runs it -- and a rule kept at two call sites is
    one that has to be right in both. It was not: the driver and the printer are the two
    places `--part-of` had to reach, and either of them forgetting it is a map with facts
    in that the tree would not have gathered, reported as a success.

    **`--part-of` is on every part, not only the ones that need it.** For a part whose path
    crosses no name a reader skips and no test directory the flag changes nothing, because
    the components it adds to the judged path are exactly the ones that match nothing -- so
    one rule is both correct and cheaper to keep than a condition somebody has to evaluate.

    Every part goes to **one output root**, so the pieces of one tree sit together as one
    maps root and `dunneflow serve` lists them side by side.
    """
    return ["dunneflow", "analyze", str(part),
            "--part-of", str(root),
            "--name", part_name(part, root),
            "--output", str(out_root / root.name)]


def _part_lines(parts: list[tuple[Path, int]], root: Path, args: argparse.Namespace,
                limit: int | None) -> list[str]:
    """One runnable command per part, ready to paste."""
    out_root = _out_root(args)
    shown = parts if limit is None else parts[:limit]
    return [
        "  " + " ".join(_shell_quote(a) for a in part_argv(d, root, out_root))
        + f"   # {n:,} files"
        for d, n in shown
    ]


def _shell_quote(s: str) -> str:
    """Quote a path for a line somebody is going to paste into a shell.

    Not `shlex.quote`, whose job is safety against a hostile string; this is a path that
    already exists, and what it has to survive is a space in it. A path with no space is
    left bare, because quoting every one of them makes a list of commands harder to read for
    a hazard that is not there.
    """
    return s if all(c not in s for c in ' \t"\'\\') else "'" + s.replace("'", "'\\''") + "'"


def _size_verdict(root: Path, args: argparse.Namespace,
                  part_of: Path | None = None) -> int | None:
    """Refuse a tree too big to finish, and say what to read instead. `None` means carry on.

    **What the number means matters more than the number.** `walk.TOO_BIG` is the edge of
    what this tool is known to read rather than a limit somebody liked the look of, so the
    sentence carries its provenance: a reader deciding whether to use `--any-size` is
    deciding whether to go past the largest tree anyone has taken through it, and that is a
    different decision from exceeding a setting.

    **`part_of` is asked the same question the analysis will be**, or the guard refuses the
    command the guard itself printed. `Engine/Source/ThirdParty` is 620 files as a part of
    Unreal and 57,373 as a root of its own, and a bound applied to the second of those
    numbers would turn the fix for `BACKLOG.md` item 10 into a refusal (rule 51: the walk
    and the guard cannot be allowed two answers about what a command reads).

    A tree named here is also the root the parts are **named and rooted against**, so a
    part that still has to be cut yields sub-parts of the same tree rather than of itself.
    """
    tree = part_of or root
    cut = parts_under(root, judge_root=part_of)
    total, parts = cut.total, cut.parts

    if args.parts:
        if cut.whole:
            # A tree already inside the bound has no parts, and saying so is the answer to
            # the question rather than an empty list (design rule 21).
            _emit(f"{root} is one part: the walk reads {total:,} files of it, within the "
                  f"{TOO_BIG:,} this tool is known to finish.")
            return 0
        _emit(f"{root} is {total:,} files the walk would read, cut into {len(parts):,} "
              f"parts of at most {TOO_BIG:,}:")
        for line in _part_lines(parts, tree, args, None):
            _emit(line)
        _emit_uncovered(cut, tree)
        return 0

    if cut.whole:
        return None

    _emit(
        f"error: {root} is {total:,} files the walk would read, and the largest tree this "
        f"tool is known to read in one go is {TOO_BIG:,}.\n"
        f"\nThat is not a setting. Past it a run has never been finished here — the last "
        f"attempt at a tree this size reached 0.1% CPU after an hour and three quarters and "
        f"was stopped — so what follows is the tree cut into parts that are each within it, "
        f"every one into the same output root so they can be read side by side:"
    )
    for line in _part_lines(parts, tree, args, PARTS_SHOWN):
        _emit(line)
    if len(parts) > PARTS_SHOWN:
        rest = parts[PARTS_SHOWN:]
        _emit(f"  … and {len(rest):,} more parts, {sum(n for _, n in rest):,} files — "
              f"`dunneflow analyze {_shell_quote(str(root))} --parts` prints all of them.")
    _emit_uncovered(cut, tree)
    _emit("\nOr `--any-size` to read it whole anyway, however long it takes.")
    return 2


def _emit_uncovered(cut: Breakdown, root: Path) -> None:
    """Say which files no part reaches, where there are any.

    Never silent and never invented: a directory that had to be split cannot also be a
    command, so its own files are outside every part (`walk.Breakdown`). It is empty on
    every tree measured — Unreal puts none there — and the sentence appears only when it
    would be true.
    """
    if not cut.uncovered:
        return
    n = sum(k for _, k in cut.uncovered)
    _emit(f"\n{n:,} files sit directly in a directory that had to be split, so no part "
          f"above reaches them — reading that directory would read its parts again:")
    for d, k in cut.uncovered:
        _emit(f"  {d.relative_to(root)}   # {k:,} files")


def cmd_analyze(args: argparse.Namespace) -> int:
    target = Path(args.path).resolve()
    if not target.exists():
        _emit(f"error: {target} does not exist")
        return 2

    # **Judged before anything is opened**, like every other refusal that can be decided
    # from the arguments alone: a name nobody reads must not abandon a half-written map.
    try:
        declined = ingest.decline(getattr(args, "without", []) or [])
    except PluginRefused as exc:
        _emit(f"error: {exc}")
        return 2

    # **The tree this is a part of, judged here for the same reason.** It decides which
    # files are read, so a wrong one is a map with the wrong facts in it rather than a
    # command that fails, and there is nothing to be gained from finding out after a store
    # is open. An ancestor or nothing: a directory the part does not sit under cannot
    # supply a relative path for it at all, and the sentence says both paths because
    # neither alone tells a reader which end they got wrong (rule 89).
    part_of: Path | None = None
    if getattr(args, "part_of", None):
        part_of = Path(args.part_of).resolve()
        if not part_of.is_dir():
            _emit(f"error: --part-of {args.part_of} is not a directory that exists.")
            return 2
        if not target.is_relative_to(part_of):
            _emit(f"error: --part-of {part_of} does not contain {target}, so it is not the "
                  f"tree this is a part of. The flag says where to judge a reader's skip "
                  f"rules and its test rule from, and that has to be a directory the part "
                  f"sits under.")
            return 2

    source_root = target
    out_root = _out_root(args)
    program, out_dir = _default_paths(target, args.name, out_root)

    # **The size guard, judged before anything is opened**, like the refusals above it: a
    # tree nobody can finish must not abandon a half-written map. It costs a `discover()` --
    # 52 s on a tree of 88,356 files -- and that is the trade being made and is said out
    # loud, because a minute spent here is the alternative to an hour spent finding out.
    if args.parts or not args.any_size:
        verdict = _size_verdict(source_root, args, part_of)
        if verdict is not None:
            return verdict
    # What this run will do, decided before it starts doing it: the dashboard draws a bar
    # against this list and it has to be right from the first line.
    prog = _Progress(analysis_steps(args), on=args.progress_json)

    # Which snapshot this analysis writes, decided before anything is opened because it
    # names the files. The sidecar is the authority: `open_working` reuses the revision
    # that is already open, so analysing twice without sealing rewrites one snapshot
    # rather than leaving two half-filled ones -- and a sealed sidecar hands back a new
    # id, which is how a second point in time comes to exist beside the first.
    #
    # `--no-source` leaves nothing to ask, so the clock answers instead. The layout is
    # the same either way; what is missing is the state (WORKING / FOR_COMPARISON),
    # which only the sidecar records.
    # Where the **manifests** live, which may be above `src/`. Found once, here, because
    # four things want it: the entrypoint reader, the version reader, the documentation
    # root, and the name of the tree recorded below.
    #
    # This walked up for `pyproject.toml` alone until chunk 12, which was the whole truth
    # while Python was the only language and is an answer of *no* for every TypeScript,
    # Rust, Go and Swift tree there is. `find_package_root` asks for any of the six, and
    # returns **every** manifest at that level -- two at one directory is the ordinary
    # polyglot repository (DunneNote's `package.json` beside its `Cargo.toml`), and
    # stopping at the first would make the answer depend on which name sorts earlier.
    #
    # **`part_of` is the ceiling, and without one the climb has none.** It reached the
    # Developer directory from a part of Unreal -- four levels above the tree, on a stray
    # `package.json` -- and took the document root and the tree's name with it. See
    # `find_package_root`.
    pkg_root, root_manifests = manifests.find_package_root(target, part_of)

    # The leaf that **identifies this tree**, and only the leaf: `target` is an absolute
    # path, and recording it would put one machine's directory layout into a map built to
    # be handed over (rule 60).
    #
    # The *package* root's leaf, not the analysed directory's. Analysing a `src/` layout
    # means `target` is `.../society-2026-08-26/src`, whose leaf is `src` -- which names
    # every src-layout program ever analysed and so identifies none of them. Measured on
    # the real corpus, which is the only place it shows: the toy fixtures have no `src/`
    # and recorded the right answer by having nowhere else to go.
    tree_leaf = pkg_root.name

    # **Every standards root is judged before anything is opened**, and a single refusal
    # stops the run. Checking them here rather than beside the scan is deliberate: by the
    # time the corpus is being read there is a graph, a source snapshot and a document
    # store on disk, and refusing then would either abandon a half-written map or -- worse
    # -- carry on with the offending root dropped, reporting part of a standard as the
    # whole of one. Rule 20: a read may refuse, but it may never repair.
    standards_roots: list[Path] = []
    if getattr(args, "standards", None):
        would_read_docs = None if args.no_docs else (
            Path(args.docs).resolve() if args.docs else pkg_root)
        standards_out_root = out_root.resolve()
        refused = False
        for given in args.standards:
            root = Path(given).resolve()
            why = standards_refusal(root, tree=target,
                                    out_root=standards_out_root,
                                    docs_root=would_read_docs)
            if why:
                _emit(f"error: --standards {given} refused — {why}")
                refused = True
            else:
                standards_roots.append(root)
        if refused:
            return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    source: SourceStore | None = None
    if not args.no_source:
        source = SourceStore(out_dir / "source.db")
        source.set_meta("program", program)
        revision = source.open_working(tree=tree_leaf)
    else:
        revision = revisions.stamp()

    db_path = (Path(args.db) if args.db
               else revisions.db_path(out_dir, revisions.GRAPH, revision))

    t0 = time.perf_counter()
    store = Store(db_path)
    # The identity, inside the file. The name is derived from this and not the other way
    # round, so a graph someone renamed can still say which snapshot it is (rule 30).
    store.set_meta("revision", revision)
    store.set_meta("program", program)
    #
    # `source_root` is **not** recorded here, and its absence is the decision. It is one
    # machine's directory layout: it leaks that layout to whoever the map is handed to, it
    # is wrong the moment the tree is moved, and it is wrong on every machine a copy
    # reaches. Every path in this graph is relative to it, and nothing at read time needs
    # it back -- bodies come from `source.db` by content hash, never by opening a path.
    # The one step that touches the disk is this one, and it is holding the root already.
    # See `migrate.py`.
    #
    # When this map was made. The cover says it out loud, because a map is a reading of
    # a program at a moment and a reader who cannot see the moment cannot judge the map.
    store.set_meta("analysed_at",
                   datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"))
    # **Unfinished until proven otherwise, and committed now.** Rule 80. A killed `analyze` leaves a
    # graph that opens perfectly and reports a program that calls nothing -- see
    # `UnfinishedMapError`. This is the only thing that can speak for a run that does not
    # reach its own last line, so it is written before any work starts and committed on the
    # spot: an uncommitted marker is lost by exactly the `kill -9` it exists for.
    store.set_meta_now("complete", "")
    prog.mark = store.set_meta_now

    # -- what read this map, and whether anything was guessed ---------------- #
    #
    # **A standing guarantee, not a placeholder waiting for a model.** Nothing on this path
    # calls a model or touches a network: the extractors are stdlib `ast` and `tokenize`,
    # the document scanner is hand-written, and `Provenance`'s two paid tiers (CITED,
    # INFERRED) are declared and unbuilt. So `inference` says `none` because that is the
    # fact, and design rule 21 says a thing worth knowing is stated rather than left absent.
    #
    # `model` is written **empty** rather than omitted, and the difference is the whole
    # reason it is here: a key that is missing means *this map predates the question* and a
    # key that is blank means *nothing read it but the code* -- two different facts that a
    # reader would otherwise have to tell apart by the absence of a row (rule 30). When a
    # reader ever turns inference on, voluntarily, this is where the answer goes.
    store.set_meta("tool_version", tool_version())
    store.set_meta("inference", "none")
    store.set_meta("model", "")
    # What the run was told, so a thin map can say it was asked to be thin rather than
    # leaving a reader to wonder why a program has no documents (design rule 1).
    store.set_meta("analysis_args", _args_said(args))

    def progress(path: str, i: int, total: int) -> None:
        if i % 50 == 0 or i == total:
            prog.detail(i, total)
        if args.quiet:
            return
        if i % 50 == 0 or i == total:
            _emit(f"  extracting {i}/{total}")

    prog.step(STEP_EXTRACT)
    stats = analyze_tree(
        source_root, store, include_tests=args.include_tests,
        jobs=args.jobs, progress=progress, declined=declined, part_of=part_of,
    )
    t_extract = time.perf_counter() - t0

    # **What the walk left out, said on both channels and recorded on the map.**
    #
    # Three places rather than one, and they are three different readers. The terminal has
    # always had these sentences and still gets them below, where they sit among the other
    # figures a run prints. The machine channel gets them here, the moment they are known,
    # because the dialog's panel is the surface this tool is actually for and it was the
    # one surface that could not see them (design rule 1). And `meta` gets them because a
    # panel is dismissed and a map is kept: *what is not in this map* is a fact about the
    # map, and a reader who opens it next week is owed it as much as the one watching it
    # being made.
    #
    # **Recorded even when it is empty**, which is the answer that could not otherwise be
    # given. A map written before this key existed cannot say what was left out; one that
    # records an empty list is saying *nothing was* -- and collapsing those two would turn
    # a silence into a promise, which is the distinction every field in *About this map*
    # is built on (design rule 21).
    residue = walk_residue(stats)
    prog.residue(residue)
    store.set_meta("walk_residue", json.dumps(residue))

    # **Every manifest, not one.** The package root's -- which for a `src/` layout means
    # `../pyproject.toml`, because packaging metadata sits above the code -- and every
    # one the walk passed inside the tree. The second half is Tom's criterion, 2026-09-17:
    # *any module that has inputs and/or outputs is included, because that is flow*. A
    # `bin` is a way in, so a member declaring one is part of the application whether or
    # not it sits at the top of it.
    #
    # The walk collected them off the listing it had already taken, so which directories
    # count is answered once: `SKIP_DIRS`, every dotted directory and every directory
    # holding a map are gone before a filename is looked at (rule 92).
    readings = manifests.read_all(root_manifests, stats.manifests,
                                  relative_to=source_root)
    entrypoints_from_manifests(readings, store)
    record_manifests(readings, store)

    # What the program says its own version is, with the tier it was learned at. Recorded
    # even when it is nothing: two versions of a program are two directories, and a reader
    # holding both is entitled to whatever each one claims about itself -- or to being told
    # plainly that it claims nothing. Never asked of a VCS; see `resolve/version.py`.
    stated = [r.version for r in manifests.versions(readings) if r.version]
    found = program_version.detect(source_root, package_root=pkg_root, leaf=tree_leaf,
                                   declared=stated)
    if found is not None:
        store.set_meta("program_version", found.value)
        store.set_meta("program_version_tier", str(found.provenance))
        store.set_meta("program_version_where", found.where)
    # **Two declared versions are both recorded, and neither is picked.** The key above
    # carries one value because a version strip draws one; this carries every declaration
    # with the file that made it, so the cover can say *this program declares two* rather
    # than quietly showing whichever `PROVIDERS` happened to order first. A tree stating
    # two versions is the honest answer and also a signal: it may be two programs.
    #
    # Written only where more than one root manifest declares anything, so a Python
    # program's `meta` is exactly what it was.
    if len(stated) > 1:
        store.set_meta("program_versions", json.dumps(
            [{"value": v.value, "tier": str(v.provenance), "where": v.where}
             for v in stated]))

    # Documentation is a parallel input, read from the package root because that is
    # where prose lives relative to `src/`. It is never a prerequisite: a program with
    # no documents yields an empty document store and a complete code map.
    doc_stats = None
    doc_store: DocStore | None = None
    docs_root: Path | None = None
    if not args.no_docs:
        docs_root = Path(args.docs).resolve() if args.docs else pkg_root
        doc_store = DocStore(revisions.db_path(out_dir, revisions.DOCS, revision))
        doc_store.set_meta("revision", revision)
        doc_store.set_meta("program", program)
        # **Every map, kept out of this run's corpus** -- asked of the tree by the walk,
        # which is where that question belongs and where `discover_docs` records why.
        #
        # This used to read `frozenset({out_dir}) | revisions.program_dirs(out_dir.parent)`,
        # and the second half was the whole defence: every map under the output root, not
        # just this program's. It held from a checkout, where the output root is `./output`
        # and so inside the tree being read, and it was empty from the packaged application,
        # whose root is `~/Library/Application Support/DunneFlow` (rule 92). Left here now
        # it would be a no-op reading as the live defence, so it is gone.
        #
        # `out_dir` stays, because the walk cannot see it: it is created above and holds no
        # graph until this run writes one.
        # `analyze_docs_tree` has taken a `progress` callback since it was written and was
        # never given one, so on a 2,064-document corpus the bar sat still through most of
        # a minute. The terminal never noticed -- there was nothing drawing a bar.
        def doc_progress(path: str, i: int, total: int) -> None:
            if i % 50 == 0 or i == total:
                prog.detail(i, total)

        prog.step(STEP_DOCS)
        doc_stats = analyze_docs_tree(
            docs_root, doc_store, jobs=args.jobs, recheck=args.recheck_docs,
            progress=doc_progress,
            exclude=frozenset({out_dir}))
        duplicates = doc_store.mark_duplicates()
        dc = doc_store.counts()
        if not args.quiet:
            if getattr(doc_store, "rebuilt", False):
                _emit("document store written by older prose rules — discarded and re-read")
            _emit(
                f"documents {doc_stats.found} (read {doc_stats.parsed}, "
                f"cached {doc_stats.cached}, removed {doc_stats.removed}, "
                f"failed {doc_stats.failed}): {dc['definitions']:,} definitions, "
                f"{dc['doc_rules']:,} stated rules, {dc['doc_annotations']:,} governance ids"
                + (f"; {duplicates:,} are copies of another document"
                   if duplicates else "")
            )
            # Design rule 1: no filter is ever silent. A nested checkout can be most
            # of a corpus -- two stale worktrees were 335 of Mensores' 2,381 documents
            # -- and a reader comparing two points in time would otherwise read their
            # absence as the project having deleted them.
            for d in doc_stats.nested:
                where = Path(d)
                shown = (where.relative_to(docs_root)
                         if where.is_relative_to(docs_root) else where)
                _emit(f"  skipped {shown} — a checkout of its own, not this program")
            # And its own sentence, because it is its own reason. A map found here is a
            # report *about a program* -- usually a different one -- and a reader told only
            # that something was "skipped" cannot tell that from a checkout.
            for d in doc_stats.maps:
                where = Path(d)
                shown = (where.relative_to(docs_root)
                         if where.is_relative_to(docs_root) else where)
                _emit(f"  skipped {shown} — a map of a program, not documentation about one")
        doc_store.optimize()

        # The **document** sidecar, the exact mirror of the source one below and driven the
        # same way: by the hashes the scan just recorded rather than by a second walk, so a
        # document whose body is already held is never opened again.
        #
        # `docs.db` records what a document *says* -- its headings, definitions, stated rules
        # and tables. Nothing anywhere held what it **is**, so 2,064 documents were mined and
        # unreadable: the glossary could quote a definition's line and then say, in as many
        # words, that it could not open the document it came from. Design rule 11 calls
        # documentation and source *equal inputs*, and source had a sidecar and a browser
        # while documentation had neither.
        #
        # Its own file rather than a lane in `source.db`, because design rule 14 turns on the
        # two being separately handable -- *"many will send documentation and never source"*.
        if not args.no_doc_source:
            prog.step(STEP_DOC_BODIES)
            docsource = DocSourceStore(out_dir / "docsource.db")
            docsource.set_meta("program", program)
            # Under the id `source.db` already chose, never one of its own: two sidecars
            # describing one analysis must name the same snapshot (see `adopt_revision`).
            docsource.adopt_revision(revision, tree=tree_leaf)
            doc_src_stats = capture_source(doc_store.known_hashes(), docsource,
                                           root=docs_root, revision=revision)
            dsc = docsource.counts()
            if not args.quiet:
                _emit(
                    f"documents: {dsc['blobs']:,} bodies for {dsc['paths']:,} paths "
                    f"({dsc['stored'] / 1e6:.1f} MB stored, {dsc['bytes'] / 1e6:.1f} MB of "
                    f"prose) — {doc_src_stats['stored']:,} read, "
                    f"{doc_src_stats['cached']:,} already held"
                    + (f", {doc_src_stats['missing']:,} unreadable"
                       if doc_src_stats["missing"] else "")
                )
            docsource.close()

    # **The standard, read into a store of its own.** Everything above describes what this
    # program says about itself; this is what somebody else says every program must do, and
    # the two are never mixed -- see `standards.py` for why that is a file and not a column.
    #
    # The same walk, deliberately: `discover_docs` already refuses a nested checkout on the
    # `.git`-file marker (rule 57), and a standards directory is exactly as likely to have
    # a worktree under it as a project is. Writing a second scanner would be a second answer
    # to "what is a document" (rule 51).
    standards_store: DocStore | None = None
    if standards_roots:
        prog.step(STEP_STANDARDS)
        standards_store = DocStore(out_dir / STANDARDS_DB)
        standards_store.set_meta("revision", revision)
        standards_store.set_meta("program", program)
        # What was read, so the store can say whose standard it holds rather than only
        # what it says. A reader looking at a rule has to be able to ask where it came from.
        standards_store.set_meta("roots", "\n".join(str(r) for r in standards_roots))
        std_found = std_read = 0
        for root in standards_roots:
            st = analyze_docs_tree(
                root, standards_store, jobs=args.jobs, recheck=args.recheck_docs,
                exclude=frozenset({out_dir}))
            std_found += st.found
            std_read += st.parsed
            # Design rule 1 again, and it matters more here than for the corpus: a reader
            # who named this directory is owed the news that part of it was skipped.
            for d in st.nested:
                where = Path(d)
                shown = where.relative_to(root) if where.is_relative_to(root) else where
                _emit(f"  skipped {shown} — a checkout of its own, not a standard")
            # The corpus walk's second sentence, worded for this reader: they named this
            # directory as somebody's standard, so what they are owed is why a part of it
            # is not one. `standards_refusal` already turns the whole root away for being
            # inside the output tree; this is the same argument for a map found within a
            # root that is otherwise perfectly good.
            for d in st.maps:
                where = Path(d)
                shown = where.relative_to(root) if where.is_relative_to(root) else where
                _emit(f"  skipped {shown} — a map of a program, not a standard")
        standards_store.mark_duplicates()
        sc = standards_store.counts()
        if not args.quiet:
            _emit(
                f"standards {std_found} documents from "
                f"{len(standards_roots)} director{'y' if len(standards_roots) == 1 else 'ies'} "
                f"(read {std_read}): {sc['doc_rules']:,} stated rules"
            )
        standards_store.optimize()
        # Left **open** until the map is written: `11-naming.md` reports the comparison, and
        # a store closed here would make the report the one surface that could not see the
        # standard it was given. Closed beside `doc_store` below, where the other corpus is.

    prog.step(STEP_RESOLVE)
    t1 = time.perf_counter()
    rstats = resolve_calls(store)
    clistats = resolve_cli(store)
    store.optimize()
    t_resolve = time.perf_counter() - t1

    if not args.quiet:
        if getattr(store, "rebuilt", False):
            # Say it out loud. A silent rebuild looks like a slow run; an unsaid
            # one looks like a fast run that quietly told you last week's truth.
            _emit("graph written by an older DunneFlow — discarded and re-extracted")
        # And the cheaper half of the same fact. A reader that changed costs its own
        # language a re-read and costs the others nothing, which is the whole point of
        # splitting the key -- and a reader watching 412 files re-parse in a repository
        # they did not touch is owed the reason (design rule 1).
        for lang, n in sorted(getattr(store, "reread", {}).items()):
            _emit(f"the {lang} reader has changed — {n:,} file{'' if n == 1 else 's'} "
                  f"dropped and read again; every other language kept its facts")
        _emit(
            f"files {stats.found} (parsed {stats.parsed}, cached {stats.cached}, "
            f"removed {stats.removed}, failed {stats.failed}) in {t_extract:.1f}s"
        )
        _emit(f"  read: {walk_languages(stats)}")
        # **Said only when it happened**, and it is worth saying: a burst that had to stop
        # for its own write-ahead log is a tree near the size this tool is known to finish,
        # and a reader watching one run slower than the last is owed the reason rather than
        # left to guess at the disk (design rule 1). Silent on every ordinary run, because
        # the count is zero and a line that always reads `0` teaches nobody anything.
        if getattr(store, "settled", 0):
            _emit(f"  the write-ahead log was drained {store.settled} time"
                  f"{'' if store.settled == 1 else 's'} mid-read, which is what keeps a "
                  f"tree this size from slowing to a crawl")
        for said in stats.reader_notes:
            _emit(f"    {said}")
        for line in residue:
            _emit("  " + line)
        _emit(
            f"calls {rstats.total:,}: {rstats.certain:,} certain, "
            f"{rstats.inferred:,} inferred, {rstats.external:,} external "
            f"({rstats.rate():.0f}% internal) in {t_resolve:.1f}s"
        )
        # **What was handed over, as against what was argued for.** A supplied edge is
        # CERTAIN and so is a Python edge pinned by an import, so the line above cannot
        # tell them apart — and *how much of this map did we not have to guess* is the
        # question chunk 10 exists to be able to answer (rule 32). Said only where
        # something was supplied, so a Python-only run reads exactly as it always did.
        if rstats.supplied:
            _emit(f"  {rstats.supplied:,} of those were supplied by a reader's own "
                  f"toolchain rather than resolved by name")
        if (said := ts_edges.LAST.sentence()):
            _emit("  " + said)
        # A language this build reads and cannot resolve is **named**, because *nothing
        # resolved* and *nothing to resolve* are the same 0% and opposite facts (design
        # rule 1). It fires for the first time with TypeScript, whose supplied edges are
        # a chunk away.
        if (said := rstats.unresolved_sentence()):
            _emit("  " + said)
        _emit(
            f"cli: {clistats.apps} apps, {clistats.commands_found} commands "
            f"({clistats.commands_attached} in a tree), "
            f"{clistats.mounts_resolved}/{clistats.mounts_total} mounts"
        )
        # **What the tree declares about itself**, on `walk_residue`'s precedent and for
        # its reason: a run that read twenty manifests and reported none of them leaves a
        # reader unable to tell *nothing declares a way in* from *nothing was looked at*
        # (design rule 1). The refusals are indented beneath, one line per kind of
        # refusal and never one per file -- DunneNote's twenty manifests produce
        # twenty-one notes and eleven of them are the same sentence.
        _emit(manifests.summary(readings))
        for said in manifests.residue(readings):
            _emit("  " + said)
        for said in collisions(readings):
            _emit("  " + said)
        # A declared way in this map cannot open is stated here rather than left to be
        # noticed as a blank in a panel. Three of DunneNote's four are Rust.
        for ep in store.entrypoints():
            if ep.declared and not (ep.routine_id or ep.parent_id):
                _emit(f"  `{ep.name}` is declared and not bound — "
                      + binding_note(store, ep.id).sentence)

    # The source sidecar. Driven by the hashes the graph just recorded rather than by a
    # second walk of the tree, so a file whose body is already held is never opened: a
    # re-analysis with nothing changed reads no source at all. Content-addressed, so this
    # is also the store the temporal layers will be built on.
    src_stats = None
    # What the index will say about every snapshot here, taken from the handle already
    # open. A second read-only handle to a database this process is holding is 36x slower
    # (rule 58), and it would also have to be opened after the close below to be correct --
    # two reasons to ask now and one answer.
    rev_rows: tuple[dict[str, object], ...] = ()
    if source is not None:
        prog.step(STEP_BODIES)
        src_stats = capture_source(store.known_hashes(), source, root=source_root,
                                   langs=store.known_langs(), revision=revision)
        sc = source.counts()
        rev = revision
        if not args.quiet:
            _emit(
                f"source: {sc['blobs']:,} bodies for {sc['paths']:,} paths "
                f"({sc['stored'] / 1e6:.1f} MB stored, {sc['bytes'] / 1e6:.1f} MB of "
                f"source) — {src_stats['stored']:,} read, {src_stats['cached']:,} "
                f"already held"
                + (f", {src_stats['missing']:,} unreadable" if src_stats["missing"] else "")
            )
            # Which snapshot this went into, and how many there are. A sidecar quietly
            # holding one revision and a sidecar quietly replacing the only one it had
            # look identical from here, and they were the same thing until now.
            _emit(
                f"        revision {rev} of {sc['revisions']:,}"
                + (f", {sc['mapped']:,} path-revision rows in all"
                   if sc["revisions"] > 1 else "")
            )
        rev_rows = tuple(source.revisions())
        source.close()

    # **Before the map is written, because the map is built out of it.** This ran after
    # rendering and rendering detected twice more -- once for `09-anomalies.md` and once
    # for the headline in `README.md` that points at it -- so one judgement over one
    # unchanged store was made three times. On `Engine/Binaries`, 3,146 files and 71,306
    # routines, `detect` is 306 s: the run spent **855.6 s writing the map and 306.4 s
    # looking for anomalies, 94.8% of 1,226.6 s**, deciding the same thing three times.
    #
    # The step order follows the work rather than the other way round. It is the same
    # steps and the same count; what changes is that the step named *looking for
    # anomalies* is now the one that looks for them, which is the only arrangement a
    # phase table can be read off (rule 32). `--no-render` is unaffected: this runs
    # either way, which is what it has always done.
    prog.step(STEP_ANOMALIES)
    store.warm()
    rep = detect(store, include_tests=args.include_tests)
    ac = rep.counts()
    if not args.quiet and any(ac.values()):
        _emit(
            f"anomalies: {ac.get(BROKEN, 0)} broken, {ac.get(SUSPECT, 0)} suspect, "
            f"{ac.get(INFO, 0)} informational"
        )

    if not args.no_render:
        prog.step(STEP_RENDER)
        t2 = time.perf_counter()
        store.warm()
        # **Into a directory named for this revision**, so a second analysis writes a
        # second map rather than over the first one's. The databases have been
        # revision-named since the spine went in; the written map was not, and a sealed
        # snapshot -- which exists to be readable after its source tree is gone -- kept its
        # graph and lost the documents a reader actually reads.
        #
        # Decided here rather than inside `render_all`, which writes the map into the
        # directory it is handed and should go on knowing nothing about revisions: *which*
        # directory is a question about time, and this is the caller that knows the answer.
        map_out = revisions.map_dir(out_dir, revision)
        files = render_all(store, map_out, program,
                           include_tests=args.include_tests,
                           docs=doc_store, standards=standards_store, report=rep)
        # And the listing that says which map is which. Written every time, because a
        # revision's *state* changes underneath it -- sealing one makes every earlier
        # listing wrong about which snapshot is the working one.
        index = render_index(out_dir, program, rows=rev_rows)
        if not args.quiet:
            _emit(f"wrote {len(files)} documents to {map_out} in "
                  f"{time.perf_counter() - t2:.1f}s")
            stale = legacy_map_files(out_dir)
            if stale:
                # Named rather than removed, and named rather than left silent: these are
                # a real map of a revision nothing records, and the reader decides.
                _emit(f"        {index.name} lists this directory's maps; {len(stale)} "
                      f"documents from before maps were named are still beside it")

    c = store.counts()
    # **stdout is one channel or the other, never both.** With `--progress-json` it is the
    # machine channel and these four lines would arrive in the middle of it; without it,
    # they are the summary the terminal has always printed. The counts are the same either
    # way -- one is the sentence and one is the object (rule 13).
    if prog.on:
        prog.done(program=program, revision=revision, graph=str(db_path),
                  routines=c["routines"], calls=c["resolved_calls"],
                  boundaries=c["boundaries"], structures=c["structures"],
                  entrypoints=c["entrypoints"],
                  files=stats.found, documents=doc_stats.found if doc_stats else 0,
                  # The machine channel says the same things the sentence does, per
                  # language and per unclaimed suffix -- rule 13, across two channels.
                  languages=dict(sorted(stats.by_lang.items())),
                  unread=dict(sorted(stats.unclaimed.items())))
    else:
        print(
            f"{program}: {c['routines']:,} routines · {c['resolved_calls']:,} internal "
            f"calls · {c['boundaries']:,} boundary touches · {c['structures']:,} "
            f"structures · {c['entrypoints']:,} ways in"
        )
        print(f"graph: {db_path}")
        if doc_stats is not None:
            print(f"docs:  {revisions.db_path(out_dir, revisions.DOCS, revision)}")
        if not args.no_render:
            # The map this run wrote, not the directory's index. Both are `README.md` and
            # they answer different questions -- one is the overview of *this* revision, the
            # other the list of every revision here -- so the line that says "start reading
            # here" has to name the one inside the map (rule 30, and the reason the index
            # says what it is in its own first heading).
            print(f"map:   {revisions.map_dir(out_dir, revision)}/README.md")
            print(f"index: {out_dir}/README.md")
    # **After `prog.done`, because `done` closes the last phase.** On stderr with the rest
    # of the prose, so it cannot land in the middle of the machine channel, and behind a
    # flag because it is an instrument rather than part of what a run says.
    if args.timings:
        _emit("where the time went:")
        for line in prog.timings():
            _emit(line)
    if doc_store is not None:
        doc_store.close()
    if standards_store is not None:
        standards_store.close()
    # The last act before the store is closed, and committed like its opposite above. Every
    # reader that presents this map as finished asks for this one value.
    store.set_meta_now("complete", "yes")
    store.close()
    return 0


def _open_store(args: argparse.Namespace, *,
                finished_only: bool = True) -> tuple[Store, Path] | None:
    """The read path every orientation command shares.

    **`finished_only` defaults to refusing**, because every command that comes through here
    presents its answer as a fact about a program: `touches`, `impact`, `glossary`,
    `naming`, `mirror` and `check` all do. An unfinished map answers all six confidently
    and wrongly -- `check` most expensively, since it is the one that gates CI and would
    report a half-read program as `0 broken`.

    `query` is the one caller that passes `False`, and it **says so out loud** rather than
    reading in silence: its whole contract is that you get the rows that are there.
    """
    target = Path(args.path).resolve()
    program, out_dir = _default_paths(target, args.name, _out_root(args))
    db_path = (Path(args.db) if args.db
               else revisions.newest(out_dir, revisions.GRAPH))
    if db_path is None:
        _emit(f"error: no graph in {out_dir} — run `dunneflow analyze` first")
        return None
    if not db_path.exists():
        _emit(f"error: no graph at {db_path} — run `dunneflow analyze` first")
        return None
    try:
        # Read-only: an orientation command must never drop the map it came to read.
        store = Store(db_path, writable=False)
    except StaleGraphError as exc:
        _emit(f"error: {exc}")
        return None
    if store.finished() == "":
        # The step is read **before** anything is closed. It was read after, once, and
        # `check` died on a closed connection while trying to explain why it was refusing.
        said = unfinished_sentence(program, store.get_meta("step") or "")
        if finished_only:
            store.close()
            _emit(f"error: {said}")
            return None
        # Read anyway, and say what is being read. An escape hatch that quietly hands over
        # a half-written map is not an escape hatch, it is a trap.
        _emit(f"warning: {said}")
    return store, db_path


def cmd_touches(args: argparse.Namespace) -> int:
    opened = _open_store(args)
    if not opened:
        return 2
    store, _ = opened
    found = find_routine(store, args.routine)
    if not found.matches and not found.module:
        _emit(f"no routine matching {args.routine!r}")
        return 1
    shown = found.matches[: args.limit]
    for line in search_said(args.routine, found, len(shown)):
        print(line)
    if not shown:
        # The module sentence *is* the answer here, and there is nothing to list under it.
        store.close()
        return 1
    for m in shown:
        reach, kinds = entry_reach(store, m["id"])
        print(f"\n{m['qualname']}  ({m['file']}:{m['line_start']})")
        print(f"  reaches {reach:,} routines")
        bounds = store.boundaries_reached(m["id"])
        if not bounds:
            print("  touches nothing outside itself")
            continue
        by_kind: dict[str, set[str]] = {}
        for b in bounds:
            by_kind.setdefault(b.kind.value, set()).add(b.target or b.evidence)
        for kind in sorted(by_kind):
            targets = sorted(t for t in by_kind[kind] if t)[:8]
            print(f"  {kind:10s} {', '.join(targets) if targets else '(dynamic)'}")
    store.close()
    return 0


def cmd_impact(args: argparse.Namespace) -> int:
    opened = _open_store(args)
    if not opened:
        return 2
    store, _ = opened
    found = find_routine(store, args.routine)
    if not found.matches and not found.module:
        _emit(f"no routine matching {args.routine!r}")
        return 1
    shown = found.matches[: args.limit]
    for line in search_said(args.routine, found, len(shown)):
        print(line)
    if not shown:
        # The module sentence *is* the answer here, and there is nothing to list under it.
        store.close()
        return 1
    for m in shown:
        callers = store.callers_of(m["id"])
        print(f"\n{m['qualname']}  ({m['file']}:{m['line_start']})")
        print(f"  {len(callers):,} routines depend on this, directly or transitively")
        eps = ways_in_affected(store, callers)
        if eps:
            print(f"  ways in affected ({len(eps)}):")
            for e in eps[:20]:
                print(f"    - {e['name']} [{e['kind']}]")
        plans = governance_over(store, callers)
        if plans:
            print(f"  governance implicated: {', '.join(plans[:25])}")
    store.close()
    return 0


def _open_docs(args: argparse.Namespace) -> DocStore | None:
    target = Path(args.path).resolve()
    _program, out_dir = _default_paths(target, args.name, _out_root(args))
    path = revisions.newest(out_dir, revisions.DOCS)
    if path is None or not path.exists():
        return None
    try:
        return DocStore(path, writable=False)
    except StaleGraphError as exc:
        _emit(f"error: {exc}")
        return None


def cmd_glossary(args: argparse.Namespace) -> int:
    """What this program's words mean, and who says so."""
    opened = _open_store(args)
    if not opened:
        return 2
    store, _ = opened
    docs = _open_docs(args)
    report = bind(store, docs)
    defined, total = report.coverage()
    print(f"{defined:,} of {total:,} terms are defined somewhere "
          f"({defined / total:.0%})" if total else "no terms found")
    for term in [t for t in report.terms if t.defined][: args.limit]:
        sense = term.senses[0]
        print(f"\n{term.term}  ({term.uses:,} uses)")
        print(f"  {sense.definition[:160]}")
        print(f"  [{sense.provenance.value}] {sense.source}:{sense.line}")
    if report.undefined:
        print(f"\nnothing defines these {len(report.undefined):,}:")
        print("  " + ", ".join(t.term for t in report.undefined[: args.limit * 3]))
        if len(report.undefined) > args.limit * 3:
            print(f"  ... see 10-glossary.md for all {len(report.undefined):,}")
    # Never a silent filter (design rule 1). The count travels with the list it was taken
    # out of, and it names the one place a reader can read the words themselves.
    if report.set_aside:
        print(f"\n{len(report.set_aside):,} more were held back as fragments of compound "
              f"constant names — see 10-glossary.md, 'Words held back'")
    if docs is not None:
        docs.close()
    store.close()
    return 0


def cmd_naming(args: argparse.Namespace) -> int:
    """The naming standard **as found**: derived from the code, quoted from the documents.

    Neither lane is a requirement and neither is a comparison. Form is counted off the
    graph; Vocabulary is quoted out of whatever the project happens to have written down.
    Checking either against a standard a team supplies is not built -- see `BRIEFING.md`.
    """
    opened = _open_store(args)
    if not opened:
        return 2
    store, _ = opened
    docs = _open_docs(args)

    stated = docs.query(
        "SELECT r.text, r.lane, r.doc, r.line FROM doc_rules r"
        " JOIN documents d ON d.path = r.doc WHERE d.duplicate_of = ''"
        " ORDER BY r.lane, r.line"
    ) if docs is not None else []
    if stated:
        print("STATED — quoted from documentation")
        for r in stated:
            print(f"  [{r['lane']:10s}] {' '.join(str(r['text']).split())[:96]}")
            print(f"               {r['doc']}:{r['line']}")
    else:
        print("STATED — nothing in this program's documentation states a naming rule")

    m = measure(store)
    print("\nMEASURED — counted against the code")
    for c in m.conventions[: args.limit]:
        exc = (f"  ({len(c.exceptions)} exception"
               f"{'s' if len(c.exceptions) != 1 else ''})") if c.exceptions else ""
        print(f"  [{c.rating()}] {c.holds:,}/{c.total:,}  {c.claim}{exc}")
    if len(m.conventions) > args.limit:
        print(f"  ... {len(m.conventions) - args.limit} more; all of them in 11-naming.md")
    for g in m.gaps:
        spread = ", ".join(f"{k} {v}" for k, v in g.spread)
        print(f"  GAP  {g.population}: {g.total:,} counted — {spread}")
    if docs is not None:
        docs.close()
    store.close()
    return 0


def cmd_mirror(args: argparse.Namespace) -> int:
    """Vocabulary the documentation defines, and what the code does with it.

    The traceability report's mirror. Prints the spectrum, then the band that is
    actually a finding -- the words nothing in the program answers to -- because a
    reader opening this is looking for drift, not for confirmation that `groma` is
    a package name.
    """
    opened = _open_store(args)
    if not opened:
        return 2
    store, _ = opened
    docs = _open_docs(args)
    report = measure_mirror(store, docs)

    if not report.had_docs:
        print("no documentation was read, so there is nothing to mirror.")
        print("point analyze at a documentation root: --docs <path>")
        store.close()
        return 0

    groups = report.by_band()
    print(f"{report.definitions_seen:,} definitions read, "
          f"{report.excluded_total:,} set aside as not a word, "
          f"{len(report.terms):,} terms carried forward")
    for band in MIRROR_BANDS:
        print(f"  {band.label:8} {len(groups[band.key]):4}   {band.meaning}")

    absent = groups["ABSENT"]
    if absent:
        print(f"\ndefined in documentation, nowhere in the code ({len(absent):,}):")
        for term in absent[: args.limit]:
            source = term.definitions[0]
            print(f"\n  {term.term}")
            print(f"    {source.definition[:160]}")
            print(f"    {source.doc}:{source.line}")
        if len(absent) > args.limit:
            print(f"\n  ... see 13-mirror.md for all {len(absent):,}, "
                  "each with its definition and the line it came from")
    # Read off the graph rather than written down, because this is the one sentence on
    # the page that is a claim about what the tool could see (rule 13).
    print("\n" + languages.only_plain(languages.read(store)) + ".")

    if docs is not None:
        docs.close()
    store.close()
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Anomalies only. Exits non-zero when something is BROKEN, so CI can gate on it."""
    opened = _open_store(args)
    if not opened:
        return 2
    store, _ = opened
    store.warm()
    report = detect(store, include_tests=args.include_tests)
    wanted = {BROKEN, SUSPECT, INFO} if args.all else (
        {BROKEN} if args.broken_only else {BROKEN, SUSPECT}
    )
    shown = [a for a in report.sorted() if a.severity in wanted]

    for a in shown[: args.limit]:
        where = f"  {a.file}:{a.line}" if a.file and a.line else (
            f"  {a.file}" if a.file else "")
        print(f"[{a.severity}/{a.confidence}] {a.kind}: {a.title}{where}")
        if args.verbose:
            print(f"    {a.detail}")
            print(f"    blind spot: {a.blind_spot}")
    if len(shown) > args.limit:
        print(f"... {len(shown) - args.limit} more (raise --limit to see them)")

    counts = report.counts()
    print(
        f"\n{counts.get(BROKEN, 0)} broken, {counts.get(SUSPECT, 0)} suspect, "
        f"{counts.get(INFO, 0)} informational"
    )
    store.close()
    return 1 if counts.get(BROKEN, 0) else 0


def cmd_revisions(args: argparse.Namespace) -> int:
    """What snapshots this sidecar holds, and how to keep the current one.

    Listing opens the store **read-only**, which is not a detail: a writable open stamps a
    sidecar written before revisions were recorded, and that is a migration. Rule 20 says a
    read may refuse but may never repair, so asking what is there must not change what is
    there. `--seal` is the writable path, and it says what it did.
    """
    out_dir = Path(args.out_dir)
    db = out_dir / "source.db"
    if not db.exists():
        _emit(f"no source sidecar at {db} — analysed with --no-source, or handed over "
              f"without it")
        return 1

    if args.seal:
        # The instant those bodies were measured is not in this store, and inventing one
        # would be provenance nobody can check (rule 13). The graph beside it recorded
        # `analysed_at` when it read them, so state that rather than today's date.
        at = args.at or _analysed_at(revisions.newest(out_dir, revisions.GRAPH))
        source = SourceStore(db)
        try:
            rev = source.seal(label=args.label or "", at=at)
        except ValueError as exc:
            # "already sealed" and "nothing here" are different answers and the store
            # keeps them apart; printing one message for both would lose that.
            _emit(f"nothing to seal: {exc}")
            source.close()
            return 1
        source.commit()
        if rev is None:
            _emit("nothing to seal: this sidecar holds no paths")
            source.close()
            return 1
        _emit(f"sealed {rev} as {STATE_FOR_COMPARISON}"
              + (f" — “{args.label}”" if args.label else "")
              + ("" if at else "\n  its capture instant is unknown and stays unknown; "
                               "state one with --at"))
        _emit("the next `analyze` opens a fresh working revision beside it")
        source.close()
        return 0

    source = SourceStore(db, writable=False)
    rows = source.revisions()
    if not rows:
        _emit(f"{db} holds no revisions and no paths")
        source.close()
        return 1
    print(f"{'revision':22} {'state':16} {'captured':22} {'files':>6}  label")
    for r in rows:
        rev = r["revision"] or "(un-stamped)"
        cap = r["captured_at"] or "—"
        print(f"{rev:22} {r['state']:16} {cap:22} {r['files']:>6,}  {r['label']}")
        if r["note"]:
            print(f"  {r['note']}")
    if any(not r["stamped"] for r in rows):
        # The table goes to stdout and the advice to stderr, which two buffers will
        # otherwise interleave backwards -- advice about a listing, printed above it.
        sys.stdout.flush()
        _emit("\nrun `dunneflow revisions <dir> --seal` to give the current snapshot a "
              "name before it is replaced")
    source.close()
    return 0


def _analysed_at(graph_db: Path | None) -> str:
    """When the graph beside this sidecar says it read the source, or "" if it cannot say.

    A separate store, opened here and nowhere else: `sourcedb` must not reach into
    `graph.db`, and the CLI is the one caller that legitimately holds both paths.

    `None` -- no graph in the directory at all -- is the same answer as an unreadable
    one and gets the same empty string, because `seal` may only ever *fill* an empty
    `captured_at` and never overwrite a recorded instant. Stating today's date for a
    snapshot measured on some other day is the invented provenance rule 13 forbids.
    """
    if graph_db is None or not graph_db.exists():
        return ""
    try:
        conn = sqlite3.connect(f"file:{graph_db}?mode=ro", uri=True)
        row = conn.execute("SELECT value FROM meta WHERE key = 'analysed_at'").fetchone()
        conn.close()
    except sqlite3.Error:
        return ""
    return "" if row is None else str(row[0])


def cmd_query(args: argparse.Namespace) -> int:
    # The one reader that will open an unfinished map, because its whole contract is that
    # you get the rows that are there. It warns rather than refusing, and rather than
    # reading in silence -- see `_open_store`.
    opened = _open_store(args, finished_only=False)
    if not opened:
        return 2
    store, db_path = opened
    # A claim this tool prints from both stores has to be re-runnable from both
    # stores, or rule 13 is satisfied only on paper.
    if getattr(args, "docs", False):
        docs_path = (Path(args.docs_db) if args.docs_db
                     else revisions.newest(db_path.parent, revisions.DOCS))
        if docs_path is None or not docs_path.exists():
            _emit(f"error: no document store at {docs_path}")
            store.close()
            return 2
        store.conn.execute("ATTACH DATABASE ? AS docs", (str(docs_path),))
    try:
        rows = store.query(args.sql)
    except Exception as exc:
        _emit(f"query failed: {exc}")
        store.close()
        return 1
    if not rows:
        print("(no rows)")
    else:
        keys = rows[0].keys()
        print(" | ".join(keys))
        for r in rows[: args.limit]:
            print(" | ".join(str(r[k]) for k in keys))
        if len(rows) > args.limit:
            print(f"... {len(rows) - args.limit} more rows")
    store.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dunneflow",
        description="Map what moves through a program: entrypoints, flows, and boundaries.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("path", help="the source tree to analyse")
        sp.add_argument("--name", help="program name (defaults to the directory name)")
        # **Asked rather than spelled** (rule 51). This read
        # `~/Library/Application Support/DunneFlow` as a literal, which was true of the
        # machine it was written on and of no other -- a Windows reader was told their maps
        # default somewhere no Windows has ever had, and a Linux reader the same. The one
        # place that answers is the one the command itself consults.
        sp.add_argument("--output", default=None,
                        help=f"output root (default: ./output, or "
                             f"{platform_output_root()} in a packaged application)")
        sp.add_argument("--db", help="graph database path")

    a = sub.add_parser("analyze", help="extract, resolve, and write the map")
    common(a)
    a.add_argument("--include-tests", action="store_true", help="include test files")
    # **Repeatable and validated, because the silent form is the failure.** `--without`
    # was named as the way out of a missing toolchain by two refusals in
    # `ingest/outofprocess.py` long before it existed anywhere -- rule 89 broken in the
    # sentence written to keep it. `ingest.decline` is the one place a name is judged.
    a.add_argument("--without", action="append", default=[], metavar="LANG",
                   help="do not read this language, and say so in the map "
                        "(repeatable; for a machine that lacks its toolchain)")
    a.add_argument("--jobs", type=int, default=None, help="parallel workers")
    a.add_argument("--no-render", action="store_true", help="build the graph only")
    a.add_argument("--docs", help="documentation root (defaults to the package root)")
    a.add_argument("--no-docs", action="store_true", help="skip documentation entirely")
    a.add_argument("--recheck-docs", action="store_true",
                   help="hash every document rather than trusting its modification time")
    # Repeatable, because an organisation files its standards in more than one place and
    # naming one root the union of several would make the reader build a directory that
    # exists only to satisfy this tool.
    a.add_argument("--standards", action="append", metavar="DIR",
                   help="a directory of naming standards to measure this program against "
                        "(repeatable); read into standards.db, never into the corpus")
    a.add_argument("--no-source", action="store_true",
                   help="do not keep a copy of the source beside the map")
    # Its own switch rather than a second meaning for `--no-source`, and design rule 14 is
    # the reason: the two corpora are handed over separately, and "send the documentation
    # but not the code" is the posture that rule names as common. One switch governing both
    # would make that posture unreachable at the point the bodies are written.
    a.add_argument("--no-doc-source", action="store_true",
                   help="do not keep a copy of the documents beside the map")
    a.add_argument("--quiet", action="store_true")
    # The machine channel, for `dunneflow serve`, which runs this as a subprocess and draws
    # a bar against what it says. On stdout, because stderr is where the prose goes and a
    # failure's reason has to survive somewhere a parser is not reading (see `_Progress`).
    a.add_argument("--progress-json", action="store_true",
                   help="report progress as one JSON object per line on stdout")
    # **The two halves of the size guard.** `--parts` answers the question the refusal
    # raises and does nothing else; `--any-size` overrules it. Both are named *in* the
    # refusal, because a refusal that does not name a command that can act on the thing it
    # is refusing leaves the reader nowhere to go (rule 89).
    a.add_argument("--parts", action="store_true",
                   help="print the tree cut into parts small enough to read, and stop")
    a.add_argument("--any-size", action="store_true",
                   help="read a tree larger than the guard allows, however long it takes")
    # **The third half, and it is what makes a part a piece of its tree.** Every
    # path-shaped discovery rule -- a reader's `skip_dirs`, and `is_test`'s `test_dirs` --
    # is matched against the path relative to the analysed root, so a directory read as a
    # root of its own is judged by a path that no longer contains the component that hid
    # it. Named in the commands `--parts` prints, because a part read without it is not
    # the part the breakdown described. `BACKLOG.md` item 10 and `walk.discover` carry
    # the measurements.
    a.add_argument("--part-of", metavar="TREE",
                   help="judge skip and test rules from TREE, which this is a part of")
    # **An instrument, so it is a flag and not the default.** Three of the eight phases
    # have printed a time for a year and the other five have not, which was survivable
    # until a part of fifteen files cost 110-400 s on Unreal and the only evidence was a
    # total (`BACKLOG.md` item 9). On stderr with the prose, never on the machine channel.
    a.add_argument("--timings", action="store_true",
                   help="print what each phase of the run cost")
    a.set_defaults(func=cmd_analyze)

    t = sub.add_parser("touches", help="what does this routine reach?")
    common(t)
    t.add_argument("--routine", required=True, help="name or qualified name")
    t.add_argument("--limit", type=int, default=5)
    t.set_defaults(func=cmd_touches)

    i = sub.add_parser("impact", help="what breaks if I change this routine?")
    common(i)
    i.add_argument("--routine", required=True, help="name or qualified name")
    i.add_argument("--limit", type=int, default=5)
    i.set_defaults(func=cmd_impact)

    ck = sub.add_parser("check", help="report anomalies; non-zero exit if any are BROKEN")
    common(ck)
    ck.add_argument("--all", action="store_true", help="include informational findings")
    ck.add_argument("--broken-only", action="store_true", help="only BROKEN findings")
    ck.add_argument("--include-tests", action="store_true",
                    help="the graph included tests (changes dead-code reporting)")
    ck.add_argument("--verbose", action="store_true", help="show detail and blind spot")
    ck.add_argument("--limit", type=int, default=40)
    ck.set_defaults(func=cmd_check)

    g = sub.add_parser("glossary", help="what this program's words mean, and who says so")
    common(g)
    g.add_argument("--limit", type=int, default=20)
    g.set_defaults(func=cmd_glossary)

    nm = sub.add_parser("naming",
                        help="the naming standard as found: derived, and quoted")
    common(nm)
    nm.add_argument("--limit", type=int, default=15)
    nm.set_defaults(func=cmd_naming)

    mr = sub.add_parser(
        "mirror", help="words the documentation defines that the code does not use")
    common(mr)
    mr.add_argument("--limit", type=int, default=15)
    mr.set_defaults(func=cmd_mirror)

    q = sub.add_parser("query", help="ask the graph directly with SQL")
    q.add_argument("--docs", action="store_true",
                   help="attach the document store as `docs` for cross-store joins")
    q.add_argument("--docs-db", help="document database path (defaults beside the graph)")
    common(q)
    q.add_argument("--sql", required=True)
    q.add_argument("--limit", type=int, default=40)
    q.set_defaults(func=cmd_query)

    rv = sub.add_parser(
        "revisions", help="what snapshots the source sidecar holds, and keep the current one")
    rv.add_argument("out_dir", help="an analysed program's output directory")
    rv.add_argument("--seal", action="store_true",
                    help="keep the current snapshot under its own name, so the next "
                         "analysis is a second one rather than a replacement")
    rv.add_argument("--label", help="a name for the sealed snapshot")
    rv.add_argument("--at", help="when its bodies were measured, if the graph cannot say")
    rv.set_defaults(func=cmd_revisions)

    rn = sub.add_parser(
        "render", help="write the map of a revision whose graph is already here")
    rn.add_argument("out_dir", help="an analysed program's output directory")
    rn.add_argument("--revision", default=None,
                    help="which snapshot to write the map of (default: every revision "
                         "here that has a graph and no map). Naming one that already has "
                         "a map rewrites it.")
    rn.add_argument("--include-tests", action="store_true",
                    help="report anomalies in test code too, as `analyze` does")
    rn.set_defaults(func=cmd_render)

    mg = sub.add_parser(
        "migrate", help="rewrite a program directory's stored paths as relative, in place")
    mg.add_argument("out_dir", help="an analysed program's output directory")
    mg.set_defaults(func=cmd_migrate)

    sv = sub.add_parser("serve", help="open the interactive map in a browser")
    sv.add_argument("out_dir", nargs="?", default=None,
                    help="an analysed program's directory, or the output root holding "
                         "several (default: the output root)")
    sv.add_argument("--port", type=int, default=8787)
    sv.add_argument("--no-open", action="store_true", help="do not open a browser")
    sv.add_argument("--revision", default=None,
                    help="which point in time to open as the base (default: the newest). "
                         "The reader can switch it from the page; this is how a chosen "
                         "base survives a restart of the server.")
    sv.set_defaults(func=cmd_serve)

    mc = sub.add_parser("mcp", help="answer the map to an agent over MCP, on stdin/stdout")
    mc.add_argument("out_dir", nargs="?", default=None,
                    help="an analysed program's directory, or the output root holding "
                         "several (default: the output root)")
    mc.add_argument("--revision", default=None,
                    help="which point in time to open as the base (default: the newest)")
    mc.set_defaults(func=cmd_mcp)

    # --- the plugin author's two commands ---------------------------------- #
    # Both are about the *seam* rather than about a map, which is why neither takes an
    # output directory: one describes what a reader must emit and the other asks whether
    # a reader emits it.
    isc = sub.add_parser(
        "ingest-schema",
        help="what a reader must emit: every fact type, as data a plugin generates from")
    isc.add_argument("--json", action="store_true",
                     help="emit the descriptor itself rather than a summary for reading")
    isc.set_defaults(func=cmd_ingest_schema)

    icf = sub.add_parser(
        "ingest-conform",
        help="does this language's reader spell a call expression the way the rules match?")
    icf.add_argument("lang", help="which language's reader to put through the cases")
    icf.set_defaults(func=cmd_ingest_conform)
    return p


def cmd_ingest_schema(args: argparse.Namespace) -> int:
    """Print what a reader has to emit, as data.

    **The point is that a plugin's own types are generated from this**, so a
    `SCHEMA_VERSION` bump breaks that plugin's *build* rather than its output — which is
    the one failure mode a fact contract across a process boundary has that a contract
    inside one process does not.

    Out of `codec.describe()`, which is the same reflection the wire itself uses. A second,
    hand-written description of `schema.py` would be exactly the drift the codec was made
    reflective to avoid, one file over (rule 13).
    """
    from .ingest.codec import describe

    shape = describe()
    if args.json:
        print(json.dumps(shape, indent=2, sort_keys=True))
        return 0

    records, enums = shape["records"], shape["enums"]
    fields = sum(len(v) for v in records.values())
    _emit(f"fact schema {shape['schema_version']} — {len(records)} record types, "
          f"{fields} fields, {len(enums)} enumerations")
    _emit(f"document schema {shape['doc_schema_version']}")
    _emit("")
    for name in sorted(records):
        required = [f["name"] for f in records[name] if f["required"]]
        owned = [f["name"] for f in records[name] if f["host_owned"]]
        line = f"  {name:16} {len(records[name]):2} fields"
        if required:
            line += f", required: {', '.join(required)}"
        if owned:
            # Named because it is the one thing a plugin author will otherwise get wrong:
            # a field the host writes, refused rather than accepted, if a reader sends it.
            line += f"  [the host writes {', '.join(owned)} — a reader must not send it]"
        _emit(line)
    _emit("")
    for name in sorted(enums):
        _emit(f"  {name:16} {', '.join(enums[name])}")
    _emit("")
    _emit("Generate your plugin's types from `--json` rather than transcribing this: a "
          "schema bump should break your build, not your output.")
    return 0


def cmd_ingest_conform(args: argparse.Namespace) -> int:
    """Put a reader through the dotted-name cases, in whatever process it lives in.

    The cases go through the reader's **ordinary** extract, so what is proved is the path
    the map is built from and not a conformance surface beside it (rule 51). For the Python
    reader that is this process; for a reader on the far side of a pipe it is the pipe,
    with no branch here to say which.
    """
    from .ingest import PLUGINS, dotted

    lang = args.lang
    plugin = PLUGINS.get(lang)
    if plugin is None:
        known = ", ".join(sorted(PLUGINS)) or "(none)"
        _emit(f"nothing in this build reads {lang!r}. This build reads: {known}.")
        return 2
    try:
        results = dotted.run(plugin, lang)
    except dotted.FixtureMissing as exc:
        _emit(str(exc))
        return 2

    _emit(f"the dotted-name contract, against the {lang} reader "
          f"({'in this process' if plugin.manifest.in_process else 'over the wire'})")
    _emit("")
    for line in dotted.report(results, lang):
        _emit(line)
    failed = [r for r in results if not r.skipped and not r.passed]
    # Non-zero so a plugin's build can gate on it — which is the only reason a conformance
    # runner is a command rather than a test.
    return 1 if failed else 0


def cmd_mcp(args: argparse.Namespace) -> int:
    """Serve the map to an agent over MCP. Read-only throughout, like `serve`.

    **Nothing may be printed.** stdout carries JSON-RPC and nothing else, so every sentence
    this command has to say goes to stderr through `_emit` — including the ones `serve`
    prints happily, such as `_out_root`'s *"no --output given"*. That is the same
    two-channel discipline `--progress-json` already runs under, one degree stricter: a
    progress reader skips a line it cannot parse and an MCP client may fail the session.

    The argument is `serve`'s, and so is the question it is asked: whether a directory is a
    program or a root is decided by whether it **holds a map**, never by what it is called
    (rule 30). One function answers it for both — `web.serve.where`.
    """
    from .mcp.server import serve as serve_mcp

    given = Path(args.out_dir) if args.out_dir else None
    if given is None:
        try:
            given = default_output_root()
        except MapsRootGone as exc:
            # Said and then carried on, exactly as `cmd_serve` does: an agent that gets
            # silence cannot tell a missing disk from an empty map (rule 49). What is
            # never done is `mkdir` on the chosen path -- see `cmd_serve` for why that
            # would put a new empty root on the very drive the reader was clearing.
            _emit(f"error: {exc}")
            given = platform_output_root()
            _emit(f"opening {given} in the meantime — nothing there has been touched")
    try:
        return serve_mcp(given, args.revision, _emit)
    except (FileNotFoundError, StaleGraphError, UnfinishedMapError) as exc:
        # Refused before a single message is exchanged, and on **stderr** with a non-zero
        # exit. A server that handshakes cheerfully and then fails every call gives an
        # agent nothing to act on; this gives its launcher a sentence and a code.
        _emit(f"error: {exc}")
        return 2


def cmd_render(args: argparse.Namespace) -> int:
    """Write the map of a revision this directory already holds a graph for.

    **Not analysis.** No source is read, no fingerprint is re-stamped and every store this
    opens is opened read-only, so rules 25 and 62 -- which forbid re-analysing a sealed
    snapshot in place -- are untouched and rule 20 is satisfied by construction.

    With no `--revision` it renders **every revision that has a graph and no map**, which is
    the job it was built for: a program directory whose maps were overwritten before they
    had names, given back what it lost. Naming one renders that one and rewrites its map if
    it has one, so a re-render is always something the reader asked for by name.

    The listing is rebuilt from the sidecar, whose rows carry the state and label a
    filename cannot (`revisions.revision_of` returns a *claim*, and the authority is inside
    the file).
    """
    out_dir = Path(args.out_dir)
    if not out_dir.is_dir():
        _emit(f"error: {out_dir} is not a directory")
        return 2

    wanted: list[str] | None = None
    if args.revision:
        wanted = [args.revision]
        if not revisions.db_path(out_dir, revisions.GRAPH, args.revision).exists():
            # Named and absent is worth listing what *is* here: a mistyped instant and a
            # snapshot whose stores were dropped look identical from the command line, and
            # rule 89 says a refusal has to name something that can act on it.
            here = mapless(out_dir) or [
                r for p in revisions.known(out_dir, revisions.GRAPH)
                if (r := revisions.revision_of(p))
            ]
            _emit(f"error: no graph for {args.revision} in {out_dir}")
            if here:
                _emit("this directory holds: " + ", ".join(here))
            return 2

    rows: list[dict] = []
    db = out_dir / "source.db"
    if db.exists():
        source = SourceStore(db, writable=False)
        try:
            rows = [dict(r) for r in source.revisions()]
        finally:
            source.close()

    done = render_maps(out_dir, wanted, include_tests=args.include_tests,
                       rows=rows, emit=_emit)
    # Non-zero on a refusal, so this can be scripted: a run that wrote nothing it was asked
    # for must not report success (rule 13's shape at the exit code).
    return 1 if any(r.refusal for r in done) else 0


def cmd_migrate(args: argparse.Namespace) -> int:
    """Make every stored path in one program directory relative to its own tree.

    In place, rather than by re-analysis, and that is the point rather than a shortcut: a
    sealed snapshot is kept so it can be read after its source tree is gone, and rebuilding
    would orphan exactly those. Nothing about what a fact *is* changes -- only the spelling
    of a path column -- so this is rule 25's argument applied to a derived store.

    Says what it did per store, because a migration that reports only "done" is one nobody
    can check, and this one rewrites tens of thousands of rows in a file the reader cannot
    rebuild.
    """
    out_dir = Path(args.out_dir)
    if not out_dir.is_dir():
        _emit(f"error: {out_dir} is not a directory")
        return 2
    try:
        report = migrate_program(out_dir)
    except MigrationRefused as exc:
        _emit(f"refused: {exc}")
        return 2

    if not report.stores:
        _emit(f"no stores in {out_dir} — nothing to migrate")
        return 1
    for st in report.stores:
        if st.already:
            _emit(f"  {st.path.name}: already relative")
            continue
        _emit(f"  {st.path.name}: {st.total:,} paths rewritten "
              f"across {len(st.rewritten)} columns")
        for col, n in sorted(st.rewritten.items(), key=lambda kv: -kv[1]):
            _emit(f"      {n:>8,}  {col}")
        for col, n in sorted(st.above.items(), key=lambda kv: -kv[1]):
            _emit(f"      {n:>8,}  {col} — above the analysed tree, now `../…`")
    done = report.migrated
    if done:
        _emit(f"\n{report.total:,} paths are now relative to the tree each store was read "
              f"from, across {len(done)} stores. The tree itself is no longer recorded "
              f"anywhere — nothing at read time needs it.")
    else:
        _emit("\nnothing to do: every store here already holds relative paths")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Open the map. Read-only throughout -- serving can never damage what it shows."""
    import webbrowser

    from .web.serve import already_serving, serve, where
    # The root when nobody said, on `_out_root`'s argument one command over: a
    # double-clicked application has no working directory for a relative default to mean
    # anything against. `serve` itself decides whether what it is handed is a program or
    # a root -- by whether it holds a map, never by what it is called.
    # **The chosen root may be on a disk that is not here**, which is the ordinary case for
    # a feature whose whole point is keeping maps off the boot drive. Falling back is right
    # -- an application that silently does nothing when double-clicked is worse than one
    # that opens and explains -- but the fallback is **said**, twice: here for a terminal,
    # and on the page for the reader who has no terminal. Rule 49 forbids a substitution
    # that hides the failure; it is a stated substitution that makes it recoverable.
    #
    # What must never happen is `mkdir` on the chosen path: `/Volumes` is an ordinary
    # directory on the boot disk, so creating it would put a new empty maps root on exactly
    # the drive the reader moved theirs off. `read_root_pointer` raises before returning a
    # path precisely so that this line is never reached with one.
    gone = ""
    if args.out_dir:
        given = Path(args.out_dir)
    else:
        try:
            given = default_output_root()
        except MapsRootGone as exc:
            gone = str(exc)
            given = platform_output_root()
            _emit(f"error: {gone}")
            _emit(f"opening {given} in the meantime — nothing there has been touched")
    if not args.out_dir:
        # **Made when nobody named it, and only then.** With no argument this is the
        # application's own data directory, and on a machine that has never run DunneFlow
        # it does not exist yet -- so the start page would state a root the reader cannot
        # open and *Show me* would refuse a directory that is simply not there. Creating a
        # directory is not repairing a store: rule 20 forbids a read bringing a *database*
        # into being, and nothing here opens one.
        #
        # A directory the reader **named** is never created, and that difference is the
        # whole guard: a mistyped path would otherwise become a new empty root, and the
        # reader would be told there are no programs in a place they have never used
        # (rule 49 -- a plausible answer hiding the failure).
        given.mkdir(parents=True, exist_ok=True)
        _emit(f"no directory given; reading {given}")
    # **One application, one server.** A double-clicked DunneFlow gets no Dock
    # running-indicator, so a reader who does not see a window fast enough launches it
    # again -- and `_free_port` used to hand each launch a fresh port, leaving three servers
    # on three ports with three sets of open stores and nothing on screen saying so.
    # Reported by Tom, who predicted the behaviour exactly from the missing dot.
    #
    # **Only when it is DunneFlow, and only when it is reading the same maps.** Two output
    # roots are two servers and always were; this joins the reader to their own application
    # rather than to any process that happens to hold the port (`already_serving`).
    running = already_serving(args.port, where(given)[1])
    if running is not None:
        _emit(f"DunneFlow is already reading these maps at {running} — opening that")
        if not args.no_open:
            webbrowser.open(running)
        return 0
    try:
        serve(given, port=args.port,
              open_browser=not args.no_open, revision=args.revision, emit=_emit,
              root_gone=gone)
    except (FileNotFoundError, StaleGraphError, UnfinishedMapError) as exc:
        _emit(f"error: {exc}")
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    """The entry point, and `freeze_support()` is its first statement for a reason.

    `walk.py` runs a `ProcessPoolExecutor` and macOS **spawns** rather than forks, so every
    worker starts by re-executing this program. In a checkout that re-executes the
    interpreter and `multiprocessing` sorts itself out; in a frozen application it
    re-executes *the application* -- which, for `serve`, means up to sixteen more servers
    each opening a browser, and for `analyze` sixteen more analyses. Not an exception the
    serial fallback in `walk.py` can catch, because nothing in the parent raises: the
    parent is fine, and the children are the program.

    `freeze_support()` is what makes a spawned child recognise itself as a worker and hand
    over. It is a no-op in every other case, which is why calling it here **and** in the
    packaged entry script is right rather than redundant -- whichever one is the real entry
    point of a given build, the first statement executed has made the call.

    `speak_utf8()` comes second, and before the parser, so that a usage message and an
    argument error are written in the same encoding as everything after them. It is here
    rather than in the packaged entry script for the reason `freeze_support` is in both:
    this is the one function every way in passes through (rule 51).
    """
    multiprocessing.freeze_support()
    speak_utf8()
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
