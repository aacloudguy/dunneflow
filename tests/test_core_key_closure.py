"""Rule 95's general remedy: the core key covers what the core imports (BACKLOG 5).

Rule 95 is *a cache key assembled from a directory does not cover what that directory
imports*. `sql.py` joined `core_extraction_inputs` by hand, which shut the gap the rule was
minted from and left the next one to be found the same way. This walks the import graph
instead, from the files the key names, and fails on any module of this package that the
core reaches and the key does not cover.

**Measured 2026-10-02, and that is why the remedy is a test rather than a derived key.**
Following module-level imports, the closure of the core is the hand-kept list plus exactly
one file, `runtime.py`, which says *where* a resource lives and never what a fact is.
Imports inside functions reach the language readers, and every one of those is in its own
language's stamp, which is where rule 12 wants it. Deriving the key at run time would put
`runtime.py` into it and discard every map on a packaging edit; asserting it here keeps the
key what it is and makes the next omission a failing test rather than a stale map.
"""

from __future__ import annotations

import ast
from pathlib import Path

from dunneflow.detectors import core_extraction_inputs

PKG = Path(__file__).resolve().parents[1] / "src" / "dunneflow"

# Reached by the core and deliberately not in its key, each with its reason.
NOT_EXTRACTION = {
    "runtime.py": "where a bundled resource lives, which changes no fact",
}


def _module(path: Path) -> str:
    parts = list(path.relative_to(PKG.parent).with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _file(module: str) -> Path | None:
    base = PKG.parent.joinpath(*module.split("."))
    for f in (base.with_suffix(".py"), base / "__init__.py"):
        if f.is_file():
            return f
    return None


def _imported(path: Path) -> set[Path]:
    """This package's modules `path` imports at module level."""
    me = _module(path)
    pkg = me if path.name == "__init__.py" else me.rsplit(".", 1)[0]
    out: set[Path] = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.ImportFrom):
            if node.level:
                parts = pkg.split(".")
                base = parts[: len(parts) - (node.level - 1)]
                mod = ".".join(base + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            if mod.startswith("dunneflow"):
                for alias in node.names:
                    found = _file(f"{mod}.{alias.name}") or _file(mod)
                    if found:
                        out.add(found)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("dunneflow") and (found := _file(alias.name)):
                    out.add(found)
    return out


def test_everything_the_core_imports_is_in_its_key_or_says_why_not():
    key = {p.resolve() for p in core_extraction_inputs() if p.suffix == ".py"}
    seen, todo = set(key), list(key)
    while todo:
        for found in _imported(todo.pop()):
            found = found.resolve()
            if found not in seen:
                seen.add(found)
                todo.append(found)
    uncovered = sorted(str(p.relative_to(PKG)) for p in seen - key)
    assert set(uncovered) <= set(NOT_EXTRACTION), (
        f"the core imports {sorted(set(uncovered) - set(NOT_EXTRACTION))} and its key does "
        "not cover them: a change there would leave every cached fact answering the old "
        "code (rules 12 and 95). Add each to `core_extraction_inputs`, or to NOT_EXTRACTION "
        "here with the reason it decides no fact."
    )


def test_the_walk_finds_what_rule_95_was_minted_from():
    """Rule 42: the guard must see the case. `ingest/literals.py` imports `sql.py` as
    `from .. import sql as sqlmod` -- a module imported by name from its package, which is
    the spelling a walk that only read `from ..x import y` would miss."""
    assert PKG / "sql.py" in _imported(PKG / "ingest" / "literals.py")
