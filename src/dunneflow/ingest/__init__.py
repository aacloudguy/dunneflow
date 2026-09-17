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
from .inprocess import InProcessPlugin, _extract_one

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
_IN_PROCESS = {"python": _extract_one}


def _rules(block: dict[str, Any], lang: str) -> DiscoveryRules:
    return DiscoveryRules(
        lang=lang,
        suffixes=frozenset(str(s).lower() for s in block.get("suffixes", [])),
        skip_dirs=frozenset(str(s) for s in block.get("skip_dirs", [])),
        test_dirs=frozenset(str(s) for s in block.get("test_dirs", [])),
        test_name_suffixes=tuple(str(s) for s in block.get("test_name_suffixes", [])),
        test_stem_prefixes=tuple(str(s) for s in block.get("test_stem_prefixes", [])),
        test_stem_suffixes=tuple(str(s) for s in block.get("test_stem_suffixes", [])),
        test_stem_exact=frozenset(str(s) for s in block.get("test_stem_exact", [])),
    )


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

    tc = data.get("toolchain")
    toolchain = None
    if isinstance(tc, dict):
        toolchain = Toolchain(
            command=str(tc.get("command", "")),
            probe=tuple(str(x) for x in tc.get("probe", ("--version",))),
            min_version=str(tc.get("min_version", "")),
            install=str(tc.get("install", "")),
        )

    return PluginManifest(
        lang=lang,
        version=str(data.get("version", "")),
        protocol=protocol,
        schema_version=declared,
        discovery=rules,
        rules=str(data.get("rules", "")),
        toolchain=toolchain,
        entry=str(data.get("entry", "")),
        workers=int(data.get("workers", 1)),
        receiver_words=tuple(str(x) for x in data.get("receiver_words", [])),
        supplies_edges=bool(data.get("supplies_edges", False)),
        reports_literals=bool(data.get("reports_literals", False)),
        fingerprint=tuple(str(x) for x in data.get("fingerprint", [])),
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
        for suffix in sorted(m.discovery.suffixes):
            if suffix in suffix_owner:
                raise PluginRefused(
                    f"{suffix} is claimed by both {suffix_owner[suffix]!r} and {m.lang!r}. "
                    f"A suffix belongs to one reader; whichever of the two was listed "
                    f"first is not a decision this tool can defend."
                )
            suffix_owner[suffix] = m.lang
        manifests[m.lang] = m

        reader = _IN_PROCESS.get(m.lang)
        if reader is not None:
            plugins[m.lang] = InProcessPlugin(m, reader)
        else:
            raise PluginRefused(
                f"the {m.lang} plugin at {m.root} is not an in-process reader and this "
                f"build has no worker for it yet."
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
