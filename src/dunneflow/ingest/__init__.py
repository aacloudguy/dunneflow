"""Which reader owns a file, and nothing else.

**This is `canonical/__init__.py`'s shape, one subject over**, and deliberately so: that
module is a suffix table, a dispatch table and an honest answer where nobody claims the
suffix, and it has been the only correct plugin seam in this codebase since it was
written. Its own docstring already set the design — *"adding a language touches two
places… `extractors/<lang>/` reads facts, and `canonical/<lang>.py` says when two
expressions are the same"* — and what was missing was a third: somewhere to say **which
reader** a file goes to. `walk.py` imported one extractor by name and its `discover()`
took `frozenset({".py"})` as a default argument that its only caller never overrode, so
the language of a file was not a question anybody asked.

**`LANG_SUFFIX` moves here from `canonical`, and it becomes derived rather than declared.**
Its comment there read *"it is here now because here is the one place that consults it"*,
which stopped being true the moment a walk and a registry consulted it — rule 51 says move
a rule to where every caller passes. Derived from the manifests, because a table written by
hand beside a set of manifests is a second answer waiting to disagree with the first.

**Discovery is `resource_root()/plugins/*/plugin.json` and nothing else** — no entry-point
group, no environment override. Three reasons, in descending weight. An entry-point group
is live in a checkout and inert in the signed application that is the shipped product, and
`runtime.py` exists as a whole module to stop that split. `fingerprint_files` labels an
input by its path relative to the package root and falls back to a bare filename for
anything outside it, so two plugins each shipping `main.mjs` would hash under one label and
rule 12 could not be satisfied. And a test asserts that nothing on the ingest path imports
an HTTP client or a model SDK — a guarantee that is printed on screen, and one that
admitting arbitrary third-party code would quietly retire.

A second discovery path is a second door a plugin can enter the cache key through, which is
why there is one.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ..runtime import resource_root
from ..schema import SCHEMA_VERSION
from .contract import (
    DiscoveryRules,
    IngestPlugin,
    PluginManifest,
    PluginRefused,
    Toolchain,
)
from .contract import (
    stamp_lang as stamp_lang,  # re-exported: `ingest.stamp_lang` is where callers look
)
from .inprocess import (
    InProcessPlugin,
    _extract_one,
    _extract_one_kotlin,
)
from .outofprocess import OutOfProcessPlugin

# Settled at import, on `detectors/__init__.py`'s precedent and for its reason: an
# application does not become a source checkout halfway through a run.
PLUGINS_DIR = resource_root() / "plugins"

# The protocol generation this build speaks. A manifest declaring another one is refused
# rather than read optimistically — a plugin that half-speaks a protocol produces facts
# nobody can vouch for, which is worse than a plugin that does not run.
PROTOCOL = 1

# Readers that are this interpreter. Named here rather than imported by a dotted string
# out of the manifest, and that is the whole difference between a plugin table and an
# entry-point group: what may run in this process is decided by this file, which is in the
# cache key and under test, and never by a name in a data file.
_IN_PROCESS = {"python": _extract_one, "kotlin": _extract_one_kotlin}


def _rules(block: dict[str, Any], lang: str) -> DiscoveryRules:
    return DiscoveryRules(
        lang=lang,
        suffixes=frozenset(str(s).lower() for s in block.get("suffixes", [])),
        skip_dirs=frozenset(str(s) for s in block.get("skip_dirs", [])),
        skip_names=tuple(str(s) for s in block.get("skip_names", [])),
        test_dirs=frozenset(str(s) for s in block.get("test_dirs", [])),
        test_name_suffixes=tuple(str(s) for s in block.get("test_name_suffixes", [])),
        test_stem_prefixes=tuple(str(s) for s in block.get("test_stem_prefixes", [])),
        test_stem_suffixes=tuple(str(s) for s in block.get("test_stem_suffixes", [])),
        test_stem_exact=frozenset(str(s) for s in block.get("test_stem_exact", [])),
    )


def plugin_fingerprint_files(lang: str) -> list[Path]:
    """Every file whose bytes decide what this reader does.

    Two shapes, and each is the honest one for its kind. A reader on the far side of a
    pipe is its **built bundle** -- `plugin.json` and `main.bundle.mjs`, named rather than
    globbed (rule 12: a glob over a directory that was not bundled returns nothing and
    blames the whole build for one missing plugin), and never its source tree and never
    `node_modules`. A reader that runs in this interpreter is a package in this program,
    so its whole tree is globbed: it cannot forget a file somebody adds, which is the
    defence the extraction keys were built on.
    """
    plugin = PLUGINS.get(lang)
    if plugin is None:
        raise PluginRefused(f"nothing in this build reads {lang!r}.")
    m = plugin.manifest
    out = [m.root / name for name in m.fingerprint]
    if m.reader:
        out += [p for p in (resource_root() / m.reader).rglob("*.py")
                if "__pycache__" not in p.parts]
    return out


def suffix_owners(rules: Sequence[DiscoveryRules]) -> dict[str, str]:
    """Which language owns each suffix, refusing where two of them both do.

    **The one place that question is answered** (rule 51). `_load()` asks it of the
    plugins this build ships and `walk.discover` asks it of whatever rules it was handed,
    so a walk and the registry cannot come to two different answers about `.js`.

    A suffix claimed twice refuses **naming both**, never first-wins: whichever the
    directory listing happened to yield first is not an order this tool can defend
    (rule 66).
    """
    owner: dict[str, str] = {}
    for r in rules:
        for suffix in sorted(r.suffixes):
            if suffix in owner and owner[suffix] != r.lang:
                raise PluginRefused(
                    f"{suffix} is claimed by both {owner[suffix]!r} and {r.lang!r}. "
                    f"A suffix belongs to one reader; whichever of the two was listed "
                    f"first is not a decision this tool can defend."
                )
            owner[suffix] = r.lang
    return owner


def read_manifest(path: Path) -> PluginManifest:
    """One `plugin.json`, validated as far as a file can be without being run.

    Everything checked here is a claim the *file* makes. An out-of-process plugin is asked
    the same questions again over the wire and any disagreement refuses the language
    quoting both answers, because a manifest is a label and the running process is the
    identity (rule 30). An in-process plugin has no wire and so cannot disagree with
    itself — which is exactly the difference the two kinds are allowed to have.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PluginRefused(f"{path} could not be read as a plugin manifest: {exc}") from exc

    lang = str(data.get("lang", "")).strip()
    if not lang:
        raise PluginRefused(f"{path} declares no language, so nothing can be routed to it.")

    protocol = int(data.get("protocol", 0))
    if protocol != PROTOCOL:
        raise PluginRefused(
            f"the {lang} plugin at {path} speaks protocol {protocol}; this build speaks "
            f"{PROTOCOL}. A plugin is never read across a protocol change — rebuild it, "
            f"or remove it and the map will say {lang} was not read."
        )

    declared = int(data.get("schema_version", 0))
    if declared != SCHEMA_VERSION:
        raise PluginRefused(
            f"the {lang} plugin at {path} was written against fact schema {declared} and "
            f"this build is schema {SCHEMA_VERSION}. The plugin's `schema_version` has to "
            f"be raised with the schema, because the facts it emits are the thing that "
            f"changed."
        )

    rules = _rules(dict(data.get("discovery", {})), lang)
    if not rules.suffixes:
        raise PluginRefused(
            f"the {lang} plugin at {path} claims no suffixes, so no file could ever reach "
            f"it. A reader that owns nothing is a reader that does nothing."
        )

    in_process = bool(data.get("in_process", False))
    reader = str(data.get("reader", "")).strip()
    fingerprint = tuple(str(x) for x in data.get("fingerprint", []))
    if in_process and not reader:
        raise PluginRefused(
            f"the {lang} plugin at {path} runs in this interpreter and does not say where "
            f"its reader lives. Its bytes would then be in no cache key at all, which is "
            f"rule 12 unenforced for every fact it produces."
        )
    if reader and not in_process:
        raise PluginRefused(
            f"the {lang} plugin at {path} is not an in-process reader and declares "
            f"`reader: {reader}`. A reader on the far side of a pipe is its own bundled "
            f"files; those belong in `fingerprint`, which is hashed, and pointing at this "
            f"package would hash something that never reads anything."
        )
    if not fingerprint:
        raise PluginRefused(
            f"the {lang} plugin at {path} names no `fingerprint` files. A plugin that "
            f"contributes nothing to the cache key cannot be told from a different "
            f"version of itself, and a declared version alone is a label that does not "
            f"move when somebody edits it (rule 30)."
        )

    build = tuple(str(x) for x in data.get("build", []))
    if build and in_process:
        raise PluginRefused(
            f"the {lang} plugin at {path} runs in this interpreter and declares a `build`. "
            f"Nothing is built for a reader that is part of this program."
        )
    product = str(data.get("product", "")).strip()
    if build and not product and "{output}" not in build:
        raise PluginRefused(
            f"the {lang} plugin at {path} declares a `build` that never says where to write "
            f"the program: none of its arguments is `{{output}}`, and it names no "
            f"`product`. A build whose product this host cannot find is a build that ran "
            f"for nothing, every time."
        )
    if product and (not build or "{workdir}" not in build):
        raise PluginRefused(
            f"the {lang} plugin at {path} names a `product` ({product}) and no `build` "
            f"argument is `{{workdir}}`, so the build is never told the directory that "
            f"product is relative to."
        )
    if product and (Path(product).is_absolute() or ".." in Path(product).parts):
        raise PluginRefused(
            f"the {lang} plugin at {path} names a `product` ({product}) outside the "
            f"build's own directory. It is relative to `{{workdir}}` and stays inside it."
        )
    raw_env = data.get("build_env", {})
    if not isinstance(raw_env, dict) or not all(
        isinstance(v, str) or v is None for v in raw_env.values()
    ):
        raise PluginRefused(
            f"the {lang} plugin at {path} declares a `build_env` that is not a table of "
            f"names to strings (or null, to remove one)."
        )
    if raw_env and not build:
        raise PluginRefused(
            f"the {lang} plugin at {path} declares a `build_env` and no `build`, so it "
            f"is the environment of nothing."
        )
    build_env = tuple(sorted((str(k), v) for k, v in raw_env.items()))
    run = tuple(str(x) for x in data.get("run", []))
    if run and not build:
        raise PluginRefused(
            f"the {lang} plugin at {path} says how to start what its build wrote (`run`) "
            f"and declares no `build`, so there is nothing for it to start."
        )
    if run and "{reader}" not in run:
        raise PluginRefused(
            f"the {lang} plugin at {path} declares a `run` that never names the program "
            f"its build wrote: none of its arguments is `{{reader}}`, so the toolchain "
            f"would be started with nothing of this reader in it."
        )

    tc = data.get("toolchain")
    toolchain = None
    if isinstance(tc, dict):
        toolchain = Toolchain(
            command=str(tc.get("command", "")),
            probe=tuple(str(x) for x in tc.get("probe", ("--version",))),
            min_version=str(tc.get("min_version", "")),
            install=str(tc.get("install", "")),
            asks_reader=bool(tc.get("asks_reader", False)),
        )

    return PluginManifest(
        lang=lang,
        display=str(data.get("display", "")).strip() or lang,
        version=str(data.get("version", "")),
        protocol=protocol,
        schema_version=declared,
        discovery=rules,
        rules=str(data.get("rules", "")),
        toolchain=toolchain,
        entry=str(data.get("entry", "")),
        workers=int(data.get("workers", 1)),
        in_process=in_process,
        reader=reader,
        receiver_words=tuple(str(x) for x in data.get("receiver_words", [])),
        rule_keys=tuple(str(x) for x in data.get("rule_keys", [])),
        supplies_edges=bool(data.get("supplies_edges", False)),
        supplies_bindings=bool(data.get("supplies_bindings", False)),
        supplies_uses=bool(data.get("supplies_uses", False)),
        supplies_macro_callees=bool(data.get("supplies_macro_callees", False)),
        facts_span_files=bool(data.get("facts_span_files", False)),
        reports_literals=bool(data.get("reports_literals", False)),
        fingerprint=fingerprint,
        build=build,
        product=product,
        build_env=build_env,
        run=run,
        root=path.parent,
    )


