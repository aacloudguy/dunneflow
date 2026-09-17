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

from ..schema import FileFacts

ProgressFn = Callable[[str, int, int], None]


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
    receiver_words: tuple[str, ...] = ()
    supplies_edges: bool = False
    reports_literals: bool = False
    # Relative to the plugin's own directory. Never a glob — see above.
    fingerprint: tuple[str, ...] = ()
    root: Path = field(default=Path("."), compare=False)


class IngestPlugin(Protocol):
    """One language's reader.

    The lifecycle is `probe` · `open` · `extract` · `close`, and `open` is not a formality.
    An in-process reader needs nothing from it; a reader that resolves symbols needs **every
    file in the compilation**, including the ones whose content hash says they have not
    changed, because a type checker over a subset is a type checker that answers wrongly.
    So `open` takes the whole file set and `extract` takes only what the cache missed, and
    the incremental path falls out of the shape rather than being bolted onto it.
    """

    manifest: PluginManifest

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
                progress: ProgressFn | None = None) -> Iterator[FileFacts]:
        """Facts for the files that missed the cache, in any order."""
        ...

    def close(self) -> None:
        """Release whatever `open` took. Must be safe to call twice."""
        ...

    def stamp(self) -> str:
        """This reader's contribution to the cache key (rule 12)."""
        ...
