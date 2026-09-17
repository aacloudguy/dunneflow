"""A reader that is another program, made to answer the same questions as one that is not.

`inprocess.py` wraps a function in this interpreter. This wraps a process, and between
them the host cannot tell the two apart — which is the whole claim the plugin design rests
on and the one this chunk exists to press.

**What genuinely differs is stated rather than smoothed.** A reader here has a toolchain
that may be absent, a handshake that may disagree, and a process that may die; an
in-process reader has none of the three, and `InProcessPlugin`'s methods say so in words
instead of being left blank. What does *not* differ is the shape of the answer: a
`FileFacts` per file, an error on a file that would not parse, and `lost` for a file that
never arrived at all.

**The host synthesises the facts for a file the plugin says it threw on.** A plugin that
has just crashed on a file is not the right authority on what that file is, and letting it
describe the wreck would put its guess in the map under the file's own name.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator, Sequence
from pathlib import Path

from ..runtime import host_interpreter
from ..schema import FileFacts, SuppliedEdge, hash_source, stored_path
from .codec import CodecError, decode, decode_facts
from .contract import (
    SOURCE_TEXT,
    PluginManifest,
    PluginRefused,
    ProgressFn,
    ProtocolError,
    ToolchainMissing,
    stamp_lang,
)
from .worker import NdjsonWorker, WorkerDied

# A toolchain command meaning **this interpreter**, never whatever `python` PATH resolves
# to. A plugin written in Python is part of the same world as its host — it imports the
# same package and is hashed into the same key — and *finding a python on PATH* is exactly
# how you get a different one, with a different standard library and a different answer.
#
# Which interpreter that is, and whether there is one at all, is `runtime.host_interpreter`
# and never `sys.executable` here: frozen, `sys.executable` **is DunneFlow**, so spelling
# it out would start the application with a script path as its subcommand. Found by
# `test_frozen.py`, which exists for exactly that.
SELF = "python"


def plugin_argv(manifest: PluginManifest) -> list[str]:
    """The command that runs this plugin. **The one place that is decided** (rule 51).

    `entry` is relative to the plugin's own directory, like `fingerprint`, because the
    plugin is a bundle and a path out of it is a path to somebody else's file.
    """
    tc = manifest.toolchain
    if tc is None or not tc.command:
        raise PluginRefused(
            f"the {manifest.lang} plugin at {manifest.root} runs out of process and names "
            f"no toolchain command, so there is nothing to start. A reader on the far side "
            f"of a pipe is a program, and a program has to be named."
        )
    if not manifest.entry:
        raise PluginRefused(
            f"the {manifest.lang} plugin at {manifest.root} names no `entry`, so its "
            f"toolchain would be started with nothing to run."
        )
    command = host_interpreter() if tc.command == SELF else tc.command
    return [command, str(manifest.root / manifest.entry)]


def probe_toolchain(manifest: PluginManifest) -> None:
    """Can this machine run this reader at all? Asked once, before any store is opened.

    `ToolchainMissing` and never `PluginRefused`: a missing toolchain is the **machine's**
    state and a reader can act on it, where a manifest that disagrees with the build is
    nobody's to fix. The sentence names the language, the command, the version wanted, the
    version found, and both ways forward (rules 49 and 89). How many files will therefore
    go unread is the caller's to add — it is the one part of the sentence this function
    cannot know.
    """
    tc = manifest.toolchain
    if tc is None or not tc.command or tc.command == SELF:
        # This interpreter is the thing asking, so there is nothing to find.
        return
    found = shutil.which(tc.command)
    if found is None:
        raise ToolchainMissing(
            f"{manifest.lang} needs `{tc.command}`"
            + (f" ≥ {tc.min_version}" if tc.min_version else "")
            + f" and nothing answers `{tc.command} "
            + " ".join(tc.probe) + "` on this machine. Install it"
            + (f" ({tc.install})" if tc.install else "")
            + f", or run again with `--without {manifest.lang}` and the map will say those "
            f"files were declined."
        )
    if not tc.min_version:
        return
    try:
        out = subprocess.run(  # noqa: S603 — argv is built, never a shell
            [found, *tc.probe], capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolchainMissing(
            f"{manifest.lang} needs `{tc.command}` ≥ {tc.min_version} and asking it its "
            f"version failed: {exc}."
        ) from exc
    said = (out.stdout or out.stderr).strip()
    if not _at_least(said, tc.min_version):
        raise ToolchainMissing(
            f"{manifest.lang} needs `{tc.command}` ≥ {tc.min_version} and this machine has "
            f"{said or '(no version in its answer)'}. Upgrade it"
            + (f" ({tc.install})" if tc.install else "")
            + f", or run again with `--without {manifest.lang}` and the map will say those "
            f"files were declined."
        )


def _at_least(said: str, wanted: str) -> bool:
    """Is the version in `said` at least `wanted`? Refuses rather than guessing.

    Deliberately small: it reads the first dotted run of digits it finds, because `node`
    says `v20.11.0` and others say `swift-driver version: 1.90.11`. A version it cannot
    find at all is **not** treated as new enough (rule 49) — a plausible pass is what hides
    the failure this probe exists for.
    """
    def parts(text: str) -> tuple[int, ...]:
        run: list[str] = []
        for ch in text:
            if ch.isdigit() or (ch == "." and run):
                run.append(ch)
            elif run:
                break
        return tuple(int(x) for x in "".join(run).strip(".").split(".") if x)

    got, need = parts(said), parts(wanted)
    if not got:
        return False
    return got >= need[: len(got)] if len(got) < len(need) else got >= need


class OutOfProcessPlugin:
    """One language, read by another program over a pipe."""

    def __init__(self, manifest: PluginManifest) -> None:
        self.manifest = manifest
        # **Always nought for this reader, and that is not an oversight.** `lost` means a
        # file that never arrived *at all*, which is the only thing an in-process pool can
        # say when a worker dies: the parent has no way to attribute the death to a file.
        # Here the host is holding the pipe and knows exactly which request was
        # outstanding, so a death produces a record naming the file and the reason instead
        # of a number. The better answer is kept rather than degraded to match the worse
        # one, and `WalkStats` counts it off `ff.errors` like any other failure.
        self.lost = 0
        # Call sites this reader walked and could not name a far end for, in two numbers
        # because they are two facts — see `IngestPlugin`. The host counts what it
        # *received*; these are the reader's own count of what it did not send, and the two
        # together say whether a thin answer is a thin program or a thin reader (rule 32).
        # Filled by `edges`, nought until it has been asked.
        self.edges_outside = 0
        self.edges_unknown = 0
        # Fields an edge carried that this build does not read. Survivable by design — a
        # plugin built against a later schema knows about fields this one does not — but
        # never silent: a file can carry its dropped keys in `FileFacts.errors` and an
        # edge has nowhere to put them, so they are held here and the walk says them
        # (design rule 1). Deduped, because one unknown key on nine thousand edges is one
        # fact.
        self.edge_notes: list[str] = []
        # What the reader said when it opened the session. See `open`.
        self.opened_notes: list[str] = []
        self._worker: NdjsonWorker | None = None

    # ------------------------------------------------------------ lifecycle --- #

    def probe(self) -> None:
        probe_toolchain(self.manifest)

    def open(self, root: Path, all_files: Sequence[Path]) -> None:
        worker = NdjsonWorker(plugin_argv(self.manifest), self.manifest)
        worker.start()
        self._worker = worker
        reply = worker.open(root, [str(p) for p in all_files])
        # **What the reader said about the session it just built, kept rather than
        # discarded.** `opened` has carried `program_ms` and `diagnostics` since chunk 7 and
        # this process threw both away — a field a plugin fills and nobody reads is an empty
        # view with no symptom (rule 35), and here what it holds is how a monorepo was
        # divided into compilations. A reader that says that is one somebody can check;
        # 1,935 edges with no account of which projects produced them is a number nobody
        # can weigh (design rule 1).
        self.opened_notes = [str(d) for d in (reply.get("diagnostics") or [])]
        ms = reply.get("program_ms")
        if isinstance(ms, int) and ms > 0:
            self.opened_notes.append(f"opened in {ms / 1000:.1f}s")

    def edges(self) -> Iterator[SuppliedEdge]:
        """Where this language's calls go, asked once and read as a stream.

        **Every frame is decoded by the same strict codec the facts are**, so an unknown
        key, a missing field or a value of the wrong shape refuses the edge by name rather
        than arriving as a plausible row (rule 49). A `SuppliedEdge` that will not decode
        is a `ProtocolError` and not a dropped row: unlike a file, there is no per-edge
        error channel and a silently short answer is a resolution rate nobody can weigh.

        **The terminator's tally is checked against what arrived.** A plugin that says it
        supplied 9,014 edges and sent 900 has a defect the host can see for nothing, and a
        count nobody checks is rule 37 — the guard that watches a name appear.
        """
        worker = self._worker
        lang = self.manifest.lang
        if worker is None:
            raise PluginRefused(
                f"the {lang} plugin was asked for edges before `open`. A checker's answer "
                f"is an answer about a whole compilation, and `open` is where it is built."
            )
        supplied = 0
        notes: list[str] = []
        self.edge_notes = []
        self.edges_outside = 0
        self.edges_unknown = 0
        for frame in worker.stream({"t": "edges"}, "edges_done"):
            if frame["t"] == "edges_done":
                said = frame.get("supplied")
                if isinstance(said, int) and said != supplied:
                    raise ProtocolError(
                        f"the {lang} plugin says it supplied {said:,} edges and sent "
                        f"{supplied:,}. A tally that disagrees with the stream means one "
                        f"of the two is not what the reader actually did, and there is no "
                        f"way to tell which from here."
                    )
                # **Two reasons, kept apart** (design rule 21). A call whose far end the
                # reader *named* and this map does not hold is an external call and the map
                # is right about it; a call the reader could not resolve at all is the
                # reader's limit. Flattened, a healthy map of a program that leans on its
                # dependencies reads exactly like a reader that has stopped resolving. A
                # plugin that sends neither is not refused — the sum is the term of the
                # protocol and these are the reader's own elaboration of it.
                self.edges_outside = int(frame.get("outside") or 0)
                self.edges_unknown = int(frame.get("unknown") or 0)
                break
            if frame["t"] != "edge":
                raise ProtocolError(
                    f"the {lang} plugin sent {frame['t']!r} during an `edges` stream; the "
                    f"frames of one are `edge` and `edges_done`."
                )
            try:
                edge = decode(SuppliedEdge, frame.get("edge"), notes)
            except CodecError as exc:
                raise ProtocolError(
                    f"the {lang} plugin sent an edge this build cannot read: {exc}. An "
                    f"edge has no error channel of its own, so one that will not decode "
                    f"is refused rather than dropped — a short answer is a resolution "
                    f"rate nobody can weigh."
                ) from exc
            if edge.file:
                supplied += 1
            yield edge
        self.edge_notes = sorted(set(notes))

    def close(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            self._worker = None

    def stamp(self) -> str:
        return self.manifest.version

    # -------------------------------------------------------------- extract --- #

    def extract(self, work: Sequence[Path], root: Path,
                progress: ProgressFn | None = None,
                jobs: int | None = None) -> Iterator[FileFacts]:
        """Facts for `work`, one request at a time.

        `jobs` is accepted and not used, and that is the contract rather than an omission:
        it is the machine's owner speaking, and how many files at once that means is still
        the reader's to decide. This reader holds one session and feeds it — the growth
        axis for a type-checking plugin is one worker per project, not per file, because
        the resolved-symbol information it exists to provide only exists inside a program.
        """
        if not work:
            return
        self.lost = 0
        if self._worker is None:
            raise PluginRefused(
                f"the {self.manifest.lang} plugin was asked to extract before `open`. A "
                f"reader that resolves symbols needs the whole compilation first, which is "
                f"what `open` is."
            )

        for i, path in enumerate(work, 1):
            rel = str(path)
            facts = self._one(path, root)
            if progress:
                progress(rel, i, len(work))
            if facts is not None:
                yield facts

    def _one(self, path: Path, root: Path) -> FileFacts | None:
        """One file, with every way it can go wrong given its own answer."""
        worker = self._worker
        assert worker is not None                       # noqa: S101 — checked by caller
        lang = self.manifest.lang
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return self._synthesised(path, root, f"could not be read: {exc}")
        wanted = hash_source(source)

        try:
            reply = worker.request({"t": "extract", "path": str(path), "hash": wanted})
        except WorkerDied as exc:
            return self._after_death(path, root, exc)

        if reply["t"] == "failed":
            # The plugin says it threw. **The host writes the record**, because a reader
            # that has just crashed on a file is not the right authority on what that file
            # is, and its guess would land in the map under the file's own name.
            reason = reply.get("reason", "(no reason given)")
            return self._synthesised(path, root, f"the {lang} reader failed on it: {reason}")

        if reply["t"] != "facts":
            raise ProtocolError(
                f"the {lang} plugin answered `extract` with {reply['t']!r}; the answers to "
                f"a file are `facts` and `failed`."
            )

        echoed = reply.get("hash")
        if echoed != wanted:
            # The file changed under the run. Storing the facts under a hash they do not
            # describe is how a stale answer becomes a cached one nobody will revisit
            # (rule 12), so they are recorded as a failure with both hashes named.
            # **Two things look like this and only one of them is the file's fault.** It
            # may have changed under the run; or the two sides may have *read the same
            # bytes differently*, which is what happens to every CRLF file when a reader
            # skips the newline normalisation `ingest.contract.SOURCE_TEXT` requires. The
            # first is a race and the second is a plugin defect, and naming only the first
            # sent a session looking for a race that was not there.
            return self._synthesised(
                path, root,
                f"the host hashed {wanted} and the {lang} reader hashed {echoed}, so its "
                f"facts describe neither version for certain. Either the file changed "
                f"while it was being read, or the reader read it differently — a source "
                f"file is {SOURCE_TEXT}.",
            )

        try:
            facts = decode_facts(reply.get("facts"))
        except CodecError as exc:
            return self._synthesised(path, root, f"came back in a shape this build cannot "
                                                 f"read: {exc}")
        # The language is the host's to write, on the file and on every record below it —
        # the same function the in-process reader passes through (rule 51).
        facts.lang = lang
        return stamp_lang(facts)

    def _after_death(self, path: Path, root: Path, exc: WorkerDied) -> FileFacts | None:
        """The worker went away. Respawn once; a second death refuses the language."""
        worker = self._worker
        assert worker is not None                       # noqa: S101 — checked by caller
        lang = self.manifest.lang
        tail = worker.stderr_tail()
        if worker.deaths >= 1:
            raise PluginRefused(
                f"the {lang} plugin has now died twice — the second time on {path} ({exc}). "
                f"It was restarted after the first and did not survive, so this is the "
                f"reader rather than one file, and every fact it has produced this run is "
                f"worth doubting.\n{tail or '(nothing on stderr)'}"
            )
        # **The file it died on is not retried.** A fresh worker meets the same file and
        # dies again, and the second death would refuse the language over one bad file.
        note = (f"the {lang} reader died reading it ({exc}); the reader was restarted and "
                f"this file was not read again. It said:\n{tail or '(nothing on stderr)'}")
        worker.respawn()
        return self._synthesised(path, root, note)

    def _synthesised(self, path: Path, root: Path, why: str) -> FileFacts:
        """The host's own record of a file the reader could not describe.

        It carries the **path and the language and nothing else**: an empty `FileFacts` with
        an error on it is exactly what the in-process reader produces for a file that will
        not parse, so both kinds of reader leave the same shape behind and `WalkStats`
        counts them the same way.

        Deliberately **no `content_hash`**, which means the file is not cached and is read
        again next run. A file that failed because a worker died is not a file whose facts
        are known, and caching the failure would make one crash permanent until somebody
        edited the file.
        """
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path
        return FileFacts(
            path=stored_path(rel), lang=self.manifest.lang, module="", content_hash="",
            errors=[why],
        )