def _load() -> tuple[dict[str, IngestPlugin], dict[str, str]]:
    """Every plugin this build ships, and the suffix table they add up to.

    A suffix claimed twice **refuses at import, naming both** — never first-wins. `.js` is
    the case that will actually arrive: a TypeScript reader and some future Node reader can
    both make a reasonable claim on it, and whichever the directory listing happened to
    yield first is not an answer anybody could defend (rule 66).
    """
    plugins: dict[str, IngestPlugin] = {}
    suffix_owner: dict[str, str] = {}
    manifests: dict[str, PluginManifest] = {}

    for manifest_path in sorted(PLUGINS_DIR.glob("*/plugin.json")):
        m = read_manifest(manifest_path)
        if m.lang in manifests:
            raise PluginRefused(
                f"two plugins declare the language {m.lang!r}: "
                f"{manifests[m.lang].root} and {m.root}."
            )
        suffix_owner = suffix_owners([*(x.discovery for x in manifests.values()),
                                      m.discovery])
        manifests[m.lang] = m

        runs_here = _IN_PROCESS.get(m.lang)
        if m.in_process != (runs_here is not None):
            # A manifest is a label and the code is the identity (rule 30). The two
            # disagreeing means either a plugin claiming to be part of this program when
            # it is not, or a reader running here that nothing declared -- and the second
            # is the one that would quietly skip the checks above.
            raise PluginRefused(
                f"the {m.lang} plugin at {m.root} declares in_process="
                f"{str(m.in_process).lower()} and this build "
                f"{'has' if runs_here else 'has no'} in-process reader for it. What runs "
                f"in this process is decided by `ingest._IN_PROCESS`, never by a data "
                f"file, and a disagreement about that is a build defect."
            )
        # The two kinds, and the manifest has already been cross-checked against
        # `_IN_PROCESS` above — so this is a dispatch and never a judgement.
        plugins[m.lang] = (
            InProcessPlugin(m, runs_here) if runs_here is not None
            else OutOfProcessPlugin(m)
        )

    if not plugins:
        raise PluginRefused(
            f"no plugins were found under {PLUGINS_DIR}. This copy of DunneFlow was "
            f"assembled without its readers, which is a build defect and not something a "
            f"reader can put right."
        )
    return plugins, suffix_owner


