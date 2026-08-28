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
from dataclasses import dataclass, field

from ..store import Store

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

STYLE_NAMES = {
    "snake_case": "snake_case",
    "SCREAMING_SNAKE": "SCREAMING_SNAKE_CASE",
    "PascalCase": "PascalCase",
    "camelCase": "camelCase",
    "kebab-case": "kebab-case",
}


def case_style(name: str) -> str:
    """Which spelling convention a name follows.

    A single lowercase word is counted as snake_case. It is equally camelCase, and the
    ambiguity is real; counting it with the majority is what keeps a one-word name from
    appearing as an exception to every convention at once.
    """
    if not name:
        return "other"
    if KEBAB.fullmatch(name):
        return "kebab-case"
    if SNAKE.fullmatch(name):
        return "snake_case"
    if SCREAMING.fullmatch(name):
        return "SCREAMING_SNAKE"
    if PASCAL.fullmatch(name):
        return "PascalCase"
    if CAMEL.fullmatch(name):
        return "camelCase"
    return "other"


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

# Each population: a label, the SQL that lists (name, where), and the SQL fragment that
# selects it again for an exception query. Kept as text so every claim is reproducible
# through `dunneflow query` rather than only inside this process.
POPULATIONS: dict[str, tuple[str, str, str]] = {
    "routines": (
        "routines",
        "SELECT name, file || ':' || line_start AS where_ FROM routines"
        " WHERE is_nested = 0 AND name NOT GLOB '__*__' AND name NOT GLOB '<*>'",
        "FROM routines WHERE is_nested = 0 AND name NOT GLOB '__*__'"
        " AND name NOT GLOB '<*>'",
    ),
    "classes": (
        "classes",
        "SELECT name, file || ':' || line AS where_ FROM classes",
        "FROM classes WHERE 1",
    ),
    "data structures": (
        "structures",
        "SELECT name, file || ':' || line AS where_ FROM structures",
        "FROM structures WHERE 1",
    ),
    "modules": (
        "modules",
        "SELECT DISTINCT module AS name, path AS where_ FROM files WHERE module <> ''",
        "FROM files WHERE module <> ''",
    ),  # dotted -- see DOTTED below
    "parameters": (
        "params",
        "SELECT DISTINCT name, '' AS where_ FROM params WHERE name NOT IN ('self', 'cls')",
        "FROM params WHERE name NOT IN ('self', 'cls')",
    ),
    "database tables": (
        "db_tables",
        "SELECT DISTINCT tbl AS name, file AS where_ FROM sql_ops WHERE tbl <> ''",
        "FROM sql_ops WHERE tbl <> ''",
    ),
    "commands": (
        "entrypoints",
        "SELECT DISTINCT name, module AS where_ FROM entrypoints WHERE kind = 'CLI'",
        "FROM entrypoints WHERE kind = 'CLI'",
    ),
    "environment variables": (
        "boundaries",
        "SELECT DISTINCT target AS name, file AS where_ FROM boundaries"
        " WHERE kind = 'ENV' AND target <> ''",
        "FROM boundaries WHERE kind = 'ENV' AND target <> ''",
    ),
}

# Populations whose names are dotted paths. A dot separates segments and is not a
# violation of anything; reading `mensores.cli.main` as one identifier made every module
# in the program an exception to its own convention.
DOTTED = frozenset({"modules"})

# The SQL predicate that finds a name *not* in a given style. Kept exactly aligned with
# `case_style` by a test that asserts the two agree on the real corpus -- a claim whose
# query returns a different count from the claim is worse than no query at all.
STYLE_PREDICATE = {
    "snake_case": "({n} <> lower({n}) OR {n} GLOB '*[^a-z0-9_]*')",
    "SCREAMING_SNAKE": "({n} <> upper({n}) OR {n} GLOB '*[^A-Z0-9_]*')",
    "PascalCase": "({n} GLOB '[^A-Z]*' OR {n} GLOB '*[^A-Za-z0-9]*')",
    "camelCase": "({n} GLOB '[^a-z]*' OR {n} GLOB '*[^A-Za-z0-9]*')",
    "kebab-case": "({n} NOT GLOB '*-*' OR {n} GLOB '*[^a-z0-9-]*')",
}

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


