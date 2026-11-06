"""What the code actually does about names, counted.

The Form lane of the naming standard. Everything here is measured over `graph.db` and
nothing is guessed: each convention carries the population it was counted over, how many
cases hold, the SQL that reproduces it, and **every exception** -- never a sample. The
exceptions are the product. `*Error` holding in 372 of 375 cases is mildly interesting;
the three classes that break it are the finding.

Conventions are *discovered* rather than listed. The affixes are mined from the
identifiers themselves and tested against properties the graph already holds, so this
works on a codebase nobody has ever described -- which is the normal case.

Two disciplines are load-bearing:

* **Never report a tautology.** A leading underscore marking a routine private is not a
  measurement, because that is how `visibility` is derived in the first place. The
  measurable claim beside it -- that a private routine is never called from another
  module -- is real, and its exceptions are worth seeing.
* **Below threshold is not dropped.** A population with no dominant convention is
  reported as a gap. A silent filter would let a reader mistake a slice for the whole.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from ..detectors import load_rules
from ..store import Store
from . import languages

# A convention has to be worth stating. Both numbers are printed wherever a convention
# is, so a reader can disagree with them.
MIN_POPULATION = 8
MIN_PREVALENCE = 0.85
MIN_AFFIX_COUNT = 5
MIN_AFFIX_PRECISION = 0.90
# A family-wise error rate, because thousands of affix/property pairs are tested at once.
COINCIDENCE_THRESHOLD = 0.01

SNAKE = re.compile(r"[a-z0-9_]+")
SCREAMING = re.compile(r"[A-Z0-9_]+")
PASCAL = re.compile(r"[A-Z][A-Za-z0-9]*")
CAMEL = re.compile(r"[a-z][A-Za-z0-9]*")
KEBAB = re.compile(r"[a-z0-9]+(-[a-z0-9]+)+")
DUNDER = re.compile(r"__.*__")

# One token, no separator and no internal case change. `widget` is *equally* snake_case,
# camelCase and kebab-case; `DDL` is equally SCREAMING_SNAKE and PascalCase. The five
# regexes above cannot say so, because each returns a yes or a no about its own style and
# the ambiguity lives between them.
ONE_LOWER = re.compile(r"[a-z][a-z0-9]*")
ONE_UPPER = re.compile(r"[A-Z][A-Z0-9]*")

STYLE_NAMES = {
    "snake_case": "snake_case",
    "SCREAMING_SNAKE": "SCREAMING_SNAKE_CASE",
    "PascalCase": "PascalCase",
    "camelCase": "camelCase",
    "kebab-case": "kebab-case",
}

# The order to fall back on when a population offers **no** unambiguous name to learn from.
#
# It is the tie-break this tool has always applied, written down: while it was implicit in
# the order of five `if`s nobody could see it, disagree with it, or measure what it cost --
# and what it cost was one language's preference imposed on every other (rule 100). It is
# Python's, because Python was the only language when the tests were written.
#
# `snake_case` leads rather than `kebab-case`, which is where the `if`s began, because a
# one-token name reaches this order and a kebab-case one never did: `KEBAB` requires a dash,
# so `widget` fell past it to `SNAKE`. The order here reproduces that answer rather than the
# source layout that produced it.
PREFERENCE = ("snake_case", "SCREAMING_SNAKE", "PascalCase", "camelCase", "kebab-case")


def styles_of(name: str, private_prefix: bool = False) -> set[str]:
    """**Every** spelling convention a name satisfies, not the first one tested.

    `case_style` below has to return one answer, and for a one-token name several are
    true at once. Which one it returned was decided by the order the tests happened to be
    written in -- and that order is the first language's preference, invisibly (rule 100).
    Measured: 146 of DunneNote's routines are single lowercase words, counted as
    `snake_case` exceptions to a `camelCase` convention they keep perfectly, and its 519
    parameters were reported as having **no convention at all** where 515 are camelCase.

    The five regexes are used exactly as they were written, which is load-bearing rather
    than lazy: `SNAKE` is `[a-z0-9_]+` and so tolerates the leading underscore that marks a
    routine private. Decomposing it into "lowercase words joined by underscores" dropped
    `_helper` to `other` and cost Mensores 1,811 false exceptions in one population.
    """
    if private_prefix and name.startswith("_") and not DUNDER.fullmatch(name):
        # **A leading underscore read as a privacy mark rather than part of the spelling**,
        # when the reader has said so (`private_prefix`). Strictly it is a violation of
        # PascalCase and camelCase -- `_Handler` does not begin with a capital -- and it is
        # also the commonest way a codebase marks a class private, so it is a Setting
        # rather than a ruling (design rule 2; Tom, 2026-10-02). `SNAKE` already tolerates
        # it; this makes the other styles agree when asked. A name that is all underscores
        # is left as it is, because stripping it would leave nothing to judge and turn a
        # name the default reading calls snake_case into none at all.
        name = name.lstrip("_") or name
    if not name:
        return {"other"}
    out: set[str] = set()
    if KEBAB.fullmatch(name):
        out.add("kebab-case")
    if SNAKE.fullmatch(name):
        out.add("snake_case")
    if SCREAMING.fullmatch(name):
        out.add("SCREAMING_SNAKE")
    if PASCAL.fullmatch(name):
        out.add("PascalCase")
    if CAMEL.fullmatch(name):
        out.add("camelCase")
    if ONE_LOWER.fullmatch(name):
        out |= {"snake_case", "camelCase", "kebab-case"}
    if ONE_UPPER.fullmatch(name):
        out |= {"SCREAMING_SNAKE", "PascalCase"}
    return out or {"other"}


def styles_in(name: str, dotted: bool, private_prefix: bool = False) -> set[str]:
    """The styles a name satisfies, judging a dotted path **segment by segment**.

    A dotted name used to be judged by substituting `.` for `_` and asking the same
    question. That is exactly right for a tree whose segments are snake_case and silently
    wrong for one whose segments are not: `apps.desktop.lib.calendar.calendar-nav` becomes
    `apps_desktop_lib_calendar_calendar-nav`, which holds both separators and so matches no
    style at all. **387 of DunneNote's 389 unreadable module names contain a dash**, and the
    tree's real convention -- kebab-case filenames -- was reported as no convention.

    A path is a list of names rather than one name with punctuation in it, so what it
    satisfies is what *all* of its segments satisfy. The 210 that still read `other` are
    the honest ones: `packages.api-types.src.AddColumnRequest` spells one segment in kebab
    and the next in Pascal, and no single answer is true of it.
    """
    if not dotted:
        return styles_of(name, private_prefix)
    # A dotted path is judged without the allowance: its populations are module paths,
    # whose segments are snake_case and tolerate the underscore already, and a per-segment
    # strip has no single SQL spelling to stand beside the claim (rule 13).
    segments = [s for s in name.split(".") if s]
    if not segments:
        return {"other"}
    out = styles_of(segments[0])
    for segment in segments[1:]:
        out &= styles_of(segment)
    return out or {"other"}


def case_style(name: str) -> str:
    """Which spelling convention a name follows, when exactly one answer is wanted.

    A single lowercase word is counted as snake_case. It is equally camelCase and equally
    kebab-case, and the ambiguity is real; counting it with the majority is what keeps a
    one-word name from appearing as an exception to every convention at once.

    Derived from `styles_of` through the stated `PREFERENCE` rather than asking the five
    regexes again, so that what `kebab-case` means is decided in one place (rule 51). This
    is the answer for a caller holding **one** name and no population to learn from;
    `resolve_styles` is the answer for a caller holding a population, and it is better,
    because a population can say which of the true answers its author meant.
    """
    got = styles_of(name)
    if got == {"other"}:
        return "other"
    return next(style for style in PREFERENCE if style in got)


def resolve_styles(sets: list[set[str]]) -> tuple[list[str], bool]:
    """One style per name, with the ambiguous ones counted *with the majority*.

    Which is what `case_style`'s docstring has promised since it was written, and what it
    has never done: it resolved every tie the same way whatever the population looked like.
    Here the names that are **not** ambiguous vote first, and each ambiguous name then goes
    to the most popular style it actually satisfies. So `main` lands on `camelCase` in a
    TypeScript program and on `snake_case` in a Python one, from the same rule.

    `other` never votes. It is the absence of a style rather than one of them, and letting
    it into the order made Mensores' 1,811 private routines outvote its 1,611 unambiguous
    snake_case ones and reported the program as having no convention.

    Returns the styles and **whether anything unambiguous was found**, because a population
    that is ambiguous all the way down was settled by `PREFERENCE` rather than by evidence,
    and a claim resting on that has to be able to say so.
    """
    firm: Counter[str] = Counter()
    for got in sets:
        if len(got) == 1:
            only = next(iter(got))
            if only != "other":
                firm[only] += 1
    order = [style for style, _ in firm.most_common()] or list(PREFERENCE)
    out: list[str] = []
    for got in sets:
        pick = next((style for style in order if style in got), None)
        if pick is None:
            # Satisfies nothing the population voted for: fall back to the stated order,
            # and only then to `other`.
            pick = next((style for style in PREFERENCE if style in got), "other")
        out.append(pick)
    return out, bool(firm)


@dataclass(slots=True)
class Exception_:
    """One case that breaks a convention. Where it is, so it can be looked at."""

    name: str
    where: str = ""


@dataclass(slots=True)
class Convention:
    """One measured claim about how this program names things."""

    kind: str            # CASE | AFFIX | LEAKAGE | HOUSE_PREFIX
    claim: str           # a sentence a person would say
    population: str      # what was counted over
    total: int
    holds: int
    # Which language this convention is about, and `""` for *the whole map*. Empty is the
    # answer for a map holding one language -- which has no language axis to state -- and
    # for the kinds that are deliberately not split. A field rather than a word parsed back
    # out of `population`: rule 30, and `Entrypoint.declared` paid for it one module over.
    lang: str = ""
    exceptions: list[Exception_] = field(default_factory=list)
    sql: str = ""        # reproduces the exceptions, via `dunneflow query`
    note: str = ""
    # The population as a **glob**, so something other than a person can ask whether a
    # given name is in it.
    #
    # `claim` is a sentence and `sql` reproduces the *exceptions*; neither can answer "is
    # `write_spec_seal_atomic` one of these?", which is exactly what the inspector needs
    # to say a routine shares a convention with others. Deriving it back out of the
    # sentence would be parsing prose to recover something the code already computed --
    # the failure rule 12 names in the other direction.
    #
    # It is the *same* string the exceptions query is built from, deliberately, so the
    # membership test and the evidence cannot drift apart. Rule 13's discipline: the
    # query beside a claim must be the query that produced it.
    #
    # Empty for the conventions that have no glob to give -- a case convention is a
    # property of every name in a population, not a subset of it -- and that is a real
    # absence rather than a missing value.
    glob: str = ""

    @property
    def prevalence(self) -> float:
        return self.holds / self.total if self.total else 0.0

    def rating(self) -> str:
        """Sonar-shaped, because a percentage implies a precision this does not have."""
        p = self.prevalence
        if p >= 0.999:
            return "A"
        if p >= 0.98:
            return "B"
        if p >= 0.95:
            return "C"
        return "D" if p >= 0.90 else "E"


@dataclass(slots=True)
class Gap:
    """A population with no convention anyone could call dominant."""

    population: str
    lang: str
    total: int
    spread: list[tuple[str, int]]


@dataclass(slots=True)
class NamingMeasurement:
    conventions: list[Convention] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    thresholds: dict[str, float] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Populations
# --------------------------------------------------------------------------- #

# Each population: a label, the SQL that lists (name, where), the SQL fragment that selects
# it again for an exception query, and the predicate that narrows either one to a single
# language. Kept as text so every claim is reproducible through `dunneflow query` rather
# than only inside this process.
#
# **The language predicate is written out per population rather than derived**, because the
# route from a name to a file is different for each and three of them have no `file` column
# to derive anything from: a parameter reaches one through its routine, and a module *is* a
# row of `files`. A single clever expression would have to be wrong somewhere, and the
# reader who checks a claim runs the string that is printed beside it.
#
# Always through `files.lang` and never `routines.lang` or `structures.lang`, though both
# exist: which language a *name* belongs to is a fact about the file it was written in, and
# two spellings of one question is what rule 51 is about.
# A name a macro wrote (`name_by`) is out of every routine population: this is the naming
# standard people keep, and `zzAppendMemberGetPrev` 12,372 times over is nobody's choice.
POPULATIONS: dict[str, tuple[str, str, str, str]] = {
    "routines": (
        "routines",
        "SELECT name, file || ':' || line_start AS where_ FROM routines"
        " WHERE is_nested = 0 AND name_by = '' AND name NOT GLOB '__*__' AND name NOT GLOB '<*>'",
        "FROM routines WHERE is_nested = 0 AND name_by = '' AND name NOT GLOB '__*__'"
        " AND name NOT GLOB '<*>'",
        "file IN (SELECT path FROM files WHERE lang = '{lang}')",
    ),
    "classes": (
        "classes",
        # `WHERE 1` so that every listing query in this table ends in a `WHERE`, which is
        # what lets the language clause always be an `AND`. The exception clause beside it
        # has carried one since it was written, for the same reason.
        "SELECT name, file || ':' || line AS where_ FROM classes WHERE 1",
        "FROM classes WHERE 1",
        "file IN (SELECT path FROM files WHERE lang = '{lang}')",
    ),
    "data structures": (
        "structures",
        "SELECT name, file || ':' || line AS where_ FROM structures WHERE 1",
        "FROM structures WHERE 1",
        "file IN (SELECT path FROM files WHERE lang = '{lang}')",
    ),
    "modules": (
        "modules",
        "SELECT DISTINCT module AS name, path AS where_ FROM files WHERE module <> ''",
        "FROM files WHERE module <> ''",
        "lang = '{lang}'",
    ),  # dotted -- see DOTTED below
    "parameters": (
        "params",
        "SELECT DISTINCT name, '' AS where_ FROM params WHERE name NOT IN ('self', 'cls')",
        "FROM params WHERE name NOT IN ('self', 'cls')",
        "routine_id IN (SELECT id FROM routines WHERE file IN"
        " (SELECT path FROM files WHERE lang = '{lang}'))",
    ),
    "database tables": (
        "db_tables",
        "SELECT DISTINCT tbl AS name, file AS where_ FROM sql_ops WHERE tbl <> ''",
        "FROM sql_ops WHERE tbl <> ''",
        "file IN (SELECT path FROM files WHERE lang = '{lang}')",
    ),
    "commands": (
        "entrypoints",
        "SELECT DISTINCT name, module AS where_ FROM entrypoints WHERE kind = 'CLI'",
        "FROM entrypoints WHERE kind = 'CLI'",
        # **The routine it starts, and only then the file that declares it.** A command is
        # the one population here whose declaring file need not be source at all: DunneFlow
        # names `dunneflow` in `pyproject.toml`, which no reader claims and which therefore
        # has no row in `files`. Scoped by its own file it belongs to no language and
        # vanishes from the split -- 15 commands where the map holds 16, a denominator
        # quietly losing a row (rule 32). What language a command is named in is best
        # answered by the code it starts, so that is asked first.
        "COALESCE((SELECT f.lang FROM routines r JOIN files f ON f.path = r.file"
        "          WHERE r.id = entrypoints.routine_id),"
        "         (SELECT lang FROM files WHERE path = entrypoints.file)) = '{lang}'",
    ),
    "environment variables": (
        "boundaries",
        "SELECT DISTINCT target AS name, file AS where_ FROM boundaries"
        " WHERE kind = 'ENV' AND target <> ''",
        "FROM boundaries WHERE kind = 'ENV' AND target <> ''",
        "file IN (SELECT path FROM files WHERE lang = '{lang}')",
    ),
}

# Populations whose names are dotted paths. A dot separates segments and is not a
# violation of anything; reading `mensores.cli.main` as one identifier made every module
# in the program an exception to its own convention.
DOTTED = frozenset({"modules"})

# The SQL predicate that finds a name *not* in a given style. Kept exactly aligned with
# `styles_of` by a test that asserts the two agree on the real corpus -- a claim whose
# query returns a different count from the claim is worse than no query at all.
#
# **`kebab-case` no longer requires a dash**, and that is `styles_of`'s change arriving in
# the query beside the claim. Once a one-token name counts as kebab-case -- which it is --
# `NOT GLOB '*-*'` reports `analyze` as an exception to a convention it keeps, and DunneFlow's
# own 16 commands are 14 one-word names and `ingest-conform` and `ingest-schema`. The claim
# is *kebab-case, 16 of 16* and the old query returned 14 rows to prove it (rule 13).
STYLE_PREDICATE = {
    "snake_case": "({n} <> lower({n}) OR {n} GLOB '*[^a-z0-9_]*')",
    "SCREAMING_SNAKE": "({n} <> upper({n}) OR {n} GLOB '*[^A-Z0-9_]*')",
    "PascalCase": "({n} GLOB '[^A-Z]*' OR {n} GLOB '*[^A-Za-z0-9]*')",
    "camelCase": "({n} GLOB '[^a-z]*' OR {n} GLOB '*[^A-Za-z0-9]*')",
    "kebab-case": "({n} GLOB '*[^a-z0-9-]*')",
}

# The same question about a **dotted** name, which `styles_in` answers segment by segment.
#
# Written out rather than produced by patching the strings above, which is what this was:
# three `str.replace` calls widening a character class to admit the dot. They were correct
# for the two styles they happened to be tested on and silently absent for `kebab-case`,
# whose predicate contains none of the three substrings -- so a dotted kebab claim carried a
# query that answered a different question, and only DunneNote having no module convention
# at all kept it off the screen.
#
# The character-class clause is the segment test collapsed: a path of snake_case segments is
# exactly a string of `[a-z0-9_.]`. Where a style also constrains a segment's **first**
# letter, the name is prefixed with a dot so that every segment is preceded by one, and the
# query looks for a separator followed by the wrong kind of letter.
DOTTED_STYLE_PREDICATE = {
    "snake_case": "({n} <> lower({n}) OR {n} GLOB '*[^a-z0-9_.]*')",
    "SCREAMING_SNAKE": "({n} <> upper({n}) OR {n} GLOB '*[^A-Z0-9_.]*')",
    "PascalCase": "(('.' || {n}) GLOB '*.[^A-Z]*' OR {n} GLOB '*[^A-Za-z0-9.]*')",
    "camelCase": "(('.' || {n}) GLOB '*.[^a-z]*' OR {n} GLOB '*[^A-Za-z0-9.]*')",
    "kebab-case": "({n} GLOB '*[^a-z0-9.-]*')",
}


def style_predicate(style: str, column: str, dotted: bool,
                    private_prefix: bool = False) -> str:
    """The SQL that finds a name in `column` which is *not* in `style`.

    `private_prefix` judges the name with its leading underscores trimmed, exactly as
    `styles_of` does -- `ltrim` is SQLite's spelling of `lstrip`, and the dunder exemption
    is kept so that `__init__` stays the snake_case name it is. Not for dotted paths, which
    `styles_in` does not relax either.
    """
    if dotted:
        return DOTTED_STYLE_PREDICATE[style].format(n=column)
    if private_prefix:
        n = (f"(CASE WHEN {column} GLOB '__*__' OR ltrim({column}, '_') = '' "
             f"THEN {column} ELSE ltrim({column}, '_') END)")
        return STYLE_PREDICATE[style].format(n=n)
    return STYLE_PREDICATE[style].format(n=column)

# The column each population's names actually live in, for the exception SQL.
NAME_COLUMN = {
    "routines": "name", "classes": "name", "data structures": "name",
    "modules": "module", "parameters": "name", "database tables": "tbl",
    "commands": "name", "environment variables": "target",
}


def _rows(store: Store, sql: str) -> list[tuple[str, str]]:
    # Every population query aliases its columns to `name` and `where_`, so this needs
    # no introspection. `x in row` on a sqlite3.Row searches values, not keys, which is
    # a quiet way to get the wrong answer.
    out: list[tuple[str, str]] = []
    for r in store.query(sql):
        if r["name"]:
            out.append((str(r["name"]), str(r["where_"] or "")))
    return out


# --------------------------------------------------------------------------- #
# Case conventions
# --------------------------------------------------------------------------- #


def population_name(label: str, lang: str) -> str:
    """What to call a population on screen: `routines`, or `Python routines`.

    One place, because two lanes name a population and both then have to decide whether to
    capitalise it to open a sentence -- and a language's display name is already capital,
    so `.capitalize()` on `TypeScript routines` yields `Typescript routines` (rule 51).
    """
    return f"{languages.display(lang)} {label}" if lang else label


def leading(named: str, lang: str) -> str:
    """The same name, fit to start a sentence."""
    return named if lang else named.capitalize()


def tie_note(sets: list[set[str]], style: str) -> str:
    """Said only where the population chose nothing, and it names what it did not choose.

    A claim resting on `PREFERENCE` rather than on evidence has to be able to say so: the
    count is right, and the *name* of the convention is this tool's. The alternatives are
    the styles **every** member also satisfies, counted rather than assumed -- a population
    of one-token lowercase names has two, and one of all-caps names has one, and a sentence
    saying "two other styles" over the second would be wrong in the one place it is trying
    to admit a limitation.
    """
    common: set[str] = set(sets[0]) if sets else set()
    for got in sets[1:]:
        common &= got
    others = sorted(common - {style})
    if not others:
        return ""
    # The chosen style leads the list rather than being glued on in front of it: joined
    # separately, a population with two alternatives reads "snake_case and camelCase and
    # kebab-case".
    words = [STYLE_NAMES.get(o, o) for o in [style, *others]]
    spelled = f"{', '.join(words[:-1])} and {words[-1]}"
    return (f"Every name in this population is spelled ambiguously — each is {spelled} "
            f"at once — so nothing here chose between them, and the tie went to the order "
            f"this tool states. The count is right; which of those names the convention is "
            f"given is DunneFlow's decision and not the program's.")


def _scoped(sql: str, clause: str, lang: str) -> str:
    """`sql`, narrowed to one language -- or handed back untouched when none is asked for.

    Every population query already ends in a `WHERE`, so the language is always an `AND`.
    """
    return sql if not lang else f"{sql} AND {clause.format(lang=lang)}"


def mine_case_conventions(
    store: Store, langs: Sequence[str] = (), private_prefix: bool = False,
) -> tuple[list[Convention], list[Gap]]:
    """How each population spells its names, counted once per language.

    **Spelling is the one thing a language decides for a program**, so mining a mixed
    corpus as though it were one is the question this could not answer. Measured on
    DunneFlow's own tree -- 107 Python files and 11 TypeScript -- the joint answer is
    *"routines are named in snake_case, 1,014 of 1,114"*, a D rating with 100 exceptions,
    and every one of the 100 is a TypeScript name spelled the way TypeScript spells names.
    Split, it is 982 of 998 and 116 of 116: two conventions, both true, neither visible
    before.

    `langs` empty means **do not split**, and that is what a map holding one language
    passes. A one-language map has no language axis to state, so its report is untouched
    -- which is also what keeps every figure recorded against Mensores reproducible.
    """
    conventions: list[Convention] = []
    gaps: list[Gap] = []

    for label, (_table, list_sql, from_clause, lang_clause) in POPULATIONS.items():
        for lang in (langs or [""]):
            rows = _rows(store, _scoped(list_sql, lang_clause, lang))
            if len(rows) < MIN_POPULATION:
                continue
            dotted = label in DOTTED
            named = population_name(label, lang)
            # Per row, not per distinct name. Keying the styles by name collapsed 3,849
            # routines into 3,063 and reported a 79% convention that actually holds in
            # every case -- a denominator counted one way and a numerator another.
            sets = [styles_in(n, dotted, private_prefix) for n, _ in rows]
            styled, firm = resolve_styles(sets)
            spread = Counter(styled)
            style, holds = spread.most_common(1)[0]
            total = len(rows)

            if style == "other" or holds / total < MIN_PREVALENCE:
                gaps.append(Gap(population=named, lang=lang, total=total,
                                spread=sorted(spread.items(), key=lambda kv: -kv[1])))
                continue

            exceptions = [Exception_(n, w)
                          for (n, w), st in zip(rows, styled, strict=True) if st != style]
            column = NAME_COLUMN[label]
            predicate = style_predicate(style, column, dotted, private_prefix)
            where = _scoped(f"{from_clause} AND {predicate}", lang_clause, lang)
            # The allowance is stated in the claim it changed, so a reader comparing two
            # screens can see why one counts `_Handler` and the other does not -- and
            # **only** there. It was keyed on the style until 2026-10-02, so kebab-case
            # commands and TypeScript camelCase said "(a leading underscore allowed)" over
            # a count it had not moved (BACKLOG 28). Judged by asking the strict question
            # too and comparing, so the tag is a fact about this population's count.
            allowed = ""
            if private_prefix:
                strict, _ = resolve_styles([styles_in(n, dotted, False) for n, _ in rows])
                if sum(1 for st in strict if st == style) != holds:
                    allowed = " (a leading underscore allowed)"
            conventions.append(Convention(
                kind="CASE",
                claim=f"{leading(named, lang)} are named in {STYLE_NAMES[style]}{allowed}.",
                population=named,
                lang=lang,
                total=total,
                holds=holds,
                exceptions=sorted(exceptions, key=lambda e: (e.name, e.where)),
                sql=f"SELECT DISTINCT {column} {where}",
                note="" if firm else tie_note(sets, style),
            ))
    return conventions, gaps


# --------------------------------------------------------------------------- #
# Affix conventions: mined, not listed
# --------------------------------------------------------------------------- #


def _segments(name: str) -> list[str]:
    """Split an identifier the way it was written, on underscores and case changes."""
    parts: list[str] = []
    for chunk in name.strip("_").split("_"):
        parts.extend(p for p in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+|\d+", chunk) if p)
    return parts


# Each property carries the SQL that decides it, so an exception list can be
# reproduced rather than merely believed. Rule 13: a measured claim proves itself with
# the query that counted it, and a query that returns something else is worse than none.
ROUTINE_PREDICATES = {
    "registered as a way in":
        "id IN (SELECT routine_id FROM entrypoints WHERE routine_id IS NOT NULL)",
    "asynchronous": "is_async = 1",
    "a predicate: it returns a boolean":
        "returns IN ('bool', 'Optional[bool]', 'bool | None')",
}

CLASS_PREDICATES = {
    "an exception subclass":
        "EXISTS (SELECT 1 FROM json_each(classes.bases) b"
        " WHERE b.value LIKE '%Error' OR b.value LIKE '%Exception'"
        " OR b.value IN ({exceptions}))",
    "an enumeration":
        "EXISTS (SELECT 1 FROM json_each(classes.bases) b"
        " WHERE b.value IN ('Enum', 'StrEnum', 'IntEnum', 'Flag', 'IntFlag'))",
    "a protocol":
        "EXISTS (SELECT 1 FROM json_each(classes.bases) b WHERE b.value = 'Protocol')",
    "a pydantic model":
        "EXISTS (SELECT 1 FROM json_each(classes.bases) b WHERE b.value = 'BaseModel')",
    "a dataclass":
        "name IN (SELECT name FROM structures WHERE kind = 'DATACLASS')",
}


def _routine_properties(store: Store) -> dict[str, set[str]]:
    """The properties the graph already holds, per routine id."""
    props: dict[str, set[str]] = defaultdict(set)
    for r in store.query(
        "SELECT DISTINCT routine_id FROM entrypoints WHERE routine_id IS NOT NULL"
    ):
        props[str(r[0])].add("registered as a way in")
    for r in store.query("SELECT id FROM routines WHERE is_async = 1"):
        props[str(r[0])].add("asynchronous")
    for r in store.query(
        "SELECT id FROM routines WHERE returns IN ('bool', 'Optional[bool]', 'bool | None')"
    ):
        props[str(r[0])].add("a predicate: it returns a boolean")
    for r in store.query("SELECT DISTINCT routine_id, kind FROM boundaries"):
        props[str(r["routine_id"])].add(f"touching the {r['kind']} boundary")
    return props


# Above this many terms the exact tail is replaced by a normal approximation. Chosen so
# every corpus this tool had read before C++ stays on the exact path and reproduces its
# recorded numbers exactly: the largest population Society offers is in the low thousands.
_EXACT_TERMS = 4_000


def _beats_coincidence(holds: int, total: int, base_rate: float, tests: int) -> bool:
    """Would this many hits happen anyway, given how common the property already is?

    The probability of seeing at least `holds` of `total` by chance, if the affix meant
    nothing, multiplied by the number of affix/property pairs tested. Below the
    threshold, the affix is telling us something the base rate does not.

    Blind spot: this tests for coincidence, not for meaning. A convention can be
    statistically undeniable and still be an accident of how one team happened to spell
    things. That is why the exceptions are always printed beside the number.

    **It was written as an exact binomial tail and that stops working at scale.**
    `math.comb(total, i)` is an exact integer, and past a few thousand it is an integer with
    more digits than a float has range — so multiplying it by a probability raises
    `OverflowError: int too large to convert to float`. It never fired on Society, DunneNote
    or DunneCorp, whose largest populations are in the low thousands; it killed a run of
    Unreal's `Runtime` **fourteen minutes in**, after every fact had been extracted, resolved
    and written, in the last pass before the map was rendered.

    Three paths now, and the first two exist so nothing already measured moves:

    * **Below the mean, the answer is known without arithmetic.** If `holds` is no more than
      what the base rate predicts, the tail is at least a half and cannot beat a threshold
      that is orders of magnitude smaller. This is also what bounds the loop below: past this
      point the tail is always the short end.
    * **Exact, in log space, while the term count is small.** `lgamma` instead of `comb`, so
      the same answer arrives without ever building the huge integer.
    * **A normal approximation with a continuity correction beyond that.** At those
      populations the binomial is indistinguishable from it, and a figure that cannot be
      computed is worth less than one computed a stated way (rule 24 — the conditions are
      the point, and they are written down here).
    """
    if base_rate >= 1.0:
        return False          # the property is universal; the affix explains nothing
    if base_rate <= 0.0:
        return True
    if total <= 0 or holds <= 0:
        return False
    mean = total * base_rate
    if holds <= mean:
        return False          # no more than chance predicts; the tail is >= 0.5

    if total - holds + 1 <= _EXACT_TERMS:
        log_n = math.lgamma(total + 1)
        log_p = math.log(base_rate)
        log_q = math.log1p(-base_rate)
        tail = 0.0
        for i in range(holds, total + 1):
            term = (log_n - math.lgamma(i + 1) - math.lgamma(total - i + 1)
                    + i * log_p + (total - i) * log_q)
            tail += math.exp(term)
    else:
        sd = math.sqrt(total * base_rate * (1.0 - base_rate))
        if sd <= 0.0:
            return True
        z = (holds - 0.5 - mean) / sd
        tail = 0.5 * math.erfc(z / math.sqrt(2.0))

    return tail * tests < COINCIDENCE_THRESHOLD


def _class_properties(store: Store) -> tuple[dict[str, tuple[str, str]], dict[str, set[str]]]:
    """Classes, and what the graph can already say about each one.

    Everything here comes from `classes.bases` and `structures.kind`, both of which are
    already extracted. Nothing is inferred from the name -- which is the whole point,
    since the name is what is being tested.
    """
    import json

    names: dict[str, tuple[str, str]] = {}
    props: dict[str, set[str]] = defaultdict(set)
    for r in store.query("SELECT name, qualname, file, line, bases FROM classes"):
        key = str(r["qualname"])
        names[key] = (str(r["name"]), f"{r['file']}:{r['line']}")
        try:
            bases = [str(b) for b in json.loads(r["bases"] or "[]")]
        except ValueError:
            bases = []
        for base in bases:
            tail = base.rsplit(".", 1)[-1]
            if tail.endswith(("Error", "Exception")) or tail in BUILTIN_EXCEPTIONS:
                props[key].add("an exception subclass")
            if tail in {"Enum", "StrEnum", "IntEnum", "Flag", "IntFlag"}:
                props[key].add("an enumeration")
            if tail in {"Protocol"}:
                props[key].add("a protocol")
            if tail in {"BaseModel"}:
                props[key].add("a pydantic model")
    for r in store.query("SELECT name, kind FROM structures WHERE kind = 'DATACLASS'"):
        for key in [k for k in names if k.rsplit(".", 1)[-1] == str(r["name"])]:
            props[key].add("a dataclass")
    return names, props


BUILTIN_EXCEPTIONS = frozenset({
    "Exception", "BaseException", "ValueError", "TypeError", "KeyError", "IndexError",
    "RuntimeError", "OSError", "IOError", "AttributeError", "NotImplementedError",
    "StopIteration", "ArithmeticError", "LookupError", "MemoryError", "SystemExit",
})


def _affix_conventions(
    members: dict[str, tuple[str, str]],
    props: dict[str, set[str]],
    noun: str,
    plural: str,
    exception_sql: str,
    predicates: dict[str, str],
    separator: str = "_",
) -> list[Convention]:
    """Affixes that predict a property, stated in the direction that is true.

    The useful sentence is the *precision* one -- "a routine ending `_cmd` is registered
    as a command, 97 of 99" -- and the two that break it are worth looking at. Coverage
    is the other direction, and on Mensores it is 63%: most commands do end in `_cmd`,
    but plenty do not. Reporting only one of the two numbers is how an affix convention
    flatters itself, so both are printed and the claim is made in the direction that
    actually holds.
    """
    by_suffix: dict[str, list[str]] = defaultdict(list)
    by_prefix: dict[str, list[str]] = defaultdict(list)
    for key, (name, _where) in members.items():
        segs = _segments(name)
        if len(segs) > 1:
            by_suffix[segs[-1]].append(key)
            by_prefix[segs[0]].append(key)

    all_props: set[str] = set()
    for owned in props.values():
        all_props |= owned

    # Every affix is tested against every property, which is thousands of tests. At
    # that many, a six-out-of-six coincidence is not merely possible, it is expected:
    # "a class ending in `Provenance` is a dataclass, 7 of 7" survived precision,
    # sample size and lift, and means nothing at all when 40% of classes are
    # dataclasses. The correction below is what separates `Error` from `Provenance`.
    tests = max(1, (len(by_suffix) + len(by_prefix)) * max(1, len(all_props)))

    out: list[Convention] = []
    for position, groups in (("ending in", by_suffix), ("beginning with", by_prefix)):
        for affix, keys in groups.items():
            if len(keys) < MIN_AFFIX_COUNT:
                continue
            for prop in sorted(all_props):
                if prop not in predicates:
                    continue     # a property no query can reproduce is not reported
                holds = [k for k in keys if prop in props.get(k, ())]
                if len(holds) / len(keys) < MIN_AFFIX_PRECISION:
                    continue
                everywhere = [k for k in members if prop in props.get(k, ())]
                if not everywhere:
                    continue
                base_rate = len(everywhere) / len(members)
                if not _beats_coincidence(len(holds), len(keys), base_rate, tests):
                    continue
                coverage = len(holds) / len(everywhere)
                # The separator matters. `is*` matches `iso_utc_now`, which begins
                # with `iso`, not with `is`; snake_case needs the underscore in the
                # glob, and PascalCase needs the capital that starts the segment.
                glob = (f"*{separator}{affix}" if position == "ending in"
                        else f"{affix}{separator}*")
                out.append(Convention(
                    kind="AFFIX",
                    claim=f"A {noun} {position} `{affix}` is {prop}.",
                    population=f"{plural} {position} `{affix}`",
                    total=len(keys),
                    holds=len(holds),
                    exceptions=sorted(
                        (Exception_(members[k][0], members[k][1])
                         for k in keys if k not in set(holds)),
                        key=lambda e: (e.name, e.where),
                    ),
                    glob=glob,
                    sql=exception_sql.format(
                        glob=glob, lacks=f"NOT ({predicates[prop]})"
                    ),
                    note=(
                        f"The other direction: {len(holds)} of {len(everywhere)} "
                        f"{plural} that are {prop} are named this way "
                        f"({coverage:.0%} coverage)."
                        + ("" if coverage >= MIN_PREVALENCE else
                           " The convention predicts the property, not the reverse.")
                    ),
                ))
    return out


def _class_predicates() -> dict[str, str]:
    quoted = ", ".join(f"'{e}'" for e in sorted(BUILTIN_EXCEPTIONS))
    return {k: v.format(exceptions=quoted) if "{exceptions}" in v else v
            for k, v in CLASS_PREDICATES.items()}


def _boundary_predicates(store: Store, base: dict[str, str], noun: str) -> dict[str, str]:
    """The fixed predicates, plus one per boundary kind the program actually touches."""
    out = dict(base)
    if noun == "routine":
        for r in store.query("SELECT DISTINCT kind FROM boundaries"):
            kind = str(r["kind"])
            out[f"touching the {kind} boundary"] = (
                f"id IN (SELECT routine_id FROM boundaries WHERE kind = '{kind}')"
            )
    return out


def mine_affix_conventions(store: Store) -> list[Convention]:
    """Affix conventions over routines and over classes."""
    routines = {
        str(r["id"]): (str(r["name"]), f"{r['file']}:{r['line_start']}")
        for r in store.query(
            "SELECT id, name, file, line_start FROM routines"
            " WHERE is_nested = 0 AND name_by = '' AND name NOT GLOB '__*__'"
            " AND name NOT GLOB '<*>'"
        )
    }
    out: list[Convention] = []
    if len(routines) >= MIN_POPULATION:
        out.extend(_affix_conventions(
            routines, _routine_properties(store), "routine", "routines",
            "SELECT name, file, line_start FROM routines"
            " WHERE is_nested = 0 AND name_by = '' AND name NOT GLOB '__*__'"
            " AND name NOT GLOB '<*>'"
            " AND name GLOB '{glob}' AND {lacks}",
            _boundary_predicates(store, ROUTINE_PREDICATES, "routine"),
        ))
    names, props = _class_properties(store)
    if len(names) >= MIN_POPULATION:
        out.extend(_affix_conventions(
            names, props, "class", "classes",
            "SELECT name, file, line FROM classes"
            " WHERE name GLOB '{glob}' AND {lacks}",
            _boundary_predicates(store, _class_predicates(), "class"),
            separator="",
        ))
    return out


# --------------------------------------------------------------------------- #
# Privacy, measured rather than assumed
# --------------------------------------------------------------------------- #


# Where a private routine may be called from, per `RuleSet.private_means`: the SQL that is
# true of a call that crosses it, and the word for what it crosses. A language declaring
# `surface` -- or nothing -- is not measured at all (see `detectors.RuleSet.private_means`).
_PRIVATE_SCOPE = {
    "module": ("caller.module <> callee.module", "module"),
    # Go's `module` column is the file, and an unexported name is the package's: the
    # package is the directory, which is the path up to its last separator.
    "package": ("rtrim(caller.file, replace(caller.file, '/', ''))"
                " <> rtrim(callee.file, replace(callee.file, '/', ''))", "package"),
}


def mine_privacy_convention(store: Store, langs: Sequence[str] = ()) -> list[Convention]:
    """A routine marked private -- but *is* it kept private, by this language's meaning?

    Counting how many private routines have a leading underscore measures nothing: that
    is how `visibility` is derived. The claim worth testing is whether a routine marked
    private is ever called from beyond where the language keeps it, and the answer names
    the callers.

    **Where that is, is the language's to say** (`private_means`). Measured with Python's
    reading, pdfcraft's Rust "leaked" 624 times, and 440 of those were `pub(crate)` doing
    what it says. `langs` empty means do not split: the map holds one language, and its
    claim is spelt exactly as it was before there were two.
    """
    present = languages.read(store)
    out: list[Convention] = []
    for lang in (langs or [""]):
        judged = lang or (present[0] if len(present) == 1 else "")
        scope = _PRIVATE_SCOPE.get(load_rules(judged).private_means) if judged else None
        if scope is None:
            continue
        crosses, unit = scope
        own = (f" AND callee.file IN (SELECT path FROM files WHERE lang = '{lang}')"
               if lang else "")
        mine = f" AND file IN (SELECT path FROM files WHERE lang = '{lang}')" if lang else ""
        where = (" WHERE callee.visibility = 'private' AND callee.name NOT GLOB '__*__'"
                 f" AND {crosses}{own}")
        rows = store.query(
            "SELECT DISTINCT callee.name AS name, callee.file AS file,"
            "       callee.line_start AS line"
            "  FROM calls c"
            "  JOIN routines callee ON callee.id = c.callee_id"
            "  JOIN routines caller ON caller.id = c.caller_id" + where
        )
        total = store.query(
            "SELECT COUNT(*) n FROM routines"
            " WHERE visibility = 'private' AND name_by = '' AND name NOT GLOB '__*__'"
            " AND is_nested = 0" + mine
        )[0]["n"]
        if total < MIN_POPULATION:
            continue
        leaked = {(str(r["name"]), f"{r['file']}:{r['line']}") for r in rows}
        named = population_name("routines", lang)
        claim = (f"{leading(named, lang)} marked private are called only from their own "
                 f"{unit}." if lang else
                 f"A routine marked private is called only from its own {unit}.")
        out.append(Convention(
            kind="LEAKAGE",
            claim=claim,
            population=population_name("private routines", lang),
            lang=lang,
            total=total,
            holds=total - len(leaked),
            exceptions=[Exception_(n, w) for n, w in sorted(leaked)],
            sql=(
                "SELECT DISTINCT callee.name, callee.file, callee.line_start FROM calls c"
                " JOIN routines callee ON callee.id = c.callee_id"
                " JOIN routines caller ON caller.id = c.caller_id" + where
            ),
            note="Counting underscores would measure nothing: that is how privacy is "
                 "derived. Whether the boundary holds is a different question.",
        ))
    return out


# --------------------------------------------------------------------------- #
# House prefix
# --------------------------------------------------------------------------- #


def mine_house_prefix(store: Store, langs: Sequence[str] = ()) -> list[Convention]:
    """The `corpname_` case: one token that most names in a population begin with.

    Split with the case conventions, and for the same reason: the token is followed by
    whichever separator the population spells, so which token leads a name is a claim
    about a spelling. `langs` empty means do not split.
    """
    out: list[Convention] = []
    for label in ("environment variables", "database tables", "modules"):
        _table, list_sql, from_clause, lang_clause = POPULATIONS[label]
        for lang in (langs or [""]):
            rows = _rows(store, _scoped(list_sql, lang_clause, lang))
            if len(rows) < MIN_POPULATION:
                continue
            firsts: Counter[str] = Counter()
            for name, _ in rows:
                segs = _segments(name)
                if segs:
                    firsts[segs[0].lower()] += 1
            if not firsts:
                continue
            token, _first_count = firsts.most_common(1)[0]
            conforming = [
                (n, w) for n, w in rows
                if _segments(n) and _segments(n)[0].lower() == token
            ]
            count = len(conforming)
            if count / len(rows) < MIN_PREVALENCE:
                continue
            keep = {n for n, _ in conforming}
            exceptions = [Exception_(n, w) for n, w in rows if n not in keep]
            column = NAME_COLUMN[label]
            named = population_name(label, lang)
            # A module is `mensores.cli`, a table is `mensores_audit`, an environment
            # variable is `MENSORES_HOME`: the house token is followed by whichever
            # separator that population uses, or by nothing at all when the name is
            # exactly the token.
            where = _scoped(
                f"{from_clause} AND lower({column}) NOT GLOB '{token}[_.-]*'"
                f" AND lower({column}) <> '{token}'", lang_clause, lang)
            out.append(Convention(
                kind="HOUSE_PREFIX",
                claim=f"{leading(named, lang)} begin with `{token}`.",
                population=named,
                lang=lang,
                total=len(rows),
                holds=count,
                exceptions=sorted(exceptions, key=lambda e: (e.name, e.where)),
                sql=f"SELECT DISTINCT {column} {where}",
            ))
    return out


def measure(store: Store, private_prefix: bool = False) -> NamingMeasurement:
    """Everything the code says about its own naming, counted.

    **The language axis exists only where the map has one.** `languages.read` is the one
    place that is asked (rule 51), and a map holding a single language is measured exactly
    as it was before any of this: no language in a claim, no language in a query, nothing
    to explain. What changes is the mixed corpus, where mining spelling across two
    languages at once reports that the program has no convention when in fact it has two.

    The two **spelling** lanes split, and so does privacy -- not because privacy is a
    spelling but because what `private` *means* is the language's (`private_means`), and
    a claim measured with one language's meaning over another's routines is false by
    construction. *This said, until 2026-11-01, that `visibility = 'private'` was a
    Python spelling no other reader recorded; Go, Rust, Kotlin and C++ all record it now.*
    An affix is a word a team chose rather than a way of spelling one, and stays whole.
    """
    langs = languages.read(store)
    split = langs if len(langs) > 1 else []
    conventions, gaps = mine_case_conventions(store, split, private_prefix)
    conventions.extend(mine_house_prefix(store, split))
    conventions.extend(mine_affix_conventions(store))
    conventions.extend(mine_privacy_convention(store, split))
    conventions.sort(key=lambda c: (-c.total, c.claim))
    return NamingMeasurement(
        conventions=conventions,
        gaps=gaps,
        thresholds={
            "minimum population": MIN_POPULATION,
            "minimum prevalence": MIN_PREVALENCE,
            "minimum affix count": MIN_AFFIX_COUNT,
            "minimum affix precision": MIN_AFFIX_PRECISION,
        },
    )
