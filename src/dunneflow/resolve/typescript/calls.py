"""Which definition a TypeScript call meant: `resolve/supplied.py`, asked for TypeScript.

The lookup lived here until 2026-11-01 and moved when a second reader came to supply
edges. It names no language there, and this module keeps its address because code, tests
and the development record cite it (rule 30). Everything that was argued here, about
locations versus ids, the four answers, and why a bare name is never matched, is now in
that module's docstring.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .. import supplied
from ..contract import CallRow, Decision
from ..supplied import Report

LANG = "typescript"

__all__ = ["LANG", "Report", "resolve"]


def resolve(store: Any, lang: str, rows: Sequence[CallRow]) -> list[Decision]:
    """`supplied.resolve` for TypeScript. `lang` is the seam's, and it is TypeScript's."""
    return supplied.resolve(store, lang, rows)


def __getattr__(name: str) -> Report:
    # `LAST` was a module global that the resolver rebound on every run. It is now one slot
    # of `supplied.REPORTS`, read when it is asked for, because a re-exported global would
    # be the value at import time and never the last run's (rule 56's shape).
    if name == "LAST":
        return supplied.REPORTS.get(LANG) or Report(lang=LANG)
    raise AttributeError(name)
