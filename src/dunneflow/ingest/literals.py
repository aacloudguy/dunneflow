"""What a string *means*, decided once for every language there will ever be.

A reader's job is to find the strings a file spells out. This module's job is to say what
each one is: a SQL statement, the name of a file the program uses, or prose that happens
to contain a dot. The two halves were one function inside `extractors/python/extract.py`
until 2026-09-17, and the split is rule 51 in the place it costs most.

**One answer to one question.** A plugin carrying its own `looks_like_sql` means the same
`"INSERT INTO queue (id) VALUES (?)"` reads one way in a `.py` and another in a `.ts` --
not because the languages differ, because two people wrote two scanners. There is nothing
about `_scan_sql` or `_scan_artefact` that is Python's: both take a string and an
extension table, and neither has ever looked at a syntax tree.

**`detectors/<lang>.yaml` stays the extension point, and host-side scanning is what keeps
it one.** An artefact is an artefact because its extension is in `artefact_kinds`; with
the judgement here, teaching the tool that `.parquet` names a file is a YAML edit that
moves `rules_fingerprint()` and re-reads every language. With the judgement in the plugin
it would be a YAML edit plus a plugin rebuild, and the rebuild is the half somebody
forgets.

**And it shrinks the plugin contract to one thing.** Once literals are host-side, the only
rules-facing thing a reader must get exactly right is `ingest/dotted.py`'s normalisation --
one contract with one fixture instead of four.

---

**What stays with the reader, and why each one has to.** The interpolation. `f"{root}/g.json"`
still names `g.json`, and turning it into text needs the module's own constant table and the
syntax tree that holds it -- so the reader resolves it and says, with `LiteralKind`, that it
did. Which routine the string sits in: by the time facts reach this module a line number is
all that is left of where anything was. And **not being a docstring**, which is rule 9 and
is the reader's because only the reader can see that a string is the first statement of a
body. A docstring that opens *"Insert candidate into capture_queue"* is a sentence about a
statement; admitted here it would be a statement.

**The bound is declared here and applied there**, which is the one place this module's
rule runs inside somebody else's process. `LITERAL_MIN` is the shortest text either
judgement below could accept, not the shortest either *has* accepted -- six is SQL's own
bound and stays inside `_sql`, where a three-character artefact name cannot trip over it.
**The count it dropped travels with the facts** (`FileFacts.literals_dropped`), because a
filter that runs in a process the host cannot look inside is exactly the silent one design
rule 1 forbids.

*Measured on Comitia before the floor was set, because the obvious reason for it is not the
true one.* 46,524 strings; the floor at three drops **4,022** of them and the payload is
26.5 MB. Taking six instead -- the bound `_scan_sql` has always applied, and the number the
plan named -- would drop a further 6,861 and save **0.43 MB, 1.6%**. So the floor is not
buying the wire anything worth having, and a floor of six would put every four-character
filename a `detectors/<lang>.yaml` might name outside the map with nothing to say so. What
the bound genuinely does is the **ceiling**: a vendored blob has no business being
lexically scanned for SQL, and that half is `_scan_sql`'s own and unchanged.
"""

from __future__ import annotations

import re

from .. import sql as sqlmod
from ..detectors import RuleSet, load_rules
from ..schema import (
    Artefact,
    FileFacts,
    IndexSchema,
    LiteralKind,
    SqlStatement,
    StringLiteral,
    TableSchema,
)
from .contract import PluginRefused

# A file basename, as a person would write one. Deliberately narrow: no spaces, no
# quoting, no shell metacharacters beyond the glob forms, and an extension of at most
# eight characters. Anything else is prose that happens to contain a dot.
_ARTEFACT_NAME = re.compile(r"^[A-Za-z0-9_*?\[\]][A-Za-z0-9_.*?\[\]-]*\.[A-Za-z0-9]{1,8}$")

