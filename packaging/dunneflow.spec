# -*- mode: python ; coding: utf-8 -*-
"""How DunneFlow is frozen. Run from the repository root:

    uv run pyinstaller packaging/dunneflow.spec --noconfirm

**Everything in `datas` is there because something reads it as a file**, and a file is
exactly what a module inside a PyInstaller archive does not have. The four kinds:

* `detectors/*.yaml` and `detectors/docs/*.yaml` -- the rules, loaded by `yaml.safe_load`.
* `schema.py`, `sql.py`, `ingest/`, every plugin's fingerprinted bytes, `detectors/__init__.py`, `detectors/prose.py` and both
  extractor trees -- **hashed**, not imported, by `core_fingerprint()`, `lang_fingerprint()`
  and `doc_rules_fingerprint()`. Rule 12 says a cached
  fact is valid only if the source *and the tool that read it* are unchanged, so the reader
  is in the key; frozen, a reader that exists only inside the archive hashes to nothing.
  They are imported from the archive as usual -- these copies are read as bytes and never
  executed.
* `web/static` and `web/vendor` -- the page, and deck.gl.

**The destination is `dunneflow/…`, and that is not cosmetic.** `fingerprint_files` labels
every input by its path relative to `runtime.resource_root()`, which is `<_MEIPASS>/dunneflow`
here and `src/dunneflow` in a checkout. Same labels, same bytes, same fingerprint -- so a map
made by the binary is readable by the checkout and back. Laid out any other way the two
builds would refuse each other's maps under rule 12, which is the opposite of what that rule
is for. `tests/test_frozen.py` asserts the layout; this file has to honour it.

`copy_metadata('dunneflow')` is how `runtime.tool_version()` keeps working, rather than
gaining a frozen branch. Stamping a version into a file at build time would be the literal
that docstring refuses, one build system further away -- and a shipped binary that records
no tool version fails the one panel that exists to say which DunneFlow read the map.

**`console=False` affects the double-click and nothing else -- on macOS.** Launched from the
Finder it opens no terminal window; run as `DunneFlow.app/Contents/MacOS/dunneflow analyze …`
from a shell it inherits that shell's streams and prints exactly as the checkout does. That
is what lets the ground truth be run *through the binary* rather than beside it.

**On Windows that second sentence is false, and it is why there are two executables.** A
GUI-subsystem binary there is not merely "started without a terminal": it is *given no
standard streams at all*, so `DunneFlow.exe analyze …` from PowerShell would do the work and
print not one line of it -- and the verification gate in `CLAUDE.md`, which exists to run the
ground truth through the binary, would have nothing to read. Windows' own answer to this is
`python.exe` beside `pythonw.exe`, and this file's is the same shape:

* `DunneFlow.exe`      -- windowed. What a reader double-clicks; no console window.
* `dunneflow-cli.exe`  -- console. The command line, and what the gate runs through.

They are **one `Analysis` and one `COLLECT`**, so the archive, the data and the vendored
engine exist once and the second executable costs a few hundred kilobytes. The names differ
by more than case deliberately: NTFS is case-insensitive, so `DunneFlow.exe` and
`dunneflow.exe` are one file there and the second build would silently overwrite the first.

**`BUNDLE` is macOS's and is skipped everywhere else.** An `.app` is a directory with a
plist; Windows has nothing it corresponds to, and asking for one produces a directory nothing
can launch.

**`DUNNEFLOW_ARCH` chooses which machines the result runs on**, and there are two answers
rather than one -- both of them macOS's. `target_arch` is a Mach-O idea: a Windows PE holds
one architecture and PyInstaller builds for the interpreter it is running under, so on
Windows this file takes no answer but `host` and **refuses the other by name** rather than
accepting a word it would then ignore (rule 49 -- a setting that is quietly dropped is worse
than one that is rejected, because only the second can be seen). Unset builds for the machine doing the building, which is what the
verification gate in `CLAUDE.md` runs and what keeps that gate at seven seconds. `universal2`
builds for Apple Silicon *and* Intel, and is what a release is, and needs an interpreter that
is itself universal2 -- uv's managed Pythons and Homebrew's are single-arch by construction,
so it has to come from python.org. **Asked for universal2 under an interpreter that cannot
produce it, this file raises** rather than quietly building for one architecture: a
"universal" build that is arm64 inside would be found by a colleague on an Intel Mac and not
here, which is rule 49 exactly.

Signing, notarisation and the disk image are `packaging/release.sh`. The Windows build has
no equivalent and needs none for now: `packaging/release.ps1` freezes and zips, and there is
nothing to sign against -- an unsigned Windows binary meets SmartScreen, which is a warning a
reader can click past, and not Gatekeeper, which is a refusal they cannot.
"""

