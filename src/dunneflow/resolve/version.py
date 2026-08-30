"""What version a program says it is -- read from the program, never from a VCS.

DunneFlow never talks to a version control system, so the only version it can report is
the one the source **asserts about itself**. That is a real limit and it is also the
point: a directory somebody hands you has no history to ask, and it is exactly the case
this tool exists to serve.

Three tiers, in the order they are trusted, and each says how it knows:

* `pyproject.toml [project] version` -- packaging metadata, the thing the program is
  actually published as. Proven by a file the reader can open.
* `__version__` at module scope -- the same claim written in code, proven by a file and
  a line.
* **the directory's own name** -- `society-2026-08-26`, `myapp-1.2.3`. A guess, marked
  `INFERRED`, and offered only when nothing better exists. Tom's rule: we may infer,
  provided we say that we did.

The tiers are `schema.Provenance`, which already exists for glossary definitions and
means the same thing here. Nothing new is invented to say "quoted" and "guessed" twice.

**`__version__` is read here rather than out of the constants table**, and that is
deliberate. `collect_module_names` filters dunders out on purpose -- "a dunder is
packaging metadata, not something the program named" -- which is right for the glossary
and is precisely why this module wants it. The filter is routed around, never removed:
the constant still stays out of the program's vocabulary while the version reads it.
"""

from __future__ import annotations

import ast
import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ..schema import Provenance

# Files a package conventionally states its own version in, in the order they are looked
# at. Not a search of the whole tree: `__version__` appears in vendored copies, test
# fixtures and generated files, and the first match in a walk is not the program's own.
VERSION_FILES: tuple[str, ...] = ("__init__.py", "_version.py", "version.py")

# A version-shaped or date-shaped tail on a directory name. Anchored at a separator so
# `society-2026-08-26` yields `2026-08-26` and `mensores` yields nothing -- a marker must
# sit at an edge of the name (rule 5), or every directory has a version in it somewhere.
_LEAF = re.compile(
    r"[-_@]("
    r"v?\d+\.\d+(?:\.\d+)?(?:[-.][0-9A-Za-z.]+)?"     # 1.2, 1.2.3, 1.2.3-rc1
    r"|\d{4}-\d{2}-\d{2}"                             # 2026-08-26
    r")$"
)


@dataclass(frozen=True)
class ProgramVersion:
    """What the program says it is, and how we came to believe it."""

    value: str
    provenance: Provenance
    where: str          # a path relative to the analysed tree, with a line where there is one

    @property
    def inferred(self) -> bool:
        return self.provenance is Provenance.INFERRED


def _from_pyproject(root: Path, relative_to: Path) -> ProgramVersion | None:
    """`[project] version`, found the way the entrypoint reader finds its scripts.

    The package root is not always the analysed tree: a `src/` layout puts
    `pyproject.toml` one directory above the code, so the honest `where` is
    `../pyproject.toml` and `os.path.relpath` is what expresses it (rule 61).

    `tomllib` gives no line numbers, so `where` is a file and not a file:line. Saying
    which is better than implying a precision that is not there.
    """
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return None
    value = data.get("project", {}).get("version")
    if not isinstance(value, str) or not value.strip():
        return None
    where = os.path.relpath(pyproject.resolve(), relative_to.resolve())
    return ProgramVersion(value.strip(), Provenance.DECLARED_CODE, where)


def _from_dunder(tree: Path) -> ProgramVersion | None:
    """`__version__ = "1.2.3"` at module scope, with its file and its line.

    Module scope only, and a plain string literal only. `__version__ = _read_it()` is a
    call whose value this cannot know without running the program, and reporting the
    expression as though it were the version would be a claim about something nobody has
    evaluated -- rule 1, precision over recall.
    """
    # The tree itself, then one level of package directory. Deep enough to find
    # `src/thing/__init__.py` from `src/`, shallow enough not to wander into vendored
    # copies and test fixtures, where the first `__version__` found is not the program's.
    roots = [tree] + sorted(d for d in tree.iterdir() if d.is_dir()) if tree.is_dir() else []
    for directory in roots:
        for name in VERSION_FILES:
            path = directory / name
            if not path.exists():
                continue
            try:
                mod = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except (SyntaxError, OSError):
                continue
            for node in mod.body:                       # module scope, never a nested one
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                targets = ([node.target] if isinstance(node, ast.AnnAssign)
                           else list(node.targets))
                names = [t.id for t in targets if isinstance(t, ast.Name)]
                if "__version__" not in names:
                    continue
                value = node.value
                if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                    continue
                where = f"{os.path.relpath(path.resolve(), tree.resolve())}:{node.lineno}"
                return ProgramVersion(value.value.strip(),
                                      Provenance.DECLARED_CODE, where)
    return None


def from_directory_name(leaf: str) -> ProgramVersion | None:
    """A version guessed from the directory the source was read from.

    Offered only when the program asserts nothing, and marked `INFERRED` so it can never
    be mistaken for something read. Tom's rule, and it is the difference between a useful
    guess and a false claim: infer freely, say so always.
    """
    m = _LEAF.search(leaf or "")
    if not m:
        return None
    return ProgramVersion(m.group(1), Provenance.INFERRED,
                          f"the directory name {leaf!r}")


def detect(tree: Path, *, package_root: Path | None = None,
           leaf: str = "") -> ProgramVersion | None:
    """The best-proven version this program states about itself, or None.

    Order is trust, not convenience: something published beats something written in a
    module, and both beat a guess off a directory name. Returning `None` is a real answer
    -- most programs say nothing about their version, and inventing one would be worse
    than the silence.
    """
    return (_from_pyproject(package_root or tree, tree)
            or _from_dunder(tree)
            or from_directory_name(leaf))