# The bound a reader applies before sending, and the *union* of what the judgements below
# can use rather than either one's own. Three is the shortest string that can name a file
# at all -- `x.y`, a one-character stem and a one-character extension, both of which a
# `detectors/<lang>.yaml` may legitimately declare. Six is `_sql`'s and is applied in
# `_sql`. Taking six for both would be a bound written for one question quietly deciding
# another, which is how a filter hides (rule 49): on Comitia it happens to cost nothing,
# because the shortest artefact literal there is seven characters -- and "it costs nothing
# on this corpus" is not the same claim as "it cannot cost anything". The difference
# between three and six is 6,861 strings and 1.6% of the payload; see the docstring.
LITERAL_MIN = 3
# Rule 8 puts no ceiling on a stored value; this is a ceiling on *scanning*, and it is the
# one `_scan_sql` has always had. A 200 KB string is a schema block; a larger one is a
# vendored blob, and running a lexical SQL scan over it buys nothing for what it costs.
LITERAL_MAX = 200_000

# A literal long enough to be worth judging, which is the question a reader is answering
# when it applies the bound.
def in_bounds(text: str) -> bool:
    return LITERAL_MIN <= len(text) <= LITERAL_MAX


# `executescript` blocks hold a whole schema; each statement counts separately, and the
# first two hundred of one string are as much schema as anybody reads.
_MAX_STATEMENTS = 200

# The longest text that can be a basename. Beyond it the string is prose (or a whole
# document), and it is checked before the regex so a 200 KB block is not backtracked over.
_ARTEFACT_MAX = 512


class _Judge:
    """One file's strings, judged. The dedupe sets are why this is a class.

    Both sets are **per file and per run of this function**, which is what they were as
    fields on the extractor. `_sql_seen` keeps one statement per line however many times
    the same text is visited; `_artefact_seen` keeps one naming act per file per line,
    and the ordering it depends on is the reader's: an interpolated string is reported
    before the plain parts it was assembled from, so `f"{root}/g.json"` keeps the fuller
    literal and the bare `"/g.json"` beneath it does not displace it.
    """

    def __init__(self, facts: FileFacts, rules: RuleSet) -> None:
        self.facts = facts
        self.rules = rules
        self._sql_seen: set[tuple[str, int]] = set()
        self._artefact_seen: set[tuple[str, int]] = set()

    def run(self) -> None:
        for lit in self.facts.literals:
            self._sql(lit)
            self._artefact(lit)
        self._claim_module_scope()

    def _claim_module_scope(self) -> None:
        """Put the module scope in the map if one of these strings turned out to be a fact.

        **The module scope is a routine only where something belongs to it**, and until
        this split that was true by accident: whichever fact asked the reader who owned it
        did the minting, so a file with nothing at module level got no such routine because
        nothing had asked. A string has to name an owner *before* anybody knows whether it
        is a fact, so asking there minted 65 of Comitia's 628 -- routines owning nothing,
        inflating every routine count in the map by 1.3%, decided by whether a string
        cleared a bound that exists to save wire (rule 96, and rule 49: the filter that hides
        is the one whose effect looks like an ordinary number).

        So the reader prepares the row and this claims it. Idempotent, and the membership
        test is on the **id** rather than the object, because over a pipe the prepared row
        and the recorded one are two decodings of the same fact and not one object.
        """
        scope = self.facts.module_scope
        if scope is None:
            return
        claimed = {rec.routine_id for rec in self.facts.sql}
        claimed |= {rec.routine_id for rec in self.facts.artefacts}
        if scope.id in claimed and not any(r.id == scope.id for r in self.facts.routines):
            self.facts.routines.append(scope)

    def _artefact(self, lit: StringLiteral) -> None:
        """A string literal that names a file the program uses.

        Precision is bought entirely by the extension list in `detectors/*.yaml`
        (rule 5): a trailing dotted part is not a file extension, or `"1.2.3"`,
        `"utf-8"` and `"lictores.cli"` would all read as named files. Everything
        else here is a guard against reading prose as a path.

        The literal is recorded whole (rule 8). The basename is what gets matched,
        because `.lictores/vestiarium.db` and `vestiarium.db` name the same file.
        """
        raw = lit.text.strip()
        if not raw or len(raw) > _ARTEFACT_MAX or any(ch.isspace() for ch in raw):
            return
        if "://" in raw:            # a URL is a network boundary, not a local artefact
            return
        base = raw.replace("\\", "/").rsplit("/", 1)[-1]
        if "." not in base[1:]:     # leading dot is a hidden file, not an extension
            return
        stem, _, ext = base.rpartition(".")
        kind = self.rules.artefact_kind(ext)
        if kind is None or not stem:
            return
        # `?` is the placeholder a reader leaves where a value was interpolated, and it is
        # a placeholder **only there**. A stem that is only a placeholder names nothing a
        # reader could look up; the same character in a string somebody typed is a glob,
        # which `is_pattern` below says so. That distinction is `LiteralKind`'s whole job,
        # and until it existed both readings ran together and the glob lost (rule 30).
        if lit.kind is LiteralKind.INTERPOLATED and "?" in stem:
            return
        if not any(ch.isalnum() for ch in stem):
            return
        if not _ARTEFACT_NAME.match(base):
            return
        if (base, lit.line) in self._artefact_seen:
            return
        self._artefact_seen.add((base, lit.line))
        self.facts.artefacts.append(Artefact(
            name=base, stem=stem, ext=ext.lower(), kind=kind,
            routine_id=lit.routine_id, line=lit.line, literal=lit.text,
            is_pattern=any(ch in base for ch in "*?["),
        ))

    def _sql(self, lit: StringLiteral) -> None:
        text, line = lit.text, lit.line
        if len(text) < 6 or len(text) > LITERAL_MAX:
            return
        chunks = text.split(";") if text.count(";") else [text]
        for chunk in chunks[:_MAX_STATEMENTS]:
            if not sqlmod.looks_like_sql(chunk):
                continue
            op = sqlmod.parse(chunk)
            if op is None:
                continue
            key = (op.sql[:80], line)
            if key in self._sql_seen:
                continue
            self._sql_seen.add(key)
            self.facts.sql.append(SqlStatement(
                routine_id=lit.routine_id, operation=op.operation,
                direction=op.direction, tables=op.tables, sql=op.sql, line=line,
            ))
            if op.operation == "CREATE TABLE":
                td = sqlmod.parse_table_def(chunk)
                if td and td.name:
                    self.facts.tables.append(TableSchema(
                        name=td.name, file=self.facts.path, line=line,
                        temporary=td.temporary,
                        columns=[(c.name, c.type, c.constraints) for c in td.columns],
                    ))
            elif op.operation == "CREATE INDEX":
                for ix in sqlmod.parse_index_defs(chunk):
                    self.facts.indexes.append(IndexSchema(
                        name=ix.name, table=ix.table, columns=ix.columns,
                        file=self.facts.path, line=line, unique=ix.unique,
                    ))


