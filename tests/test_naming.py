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
    STYLE_PREDICATE,
    _beats_coincidence,
    case_style,
    measure,
    mine_privacy_convention,
    resolve_styles,
    style_predicate,
    styles_in,
    styles_of,
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


# A second program, because the one above produces **no affix convention at all**: five
# `is_*` routines out of nine do not survive the coincidence correction, which is rule 14
# working exactly as intended. That is worth knowing on its own --
# `test_an_affix_glob_respects_the_separator` guards its assertion with `if predicates:`
# and has therefore never once run.
#
# So this one is shaped to produce one: eight `check_*` routines that all return a boolean,
# against twenty-seven that do not, which is high precision over a *low* base rate. Both
# terms are needed. Seven of seven against a background where a third of routines have the
# property anyway is the `Provenance` coincidence rule 14 was written from, and it is
# correctly rejected.
AFFIX_PROGRAM = (
    '"""One clear affix convention against a background that lacks the property."""\n\n'
    + "\n\n".join(
        f"def check_{n}(x: int) -> bool:\n    return x > {i}"
        for i, n in enumerate(
            ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta"]))
    + "\n\n"
    + "\n\n".join(
        f"def render_{n}(x: int) -> str:\n    return str(x)"
        for n in ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
                  "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
                  "seventeen", "eighteen", "nineteen", "twenty", "hazel", "willow",
                  "cedar", "maple", "rowan", "alder", "aspen"])
)


# The same shape over classes rather than routines, and it exists because the routine
# fixture cannot see a whole family of defects: `noun` is "routine" there, and "routines"
# is what `f"{noun}s"` produces, so a bug in how a population names itself is invisible.
# Eight classes ending in `Error` that really are exceptions, against twenty-seven that
# are neither -- high precision over a low base rate, which is what rule 14 requires.
CLASS_AFFIX_PROGRAM = (
    '"""Classes with one clear suffix convention."""\n\n'
    + "\n\n".join(
        f"class {n}Error(Exception):\n    pass"
        for n in ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta"])
    + "\n\n"
    + "\n\n".join(
        f"class {n}Panel:\n    pass"
        for n in ["One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
                  "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
                  "Seventeen", "Eighteen", "Nineteen", "Twenty", "Hazel", "Willow",
                  "Cedar", "Maple", "Rowan", "Alder", "Aspen"])
)


def _class_affix_store(tmp_path: Path) -> Store:
    (tmp_path / "classes.py").write_text(CLASS_AFFIX_PROGRAM, encoding="utf-8")
    store = Store(tmp_path / "classes.db")
    analyze_tree(tmp_path, store)
    return store


def _affix_store(tmp_path: Path) -> Store:
    (tmp_path / "affix.py").write_text(AFFIX_PROGRAM, encoding="utf-8")
    store = Store(tmp_path / "affix.db")
    analyze_tree(tmp_path, store)
    return store


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


def test_the_glob_and_the_query_name_the_same_population(tmp_path: Path) -> None:
    """The membership test and the evidence must be one string, not two that agree today.

    `glob` exists so something other than a person can ask "is this name one of these?" --
    the inspector says a routine shares a convention with others, and neither `claim`, which
    is a sentence, nor `sql`, which reproduces the *exceptions*, can answer that.

    The risk it introduces is drift: two derivations of one population, correct on the day
    they were written and silently disagreeing after the next edit. So the glob is the same
    string the exceptions query is built from, and this asserts it -- rule 13 applied to a
    second way of naming the same set. The alternative, deriving the affix back out of the
    claim sentence, would be parsing prose to recover something the code had already
    computed and thrown away.
    """
    store = _affix_store(tmp_path)
    m = measure(store)
    affixes = [c for c in m.conventions if c.kind == "AFFIX"]
    assert affixes, "no affix convention was measured; this test is blind"
    for c in affixes:
        assert c.glob, f"an affix convention with no glob: {c.claim!r}"
        assert f"'{c.glob}'" in c.sql, (
            f"the glob {c.glob!r} is not the one {c.claim!r} counts with -- two "
            "derivations of one population, free to disagree after the next edit"
        )
    store.close()


def test_a_population_names_itself_in_the_plural(tmp_path: Path) -> None:
    """`population` is prose the dashboard prints as a heading, so it has to be English.

    `_affix_conventions` takes both `noun` and `plural` -- "class" and "classes" -- and
    built the population with `f"{noun}s"`, so every class affix convention on a real
    program was headed **classs ending in `Error`**. Invisible for as long as it was, because
    the naming page had never been ported and nothing printed the string.
    """
    store = _class_affix_store(tmp_path)
    populations = [c.population for c in measure(store).conventions if c.kind == "AFFIX"]
    assert populations, "no class affix convention was measured; this test is blind"
    for pop in populations:
        assert "sss" not in pop and not pop.startswith("classs"), (
            f"a population that is not English: {pop!r} -- it is printed as a heading"
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


# -- one name, several true answers (rule 100) -------------------------------- #


def test_a_one_token_name_satisfies_every_style_it_could_be_written_in() -> None:
    """`widget` is snake_case, camelCase and kebab-case at once, and all three are true.

    `case_style` has to answer with one of them and picked by the order its tests were
    written in -- Python's order, because Python was the only language. Measured on
    DunneNote before this existed: 146 routines and 335 parameters counted as `snake_case`
    exceptions to conventions they keep perfectly.
    """
    assert styles_of("widget") == {"snake_case", "camelCase", "kebab-case"}
    assert styles_of("DDL") == {"SCREAMING_SNAKE", "PascalCase"}
    # And a name that settles the question settles it: one answer, not three.
    assert styles_of("load_widget") == {"snake_case"}
    assert styles_of("loadWidget") == {"camelCase"}
    assert styles_of("load-widget") == {"kebab-case"}
    assert styles_of("WIDGET_HOME") == {"SCREAMING_SNAKE"}


def test_a_leading_underscore_still_reads_as_snake_case() -> None:
    """The regexes are reused exactly as written, and this is why.

    `SNAKE` is `[a-z0-9_]+`, which tolerates the underscore that marks a routine private.
    Decomposing it into "lowercase words joined by underscores" -- which is what a reader
    writing this from scratch would do -- drops `_helper` to `other`, and Mensores has
    1,811 of those in one population: enough to outvote its 1,611 unambiguous names and
    report a program with a 99.97% convention as having none.
    """
    assert styles_of("_helper") == {"snake_case"}
    assert styles_of("_PRIVATE_HOME") == {"SCREAMING_SNAKE"}
    assert styles_of("do_GET") == {"other"}


def test_an_ambiguous_name_is_counted_with_its_own_populations_majority() -> None:
    """The docstring's promise, kept: the population decides, not the source layout."""
    camel = [styles_of(n) for n in ("loadWidget", "saveWidget", "main", "line")]
    styles, firm = resolve_styles(camel)
    assert firm, "two unambiguous camelCase names is evidence"
    assert styles == ["camelCase"] * 4, "the one-token names went to the majority"

    snake = [styles_of(n) for n in ("load_widget", "save_widget", "main", "line")]
    styles, firm = resolve_styles(snake)
    assert styles == ["snake_case"] * 4, "the same two names, the other way, from one rule"


def test_other_never_votes_on_what_the_convention_is() -> None:
    """It is the absence of a style rather than one of them.

    Letting it into the order made Mensores' unreadable names the plurality and reported
    `other` as the convention -- a population's dominant style being "no style".
    """
    sets = [styles_of(n) for n in ("do_GET", "do_POST", "visit_Call", "load_widget", "main")]
    styles, firm = resolve_styles(sets)
    assert firm
    assert styles[-2:] == ["snake_case", "snake_case"], (
        "three unreadable names outvoted the one that could be read"
    )


def test_a_population_with_nothing_unambiguous_says_so() -> None:
    """Every name one token, so nothing in the population chose: the tie went to the order.

    The count is still right -- they are all spelled the same way -- but *which* convention
    it is called was decided by this tool and not by the program, and a claim resting on
    that has to be able to say so.
    """
    styles, firm = resolve_styles([styles_of(n) for n in ("alpha", "beta", "gamma")])
    assert not firm, "nothing here was unambiguous, and the caller has to know"
    assert styles == ["snake_case"] * 3, "and the stated order settled it"


# -- a dotted name is a list of names ----------------------------------------- #


def test_a_dotted_name_is_judged_segment_by_segment() -> None:
    """Substituting `.` for `_` asks the question of a string that was never written.

    `apps.desktop.lib.calendar-nav` becomes `apps_desktop_lib_calendar-nav`, which holds
    both separators and so matches nothing. **387 of DunneNote's 389 unreadable module
    names contain a dash**, and a tree whose files are named in kebab-case throughout was
    reported as having no module convention at all.
    """
    assert styles_in("apps.desktop.lib.calendar-nav", dotted=True) == {"kebab-case"}
    assert "snake_case" in styles_in("mensores.cli.call_args", dotted=True)
    # And a path whose segments genuinely disagree has no single answer, which is the
    # honest result rather than a failure of the judge.
    assert styles_in("packages.api-types.src.AddColumnRequest", dotted=True) == {"other"}
    # Undotted, the dots are just characters and none of this applies.
    assert styles_in("apps.desktop", dotted=False) == {"other"}


# -- the query beside a claim (rule 13), for every style ---------------------- #


def test_every_style_predicate_agrees_with_the_judge_that_produced_it() -> None:
    """Rule 13 at the level of the predicate, rather than of one corpus that exercised two.

    `test_every_query_returns_exactly_the_exceptions_listed` proves the claims a *fixture*
    happens to produce, and a fixture only ever reaches the styles it is written in --
    `kebab-case`'s predicate went years without a population and was wrong when it got one:
    it required a dash, so the 14 one-word commands of a 16-command kebab-case program were
    returned as exceptions to a convention that holds in all 16.

    This asks every style about every name directly, in SQLite, so a predicate cannot be
    right only where somebody thought to look.
    """
    import sqlite3

    names = [
        "widget", "load_widget", "loadWidget", "load-widget", "LoadWidget",
        "WIDGET_HOME", "DDL", "_helper", "do_GET", "visit_Call", "a1", "X9",
    ]
    dotted_names = [
        "apps.desktop", "apps.desktop.calendar-nav", "mensores.cli.call_args",
        "packages.api-types.src.AddColumnRequest", "Foo.Bar", "fooBar.bazQux",
        "A.B", "ONE.TWO_THREE",
    ]
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE n (name TEXT)")
    for style in STYLE_PREDICATE:
        for label, sample, dotted in (("plain", names, False),
                                      ("dotted", dotted_names, True)):
            conn.execute("DELETE FROM n")
            conn.executemany("INSERT INTO n VALUES (?)", [(x,) for x in sample])
            sql = f"SELECT name FROM n WHERE {style_predicate(style, 'name', dotted)}"
            returned = {str(r[0]) for r in conn.execute(sql)}
            expected = {x for x in sample if style not in styles_in(x, dotted)}
            assert returned == expected, (
                f"the {label} predicate for {style} disagrees with the judge: "
                f"it returns {sorted(returned)} where the judge refuses {sorted(expected)}"
            )
    conn.close()


def test_a_leading_underscore_allowed_is_allowed_by_the_judge_and_its_query_alike() -> None:
    """The reader's Setting, answered in both places a claim is made.

    `_Handler` is strictly not PascalCase and is the commonest spelling of a private class,
    so whether it counts is a Setting (Tom, 2026-10-02). With it on, the judge reads the
    name without its leading underscores, and the SQL beside the claim must return exactly
    the names the judge refuses (rule 13). Dunders stay what they are.
    """
    import sqlite3

    names = ["_Handler", "__Private", "Handler", "_handler", "_loadWidget", "__init__",
             "_", "__", "_WIDGET_HOME", "Field_", "_Field_"]
    assert "PascalCase" not in styles_of("_Handler")
    assert "PascalCase" in styles_of("_Handler", private_prefix=True)
    assert "snake_case" in styles_of("__init__", private_prefix=True)
    assert styles_of("__", private_prefix=True) == styles_of("__")

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE n (name TEXT)")
    conn.executemany("INSERT INTO n VALUES (?)", [(x,) for x in names])
    for style in STYLE_PREDICATE:
        sql = (f"SELECT name FROM n WHERE "
               f"{style_predicate(style, 'name', False, private_prefix=True)}")
        returned = {str(r[0]) for r in conn.execute(sql)}
        expected = {x for x in names
                    if style not in styles_in(x, False, private_prefix=True)}
        assert returned == expected, (
            f"with a leading underscore allowed, the {style} query returns "
            f"{sorted(returned)} where the judge refuses {sorted(expected)}"
        )
    conn.close()
