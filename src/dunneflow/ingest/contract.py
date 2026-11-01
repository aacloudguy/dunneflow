"""What a reader of source code has to be, and what it may refuse.

`schema.py` says what every extractor *emits*. This says what one *is*: a thing that
claims some suffixes, needs some toolchain, and turns files into `FileFacts`. The two
halves are separate on purpose — a language's facts are a contract with the whole tool,
and how they were read is a contract with this module alone.

**Modelled on `canonical/__init__.py`, which is the one seam this codebase already got
right**: a suffix table, a dispatch table, and a named honest answer where nobody claims
the suffix. The one thing a canonicaliser never needs and a reader does is a way to say
*I cannot run here* — because a canonicaliser is this interpreter and a reader may be a
program on the far side of a pipe that is not installed.

The three exceptions are three different facts and are never collapsed (rule 49):
`ToolchainMissing` is the machine's, and a reader can act on it; `PluginRefused` is this
build's, and a reader cannot; `ProtocolError` is the plugin's, and it means what came back
cannot be trusted rather than that it was empty.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ..schema import DataStructure, FileFacts, Routine, SuppliedEdge

ProgressFn = Callable[[str, int, int], None]

# **What a reader must read, and it was an accident of a default until it cost two files.**
#
# The host opens a source file with `Path.read_text(encoding="utf-8", errors="replace")`,
# and Python reads text files with **universal newlines** on: `\r\n` and a lone `\r` both
# arrive as `\n`. Every hash the host computes — `content_hash`, `Routine.body_hash`, the
# blob key in `source.db` — is of *that* text, and the in-process reader is handed the same
# string, so Python could never disagree with itself.
#
# A reader in another runtime reads bytes. Node's `readFileSync(p, "utf8")` keeps the
# carriage returns, so a CRLF file hashes differently on the two sides — and the echo check
# in `OutOfProcessPlugin._one` then refuses it, correctly and with the wrong reason: the
# file did not change, the two sides read it differently. Measured on `../uigen`: **2 of 54
# files**, both generated with CRLF, both reported unreadable in a map that was otherwise
# perfect, and neither would ever have been read on any later run.
#
# So it is a term of the protocol rather than a property of one implementation, and it is
# stated here because this is the file a plugin author reads. There is no way for the host
# to enforce it — the enforcement *is* the echo, which is why the echo exists.
SOURCE_TEXT = "utf-8, errors replaced, newlines normalised to \n"



class ToolchainMissing(RuntimeError):
    """The thing that reads this language is not on this machine.

    Never a defect and always recoverable, which is why it is not `PluginRefused`. The
    sentence must name the language, the command, the version wanted, the version found
    if there was one, **how many files will therefore not be read**, and both ways
    forward — install it, or run again declining the language and have the map say so
    (rules 49 and 89).
    """


class PluginRefused(RuntimeError):
    """This build cannot use this plugin, and no reader can fix it.

    A manifest that disagrees with the running process, two plugins claiming one suffix,
    a protocol version this build does not speak. Always a build or packaging defect,
    like `RulesMissing`, and raised rather than worked around: a plugin admitted on a
    disagreement is a plugin whose facts nobody can vouch for.
    """


class ProtocolError(RuntimeError):
    """What came back was not this protocol.

    Raised once and loudly rather than absorbed per file. A line that will not parse is
    not a file that failed — it means the channel is carrying something other than what
    this module reads, and every fact already taken from it is suspect. Skipping six
    hundred of these quietly is how a map comes back confident and empty.
    """


def stamp_lang(facts: FileFacts) -> FileFacts:
    """Write the file's language onto every record inside it, and refuse a second answer.

    **A language travels in exactly one place**, `FileFacts.lang`, and this is the one
    place it is copied down onto the routines and structures below it (rule 51). A plugin
    never sets it: it cannot then forget it on one record out of forty, and it cannot
    disagree with itself. For an out-of-process reader this is what the codec does on
    decode; in this process it is done here, so both kinds of reader are stamped by the
    same function rather than by two that have to be kept in step.

    A record that arrives **already carrying** a language is refused rather than
    overwritten, and rather than accepted. It is a host-derived field, so a value in it
    is a second answer to a question the file has already answered — and the two are only
    ever noticed when they differ, which is long after the map was written.
    """
    if not facts.lang:
        raise PluginRefused(
            f"{facts.path} came back with no language on it. A reader says what it read; "
            f"a file whose language is blank cannot be routed, cannot be resolved by the "
            f"right rules, and would be stored as a fact about nothing."
        )
    # `module_scope` is here because it is a record inside these facts like any other,
    # and it is the one the host may still append *after* this ran: `ingest.literals.judge`
    # claims it when a string turns out to be a fact. Stamped here whether or not it is
    # ever claimed -- where the reader already recorded module-level work it is the same
    # object as the one in `routines` and stamping it twice writes the same value.
    records: list[Routine | DataStructure] = [*facts.routines, *facts.structures]
    if facts.module_scope is not None:
        records.append(facts.module_scope)
    for record in records:
        if record.lang and record.lang != facts.lang:
            raise PluginRefused(
                f"{facts.path} is {facts.lang!r} and carries a record claiming "
                f"{record.lang!r} ({record.id}). The language is the file's answer and "
                f"the host's to write; a record that brings its own is a second answer "
                f"to one question."
            )
        record.lang = facts.lang
    return facts


@dataclass(frozen=True, slots=True)
class DiscoveryRules:
    """How one language spells *mine*, *never look here*, and *this is a test*.

    Per language, never global, and the asymmetry between the three is the point.

    **`suffixes` is a union** across plugins: a suffix belongs to exactly one language and
    the walk needs all of them to know what to offer anybody.

    **`skip_dirs` is NOT a union**, and this is the one that bites. A TypeScript plugin
    adding `out` to a shared set would take `out/` out of the *Python* corpus too, which
    is a plugin quietly shrinking somebody else's map. So these are applied at the **file**
    level, after the suffix has already said which language owns the file; the walk prunes
    directories only on the set every language genuinely agrees about. It costs a descent
    that finds nothing, and it buys a plugin that can contribute a filter without being
    able to impose one.

    **`skip_names` is the third kind of *not mine*, and it was paid for.** uigen vendors a
    generated Prisma client as `src/generated/prisma/*.d.ts`: read as program source it
    contributed 500-odd routines with no bodies and **83 BROKEN anomalies**, every one an
    overload set in a library's declarations reported as a name collision in somebody's
    program -- and `dunneflow check` exits non-zero on BROKEN. A `.d.ts` is TypeScript's
    header file: it declares and never implements, so a routine from one is a signature
    and not a routine. Measured against what it costs: `types/next-auth.d.ts` in DunneCorp
    is 3 genuine interfaces, and they go with it. Stated rather than hidden -- the walk
    names the count.

    **The test rules are three shapes because languages spell a test three ways**, and
    `test_suffixes` exists because the obvious spelling is wrong. `Path("client.test.ts")`
    has stem `"client.test"`, which starts with neither `test_` nor ends with `_test`, so
    Python's rule admits every TypeScript test there is — measured at **322 of DunneNote's
    767 `.ts` files**, 42% of the corpus, all of it counted as program code.

    **The stem markers are three fields rather than one, and that is not bureaucracy.** The
    obvious design is a single list of words matched "at an edge", and it is wrong in both
    directions at once: it would newly catch a file called `test.py` and one called
    `helpers_conftest.py`, neither of which Python's rule catches today, and getting that
    wrong silently changes which files are in the map. So each marker says which edge it
    lives on and carries its own separator, and what a manifest declares is exactly the
    rule rather than a generalisation of it.

    Matching is at an **edge** and never a substring, which is rule 5's precision and was
    paid for: `_test_stage.py` is the Test stage of a pipeline, `_test_extras_schemas.py`
    declares schemas, and all three were once dropped from a map — routines, boundaries,
    comments and all — for containing the word.
    """

    lang: str
    suffixes: frozenset[str]
    skip_dirs: frozenset[str] = frozenset()
    # The END of the whole filename, for a file this language claims by suffix and does
    # **not** consider program source: `.d.ts`. Not a test, not a directory, and not a
    # suffix the walk could route away -- a declaration file is `.ts` and belongs to the
    # TypeScript reader, which is exactly why only that reader can say it is a header
    # rather than a program.
    skip_names: tuple[str, ...] = ()
    # Any path component equal to one of these makes everything below it a test.
    test_dirs: frozenset[str] = frozenset()
    # The END of the whole filename, separator included: `.test.ts`, `.spec.tsx`.
    test_name_suffixes: tuple[str, ...] = ()
    # The START of the stem, separator included: `test_`.
    test_stem_prefixes: tuple[str, ...] = ()
    # The END of the stem, separator included: `_test`.
    test_stem_suffixes: tuple[str, ...] = ()
    # The WHOLE stem: `conftest`.
    test_stem_exact: frozenset[str] = frozenset()

    def is_test(self, rel: Path) -> bool:
        """Is this a test, as opposed to a file that has something to do with testing?"""
        if any(p in self.test_dirs for p in rel.parts):
            return True
        if any(rel.name.endswith(s) for s in self.test_name_suffixes):
            return True
        stem = rel.stem
        return (
            stem in self.test_stem_exact
            or stem.startswith(self.test_stem_prefixes)
            or stem.endswith(self.test_stem_suffixes)
        )


@dataclass(frozen=True, slots=True)
class Toolchain:
    """What has to be on the machine before this plugin can read anything.

    `None` for a plugin that runs in this interpreter, and that is a real answer rather
    than an empty one: Python's reader needs nothing because it *is* the thing asking.
    """

    command: str
    probe: tuple[str, ...] = ("--version",)
    min_version: str = ""
    install: str = ""


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """A plugin as it describes itself on disk, before anything has been run.

    **A label, not an identity** (rule 30). Everything here is a claim the file makes; an
    out-of-process plugin is asked the same questions again over the wire and any
    disagreement refuses the language quoting both answers. For an in-process plugin the
    two cannot disagree, and that is the whole difference between them.

    `fingerprint` **names files and never globs**, and that is rule 12 rather than taste.
    `fingerprint_files` refuses an empty list, because a hash of nothing is
    `e3b0c44298fc1c14` and looks exactly like a hash — but a glob over a directory that
    was not bundled returns `[]` and so blames the *whole build* for one missing plugin.
    Named files hit the other refusal, which can say which plugin and which file, and that
    is the sentence somebody can act on (rule 89).
    """

    lang: str
    # What to call this language in a sentence a person reads. `lang` is the key -- it is
    # what `files.lang` stores, what a suffix maps to and what a manifest declares -- and
    # `python` is not how the word is spelled in prose. The plugin says it, because the
    # alternative is a table of display names kept beside the manifests and out of step
    # with them (rule 51); a plugin that says nothing is called by its key, which is
    # honest rather than guessed.
    display: str
    version: str
    protocol: int
    schema_version: int
    discovery: DiscoveryRules
    # The `detectors/<name>` rules file. Empty means this language deliberately declares
    # no rules — which is a different fact from "the file is missing" and is why
    # `load_rules` may not answer an undeclared language with an empty `RuleSet`.
    rules: str = ""
    toolchain: Toolchain | None = None
    entry: str = ""
    workers: int = 1
    # **Whether this reader claims to run in this interpreter**, which is a claim and not
    # a decision: `ingest._IN_PROCESS` decides, and a manifest that disagrees with it is
    # refused naming both (rule 30). It was declared and read by nothing at all until the
    # fingerprint needed to know which kind of reader it was hashing.
    in_process: bool = False
    # Where the reader lives, **relative to the package root** rather than to this
    # plugin's directory -- an in-process reader is part of this program, so
    # `extractors/python` is a path in the same tree. Empty for a reader on the far side
    # of a pipe, whose own bytes are its `fingerprint` files. One of the two is always
    # required: a reader whose bytes are in no key is rule 12 unenforced, and a build that
    # cannot say which files those are cannot enforce it later either.
    reader: str = ""
    receiver_words: tuple[str, ...] = ()
    supplies_edges: bool = False
    reports_literals: bool = False
    # Relative to the plugin's own directory. Never a glob — see above.
    fingerprint: tuple[str, ...] = ()
    # **A reader shipped as source and built on this machine before it is first run.** The
    # argv of the build, run in the plugin's own directory, with `{output}` standing for the
    # path the program is to be written to; empty for a reader that runs as it is shipped.
    # Added for Go, whose checker needs the `go` toolchain at run time anyway, so building
    # with it costs nothing more than being able to run at all. Shipping one binary per
    # platform instead would give one `fingerprint` per platform, and a map written on one
    # machine would then be refused as stale on another (rule 12).
    build: tuple[str, ...] = ()
    # **Where a build that cannot be told where to write leaves its program.** Added for
    # Rust: `cargo build` writes `<target-dir>/release/<bin>` and nothing on stable can name
    # that file, so such a build is given `{workdir}`, a scratch directory outside the
    # package, and `product` is the path inside it that the host copies to `{output}`. One
    # of the two placeholders always says where the program lands; the `.exe` is the host's.
    product: str = ""
    # **The environment a build runs under, declared by the language it belongs to.** A
    # value of `None` removes that variable. It was Go's four names spelt in the host until
    # Rust, which is the host naming a language one layer below where rule 92 looked.
    build_env: tuple[tuple[str, str | None], ...] = ()
    root: Path = field(default=Path("."), compare=False)


class IngestPlugin(Protocol):
    """One language's reader.

    The lifecycle is `probe` · `open` · `extract` · `edges` · `close`, and `open` is not a
    formality.
    An in-process reader needs nothing from it; a reader that resolves symbols needs **every
    file in the compilation**, including the ones whose content hash says they have not
    changed, because a type checker over a subset is a type checker that answers wrongly.
    So `open` takes the whole file set and `extract` takes only what the cache missed, and
    the incremental path falls out of the shape rather than being bolted onto it.
    """

    manifest: PluginManifest
    # Files the last `extract` could not deliver **at all**, as opposed to files that came
    # back carrying an error. The two are different facts and only one of them is visible
    # to the host: a file that will not parse arrives as an empty `FileFacts` with its
    # error on it and the host counts that off `ff.errors`, while a file whose reader died
    # never arrives, so the reader is the only thing that can say it existed. Without this
    # a crashed worker is a file that silently leaves the map — design rule 1, one process
    # over. Reset by `extract`, because a plugin outlives one call.
    lost: int
    # What the last `edges` could not turn into an edge, in **two numbers because they are
    # two facts** (design rule 21). `edges_outside` is a call whose far end the reader named
    # and this map does not hold — a library, a `.d.ts`, a declaration with no body — which
    # is an external call the map is right about. `edges_unknown` is a call the reader could
    # not resolve at all, which is the reader's limit. Flattened, a healthy map of a program
    # that leans on its dependencies reads exactly like a reader that has stopped resolving.
    #
    # `edge_notes` is the fields an edge carried that this build does not read. All three
    # are `lost`'s shape and exist for its reason: only the reader can count what never left
    # it, and a number nobody holds is a filter nobody can see (design rule 1).
    edges_outside: int
    edges_unknown: int
    edge_notes: list[str]
    # **What a reader read from outside the analysed tree to name its frontier, and what it
    # looked for and did not find** -- Rust's dependency sources out of the local cargo
    # cache, never fetched (design rule 14). A reader that reads nothing beyond the tree
    # leaves both empty; one that does must say so, because a frontier read against a
    # dependency is a claim about code that is not in the map (design rule 1).
    edges_read_beyond: list[str]
    edges_not_present: list[str]
    # What the reader said when `open` built its session — how it divided the file set
    # into compilations, how long that took, whatever else it has to declare. Empty for a
    # reader that opens nothing, and the `opened` frame carried both fields for three
    # chunks with the host discarding them (rule 35).
    opened_notes: list[str]

    def probe(self) -> None:
        """Raise `ToolchainMissing` if this machine cannot run this reader.

        Asked once, at pre-flight, **before any store is opened** — the placement
        `cmd_analyze` already uses for `--standards`, so a refusal never abandons a
        half-written map.
        """
        ...

    def open(self, root: Path, all_files: Sequence[Path]) -> None:
        """Every file this language owns in the tree, changed or not."""
        ...

    def extract(self, work: Sequence[Path], root: Path,
                progress: ProgressFn | None = None,
                jobs: int | None = None) -> Iterator[FileFacts]:
        """Facts for the files that missed the cache, in any order.

        `jobs` is **the machine's owner speaking, not the host's opinion of the reader**,
        and that is why it crosses a seam that otherwise leaves parallelism entirely to
        the plugin. It is `--jobs`, typed by somebody who knows what else this machine is
        doing; how many files that means at once is still the reader's to decide, and a
        reader with nothing to spend it on ignores it. Leaving it out would have made
        `--jobs` a flag that silently stopped reaching the only extractor there is.
        """
        ...

    def edges(self) -> Iterator[SuppliedEdge]:
        """Where this language's calls go, if this reader's toolchain already knows.

        Asked **once per session**, after `extract` and before `close`, and only where the
        manifest declares `supplies_edges` -- so a reader that resolves nothing is never
        asked and a reader that does is asked whether or not any file changed this run.

        It answers about the **whole compilation**, not about the files `extract` was
        given, which is why it takes no arguments: the checker's answer for one file is
        built out of all of them, so an answer restricted to what changed would be an
        answer built from a subset and wrong rather than partial. The host replaces the
        stored set whole (`Store.replace_supplied_edges`).

        An empty iterator is a real answer, not an omission, and `InProcessPlugin` gives
        it in words.
        """
        ...

    def close(self) -> None:
        """Release whatever `open` took. Must be safe to call twice."""
        ...

    def stamp(self) -> str:
        """This reader's contribution to the cache key (rule 12)."""
        ...