def judge(facts: FileFacts, reports_literals: bool = True) -> FileFacts:
    """Fill `sql`, `tables`, `indexes` and `artefacts` from what the reader reported.

    In place and returning the same object, on `stamp_lang`'s precedent: this is a host
    pass over facts that have arrived, not a transformation into something else.

    **A reader that sends those four is refused rather than believed**, and that is rule 30
    rather than tidiness. They are this module's answers now; a plugin that supplies one is
    offering a second answer to a question the host has already been given the evidence
    for, and two answers are only ever noticed when they differ -- which is long after the
    map was written. The same argument, one field over, as `stamp_lang`'s refusal of a
    record that brings its own language.

    `reports_literals` is the plugin's declared capability, and a **disagreement with it
    is refused both ways**: a reader that declared it sends none, and one that declared it
    does not sends some. A capability is a claim the manifest makes and the running process
    is the identity (rule 30), and the silent version of the first is the expensive one --
    a language reporting no literals reports no SQL and no artefacts, which is
    indistinguishable from a language that touches no database and names no files.
    """
    supplied = [
        name for name in ("sql", "tables", "indexes", "artefacts")
        if getattr(facts, name)
    ]
    if supplied:
        raise PluginRefused(
            f"{facts.path} arrived from the {facts.lang} reader already carrying "
            f"{', '.join(supplied)}. What a string means is the host's answer, decided in "
            f"`ingest/literals.py` for every language at once; a reader that judged its "
            f"own would make the same text read two ways in two languages."
        )
    if facts.literals and not reports_literals:
        raise PluginRefused(
            f"the {facts.lang} reader declares `reports_literals: false` and sent "
            f"{len(facts.literals):,} for {facts.path}. A capability is what the manifest "
            f"claims and the running process is the identity; the two disagreeing means "
            f"nobody can say what else the manifest is wrong about."
        )
    if not reports_literals:
        # A real answer and not an empty one: this language contributes no SQL and no
        # named files, on purpose, and `walk` says so in its own words rather than
        # leaving a reader to read the absence as a program that touches no database.
        return facts
    _Judge(facts, load_rules(facts.lang)).run()
    return facts
