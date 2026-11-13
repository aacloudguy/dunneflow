"""Reality against intent: a stated rule, measured over the population it governs.

`naming.py` counts what the code does and quotes nobody. `stated.py` quotes what somebody
wrote and counts nothing. This is the third question -- *does the program do what the rule
says* -- and it is the one both of those were careful not to answer.

**Which population a rule governs is the whole feature, and getting it wrong is worse than
not answering.** Measured on Lictores before a line of this was written: all six of its
`checkable` rules come from a *harness* standard, and not one of them is a question about
`graph.db`. Checked against the graph, *"Files: kebab-case"* scores **0 of 628** Python
files -- a confident, catastrophic claim about a rule whose own document scopes it to
`src/**/*.md`, three documents. And `commands` would seize the graph's 30 CLI entrypoints
and condemn a Python program against a rule belonging to a different tool entirely.

So the population is never inferred from the scope word alone:

* **A path-shaped scope requires a declared scope.** *"Files"* does not say *which* files,
  and no reading of the word supplies it. A rule naming files whose document declares no
  `paths:` is reported as having no population rather than measured against everything --
  rule 49, because a plausible population is exactly what hides the failure.
* **An entity scope names its own population**, and a declared glob narrows it to the files
  those entities live in. *"Classes"* means the classes, and `['src/**/*.py']` means the
  ones under `src`.

**Three verdicts, never two.** A rule that holds, a rule with nothing to measure, and a
rule whose spelling this tool cannot test are three different facts, and rendering any two
alike would let *"we could not check"* read as *"it passes"*. That is the same discipline
`Store.finished` applies to a map that never finished, and design rule 21's on a blank pane.

**What is deliberately not built: a pattern language.** Only case styles are tested, through
`naming.case_style` so that what `kebab-case` means is defined once (rule 51). `NN-kebab-name`,
`paul:kebab-case` and *"colon separator"* are quoted back and declared untestable. Inventing
a template syntax to cover them would mean guessing what a placeholder meant, and a guess
here is indistinguishable on screen from a measurement -- which is the failure this module
exists to avoid, arriving through the back door.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from ..docstore import DocStore
from ..store import Store
from . import languages
from .naming import (
    DOTTED,
    POPULATIONS,
    Exception_,
    population_name,
    styles_in,
)
from .stated import StatedRule, stated_rules

# The three answers. Strings rather than an enum because they travel to a browser as JSON
# and a name a reader can see in the payload is worth more than a type nobody serialises.
CHECKED = "CHECKED"
NO_POPULATION = "NO_POPULATION"
NOT_CHECKABLE = "NOT_CHECKABLE"

# Where a rule came from, which a reader must never have to guess: an outside standard is
# a different kind of claim from a rule the project wrote about itself.
OWN = "the program's own documents"
IMPORTED = "a standards directory"

# The frontmatter keys that scope a rule to part of a tree. Both are read because both
# occur: `paths` in the harness standard, `applies_to` elsewhere in the same corpus.
SCOPE_KEYS = ("paths", "applies_to")

# Scope words that name a **path**, and so cannot say which paths without a declared scope.
PATH_SCOPES = frozenset({"file", "files", "filename", "filenames"})
DIR_SCOPES = frozenset({"directory", "directories", "folder"})

# Scope words that name a population of their own, mapped onto the labels `naming.py`
# already defines. Reusing those labels rather than writing new SQL is rule 51: there is one
# place that knows what "the classes" means, and a second would drift from it silently.
SCOPE_TO_POPULATION: dict[str, str] = {
    "module": "modules", "modules": "modules",
    "class": "classes", "classes": "classes",
    "function": "routines", "functions": "routines",
    "method": "routines", "methods": "routines",
    "routine": "routines", "routines": "routines",
    "parameter": "parameters", "parameters": "parameters",
    "argument": "parameters", "arguments": "parameters",
    "command": "commands", "commands": "commands",
    "subcommand": "commands",
    "table": "database tables", "tables": "database tables",
    "type": "data structures", "types": "data structures",
    "interface": "data structures",
    "environment variable": "environment variables",
    "env var": "environment variables",
}

# One population this needs and the derived lane does not mine: constants are a *stated*
# subject far more often than a measured one. Kept here rather than added to `POPULATIONS`
# because that dict is iterated to mint the derived lane's conventions, and adding an entry
# would quietly grow a different feature's output -- a change to what the naming report says
# about a program, made as a side effect of building this one.
CONSTANTS = (
    "SELECT DISTINCT name, file AS where_ FROM constants WHERE name <> ''",
    "FROM constants WHERE name <> ''",
    "file IN (SELECT path FROM files WHERE lang = '{lang}')",
)

# What a scope word means when this tool holds nothing that could answer it. Stated rather
# than lumped in with "no rows matched", because *"the map records no such thing"* and
# *"the map records them and this glob selected none"* send a reader to different places.
UNMAPPED_REASONS: dict[str, str] = {
    "variable": "DunneFlow does not record variables — local variables and assignments "
                "are deliberately outside what it maps, so there is nothing to count",
    "variables": "DunneFlow does not record variables — local variables and assignments "
                 "are deliberately outside what it maps, so there is nothing to count",
    "branch": "DunneFlow reads a source tree, not a version control history",
    "branches": "DunneFlow reads a source tree, not a version control history",
    "commit": "DunneFlow reads a source tree, not a version control history",
    "commits": "DunneFlow reads a source tree, not a version control history",
}


@dataclass(slots=True)
class RuleCheck:
    """One stated rule, and what happened when this map was asked about it."""

    rule: StatedRule
    source: str                  # OWN | IMPORTED
    verdict: str                 # CHECKED | NO_POPULATION | NOT_CHECKABLE
    reason: str = ""             # why, whenever the verdict is not CHECKED
    population: str = ""         # what was counted over, in words
    scoped_by: str = ""          # the declared glob, as written, or ""
    # Which language this rule was measured in, and `""` when the question had no language
    # axis -- a map holding one language, a scope that narrows to one, or a path-shaped
    # scope, which is about filenames and not identifiers.
    lang: str = ""
    # What would make this result a false alarm, in the anomalies module's discipline. A
    # rule measured against a language its document never mentions is a true count of a
    # question nobody may have asked, and saying so is the difference between a finding
    # and an accusation.
    blind_spot: str = ""
    total: int = 0
    holds: int = 0
    exceptions: list[Exception_] = field(default_factory=list)
    sql: str = ""                # reproduces the population, via `dunneflow query`

    @property
    def prevalence(self) -> float:
        return self.holds / self.total if self.total else 0.0


def scope_globs(frontmatter: dict[str, str]) -> list[str]:
    """The globs a document declares, from either key, as written.

    `frontmatter` is `dict[str, str]` all the way from the extractor, so a YAML list
    arrives as the literal string `"['src/**/*.md']"` rather than as a list. Parsing it
    here rather than teaching the extractor to keep types is deliberate: the extractor's
    output is hashed into the document cache key, and changing its shape would discard
    every document store on the machine to gain a convenience one caller wants.
    """
    out: list[str] = []
    for key in SCOPE_KEYS:
        raw = (frontmatter.get(key) or "").strip()
        if not raw:
            continue
        # `['a', 'b']` or a bare `a`. Quotes and brackets stripped per item; nothing here
        # is a YAML parser, and anything it cannot read is skipped rather than guessed at.
        for piece in raw.strip("[]").split(","):
            item = piece.strip().strip("'\"").strip()
            if item:
                out.append(item)
    return out


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """A path glob, as a regex. `**` crosses directories; `*` and `?` do not.

    Written out rather than taken from `fnmatch`, whose `*` matches `/` and so makes
    `src/*.md` select every markdown file in the tree -- and rather than
    `PurePath.full_match`, which is Python 3.13 and this package supports 3.12.
    """
    i, out = 0, [r"\A"]
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")      # zero or more directories, including none
            i += 3
            continue
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        ch = pattern[i]
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    out.append(r"\Z")
    return re.compile("".join(out))


def _matches_any(path: str, globs: list[str]) -> bool:
    return any(glob_to_regex(g).match(path) for g in globs)


def _pattern_style(pattern: str) -> str:
    """The case style a stated pattern names, or `""` when it names none.

    The stated vocabulary and `case_style`'s are not the same list -- a document writes
    `CAPS_UNDERSCORES` and `SCREAMING_SNAKE_CASE` for what `case_style` calls
    `SCREAMING_SNAKE` -- so the two are joined here, in one place, rather than at each
    comparison.
    """
    p = pattern.strip().strip("`").strip().lower().replace(" ", "_").replace("-", "_")
    return {
        "snake_case": "snake_case",
        "kebab_case": "kebab-case",
        "pascalcase": "PascalCase",
        "camelcase": "camelCase",
        "screaming_snake_case": "SCREAMING_SNAKE",
        "screaming_snake": "SCREAMING_SNAKE",
        "caps_underscores": "SCREAMING_SNAKE",
        "upper_snake": "SCREAMING_SNAKE",
        "upper_snake_case": "SCREAMING_SNAKE",
        "screaming_snake_case_": "SCREAMING_SNAKE",
    }.get(p, "")


def _paths(store: Store | None, docs: DocStore | None) -> list[tuple[str, str]]:
    """Every path this map holds, from both stores, as `(path, where)`.

    Both, because *"files"* means different files in different standards and only the
    declared glob decides which: `src/**/*.md` is a question about the document corpus and
    `**/*.py` is a question about the source tree. Answering from one store would make the
    tool's answer depend on which store it happened to look in.

    **A duplicate is kept here, and that is the opposite of what `stated.py` does.** That
    module folds byte-identical copies because a rule quoted twice out of two copies of one
    file is one rule counted as two. This counts *paths*, and two paths holding identical
    bytes are still two distinct filenames, each of which the rule governs. Dropping them
    made Lictores' `src/**/*.md` population **1 document instead of 3** -- both ADRs there
    are byte-identical to copies under `.groma/adrs/`, and their names break the convention
    exactly as much for being copies.
    """
    out: list[tuple[str, str]] = []
    if store is not None:
        out += [(str(r["path"]), str(r["path"])) for r in store.query(
            "SELECT path FROM files WHERE path <> ''")]
    if docs is not None:
        out += [(str(r["path"]), str(r["path"])) for r in docs.query(
            "SELECT path FROM documents WHERE path <> ''")]
    return out


def _population(rule: StatedRule, globs: list[str], store: Store | None,
                docs: DocStore | None, lang: str = "",
                ) -> tuple[str, list[tuple[str, str]], str, str]:
    """`(label, [(name, where)], sql, refusal)` for one rule's scope.

    A non-empty `refusal` means no check may be run, and is the sentence saying why.

    `lang` narrows an **entity** population to one language, through the same clause
    `naming.py` prints beside its own claims (rule 51). A path scope is never narrowed:
    `files` is a question about filenames, the population is drawn from the document store
    as well as the graph, and a document has no language.
    """
    scope = rule.scope.strip().lower()

    if scope in PATH_SCOPES or scope in DIR_SCOPES:
        # The finding that reordered this whole feature, as behaviour: the word names a
        # path and nothing supplies which paths, so an undeclared scope is refused rather
        # than widened to the whole map.
        if not globs:
            return "", [], "", (
                f"the rule names {scope} but its document declares no `paths:` or "
                "`applies_to:` scope, so which ones it governs is not stated — DunneFlow "
                "will not guess a population")
        rows = [(p, w) for p, w in _paths(store, docs) if _matches_any(p, globs)]
        if scope in DIR_SCOPES:
            # A directory is judged on its own leaf, and each is counted once however many
            # files it holds -- otherwise a deep directory votes as often as it has files.
            seen: dict[str, str] = {}
            for p, _w in rows:
                parent = PurePosixPath(p).parent
                if str(parent) not in (".", ""):
                    seen.setdefault(parent.name, str(parent))
            # The label is the population and `scoped_by` is the glob -- said once each.
            # Folding the glob into the label printed it twice on both surfaces.
            return "directories", sorted(seen.items()), "", ""
        # The stem, because the standard's own example says so: `Files | kebab-case |
        # `plan-phase.md`` -- the extension is not part of what is being spelled.
        return "files", [(PurePosixPath(p).stem, w) for p, w in rows], "", ""

    label = SCOPE_TO_POPULATION.get(scope)
    if label is None and scope != "constant" and scope != "constants":
        why = UNMAPPED_REASONS.get(scope)
        return "", [], "", (
            why or f"DunneFlow holds no population it calls “{scope}”")

    if label is None:
        list_sql, _from, lang_clause = CONSTANTS
        label = "constants"
    else:
        _table, list_sql, _from, lang_clause = POPULATIONS[label]
    if store is None:
        return label, [], list_sql, "this map holds no code graph to count over"

    if lang:
        list_sql = f"{list_sql} AND {lang_clause.format(lang=lang)}"
        label = population_name(label, lang)

    rows = []
    for r in store.query(list_sql):
        name, where = str(r["name"] or ""), str(r["where_"] or "")
        if not name:
            continue
        # A glob narrows an entity population by the file its members live in. `where_`
        # is `file:line` for some populations and a bare path for others, so the path is
        # taken up to the first colon rather than assumed.
        if globs and not _matches_any(where.split(":", 1)[0], globs):
            continue
        rows.append((name, where))
    return label, rows, list_sql, ""


def check_rule(rule: StatedRule, frontmatter: dict[str, str], source: str,
               store: Store | None, docs: DocStore | None,
               langs: Sequence[str] = (), private_prefix: bool = False) -> list[RuleCheck]:
    """One rule, checked -- or refused, with the reason it was refused.

    **A list, because one rule can be more than one question.** A map holding two languages
    holds two populations of functions, spelled the way each language spells them, and a
    stated rule that names no path governs both without saying so. Measured on DunneFlow's
    own tree, *"Functions: snake_case"* scores **1,014 of 1,114** with 100 exceptions, and
    every one of the 100 is a TypeScript name doing exactly what TypeScript says. One
    number, 91%, made of two answers that are 98% and 0%.

    This is the failure this module was written to prevent, arriving one door along. A
    path-shaped scope is *refused* here because nothing supplies which paths -- and the
    difference is that **the map supplies which languages**. Splitting reads a fact;
    widening guessed a population. So the rule is measured once per language, each result
    saying which, and none of them is the sum.

    Each split result carries a `blind_spot`, because a rule measured against a language
    its document never mentions is a true count of a question nobody may have asked.
    """
    globs = scope_globs(frontmatter)
    scoped_by = ", ".join(globs)

    if not rule.checkable:
        return [RuleCheck(rule=rule, source=source, verdict=NOT_CHECKABLE,
                          scoped_by=scoped_by,
                          reason="the rule does not name both a class of identifier and a "
                                 "spelling, so there is no check to write")]

    style = _pattern_style(rule.pattern)
    if not style:
        return [RuleCheck(rule=rule, source=source, verdict=NOT_CHECKABLE,
                          scoped_by=scoped_by,
                          reason=f"“{rule.pattern}” is not a spelling DunneFlow can test — "
                                 "it tests case styles, and inventing a pattern language to "
                                 "cover the rest would mean guessing what this one meant")]

    scope = rule.scope.strip().lower()
    # `dotted` is a property of the *scope*, not of the label, which now carries a language
    # in front of it. Asking `label in DOTTED` after the prefix went on would have read
    # "Python modules" as undotted and made every module an exception again -- the defect
    # this line's own comment records, reintroduced by a cosmetic change.
    dotted = SCOPE_TO_POPULATION.get(scope) in DOTTED

    # A path scope is never split: it asks about filenames, its population is drawn from the
    # document store as well as the graph, and a document has no language.
    path_shaped = scope in PATH_SCOPES or scope in DIR_SCOPES
    candidates: list[str] = [""]
    if not path_shaped and store is not None and len(langs) > 1:
        # Only the languages that actually hold some of this population. A rule whose
        # document already scopes it to `**/*.py` narrows to one language on its own, and
        # labelling that answer -- or pairing it with an empty TypeScript one -- would be
        # announcing an axis the reader's own standard had already closed.
        with_rows = [x for x in langs if _population(rule, globs, store, docs, x)[1]]
        if len(with_rows) > 1:
            candidates = with_rows

    out: list[RuleCheck] = []
    for lang in candidates:
        blind = "" if not lang else (
            "the document states no `paths:` scope, so whether this rule was meant for "
            f"{languages.display(lang)} is not stated — it is measured here because the "
            "map holds it, not because the rule claims it")
        label, rows, sql, refusal = _population(rule, globs, store, docs, lang)
        if refusal:
            out.append(RuleCheck(rule=rule, source=source, verdict=NO_POPULATION,
                                 population=label, scoped_by=scoped_by, sql=sql,
                                 lang=lang, blind_spot=blind, reason=refusal))
            continue
        if not rows:
            out.append(RuleCheck(
                rule=rule, source=source, verdict=NO_POPULATION, population=label,
                scoped_by=scoped_by, sql=sql, lang=lang, blind_spot=blind,
                reason=f"this map holds nothing in {label or 'that population'} — "
                       "the rule may still be right, and nothing here can say"))
            continue

        # **A dotted name is a path, not an identifier**, and `naming.py` paid for this
        # once already: reading `lictores.cli.main` as one word made every module in the
        # program an exception to its own convention. Reusing `POPULATIONS` without reusing
        # `DOTTED` reproduced it exactly -- `modules / snake_case` reported **1 of 628**.
        #
        # `styles_in` rather than `case_style`, and that is the other half: a name can
        # satisfy a stated spelling without being the one answer `case_style` picks. A
        # command called `analyze` keeps a `kebab-case` rule and keeps a `snake_case` one,
        # and asking which it *is* condemns it to one of the two (rule 100).
        bad = [Exception_(name=n, where=w) for n, w in rows
               if style not in styles_in(n, dotted, private_prefix)]
        out.append(RuleCheck(
            rule=rule, source=source, verdict=CHECKED, population=label,
            scoped_by=scoped_by, lang=lang, blind_spot=blind, total=len(rows),
            holds=len(rows) - len(bad),
            exceptions=sorted(bad, key=lambda e: (e.name, e.where)), sql=sql))
    return out


def check_stated(store: Store | None, docs: DocStore | None,
                 standards: DocStore | None,
                 private_prefix: bool = False) -> list[RuleCheck]:
    """Every stated rule this map can see, checked against what it holds.

    Both corpora, and each rule keeps the name of the one it came from: a rule the project
    wrote about itself and a rule an outside standard imposes are different claims, and a
    reader who cannot tell them apart cannot weigh either.
    """
    # Asked once, of the one place that answers it (rule 51), and only where there is an
    # axis to split on: a map holding one language is checked exactly as it was before.
    langs = languages.read(store) if store is not None else []
    out: list[RuleCheck] = []
    for corpus, source in ((docs, OWN), (standards, IMPORTED)):
        if corpus is None:
            continue
        fronts = {
            str(r["path"]): str(r["frontmatter"] or "")
            for r in corpus.query("SELECT path, frontmatter FROM documents")
        }
        for rule in stated_rules(corpus):
            # `docs` for both, never `corpus`: an imported rule is a claim about *this*
            # program, so its population is the program's own files -- never the standards
            # directory's own documents, which nobody is measuring.
            out.extend(check_rule(rule, _front(fronts.get(rule.doc, "")), source,
                                  store, docs, langs, private_prefix))
    # Checked first and worst first inside that, because the exceptions are the product.
    # `population` breaks the tie so a rule's languages keep a stable order beside each
    # other rather than one decided by whichever scored lower (rule 66).
    order = {CHECKED: 0, NO_POPULATION: 1, NOT_CHECKABLE: 2}
    return sorted(out, key=lambda c: (order[c.verdict], c.prevalence, c.rule.doc,
                                      c.population))


def _front(raw: str) -> dict[str, str]:
    """The stored frontmatter blob, back into a mapping.

    It is written as JSON by the store and read back here rather than carried on
    `StatedRule`, because a rule's scope belongs to its *document* -- one document scopes
    every rule it states, and hanging a copy on each rule would be the same fact in as many
    places as the document has rows.
    """
    if not raw:
        return {}
    try:
        got = json.loads(raw)
    except ValueError:
        return {}
    return {str(k): str(v) for k, v in got.items()} if isinstance(got, dict) else {}
