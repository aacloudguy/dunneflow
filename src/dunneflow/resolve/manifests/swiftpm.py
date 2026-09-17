"""`Package.swift` -- the Swift Package Manager manifest.

**It is a Swift program, not a data file**, and that decides everything here. The only
honest way to evaluate one is to run it, which this tool will not do, so what is read is
the literal form and nothing else: `.executable(name: "x", targets: [...])` in the
`products:` list. A product whose name is computed, or built in a loop, is not reported --
`_from_dunder`'s reasoning verbatim (`version.py:90`): reporting an expression as though it
were the value would be a claim about something nobody has evaluated.

**A `.library` is not a way in here**, and that is the measurement rather than an
omission. Both Swift packages available on this machine -- `../AlphaVantage-main` and
`../TestReality` -- declare `.library` products and no executable, so the corpus proves
this provider reads *products* rather than package names. A Swift library's callers are
outside the analysed tree entirely, where a `package.json` `main` at least names a file
this map may hold.

**No version.** SwiftPM has no version field: a Swift package is versioned by its git tags,
which this tool never asks for (`resolve/version.py`'s opening paragraph). The absence is
stated rather than filled.
"""

from __future__ import annotations

import re
from pathlib import Path

from ...schema import EntrypointKind
from .records import ManifestEntry, ManifestReading, Provider, TargetKind

FILENAME = "Package.swift"

# `.executable(name: "x"` — the literal form, and only the literal form. `\s*` across the
# break because a products list is conventionally wrapped one product per line and the
# name may sit on the next one.
_EXECUTABLE = re.compile(r'\.executable\s*\(\s*name\s*:\s*"([^"]+)"')

# The same call with something that is not a string literal where the name goes. Matched
# separately so the refusal can be counted and said, rather than the product vanishing.
_EXECUTABLE_COMPUTED = re.compile(r'\.executable\s*\(\s*name\s*:\s*(?!")')

# `let package = Package(name: "x"` — the package's own name, which is not a way in.
_PACKAGE_NAME = re.compile(r'Package\s*\(\s*name\s*:\s*"([^"]+)"')


def read(text: str, path: Path, where: str) -> ManifestReading | None:
    entries = [
        ManifestEntry(
            name=name, kind=EntrypointKind.CLI,
            evidence=f'Package.swift .executable(name: "{name}")',
            # A Swift product names **targets**, and a target names a directory of
            # sources rather than a file. Nothing here can turn that into one place to
            # open, and inventing `Sources/<name>/main.swift` would be a convention this
            # provider has no evidence for.
            target_kind=TargetKind.NONE,
        )
        for name in _EXECUTABLE.findall(text)
    ]

    notes: list[str] = []
    computed = len(_EXECUTABLE_COMPUTED.findall(text))
    if computed:
        notes.append(f"refused {computed} .executable "
                     f"{'product' if computed == 1 else 'products'} whose name is not a "
                     f"string literal — Package.swift is a program, and this tool does "
                     f"not run one")
    if not entries and not computed and ".library" in text:
        notes.append("declares library products and no executable — a library's callers "
                     "are outside this tree")
    notes.append("SwiftPM declares no version; a Swift package is versioned by its git "
                 "tags, which this tool never asks for")

    name = _PACKAGE_NAME.search(text)
    return ManifestReading(filename=FILENAME, where=where,
                           name=name.group(1) if name else "",
                           entries=tuple(entries), notes=tuple(notes))


PROVIDER = Provider(filename=FILENAME, read=read)
