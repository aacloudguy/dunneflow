"""Do a frozen binary and this checkout still agree about who read what?

Rule 12 puts the reader in the cache key, so a map is readable by another build only if
that build computes the same stamps. Chunk 5 split the one stamp into two kinds -- a
**core** stamp for what every language passes through, and a **per-language** stamp for
one reader's rules and bytes -- and a build whose core agrees while its TypeScript reader
does not will open a Python map perfectly and refuse a TypeScript one.

**This file exists because a shell script is a bad place to ask a Python question.** Both
`release-linux.sh` and `release.ps1` asked it by writing `from dunneflow.detectors import
rules_fingerprint` inline; chunk 5 renamed that function, and both steps have been raising
`ImportError` ever since -- in the step written to defend rule 12, on no test path, saying
nothing. That is rule 51 exactly: a rule kept at a call site rots as callers are added, and
there were three callers with three spellings and one of them (macOS) had never asked at
all. So the question is asked here, once, and the three scripts call this.

**The comparison is the thing that would actually fail, not a proxy for it.** Printing two
hex strings and diffing them tests this file's arithmetic. What a colleague meets is
`Store(writable=False)` raising, so the gate *opens* each build's map with the other build
and lets `_refuse_if_stale` and `_refuse_if_a_language_is_stale` speak -- their sentences
already name the language and the remedy (rule 89). The stamps are printed beside the
result because a check whose evidence is not shown is a tick (rules 13 and 37).

**Every language is asked, and none is named here** (rule 92). The list comes from
`ingest.PLUGINS`, so a third reader joins this gate by existing rather than by somebody
remembering. And a language that contributed **no rows** is a refusal rather than a pass:
a stamp that was never compared is not a stamp that agrees, which is rule 37 one more time
-- the Linux step analysed `src/dunneflow/web` and the Windows step `src/dunneflow/
canonical`, both of which are Python to the last file, so neither has ever compared a
TypeScript stamp at all.

Three answers when a language contributes nothing, never two (design rule 21): the probe
tree holds no file that reader claims, which is a fact about the tree; it holds them and
none was read, which is a fact about the machine and names the toolchain; or it was read
and disagrees, which is the failure this gate is for.

    uv run python tools/fingerprints.py dist/DunneFlow.app/Contents/MacOS/dunneflow
    uv run python tools/fingerprints.py dist/dunneflow/dunneflow --tree ../DunneNote
"""

from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from dunneflow import revisions
from dunneflow.detectors import core_fingerprint, lang_fingerprint
from dunneflow.ingest import PLUGINS
from dunneflow.runtime import self_argv
from dunneflow.schema import SCHEMA_VERSION
from dunneflow.store import StaleGraphError, Store, read_only_uri

ROOT = Path(__file__).resolve().parent.parent

# The probe tree, and it is this repository's own package deliberately. It is the one tree
# on every machine that builds DunneFlow which holds source in more than one of the
# languages this build reads -- 107 Python files and 11 TypeScript, read in four seconds.
# A tree that exercises one reader lets the other's stamp go unchecked, and an unchecked
# stamp is what this gate exists to stop being possible.
PROBE = Path("src/dunneflow")

# The two names the maps are written under. Different, so that a failure leaves two
# directories a person can open rather than one that was overwritten.
BY_BINARY = "_fp_binary"
BY_CHECKOUT = "_fp_checkout"


class Disagreement(RuntimeError):
    """The two builds cannot read each other's maps, or the gate could not tell."""


@dataclass(frozen=True)
class Stamps:
    """What one build wrote into one map: the core key, and one per language.

    Read with `sqlite3` rather than through `Store`, and that is the point of having both
    here. `Store` **refuses** a map whose stamps disagree, which is the property being
    tested -- so asking it for the values would mean never seeing the values that failed.
    The refusal is exercised separately, by `opens`.
    """

    core: str
    langs: dict[str, str]
    rows: dict[str, int]


def read_stamps(graph: Path) -> Stamps:
    """The stamps in a map, whoever wrote it and whether or not this build agrees."""
    conn = sqlite3.connect(read_only_uri(graph), uri=True)
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = 'extractor'").fetchone()
        core = str(row[0]) if row else ""
        langs: dict[str, str] = {}
        rows: dict[str, int] = {}
        for lang, stamp, n in conn.execute(
                "SELECT lang, extractor, COUNT(*) FROM files WHERE lang <> '' "
                "GROUP BY lang, extractor ORDER BY lang"):
            # A language stamped two ways in one map is a map mid-re-read, and joining the
            # two with a comma keeps that visible instead of letting one win (rule 30).
            langs[str(lang)] = ", ".join(filter(None, [langs.get(str(lang), ""), str(stamp)]))
            rows[str(lang)] = rows.get(str(lang), 0) + int(n)
        return Stamps(core=core, langs=langs, rows=rows)
    finally:
        conn.close()


