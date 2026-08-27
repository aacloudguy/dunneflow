"""Ways in that are declared rather than written.

Packaging metadata is the most reliable entrypoint source there is: `[project.scripts]`
is not a heuristic, it is the literal contract between the program and whoever installs
it. Anything found here outranks a decorator or a naming convention.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from ..schema import Entrypoint, EntrypointKind, make_id
from ..store import Store


def _target_routine(store: Store, module: str, attr: str) -> str | None:
    """Find the routine a `module:attr` console-script target names."""
    row = store.query(
        "SELECT id FROM routines WHERE module = ? AND name = ? LIMIT 1", (module, attr)
    )
    if row:
        return str(row[0]["id"])
    # A Typer/Click application object rather than a function: the way in is the
    # module that builds it.
    row = store.query(
        "SELECT id FROM routines WHERE module = ? AND name = '<module>' LIMIT 1", (module,)
    )
    return str(row[0]["id"]) if row else None


def entrypoints_from_packaging(root: Path, store: Store) -> list[Entrypoint]:
    """Read `[project.scripts]` and `[project.gui-scripts]` out of pyproject.toml."""
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return []
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return []

    project = data.get("project", {})
    scripts: dict[str, str] = {}
    scripts.update(project.get("scripts", {}) or {})
    scripts.update(project.get("gui-scripts", {}) or {})

    found: list[Entrypoint] = []
    for name, target in scripts.items():
        module, _, attr = target.partition(":")
        ep = Entrypoint(
            id=make_id("script", name),
            kind=EntrypointKind.CLI,
            name=name,
            routine_id=_target_routine(store, module, attr or "main"),
            module=module,
            evidence=f"pyproject.toml [project.scripts] {name} = {target}",
        )
        found.append(ep)
        store.add_entrypoint(ep, file=str(pyproject))
    store.conn.commit()
    return found
