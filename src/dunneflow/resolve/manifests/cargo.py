"""`Cargo.toml` -- the Rust manifest.

Two ways a Rust crate declares an executable, and both are read:

* **`[[bin]]`** -- explicit, with a name and usually a `path`. DunneNote's
  `apps/host-http` declares `dunnenote-host`, and `legacy/v0.1/crates/app` declares
  `calnote`.
* **`src/main.rs`** -- the convention, which Cargo honours with no `[[bin]]` at all. Asked
  of the **disk** rather than guessed, which is why `read` is handed the path: a
  convention that names a file is only a way in when the file is there.

**A workspace declares a version and no executable.** DunneNote's root `Cargo.toml` is
`[workspace]` with `[workspace.package] version = "0.9.0"` and no `[package]` at all;
reading only `[package]` would report that the tree states no version while a file in it
plainly does. `[package]` wins where both exist, because it is the crate's own.

*What this does **not** do is understand a workspace.* Members are read because the walk
reaches them, not because `members = [...]` was followed -- see the residue in the record.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from ...schema import EntrypointKind, Provenance
from ..version import ProgramVersion
from .records import ManifestEntry, ManifestReading, Provider, TargetKind

FILENAME = "Cargo.toml"

# Cargo's own default when a `[[bin]]` omits `path`, and the convention it applies when
# there is no `[[bin]]` at all.
_CONVENTIONAL_MAIN = "src/main.rs"


def _table(data: dict[str, Any], key: str) -> dict[str, Any]:
    """One TOML table, or an empty one. A manifest is somebody else's file and may hold
    anything at all under a name this reader expects to be a table."""
    got = data.get(key)
    return got if isinstance(got, dict) else {}


def read(text: str, path: Path, where: str) -> ManifestReading | None:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return ManifestReading(filename=FILENAME, where=where,
                               notes=("could not be parsed as TOML",))

    package = _table(data, "package")
    workspace = _table(data, "workspace")
    ws_package = _table(workspace, "package")

    entries: list[ManifestEntry] = []
    notes: list[str] = []

    bins = data.get("bin")
    declared_bins = bins if isinstance(bins, list) else []
    for entry in declared_bins:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            continue
        target = entry.get("path")
        target = target if isinstance(target, str) and target else _CONVENTIONAL_MAIN
        entries.append(ManifestEntry(
            name=name, kind=EntrypointKind.CLI,
            evidence=f'Cargo.toml [[bin]] name = "{name}"',
            target_kind=TargetKind.FILE, target=target,
        ))

    # The convention, and only where there is no explicit `[[bin]]` -- a crate that lists
    # its binaries has said what they are, and adding an unnamed seventh from a file on
    # disk would be this tool disagreeing with the manifest.
    if not entries and (path.parent / _CONVENTIONAL_MAIN).is_file():
        crate = package.get("name")
        crate = crate if isinstance(crate, str) and crate else path.parent.name
        entries.append(ManifestEntry(
            name=crate, kind=EntrypointKind.CLI,
            evidence=f"Cargo.toml {_CONVENTIONAL_MAIN} — Cargo's own convention, "
                     f"with no [[bin]] declared",
            target_kind=TargetKind.FILE, target=_CONVENTIONAL_MAIN,
        ))

    version = None
    for table, label in ((package, "[package]"), (ws_package, "[workspace.package]")):
        raw = table.get("version")
        if isinstance(raw, str) and raw.strip():
            version = ProgramVersion(raw.strip(), Provenance.DECLARED_CODE, where)
            if label == "[workspace.package]":
                notes.append("the version is the workspace's, declared in "
                             "[workspace.package] — this file declares no [package]")
            break
        # A member inheriting with `version.workspace = true` states that it takes the
        # workspace's, which is a real declaration and not a version. Named rather than
        # read, because the workspace this member belongs to is not resolved here.
        if isinstance(raw, dict) and raw.get("workspace") is True:
            notes.append("version is inherited from the workspace "
                         "(`version.workspace = true`) — this tool does not resolve "
                         "workspace membership, so the inherited value is not read")
            break

    name = package.get("name") if isinstance(package.get("name"), str) else ""
    if not name and workspace:
        notes.append("a [workspace] rather than a crate — it declares members, and this "
                     "tool reads each member's own manifest where the walk reaches it")

    return ManifestReading(filename=FILENAME, where=where, name=str(name or ""),
                           version=version, entries=tuple(entries), notes=tuple(notes))


PROVIDER = Provider(filename=FILENAME, read=read)