def mine_case_conventions(store: Store) -> tuple[list[Convention], list[Gap]]:
    conventions: list[Convention] = []
    gaps: list[Gap] = []

    for label, (_table, list_sql, from_clause) in POPULATIONS.items():
        rows = _rows(store, list_sql)
        if len(rows) < MIN_POPULATION:
            continue
        dotted = label in DOTTED
        # Per row, not per distinct name. Keying the styles by name collapsed 3,849
        # routines into 3,063 and reported a 79% convention that actually holds in
        # every case -- a denominator counted one way and a numerator another.
        styled = [(n, w, case_style(n.replace(".", "_") if dotted else n)) for n, w in rows]
        spread = Counter(st for _, _, st in styled)
        style, holds = spread.most_common(1)[0]
        total = len(rows)

        if style == "other" or holds / total < MIN_PREVALENCE:
            gaps.append(Gap(population=label, total=total,
                            spread=sorted(spread.items(), key=lambda kv: -kv[1])))
            continue

        exceptions = [Exception_(n, w) for n, w, st in styled if st != style]
        column = NAME_COLUMN[label]
        predicate = STYLE_PREDICATE[style].format(n=column)
        if dotted:
            predicate = predicate.replace("a-z0-9_]", "a-z0-9_.]").replace(
                "A-Za-z0-9]", "A-Za-z0-9.]").replace("A-Z0-9_]", "A-Z0-9_.]")
        conventions.append(Convention(
            kind="CASE",
            claim=f"{label.capitalize()} are named in {STYLE_NAMES[style]}.",
            population=label,
            total=total,
            holds=holds,
            exceptions=sorted(exceptions, key=lambda e: e.name),
            sql=f"SELECT DISTINCT {column} {from_clause} AND {predicate}",
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


def _beats_coincidence(holds: int, total: int, base_rate: float, tests: int) -> bool:
    """Would this many hits happen anyway, given how common the property already is?

    The probability of seeing at least `holds` of `total` by chance, if the affix meant
    nothing, multiplied by the number of affix/property pairs tested. Below the
    threshold, the affix is telling us something the base rate does not.

    Blind spot: this tests for coincidence, not for meaning. A convention can be
    statistically undeniable and still be an accident of how one team happened to spell
    things. That is why the exceptions are always printed beside the number.
    """
    if base_rate >= 1.0:
        return False          # the property is universal; the affix explains nothing
    if base_rate <= 0.0:
        return True
    tail = sum(
        math.comb(total, i) * base_rate**i * (1.0 - base_rate) ** (total - i)
        for i in range(holds, total + 1)
    )
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
                        key=lambda e: e.name,
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
            " WHERE is_nested = 0 AND name NOT GLOB '__*__' AND name NOT GLOB '<*>'"
        )
    }
    out: list[Convention] = []
    if len(routines) >= MIN_POPULATION:
        out.extend(_affix_conventions(
            routines, _routine_properties(store), "routine", "routines",
            "SELECT name, file, line_start FROM routines"
            " WHERE is_nested = 0 AND name NOT GLOB '__*__' AND name NOT GLOB '<*>'"
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


def mine_privacy_convention(store: Store) -> list[Convention]:
    """A leading underscore means private -- but *is* it kept private?

    Counting how many private routines have a leading underscore measures nothing: that
    is how `visibility` is derived. The claim worth testing is whether a routine marked
    private is ever called from another module, and the answer names the callers.
    """
    rows = store.query(
        "SELECT DISTINCT callee.name AS name, callee.module AS home,"
        "       caller.module AS caller_module, callee.file AS file,"
        "       callee.line_start AS line"
        "  FROM calls c"
        "  JOIN routines callee ON callee.id = c.callee_id"
        "  JOIN routines caller ON caller.id = c.caller_id"
        " WHERE callee.visibility = 'private'"
        "   AND callee.name NOT GLOB '__*__'"
        "   AND caller.module <> callee.module"
    )
    total = store.query(
        "SELECT COUNT(*) n FROM routines"
        " WHERE visibility = 'private' AND name NOT GLOB '__*__' AND is_nested = 0"
    )[0]["n"]
    if total < MIN_POPULATION:
        return []
    leaked = {(str(r["name"]), f"{r['file']}:{r['line']}") for r in rows}
    holds = total - len(leaked)
    return [Convention(
        kind="LEAKAGE",
        claim="A routine marked private is called only from its own module.",
        population="private routines",
        total=total,
        holds=holds,
        exceptions=[Exception_(n, w) for n, w in sorted(leaked)],
        sql=(
            "SELECT DISTINCT callee.name, callee.file, callee.line_start FROM calls c"
            " JOIN routines callee ON callee.id = c.callee_id"
            " JOIN routines caller ON caller.id = c.caller_id"
            " WHERE callee.visibility = 'private' AND callee.name NOT GLOB '__*__'"
            " AND caller.module <> callee.module"
        ),
        note="Counting underscores would measure nothing: that is how privacy is "
             "derived. Whether the boundary holds is a different question.",
    )]


# --------------------------------------------------------------------------- #
# House prefix
# --------------------------------------------------------------------------- #


def mine_house_prefix(store: Store) -> list[Convention]:
    """The `corpname_` case: one token that most names in a population begin with."""
    out: list[Convention] = []
    for label in ("environment variables", "database tables", "modules"):
        _table, list_sql, from_clause = POPULATIONS[label]
        rows = _rows(store, list_sql)
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
        out.append(Convention(
            kind="HOUSE_PREFIX",
            claim=f"{label.capitalize()} begin with `{token}`.",
            population=label,
            total=len(rows),
            holds=count,
            exceptions=sorted(exceptions, key=lambda e: e.name),
            # A module is `mensores.cli`, a table is `mensores_audit`, an environment
            # variable is `MENSORES_HOME`: the house token is followed by whichever
            # separator that population uses, or by nothing at all when the name is
            # exactly the token.
            sql=(f"SELECT DISTINCT {column} {from_clause}"
                 f" AND lower({column}) NOT GLOB '{token}[_.-]*'"
                 f" AND lower({column}) <> '{token}'"),
        ))
    return out


def measure(store: Store) -> NamingMeasurement:
    """Everything the code says about its own naming, counted."""
    conventions, gaps = mine_case_conventions(store)
    conventions.extend(mine_house_prefix(store))
    conventions.extend(mine_affix_conventions(store))
    conventions.extend(mine_privacy_convention(store))
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
