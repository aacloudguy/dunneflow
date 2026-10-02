"""A count and its noun, agreeing.

`"1 routines"` is a small defect and an easy one to ship, because every test fixture has
more than one of everything. Lifted out of `web/threads.py`, where it was the only helper,
when the retake found `` `note` is called 1 times `` in the worklist and *1 terms carried
forward* on the command line (BACKLOG 28). One door, so the next count takes it rather
than a fresh inline `'s' if n != 1` that forgets the verb (rule 51).
"""

from __future__ import annotations


def plural(n: int, one: str, many: str = "") -> str:
    """`1 call`, `2 calls`, `1,047 analyses` -- the number formatted, the noun agreeing."""
    return f"{n:,} {one}" if n == 1 else f"{n:,} {many or one + 's'}"


def are(n: int) -> str:
    """The verb that agrees with `n` of something: *is* or *are*."""
    return "is" if n == 1 else "are"