def mine() -> Stamps:
    """What this checkout would stamp, for every language it has a reader for.

    `rows` is empty and stays empty: a checkout has not read anything here. The field
    belongs to a map rather than to a build, and filling it with a plausible zero would
    make *this build reads no TypeScript* and *this map holds no TypeScript* the same
    answer (rule 49).
    """
    return Stamps(
        core=f"{SCHEMA_VERSION}:{core_fingerprint()}",
        langs={lang: lang_fingerprint(lang) for lang in sorted(PLUGINS)},
        rows={},
    )


def candidates(tree: Path, lang: str) -> int:
    """How many files in this tree the named reader would claim.

    Asked of the plugin's own `DiscoveryRules` rather than of a suffix list written here,
    so *the tree holds none* means what the walk would mean by it. Tests and declaration
    files are excluded because the walk excludes them: a tree of nothing but `.test.ts`
    holds no TypeScript this gate can measure a stamp from.
    """
    rules = PLUGINS[lang].manifest.discovery
    n = 0
    for path in tree.rglob("*"):
        if not path.is_file() or path.suffix not in rules.suffixes:
            continue
        rel = path.relative_to(tree)
        if set(rel.parts) & rules.skip_dirs or rel.name.endswith(rules.skip_names):
            continue
        if rules.is_test(rel):
            continue
        n += 1
    return n


def why_nothing(tree: Path, lang: str) -> str:
    """The sentence for a language that contributed no rows -- and which of the two it is.

    Rule 89: a refusal names a command that can act on the thing it is refusing. *The tree
    has none* is answered by pointing this at another tree; *the reader could not run* is
    answered by installing what the manifest already says to install, and the manifest is
    where that sentence comes from rather than a copy of it kept here (rule 51).
    """
    manifest = PLUGINS[lang].manifest
    n = candidates(tree, lang)
    if not n:
        offered = ", ".join(sorted(manifest.discovery.suffixes))
        return (
            f"{lang}: this build has a reader for it and {tree} holds no file it claims "
            f"({offered}), so its stamp was never compared. Point --tree at a tree that "
            f"holds some."
        )
    if manifest.toolchain is not None:
        install = manifest.toolchain.install or f"install {manifest.toolchain.command}"
        return (
            f"{lang}: {tree} holds {n:,} files this build claims and the binary read none "
            f"of them, so its stamp was never compared. The reader runs "
            f"`{manifest.toolchain.command}`, which this machine has to have: {install}."
        )
    return (
        f"{lang}: {tree} holds {n:,} files this build claims and the binary read none of "
        f"them, so its stamp was never compared. This reader runs in the interpreter and "
        f"needs nothing installed, so something refused it — run the analysis by hand and "
        f"read what the walk says it left out."
    )


def analyse(argv: Sequence[str], tree: Path, out: Path, name: str) -> None:
    """Read `tree` with the build `argv` names, into a map of its own.

    `--no-docs` and `--no-render` because neither the corpus nor the Markdown carries a
    code stamp, and the gate is about the code stamps. `--quiet` because what this reads
    afterwards is the map, never the sentences.
    """
    done = subprocess.run(
        [*argv, "analyze", str(tree), "--name", name, "--no-docs", "--no-render",
         "--quiet", "--output", str(out)],
        capture_output=True, text=True)
    if done.returncode != 0:
        last = (done.stderr or done.stdout or "").strip().splitlines()
        raise Disagreement(
            f"{argv[0]} could not read {tree}, so there is nothing to compare:\n"
            + ("  " + last[-1] if last else "  it said nothing at all"))


def graph_of(out: Path, name: str) -> Path:
    """The map an analysis just wrote, or a refusal rather than a plausible path."""
    found = revisions.newest(out / name, revisions.GRAPH)
    if found is None:
        raise Disagreement(
            f"{out / name} holds no graph, although the analysis reported success — the "
            f"build being gated is not writing a map where it says it is.")
    return found


def opens_here(graph: Path) -> str:
    """Can **this checkout** read that map? The refusal's own sentence, or empty.

    This is the gate. `_refuse_if_stale` and `_refuse_if_a_language_is_stale` are the two
    functions a colleague's machine would run, and they already say which language moved
    and what re-analysing costs.
    """
    try:
        Store(graph, writable=False).close()
    except StaleGraphError as exc:
        return str(exc)
    return ""


