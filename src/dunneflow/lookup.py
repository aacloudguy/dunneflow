"""Which routine did they mean — and **how** the answer was arrived at.

Out of `cli.py` because it stopped being the command line's business. `touches` and
`impact` shared it there, and `dunneflow mcp` is the third caller: a rule kept at a call
site rots as callers are added, so it moves to where they all pass (rule 51). Nothing here
prints; it returns what was found and what has to be said about it, and each surface says
it in its own words.

The defect it was minted from is in `Found`'s docstring below, and it is worth reading
before reusing any of this. `Found.exact` is not a convenience — a caller that takes
`matches` and drops it is reimplementing the silence the whole type exists to break.
"""

from __future__ import annotations

from dataclasses import dataclass

from .store import Store

_ROUTINE_COLUMNS = "id, name, qualname, module, file, line_start"


@dataclass(frozen=True, slots=True)
class Found:
    """What a routine search found, and **how it found it**.

    The rows alone were the defect. `find_routine` matched a qualname or a name exactly
    and, on no hit, fell back to a substring search -- silently -- so
    `touches --routine lictores.cli.app` answered about **`lictores.cli.apply.apply`** and
    reported a reach of 1. `app` is a Typer object rather than a routine, so nothing could
    match it and the fallback returned something plausible instead: rule 49's shape (a
    fallback that yields a plausible value has hidden the failure it was written for)
    inside rule 5's (never match on a bare common name), in the one command a reader would
    use to check an executable's reach.

    The fallback is kept, because a half-remembered name is a real way to arrive. What it
    may not do is wear an exact match's clothes, so `exact` travels with the rows and the
    caller says which it is holding.

    `total` is how many the search really matched, before the query's own cap and before
    `--limit` -- a count must say what it counts (rule 32), and *showing 1* over a search
    that matched forty is the same silence one level down.

    `module` is the true answer to the case that bit. A needle shaped `<module>.<tail>`
    whose head **is** a module in this map is not a misspelling; it is a name that belongs
    to something the map does not hold as a routine, and saying so is worth more than any
    number of near-misses. Read from `routines.module`, never guessed.
    """

    matches: list[dict]
    exact: bool
    total: int
    module: str
    module_file: str
    module_routines: int


def find_routine(store: Store, needle: str) -> Found:
    rows = store.query(
        f"SELECT {_ROUTINE_COLUMNS} FROM routines"
        " WHERE qualname = ? OR name = ? ORDER BY qualname LIMIT 25",
        (needle, needle),
    )
    if rows:
        # Counted, not `len(rows)`, for the same reason as the name search below: the
        # LIMIT has already decided that number. `touches --routine resolve --limit 2`
        # over four routines called `resolve` showed two and said nothing (rule 32).
        exact_total = store.query(
            "SELECT COUNT(*) AS n FROM routines WHERE qualname = ? OR name = ?",
            (needle, needle),
        )[0]["n"]
        return Found([dict(r) for r in rows], exact=True, total=exact_total,
                     module="", module_file="", module_routines=0)

    rows = store.query(
        f"SELECT {_ROUTINE_COLUMNS} FROM routines"
        " WHERE qualname LIKE ? ORDER BY qualname LIMIT 25",
        (f"%{needle}%",),
    )
    # Counted rather than inferred from `len(rows)`, which the LIMIT above has already
    # decided (rule 32). The two are equal until they are not, and that is the point.
    total = store.query(
        "SELECT COUNT(*) AS n FROM routines WHERE qualname LIKE ?", (f"%{needle}%",),
    )[0]["n"]

    module, module_file, module_routines = "", "", 0
    if "." in needle:
        head = needle.rsplit(".", 1)[0]
        # **`files`, not `routines`** -- and that is the whole of why this fires. A package
        # module declares no routines of its own, so asking `routines.module` says "not a
        # module here" about `lictores.cli`, which is a file this analysis read. `files`
        # is where a module is recorded as having been read at all; how many routines it
        # holds is the *next* question and often the answer (rule 32).
        seen = store.query("SELECT path FROM files WHERE module = ? LIMIT 1", (head,))
        if seen:
            module, module_file = head, str(seen[0]["path"])
            # `<module>` is excluded, and that is not tidiness. It is the module's own
            # top-level code wearing a routine's shape -- nobody declared it -- so
            # counting it would answer *"declares 1 routine"* about a package `__init__`
            # holding a docstring and two assignments, which is the opposite of the
            # sentence's job. `<module>` is answered as what it is everywhere else.
            module_routines = store.query(
                "SELECT COUNT(*) AS n FROM routines WHERE module = ? AND name != ?",
                (head, "<module>"),
            )[0]["n"]

    return Found([dict(r) for r in rows], exact=False, total=total,
                 module=module, module_file=module_file,
                 module_routines=module_routines)


def search_said(needle: str, found: Found, shown: int) -> list[str]:
    """What to say above rows that are not what was asked for. Empty for an exact match.

    One place, because `touches` and `impact` share `find_routine` and shared exactly
    this defect (rule 51). Printed to **stdout** with the answer rather than to stderr:
    a reader who pipes the answer to a file must not lose the sentence saying it is a
    name search.
    """
    if found.exact:
        # An exact match needs no caveat -- but a *bounded* one does. Two answers where
        # the reader asked about a name four routines share is not four answers.
        if shown < found.total:
            return [f"{found.total:,} routines are named {needle!r}; showing {shown:,}."]
        return []
    said = [f"no routine is named {needle!r}."]
    if found.module:
        # The measured statement, and the reason this is worth a line of its own: the
        # needle names a real module and something in it that is not a routine -- a Typer
        # app, a class attribute, a module-level object. That is an answer; the
        # near-misses below are not.
        tail = needle.rsplit(".", 1)[1]
        holds = (f"declares {found.module_routines:,} routine"
                 f"{'' if found.module_routines == 1 else 's'}"
                 if found.module_routines else "declares no routines at all")
        said.append(f"  {found.module} is a module here — {found.module_file} — and "
                    f"{holds}; nothing in it is named {tail!r}.")
    if found.matches:
        more = f", showing {shown:,}" if shown < found.total else ""
        said.append(f"  {found.total:,} routine name"
                    f"{' contains' if found.total == 1 else 's contain'} it{more} — "
                    f"a name search, not the routine you asked for:")
    return said