import json
import os
import sys
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

# `PyInstaller.utils.osx` needs `macholib`, which is a macOS-only dependency and genuinely
# absent elsewhere -- so it is imported where it is used rather than here, and this file can
# be read at all on Windows.

ROOT = Path(SPECPATH).parent           # noqa: F821 -- SPECPATH is PyInstaller's
PKG = ROOT / "src" / "dunneflow"

# **The version is `pyproject.toml`'s, and this file only reads it** (rule 51). It was spelled
# here a second time as `CFBundleShortVersionString`, which is the one `release.sh` names the
# `.dmg` after -- so a release that bumped pyproject alone would have shipped a 0.2.0 tool in
# `DunneFlow-0.1.0.dmg`, with the About panel and the disk image disagreeing about which
# DunneFlow it was. The Windows zip and the Linux tarball already read pyproject or the
# dist-info; now the bundle does too.
VERSION = tomllib.loads(
    (ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]

# **Three platforms, asked once.** `_WINDOWS` was the only one named, and everything else
# read as "not Windows" -- which was true while there were two and quietly wrong the moment
# there were three: `BUNDLE` was guarded by `if not _WINDOWS`, so a Linux build would have
# tried to produce a `.app`. A negation is a fine way to say *the other one* and no way at
# all to say *the other two* (rule 51's shape, in a boolean).
_MACOS = sys.platform == "darwin"
_WINDOWS = sys.platform == "win32"
_LINUX = sys.platform.startswith("linux")

# The icon, and it is **named rather than found**: PyInstaller takes `icon=None` without a
# word, so a path that has stopped existing would build a perfectly good application with
# the generic bundle icon and nothing anywhere would say so (rule 49). A build asked for an
# icon that is not there should fail while somebody is watching it.
#
# One container per platform, out of one drawing -- `build_supplied_icon.py` writes them all
# from the same composed canvas, so this is a choice of file and never a second icon.
#
# **Linux is `None`, and that is the whole answer rather than a gap.** An ELF executable
# carries no icon: what a reader sees in the menu is the PNG named by the `.desktop` entry,
# and that pair is installed by `release-linux.sh` rather than embedded by anything here. So
# there is nothing for this file to require, and requiring the `.icns` anyway -- which is what
# "not Windows" used to do -- would fail a Linux build over a file it would then not use.
ICON = None if _LINUX else ROOT / "packaging" / "icon" / (
    "dunneflow.ico" if _WINDOWS else "dunneflow.icns")
if ICON is not None and not ICON.exists():
    raise SystemExit(
        f"{ICON} is not there — build it first:\n"
        f"  uv run --with pillow python packaging/icon/build_supplied_icon.py "
        f"packaging/icon/rabbit-head.png")


def _target_arch() -> str | None:
    """Which architectures to build for, and a refusal rather than a plausible answer.

    **Universal is the default**, and it used to be the other way round. Unset meant *this
    machine*, which made the fast build the easy one and the shippable build the one you had
    to remember -- and forgetting is silent, because an arm64 bundle installs and runs
    perfectly on the machine that built it. The whole failure lands on somebody else's Intel
    Mac. Measured before flipping it: 12.9s universal against 11.5s host, so the cheap
    default was not even buying anything (Tom's call, on those numbers).

    `host` is still there and still one word, for the verification gate in `CLAUDE.md` that
    wants a bundle to run ground truth through rather than a bundle to hand over. `None` is
    PyInstaller's own word for *the machine I am running on*.

    The check is on `sys._base_executable` rather than `sys.executable`, because a virtual
    environment's `python` is a stub that says nothing about the interpreter behind it.
    """
    if not _MACOS:
        # **`target_arch` is Mach-O's and nothing else has one.** A PE and an ELF each hold
        # one architecture and PyInstaller builds for the interpreter running it, so there is
        # no choice here to make -- but a `DUNNEFLOW_ARCH` somebody set out of habit must not
        # be *accepted and ignored*, which is how a person comes to believe they built
        # something they did not. `host` is the one word that is true everywhere, so it is
        # the one word this takes.
        #
        # **A fat ELF is not a counter-example.** `FatELF` was proposed and never merged, and
        # a `lipo` for Linux does not exist -- so a machine that wants both architectures
        # builds twice, on two machines, which is a different answer to a different question
        # and not something this variable could ever have expressed.
        asked = os.environ.get("DUNNEFLOW_ARCH", "").strip()
        if asked and asked not in ("host", "native"):
            kind = "An ELF executable" if _LINUX else "A Windows executable"
            raise SystemExit(
                f"DUNNEFLOW_ARCH={asked!r} is a macOS answer and this is {sys.platform}. "
                f"{kind} holds one architecture, the one this interpreter is built for, and "
                "there is nothing here to choose. Leave it unset, or set it to 'host'."
            )
        return None

    asked = os.environ.get("DUNNEFLOW_ARCH", "").strip() or "universal2"
    if asked in ("host", "native"):
        return None
    if asked != "universal2":
        raise SystemExit(
            f"DUNNEFLOW_ARCH={asked!r} is not a target this file knows. "
            "Leave it unset for 'universal2', or set it to 'host' to build only for this "
            "machine."
        )
    from PyInstaller.utils.osx import get_binary_architectures

    real = getattr(sys, "_base_executable", None) or sys.executable
    fat, archs = get_binary_architectures(real)
    if not fat or "x86_64" not in archs or "arm64" not in archs:
        raise SystemExit(
            "A universal2 build was asked for (the default), and this interpreter cannot "
            f"produce it: {real} is {'+'.join(archs)}.\n"
            "A universal2 build needs a universal2 interpreter, which uv's managed Pythons "
            "and Homebrew's are not. Either:\n"
            "  ./packaging/release.sh build          — builds it properly, and makes the "
            "universal2 environment first if it is missing\n"
            "  DUNNEFLOW_ARCH=host pyinstaller …     — a fast build for this machine only, "
            "which is what the verification gate wants and must never be shipped\n"
            "The universal2 interpreter is python.org's "
            "https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg."
        )
    return "universal2"


def _tree(src: Path, dest: str) -> list[tuple[str, str]]:
    """Every file under `src`, each with the directory it belongs in.

    Written out rather than handed to PyInstaller as a directory because the layout is the
    contract: a `datas` entry naming a directory unpacks it under a name PyInstaller
    chooses, and `resource_root()` has to be able to find it by the name the checkout uses.
    """
    out = []
    for path in sorted(src.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            out.append((str(path), f"{dest}/{path.parent.relative_to(src)}".rstrip("/.")))
    return out


def _reader_files() -> list[tuple[str, str]]:
    """Every **in-process** reader's tree, named by the manifest that declares it.

    This line read `_tree(PKG / "extractors" / "python", …)` until 2026-09-18, two lines
    under a comment arguing rule 92 for the rules directory and four above one arguing it
    for the plugins. It was the whole truth while the only reader in this interpreter was
    Python's, and it is the *third* enumeration in this file to be found the same way —
    `detectors/*.yaml` was named until TypeScript, `plugins/` was a tree until TypeScript
    brought a `node_modules`.

    What it costs is worse than either, because it fails later and quieter. A new
    in-process reader's manifest ships (`_plugin_files` finds it), its rules ship (the glob
    finds them), the registry loads it, and every gate here passes — and the reader's own
    bytes are not in the bundle. `resource_root()` then has nothing to hash for
    `lang_fingerprint`, and the application meets its first file of that language in a
    colleague's hands.

    `reader` is relative to the package root rather than to the plugin directory, because
    an in-process reader is part of this program; an out-of-process one declares `entry`
    instead and its bytes are its `fingerprint`, which `_plugin_files` already ships. A
    plugin declaring neither is refused at load, so there is no third case here.
    """
    out: list[tuple[str, str]] = []
    for manifest in sorted((PKG / "plugins").glob("*/plugin.json")):
        rel = json.loads(manifest.read_text(encoding="utf-8")).get("reader", "")
        if not rel:
            continue                      # a reader on the far side of a pipe
        src = PKG / Path(rel)
        if not src.is_dir():
            raise SystemExit(
                f"the {manifest.parent.name} plugin declares its reader at {rel} and this "
                f"tree has no such directory at {src}. An in-process reader is bundled as "
                f"the bytes its stamp is computed from; there is nothing to ship."
            )
        out += _tree(src, f"dunneflow/{rel}")
    return out


def _plugin_files() -> list[tuple[str, str]]:
    """`plugin.json` and the files it names, for every plugin in the tree.

    Read off the manifests rather than off the directory, so a plugin's shipped bytes are
    the bytes its language's stamp is computed from. A file a plugin needs at runtime and
    does not fingerprint is a file whose change does not discard a map (rule 12), so there
    is deliberately no third category.
    """
    out: list[tuple[str, str]] = []
    for manifest in sorted((PKG / "plugins").glob("*/plugin.json")):
        dest = f"dunneflow/plugins/{manifest.parent.name}"
        wanted = {"plugin.json"}
        wanted.update(json.loads(manifest.read_text(encoding="utf-8")).get("fingerprint", []))
        for name in sorted(wanted):
            path = manifest.parent / name
            if not path.is_file():
                raise SystemExit(
                    f"the {manifest.parent.name} plugin fingerprints {name} and this tree "
                    f"has no such file at {path}. A plugin ships the bytes it is stamped "
                    f"from; build it before building the application."
                )
            out.append((str(path), dest))
    return out


datas = [
    # The rules: the extension point, loaded as YAML. **Globbed, never named**, and that
    # is rule 92 rather than economy: this line named `python.yaml` and `annotations.yaml`
    # for as long as there was one language, and the TypeScript reader's `typescript.yaml`
    # would have been left out of the bundle entirely — `load_rules` would then have raised
    # `RulesMissing` on the first `.ts` file in the signed application and nowhere else.
    # `core_extraction_inputs()` has globbed this same directory all along, so a hand-kept
    # list here was already a second answer waiting to disagree with the key.
    *[(str(p), "dunneflow/detectors") for p in sorted((PKG / "detectors").glob("*.yaml"))],
    (str(PKG / "detectors" / "docs" / "prose.yaml"), "dunneflow/detectors/docs"),
    # The readers, as **bytes to be hashed**. See the note above: rule 12 puts the reader in
    # the cache key, and a reader with no file hashes to nothing at all.
    (str(PKG / "detectors" / "__init__.py"), "dunneflow/detectors"),
    (str(PKG / "detectors" / "prose.py"), "dunneflow/detectors"),
    (str(PKG / "schema.py"), "dunneflow"),
    # What a string literal *means* -- in the core key since rule 95, because a change to
    # SQL parsing reshapes every `sql_ops` row and moved no key at all before it.
    (str(PKG / "sql.py"), "dunneflow"),
    *_tree(PKG / "ingest", "dunneflow/ingest"),
    # **Every in-process reader, found rather than named** — see `_reader_files()`. The
    # documentation scanner stays spelled out beside it because it is not a language
    # reader: no manifest declares it, nothing routes a suffix to it, and it is hashed by
    # `doc_extraction_inputs()` rather than by any language's key. Two different questions,
    # and only one of them has a registry to ask.
    *_reader_files(),
    *_tree(PKG / "extractors" / "docs", "dunneflow/extractors/docs"),
    # **Every plugin, and exactly the bytes its manifest names.** A tree here was right
    # while the only plugin was a `plugin.json`; the TypeScript reader brought a
    # `node_modules` of several thousand files, a lockfile and a TypeScript source tree,
    # none of which the application runs — `_tree` would have put all of it in the signed
    # bundle.
    #
    # So it is derived from the manifests rather than from the directory listing, which
    # makes it the same list rule 12 hashes: **what ships and what is stamped are the same
    # bytes by construction**, rather than two answers that agree until somebody adds a
    # file. Rule 92's argument is kept — nothing here enumerates the plugins — and a test
    # asserts every registered plugin's fingerprint files are in `datas`.
    *_plugin_files(),
    # The page, and the vendored engine.
    *_tree(PKG / "web" / "static", "dunneflow/web/static"),
    *_tree(PKG / "web" / "vendor", "dunneflow/web/vendor"),
    # Which DunneFlow read this map, from the one place that answers it.
    *copy_metadata("dunneflow"),
]

# PyYAML's C extension is **never used and is not shippable universal2**. Every call site in
# this program is `yaml.safe_load`, which is the pure-Python `SafeLoader` whether or not
# `yaml._yaml` can be imported -- `yaml/__init__.py` takes `yaml.cyaml` inside a `try` and records
# its absence in `__with_libyaml__`, which nothing here reads. PyPI has no universal2 PyYAML
# wheel for any version, so the extension is the one thing in the bundle that cannot be built
# for both architectures. Excluding it costs nothing measurable: the three detector files are
# a few kilobytes each, read once. `tests/test_frozen.py` holds the "never used" half.
#
# **Both names, and `cyaml` is the one that does the work.** Excluding the extension alone
# leaves `yaml.cyaml` importing it, which is an ImportError where there used to be a
# fallback; excluding the wrapper is what makes `__init__.py` take the branch it already
# has for a PyYAML built without libyaml.
excludes = ["yaml.cyaml", "yaml._yaml"]

a = Analysis(                                   # noqa: F821
    [str(ROOT / "packaging" / "dunneflow_app.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)                               # noqa: F821

exe = EXE(                                      # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    # `dunneflow` inside the `.app`, where the bundle supplies the name a reader sees;
    # `DunneFlow` on Windows, where this file *is* the name a reader sees.
    name="DunneFlow" if _WINDOWS else "dunneflow",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ICON) if _WINDOWS else None,
    target_arch=_target_arch(),
)

# **The console half, Windows only** -- see the note at the top. Built from the same `pyz`
# and the same `a.scripts`, so it is the same program and not a second assembly of it; the
# only difference is the subsystem it is linked for, which is the whole point.
exes = [exe]
if _WINDOWS:
    exes.append(EXE(                            # noqa: F821
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="dunneflow-cli",
        debug=False,
        strip=False,
        upx=False,
        console=True,
        icon=str(ICON),
    ))

coll = COLLECT(                                 # noqa: F821
    *exes,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="dunneflow",
)

if _MACOS:
    app = BUNDLE(                               # noqa: F821
        coll,
        name="DunneFlow.app",
        icon=str(ICON),
        bundle_identifier="com.dunnecorp.dunneflow",
        info_plist={
            # It serves on localhost and opens the default browser. Nothing here reaches a
            # network, and the map states that as a standing guarantee.
            "NSHighResolutionCapable": True,
            "LSBackgroundOnly": False,
            "CFBundleShortVersionString": VERSION,
        },
    )