def opens_there(argv: Sequence[str], tree: Path, out: Path, name: str) -> str:
    """Can **the binary** read a map this checkout wrote? The other direction.

    Asked with `query`, which opens read-only and so refuses rather than repairing (rule
    20), and with a statement whose answer nobody reads: what is being tested is whether
    the store opened at all.
    """
    done = subprocess.run(
        [*argv, "query", str(tree), "--name", name, "--output", str(out),
         "--sql", "SELECT COUNT(*) FROM files"],
        capture_output=True, text=True)
    if done.returncode == 0:
        return ""
    said = (done.stderr or done.stdout or "").strip().splitlines()
    return said[-1] if said else "it refused the map and said nothing"


def compare(theirs: Stamps, ours: Stamps, tree: Path) -> list[str]:
    """Every way the two can disagree, all of them, in the order a reader wants them.

    A list rather than the first one found: a core mismatch and a language mismatch have
    different remedies, and stopping at the first would hide the second behind it.
    """
    bad: list[str] = []
    if theirs.core != ours.core:
        bad.append(
            f"core: the binary stamps {theirs.core} and this checkout computes "
            f"{ours.core}. Every language's facts are refused both ways. The usual cause "
            f"is the bundle layout — the spec must place this package's data under "
            f"`dunneflow/`, because `fingerprint_files` labels every input relative to "
            f"`runtime.resource_root()`.")
    for lang in sorted(ours.langs):
        if lang not in theirs.langs:
            bad.append(why_nothing(tree, lang))
        elif theirs.langs[lang] != ours.langs[lang]:
            bad.append(
                f"{lang}: the binary stamps {theirs.langs[lang]} and this checkout "
                f"computes {ours.langs[lang]}. Only this language's rows are refused — "
                f"what ships is `plugin.json` and the files its `fingerprint` names, so "
                f"one of them is stale in the bundle or absent from it.")
    for lang in sorted(set(theirs.langs) - set(ours.langs)):
        bad.append(
            f"{lang}: the binary read {theirs.rows.get(lang, 0):,} files as {lang} and "
            f"this checkout has no reader for it at all. The two builds are not the same "
            f"program.")
    return bad


def report(theirs: Stamps, ours: Stamps) -> None:
    """Both sides, side by side, whether or not they agree (rule 13)."""
    print(f"   {'':<12} {'binary':<24} {'checkout':<24}")
    print(f"   {'core':<12} {theirs.core:<24} {ours.core:<24}")
    for lang in sorted(set(ours.langs) | set(theirs.langs)):
        n = theirs.rows.get(lang)
        counted = f"  ({n:,} files)" if n else "  (read nothing)"
        print(f"   {lang:<12} {theirs.langs.get(lang, '—'):<24} "
              f"{ours.langs.get(lang, '—'):<24}{counted}")


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="fingerprints",
        description="Do a frozen binary and this checkout still agree about who read what?")
    p.add_argument("binary", type=Path,
                   help="the built executable — the .app's `dunneflow`, or dunneflow-cli.exe")
    p.add_argument("--tree", type=Path, default=ROOT / PROBE,
                   help=f"the tree both builds read (default: {PROBE}, which holds both "
                        f"languages)")
    p.add_argument("--one-way", action="store_true",
                   help="only ask whether this checkout opens the binary's map, not the "
                        "reverse — for a machine where the checkout cannot analyse")
    args = p.parse_args(argv)

    if not args.binary.exists():
        print(f"!! there is no {args.binary} to gate — build it first", file=sys.stderr)
        return 1
    tree: Path = args.tree.resolve()
    if not tree.is_dir():
        print(f"!! {tree} is not a directory", file=sys.stderr)
        return 1

    binary = [str(args.binary.resolve())]
    with tempfile.TemporaryDirectory(prefix="dunneflow-fp-") as tmp:
        out = Path(tmp)
        try:
            analyse(binary, tree, out, BY_BINARY)
            theirs = read_stamps(graph_of(out, BY_BINARY))
            ours = mine()
            report(theirs, ours)

            bad = compare(theirs, ours, tree)
            refused = opens_here(graph_of(out, BY_BINARY))
            if refused:
                bad.append(f"this checkout refuses the binary's map: {refused}")
            if not args.one_way:
                analyse(self_argv(), tree, out, BY_CHECKOUT)
                back = opens_there(binary, tree, out, BY_CHECKOUT)
                if back:
                    bad.append(f"the binary refuses this checkout's map: {back}")
            if bad:
                raise Disagreement("\n".join(bad))
        except Disagreement as exc:
            print(f"\n!! {exc}", file=sys.stderr)
            return 1

        read = ", ".join(f"{lang} {theirs.rows[lang]:,}" for lang in sorted(theirs.rows))
        both = "and each build opened the other's map" if not args.one_way else \
            "and this checkout opened the binary's map"
        print(f"   they agree on all {len(ours.langs) + 1} stamps, {both}")
        print(f"   read from {tree.name}: {read}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
