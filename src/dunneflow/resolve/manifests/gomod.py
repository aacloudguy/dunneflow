"""`go.mod` -- the Go module file.

**It declares no version of the program, and saying so is the whole of this provider's
precision.** `go.mod`'s directives are `module`, `go`, `toolchain`, `require`, `replace`,
`exclude` and `retract`. The `go` line is a *language and toolchain floor* --
`go 1.25.6` in `../beads-main`, `go 1.23.7` with `toolchain go1.23.10` in
`../AppGraphs/rain-main` -- and reporting it as what the program says it is would be
`_from_dunder`'s refusal in reverse: a number that is certainly in the file and is
certainly not the answer.

What it *does* declare is a **module path**, and the `/vN` suffix on one is a real
published claim: `module github.com/x/y/v2` is Go's only way to say *this is major
version 2*, and it is a declaration a reader can open the file and check. It is recorded
as `2`, marked `DECLARED_CODE`, and the note beside it says it is a major version and not
a full one, because `2` and `2.1.4` are different precisions and a column holding both
without saying which is a column nobody can act on (rule 32).

**No entrypoints at all.** Go's way in is `func main` in `package main`, which is a fact
about the source and belongs to a language reader -- `plugins/go`, which reads the
`.go` files -- and not to this provider.
"""

from __future__ import annotations

import re
from pathlib import Path

from ...schema import Provenance
from ..version import ProgramVersion
from .records import ManifestReading, Provider

FILENAME = "go.mod"

# `module <path>`, on its own line, before any comment. Go's grammar allows a quoted path
# and a parenthesised block; both are rare and the quoted form is stripped below.
_MODULE = re.compile(r"^\s*module\s+(\S+)", re.MULTILINE)

# The major-version suffix a module path carries from v2 onward. Anchored at the end and
# at a slash, because `github.com/v2ray/core` is not version 2 of anything (rule 5).
_MAJOR = re.compile(r"/v([1-9]\d*)$")


def read(text: str, path: Path, where: str) -> ManifestReading | None:
    m = _MODULE.search(text)
    if not m:
        return ManifestReading(
            filename=FILENAME, where=where,
            notes=("no `module` directive — this file declares nothing this tool reads",))
    module = m.group(1).strip().strip('"')

    notes = ["go.mod declares no version of the program; its `go` directive is a "
             "toolchain floor, not a version"]
    version = None
    major = _MAJOR.search(module)
    if major:
        version = ProgramVersion(major.group(1), Provenance.DECLARED_CODE, where)
        notes.append(f"the module path ends `/v{major.group(1)}`, which is Go's way of "
                     f"declaring a major version — a major only, not a full version")

    return ManifestReading(filename=FILENAME, where=where, name=module,
                           version=version, notes=tuple(notes))


PROVIDER = Provider(filename=FILENAME, read=read)
