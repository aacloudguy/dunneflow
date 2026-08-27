"""The Form lane: what the code does about names, counted.

Two properties matter more than any individual convention.

**A claim must reproduce.** Every convention ships the SQL that produced it, and that
query has to return exactly the exceptions listed beside it -- not approximately, not
the population it was drawn from. Three of the first twenty-seven did not: a glob
matched `iso_utc_now` as a routine beginning with `is`, and a house-prefix query counted
its numerator over multi-segment names while its denominator counted all of them.

**A convention must not be a coincidence.** Thousands of affix/property pairs are tested
at once, so six-of-six agreements happen by themselves. "A class ending in `Provenance`
is a dataclass, 7 of 7" survived precision, sample size and lift, and means nothing when
two classes in five are dataclasses anyway.
"""

from __future__ import annotations

from pathlib import Path

from dunneflow.resolve.naming import (
    _beats_coincidence,
    case_style,
    measure,
    mine_privacy_convention,
)
from dunneflow.store import Store
from dunneflow.walk import analyze_tree

PROGRAM = '''
"""A program with conventions and with exceptions to them."""
import os


class WidgetError(Exception):
    pass


class GadgetError(ValueError):
    pass


class SprocketError:
    """Named like an exception and is not one. This is the finding."""


class PlainThing:
    pass


def load_widget(path: str) -> str:
    return os.environ["WIDGET_HOME"] + path


def save_widget(path: str) -> None:
    os.environ["WIDGET_CACHE"] = path


def is_ready(x: int) -> bool:
    return x > 0


def is_open(x: int) -> bool:
    return x > 1


def is_valid(x: int) -> bool:
    return x > 2


def is_stale(x: int) -> bool:
    return x > 3


def is_pinned(x: int) -> bool:
    return x > 4


def isolate_widget(x: int) -> str:
    """Begins with `iso`, not with `is`. A glob that ignores the separator eats it."""
    return str(x)


def CamelRoutine() -> None:
    """The one exception to snake_case, and it must appear as one."""
'''


def _store(tmp_path: Path) -> Store:
    (tmp_path / "prog.py").write_text(PROGRAM, encoding="utf-8")
    store = Store(tmp_path / "graph.db")
    analyze_tree(tmp_path, store)
    return store


# -- case style -------------------------------------------------------------- #


def test_case_style_reads_the_common_shapes() -> None:
    assert case_style("load_widget") == "snake_case"
    assert case_style("WidgetError") == "PascalCase"
    assert case_style("loadWidget") == "camelCase"
    assert case_style("WIDGET_HOME") == "SCREAMING_SNAKE"
    assert case_style("load-widget") == "kebab-case"


def test_a_single_lowercase_word_counts_with_the_majority() -> None:
    """Ambiguous by construction; counting it as an exception to everything is worse."""
    assert case_style("widget") == "snake_case"


# -- reproducibility --------------------------------------------------------- #


def test_every_query_returns_exactly_the_exceptions_listed(tmp_path: Path) -> None:
    """Rule 13: a claim proves itself with its query, or it is an assertion.

    A query that returns something other than what is printed beside it is worse than
    no query at all, because it invites a reader to check and then misleads them.
    """
    store = _store(tmp_path)
    m = measure(store)
    assert m.conventions, "nothing was measured over a program with clear conventions"
    for c in m.conventions:
        rows = store.query(c.sql)          # raises if the SQL is malformed
        assert {str(r[0]) for r in rows} == {e.name for e in c.exceptions}, (
            f"the query for {c.claim!r} does not reproduce its own exception list"
        )
    store.close()


def test_exceptions_are_complete_not_sampled(tmp_path: Path) -> None:
    store = _store(tmp_path)
    m = measure(store)
    for c in m.conventions:
        assert len(c.exceptions) == c.total - c.holds, (
            f"{c.claim!r} lists {len(c.exceptions)} of {c.total - c.holds} exceptions"
        )
    store.close()


def test_the_exception_is_named(tmp_path: Path) -> None:
    store = _store(tmp_path)
    snake = [c for c in measure(store).conventions
             if c.claim.startswith("Routines are named")]
    assert snake, "no case convention was found for routines"
    assert [e.name for e in snake[0].exceptions] == ["CamelRoutine"]
    store.close()


def test_synthetic_names_are_not_counted_as_names(tmp_path: Path) -> None:
    """`<module>` is a routine DunneFlow invents, not a name anyone chose.

    Counting them made a convention that holds in every real case read as 92%.
    """
    store = _store(tmp_path)
    for c in measure(store).conventions:
        assert not any(e.name.startswith("<") for e in c.exceptions)
    store.close()


def test_an_affix_glob_respects_the_separator(tmp_path: Path) -> None:
    """`is*` matches `isolate_widget`, which begins with `iso`."""
    store = _store(tmp_path)
    predicates = [c for c in measure(store).conventions
                  if "beginning with `is`" in c.claim]
    if predicates:
        assert "isolate_widget" not in {e.name for e in predicates[0].exceptions}
        assert "is_*" in predicates[0].sql
    store.close()


# -- coincidence ------------------------------------------------------------- #


def test_a_small_run_against_a_common_property_is_coincidence() -> None:
    """Seven of seven, where two in five have the property anyway, means nothing."""
    assert not _beats_coincidence(holds=7, total=7, base_rate=0.40, tests=7500)


def test_a_real_convention_survives_the_correction() -> None:
    """372 of 375 `*Error` classes subclassing an exception is not an accident."""
    assert _beats_coincidence(holds=372, total=375, base_rate=0.33, tests=7500)
    assert _beats_coincidence(holds=97, total=99, base_rate=0.037, tests=7500)


def test_a_universal_property_explains_nothing() -> None:
    assert not _beats_coincidence(holds=10, total=10, base_rate=1.0, tests=1)


# -- no tautologies ---------------------------------------------------------- #


def test_privacy_is_measured_by_leakage_not_by_underscores(tmp_path: Path) -> None:
    """Counting how many private routines start with `_` measures the extractor.

    That is how `visibility` is derived in the first place, so it can only ever come
    out at 100%. The measurable claim is whether the boundary is respected.
    """
    store = _store(tmp_path)
    for c in mine_privacy_convention(store):
        assert "called only from its own module" in c.claim
        assert "underscore" not in c.claim.lower()
    store.close()
