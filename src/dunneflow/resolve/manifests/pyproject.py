"""`pyproject.toml` -- Python packaging metadata.

The provider this whole package was generalised out of. Its evidence sentence is unchanged
from the day it was written, because `web/waysin.py:120` renders it verbatim and
`tests/test_waysin.py` pins it byte for byte.

**One thing here is a correction rather than a move.** The old reader merged
`[project.gui-scripts]` into the same dictionary as `[project.scripts]` and labelled every
entry `[project.scripts]`, so the marker lied about its own source -- in the one string a
reader is shown verbatim. Each table names itself now.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from ...schema import EntrypointKind, Provenance
from ..version import ProgramVersion
from .records import ManifestEntry, ManifestReading, Provider, TargetKind

FILENAME = "pyproject.toml"

# The two tables that declare an executable, and the kind each one means. `gui-scripts` is
# still a CLI here: `EntrypointKind` has no GUI word, and inventing one would change the
# meaning of a stored fact for a distinction nothing in this tool acts on. What is not
# flattened is the *evidence*, which is the half a reader sees.
_SCRIPT_TABLES = ("scripts", "gui-scripts")


def read(text: str, path: Path, where: str) -> ManifestReading | None:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return ManifestReading(filename=FILENAME, where=where,
                               notes=("could not be parsed as TOML",))
    project = data.get("project") or {}
    if not isinstance(project, dict):
        return ManifestReading(filename=FILENAME, where=where)

    entries: list[ManifestEntry] = []
    for table in _SCRIPT_TABLES:
        scripts = project.get(table) or {}
        if not isinstance(scripts, dict):
            continue
        for name, target in scripts.items():
            if not isinstance(name, str) or not isinstance(target, str):
                continue
            entries.append(ManifestEntry(
                name=name, kind=EntrypointKind.CLI,
                evidence=f"pyproject.toml [project.{table}] {name} = {target}",
                target_kind=TargetKind.MODULE_ATTR, target=target,
            ))

    notes: list[str] = []
    version = None
    raw = project.get("version")
    if isinstance(raw, str) and raw.strip():
        # `tomllib` gives no line numbers, so `where` is a file and not a file:line.
        # Saying which is better than implying a precision that is not there.
        version = ProgramVersion(raw.strip(), Provenance.DECLARED_CODE, where)
    elif isinstance(project.get("dynamic"), list) and "version" in project["dynamic"]:
        # **A declared absence, and it earns its own sentence.** `dynamic = ["version"]`
        # says the version is computed at build time -- by `hatch-vcs`, in Comitia's case,
        # out of a git tag this tool will never ask for. Falling silently through to the
        # directory-name guess is the right *answer* and the wrong *silence*: the reader
        # then sees an INFERRED version with no hint that the program did state something
        # about the question (design rule 21 -- the three absences are three answers).
        notes.append('[project] declares `dynamic = ["version"]` — the version is computed '
                     'at build time and is not stated in this file')

    return ManifestReading(
        filename=FILENAME, where=where,
        name=str(project.get("name") or ""),
        version=version, entries=tuple(entries), notes=tuple(notes),
    )


PROVIDER = Provider(filename=FILENAME, read=read)
