"""What a provider reads, and what it hands back -- in one module both sides import.

Its own file rather than `__init__.py` for the plainest of reasons: the registry imports
every provider and every provider needs these types, so putting them in the registry is a
cycle. `ingest/contract.py` sits the same way beside `ingest/__init__.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# `TargetKind` lives in `schema.py` rather than here, and that placement is the
# point: it is a **stored** fact (`entrypoints.target_kind`), read by
# `render/markdown.py` and `anomalies.py` long after the provider that decided it
# has gone. `schema.py` is what a fact is; this file is what a provider hands over.
from ...schema import EntrypointKind, TargetKind
from ..version import ProgramVersion


@dataclass(frozen=True, slots=True)
class ManifestEntry:
    """One way in, as a manifest declares it -- before anything is bound to it.

    Deliberately not an `Entrypoint`. Minting the id needs to know whether this manifest is
    the package root's, which is the caller's question rather than the provider's, and
    binding needs the store, which a provider never touches.
    """

    name: str
    kind: EntrypointKind
    evidence: str
    target_kind: TargetKind
    target: str = ""


@dataclass(frozen=True, slots=True)
class ManifestReading:
    """One manifest, read.

    `notes` is what this provider declined, and why, in its own words. Not housekeeping:
    `"scripts"` in a `package.json` is up to sixteen build commands that are not ways in,
    and a reader who sees no ways in from a file plainly listing sixteen somethings is owed
    the difference (design rule 1).

    `at_root` is set by the registry, never by a provider: whether a manifest is the
    package root's is a fact about where the walk found it.
    """

    filename: str
    where: str                  # relative to the analysed tree; may climb out with `..`
    name: str = ""              # what this manifest calls the program
    version: ProgramVersion | None = None
    entries: tuple[ManifestEntry, ...] = ()
    notes: tuple[str, ...] = ()
    at_root: bool = False

    @property
    def declares_nothing(self) -> bool:
        return not (self.name or self.version or self.entries)


@dataclass(frozen=True, slots=True)
class Provider:
    """One manifest filename and the function that reads it.

    A record rather than a module, so the registry is an ordinary tuple a test can walk and
    mypy can type. `read` is handed the text and the path: the text because every provider
    parses it, and the path because two of them ask the *directory* a question -- Cargo's
    `src/main.rs` convention is a file on disk, not a line in the manifest.
    """

    filename: str
    read: Callable[[str, Path, str], ManifestReading | None]
