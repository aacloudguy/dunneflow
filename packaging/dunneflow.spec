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

Unsigned. Signing and notarisation are the last step and need the Developer account.
"""

from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

ROOT = Path(SPECPATH).parent           # noqa: F821 -- SPECPATH is PyInstaller's
PKG = ROOT / "src" / "dunneflow"


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

a = Analysis(                                   # noqa: F821
    [str(ROOT / "packaging" / "dunneflow_app.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
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
