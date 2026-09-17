"""A reader that is this interpreter.

Python's extractor needs no toolchain, no handshake and no wire: it is a function in this
process. So this wrapper exists to make it answer the same questions an out-of-process
plugin answers, and to hold the one thing that genuinely differs — **who owns the
parallelism**.

The pool lives here rather than in `walk.py`, and that is the seam rather than an
accident. How many files are read at once is the *reader's* business: this one forks a
`ProcessPoolExecutor` because parsing is CPU-bound and embarrassingly parallel, and a
reader on the far side of a pipe will instead hold one type-checker open and feed it. A
host that owned the pool would be making a decision it cannot make for a reader it has
never seen.

The loop below is `analyze_tree`'s, moved intact — including the serial fallback, which is
what keeps a machine that cannot fork from getting no facts at all rather than slower ones.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from ..schema import FileFacts
from .contract import PluginManifest, ProgressFn


def _extract_one(args: tuple[str, str]) -> FileFacts:
    """Worker entry point. Must be module-level and picklable."""
    from ..extractors.python.extract import extract_file
    path_s, root_s = args
    return extract_file(Path(path_s), Path(root_s))


class InProcessPlugin:
    """Wraps a reader that runs here, so the host cannot tell the two kinds apart."""

    def __init__(self, manifest: PluginManifest,
                 reader: Callable[[tuple[str, str]], FileFacts],
                 jobs: int | None = None) -> None:
        self.manifest = manifest
        self._reader = reader
        self._jobs = jobs
        # Files whose *worker* raised, as opposed to files that failed to parse. The
        # second kind comes back as an empty `FileFacts` carrying its error and is the
        # caller's to count off `ff.errors`; this kind never comes back at all, so
        # somebody has to hold the number or the file disappears silently. Reset per
        # `extract`, because a plugin outlives one call.
        self.lost = 0

    def probe(self) -> None:
        """Nothing to find. This reader is the process doing the asking."""

    def open(self, root: Path, all_files: Sequence[Path]) -> None:
        """Nothing to open. Python's reader answers one file without seeing the others.

        Stated rather than left blank, because *this is the difference* that decides the
        protocol's shape: a reader that resolves symbols cannot say this, and `open` exists
        for the ones that cannot.
        """

    def close(self) -> None:
        """Nothing to release. Safe to call twice, as the contract requires."""

    def stamp(self) -> str:
        return self.manifest.version

    def extract(self, work: Sequence[Path], root: Path,
                progress: ProgressFn | None = None) -> Iterator[FileFacts]:
        """Facts for `work`, in whatever order they finish.

        Failures are the caller's to count: a file that will not parse comes back as an
        empty `FileFacts` carrying its error, and one that made the *worker* raise comes
        back not at all. Both are visible to the caller, which is what lets `WalkStats`
        tell them apart from a file that simply had nothing in it.
        """
        if not work:
            return
        self.lost = 0
        jobs = self._jobs or min(os.cpu_count() or 4, 16)
        payload = [(str(p), str(root)) for p in work]
        out: list[FileFacts] = []

        if jobs > 1 and len(work) > 8:
            try:
                with ProcessPoolExecutor(max_workers=jobs) as pool:
                    futures = {pool.submit(self._reader, a): a[0] for a in payload}
                    for i, fut in enumerate(as_completed(futures), 1):
                        try:
                            out.append(fut.result())
                        except Exception:       # noqa: BLE001 — recorded, never raised
                            self.lost += 1
                        if progress:
                            progress(futures[fut], i, len(payload))
            except Exception:                   # noqa: BLE001 — fall through to serial
                out = []
                self.lost = 0

        if not out:
            for i, a in enumerate(payload, 1):
                try:
                    out.append(self._reader(a))
                except Exception:               # noqa: BLE001 — recorded, never raised
                    self.lost += 1
                if progress:
                    progress(a[0], i, len(payload))

        yield from out