PLUGINS, LANG_SUFFIX = _load()


def language_of(path: str | Path) -> str | None:
    """Which language owns this file, or `None` where nobody claims the suffix.

    `None` is an answer and not a failure — the same honest shape `canonical()` takes when
    no language can say whether two expressions are the same. What must never happen is
    the file being read *anyway* by whichever reader was nearest.
    """
    return LANG_SUFFIX.get(Path(path).suffix.lower())


def plugin_for(path: str | Path) -> IngestPlugin | None:
    lang = language_of(path)
    return PLUGINS.get(lang) if lang else None


def decline(names: Sequence[str]) -> frozenset[str]:
    """Turn what somebody typed into languages this build has, or refuse naming both.

    **The one place a declined name is judged** (rule 51), because there are three callers
    now and the failure they share is silent: `--without pythn` that is simply not in the
    set reads as a run that declined nothing, and the difference between *I turned Python
    off* and *I typed it wrong* is the entire map (rule 49).

    **Declining every language is refused too.** It is not a smaller map, it is a map with
    no code in it, and a reader who meant `--no-docs` should be told rather than handed one.

    The word is matched case-insensitively and nothing else is normalised: `lang` is a key
    and `display` is prose, and matching the prose would make *TypeScript* and *typescript*
    two ways to say one thing in a value that is compared as a string everywhere else
    (rule 30).
    """
    asked = {n.strip().lower() for n in names if n and n.strip()}
    if not asked:
        return frozenset()
    unknown = sorted(asked - set(PLUGINS))
    if unknown:
        raise PluginRefused(
            f"nothing in this build reads {', '.join(repr(u) for u in unknown)}, so "
            f"declining it would change nothing. This build reads: "
            f"{', '.join(sorted(PLUGINS))}."
        )
    if asked >= set(PLUGINS):
        raise PluginRefused(
            f"that declines every language this build reads ({', '.join(sorted(PLUGINS))}), "
            f"which is a map with no code in it rather than a smaller one. To read the "
            f"documentation alone, analyse and read the Document lane; to skip the "
            f"documentation, use --no-docs."
        )
    return frozenset(asked)


def enabled(declined: frozenset[str] = frozenset()) -> dict[str, IngestPlugin]:
    """The plugins this run will use, minus the ones the reader declined by name."""
    return {lang: p for lang, p in PLUGINS.items() if lang not in declined}


def suffixes(declined: frozenset[str] = frozenset()) -> frozenset[str]:
    """Every suffix a walk should offer somebody. A union, unlike the skip sets."""
    return frozenset(
        s for s, lang in LANG_SUFFIX.items() if lang not in declined
    )


def discovery(declined: frozenset[str] = frozenset()) -> tuple[DiscoveryRules, ...]:
    return tuple(
        p.manifest.discovery for lang, p in PLUGINS.items() if lang not in declined
    )
