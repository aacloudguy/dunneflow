"""`build.gradle.kts` -- the Gradle Kotlin DSL build script.

**This provider has no population.** There is no `build.gradle.kts` anywhere on the
machine this was written on, so unlike its five siblings it is proved by fixtures and by
nothing else. That is recorded here rather than left to be assumed from the fact that it
shipped (rule 24: a measurement must measure the thing it names, and this one measures a
fixture).

**It is a program, not a data file**, so only the literal
`application { mainClass.set("Foo") }` form is read and anything computed is refused --
the same rule `Package.swift` is read under, and `_from_dunder`'s (`version.py:90`)
one language over. `mainClass = "Foo"` is the property-assignment spelling of the same
declaration and is read too.

**No version.** A Gradle `version = "1.2"` is a *property assignment in a build script*,
evaluated against a project object, and frequently `version = rootProject.version` or a
value loaded from `gradle.properties`. Reading the literal case alone would answer for
some projects and silently not for others, which is the shape rule 49 warns about; the
absence is stated instead.

**`mainClass` names a class on a classpath**, not a file, so its target kind is `NONE`.
A Java class name is not a path until a source set's layout is known, and this provider
does not read one.
"""

from __future__ import annotations

import re
from pathlib import Path

from ...schema import EntrypointKind
from .records import ManifestEntry, ManifestReading, Provider, TargetKind

FILENAME = "build.gradle.kts"

# The two literal spellings of one declaration: the setter and the property assignment.
_MAIN_CLASS = re.compile(r'mainClass\s*(?:\.set\s*\(\s*"([^"]+)"\s*\)|=\s*"([^"]+)")')

# The same two with something that is not a string literal where the class goes.
_MAIN_CLASS_COMPUTED = re.compile(r'mainClass\s*(?:\.set\s*\(\s*(?!")|=\s*(?!"))')


def read(text: str, path: Path, where: str) -> ManifestReading | None:
    names = [a or b for a, b in _MAIN_CLASS.findall(text)]
    entries = tuple(
        ManifestEntry(
            name=name, kind=EntrypointKind.MAIN,
            evidence=f'build.gradle.kts application.mainClass = "{name}"',
            target_kind=TargetKind.NONE,
        )
        for name in names
    )

    notes: list[str] = []
    computed = len(_MAIN_CLASS_COMPUTED.findall(text)) - len(names)
    if computed > 0:
        notes.append(f"refused {computed} mainClass "
                     f"{'declaration' if computed == 1 else 'declarations'} that is not a "
                     f"string literal — build.gradle.kts is a program, and this tool does "
                     f"not run one")
    notes.append("Gradle's `version` is a property assignment evaluated against the "
                 "project, so no version is read from this file")

    return ManifestReading(filename=FILENAME, where=where,
                           entries=entries, notes=tuple(notes))


PROVIDER = Provider(filename=FILENAME, read=read)
