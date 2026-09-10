# -*- mode: python ; coding: utf-8 -*-
"""How DunneFlow is frozen. Run from the repository root:

    uv run pyinstaller packaging/dunneflow.spec --noconfirm

**Everything in `datas` is there because something reads it as a file**, and a file is
exactly what a module inside a PyInstaller archive does not have. The four kinds:

* `detectors/*.yaml` and `detectors/docs/*.yaml` -- the rules, loaded by `yaml.safe_load`.
* `detectors/__init__.py`, `detectors/prose.py` and both extractor trees -- **hashed**, not
  imported, by `rules_fingerprint()` and `doc_rules_fingerprint()`. Rule 12 says a cached
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

**`console=False` affects the double-click and nothing else.** Launched from the Finder it
opens no terminal window; run as `DunneFlow.app/Contents/MacOS/dunneflow analyze …` from a
shell it inherits that shell's streams and prints exactly as the checkout does. That is what
lets the ground truth be run *through the binary* rather than beside it.

**`DUNNEFLOW_ARCH` chooses which machines the result runs on**, and there are two answers
rather than one. Unset builds for the machine doing the building, which is what the
verification gate in `CLAUDE.md` runs and what keeps that gate at seven seconds. `universal2`
builds for Apple Silicon *and* Intel, and is what a release is, and needs an interpreter that
is itself universal2 -- uv's managed Pythons and Homebrew's are single-arch by construction,
so it has to come from python.org. **Asked for universal2 under an interpreter that cannot
produce it, this file raises** rather than quietly building for one architecture: a
"universal" build that is arm64 inside would be found by a colleague on an Intel Mac and not
here, which is rule 49 exactly.

Signing, notarisation and the disk image are `packaging/release.sh`.
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata
from PyInstaller.utils.osx import get_binary_architectures

ROOT = Path(SPECPATH).parent           # noqa: F821 -- SPECPATH is PyInstaller's
PKG = ROOT / "src" / "dunneflow"


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
    asked = os.environ.get("DUNNEFLOW_ARCH", "").strip() or "universal2"
    if asked in ("host", "native"):
        return None
    if asked != "universal2":
        raise SystemExit(
            f"DUNNEFLOW_ARCH={asked!r} is not a target this file knows. "
            "Leave it unset for 'universal2', or set it to 'host' to build only for this "
            "machine."
        )
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


datas = [
    # The rules: the extension point, loaded as YAML.
    (str(PKG / "detectors" / "python.yaml"), "dunneflow/detectors"),
    (str(PKG / "detectors" / "annotations.yaml"), "dunneflow/detectors"),
    (str(PKG / "detectors" / "docs" / "prose.yaml"), "dunneflow/detectors/docs"),
    # The readers, as **bytes to be hashed**. See the note above: rule 12 puts the reader in
    # the cache key, and a reader with no file hashes to nothing at all.
    (str(PKG / "detectors" / "__init__.py"), "dunneflow/detectors"),
    (str(PKG / "detectors" / "prose.py"), "dunneflow/detectors"),
    *_tree(PKG / "extractors" / "python", "dunneflow/extractors/python"),
    *_tree(PKG / "extractors" / "docs", "dunneflow/extractors/docs"),
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
    name="dunneflow",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    target_arch=_target_arch(),
)

coll = COLLECT(                                 # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="dunneflow",
)

app = BUNDLE(                                   # noqa: F821
    coll,
    name="DunneFlow.app",
    icon=None,
    bundle_identifier="com.dunnecorp.dunneflow",
    info_plist={
        # It serves on localhost and opens the default browser. Nothing here reaches a
        # network, and the map states that as a standing guarantee.
        "NSHighResolutionCapable": True,
        "LSBackgroundOnly": False,
        "CFBundleShortVersionString": "0.1.0",
    },
)
