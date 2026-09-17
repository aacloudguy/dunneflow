"""`package.json` -- the npm/pnpm manifest.

**`bin` is the contract; `scripts` is a label** (rule 30). `bin` is what gets put on a
reader's `PATH` when they install the program; `scripts` is a task runner, and admitting it
would put fourteen build commands in the ways-in panel beside real ones. Measured across
the four JavaScript corpora here: **31 `scripts` entries and not one `bin`** -- DunneNote 4,
DunneCorp 16, uigen 8, Society 3. Every one of them is declined by name, so a reader
looking at a manifest that plainly lists sixteen somethings is told why none of them is a
way in (design rule 1).

`main` and `exports` are a **LIBRARY** way in: they say how another program reaches into
this one, which is a way in even though nobody types it.

**`exports` is read only where it names a single target.** A conditional-exports map --
uigen's generated Prisma client has nineteen subpaths across six runtime conditions -- is
one package declaring one entry point in many dialects, not nineteen ways in. `main` is
preferred where both exist, because it is the unconditional answer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...schema import EntrypointKind, Provenance
from ..version import ProgramVersion
from .records import ManifestEntry, ManifestReading, Provider, TargetKind

FILENAME = "package.json"


def _single_export(exports: Any) -> str | None:
    """The one file `exports` names, or None when it names more than one.

    A string is the whole answer. A dict is read only through its root subpath `"."`, and
    only down to a string: a condition map (`{"require": …, "import": …}`) is the same
    entry point spelled for several runtimes and picking one of them would be this tool
    choosing a module system on the reader's behalf.
    """
    if isinstance(exports, str):
        return exports
    if not isinstance(exports, dict):
        return None
    root = exports.get(".")
    return root if isinstance(root, str) else None


def read(text: str, path: Path, where: str) -> ManifestReading | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return ManifestReading(filename=FILENAME, where=where,
                               notes=("could not be parsed as JSON",))
    if not isinstance(data, dict):
        return ManifestReading(filename=FILENAME, where=where)

    entries: list[ManifestEntry] = []
    notes: list[str] = []

    # `bin` has two spellings and both are the same contract: a string means one command
    # named after the package, a dict means several named individually.
    name = str(data.get("name") or "")
    raw_bin = data.get("bin")
    commands: dict[str, str] = {}
    if isinstance(raw_bin, str) and name:
        commands[name] = raw_bin
    elif isinstance(raw_bin, dict):
        commands = {k: v for k, v in raw_bin.items()
                    if isinstance(k, str) and isinstance(v, str)}
    for cmd, target in commands.items():
        entries.append(ManifestEntry(
            name=cmd, kind=EntrypointKind.CLI,
            evidence=f'package.json "bin" {cmd} = {target}',
            target_kind=TargetKind.FILE, target=target,
        ))

    main = data.get("main")
    exported = _single_export(data.get("exports"))
    lib_target, lib_field = (
        (main, "main") if isinstance(main, str) and main
        else (exported, "exports") if exported else (None, "")
    )
    if lib_target and name:
        entries.append(ManifestEntry(
            name=name, kind=EntrypointKind.LIBRARY,
            evidence=f'package.json "{lib_field}" {name} = {lib_target}',
            target_kind=TargetKind.FILE, target=lib_target,
        ))
    elif isinstance(data.get("exports"), dict) and not exported:
        notes.append('"exports" names more than one target — a condition map is one entry '
                     'point spelled for several runtimes, and choosing one would be this '
                     'tool picking a module system')

    scripts = data.get("scripts")
    if isinstance(scripts, dict) and scripts:
        n = len(scripts)
        notes.append(f'refused {n} "scripts" '
                     f'{"entry" if n == 1 else "entries"} — a task runner, not a way in')

    version = None
    raw = data.get("version")
    if isinstance(raw, str) and raw.strip():
        version = ProgramVersion(raw.strip(), Provenance.DECLARED_CODE, where)

    return ManifestReading(filename=FILENAME, where=where, name=name, version=version,
                           entries=tuple(entries), notes=tuple(notes))


PROVIDER = Provider(filename=FILENAME, read=read)
