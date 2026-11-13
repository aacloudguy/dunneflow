"""Nothing tracked names a person's disk, their signing identity or their address.

This repository is public, so a tracked file is a published one. Four things were in it on
2026-11-12 and none had been put there on purpose:

- the build machine's path, twice, inside `plugins/typescript/main.bundle.cjs`, which ships
  in every build -- esbuild wrote it, from a worktree that reached `node_modules` through
  eleven parent directories;
- the same path in three image descriptions in `docs/`;
- one person's name and Apple team id, as the *default* of `packaging/release.sh` and again
  in `PACKAGING.md`.

A placeholder is how a path is written here: `/Volumes/YourDisk`, `/Users/you`,
`/home/reader`, `Developer ID Application: Your Name (TEAMID)`. This reads every tracked
text file, the bundle included, and fails on anything shaped like the real thing.

Skipped outside a git checkout, by name: a frozen build and an unpacked archive have no
index to ask, and a walk of the directory instead would read `output/` and `dist/`, which
are this machine's and were never going anywhere.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Other people's code, with other people's names in it, kept as they wrote it.
THIRD_PARTY = ("/vendor/", "THIRD-PARTY-NOTICES.md", "licenses/")
BINARY = (".png", ".jpg", ".jpeg", ".gif", ".icns", ".ico", ".woff", ".woff2", ".wasm", ".pdf")

SHAPES = {
    "a volume that is not the placeholder":
        re.compile(r"/Volumes/(?!YourDisk\b)[A-Za-z0-9_][\w.-]*"),
    "a home directory that is not the placeholder":
        re.compile(r"/Users/(?!you\b)[A-Za-z0-9_][\w.-]*"),
    "a Linux home directory that is not the placeholder":
        re.compile(r"/home/(?!reader\b|you\b|x\b)[A-Za-z0-9_][\w.-]*"),
    "a Windows profile that is not the placeholder":
        re.compile(r"[A-Za-z]:\\{1,2}Users\\{1,2}(?!you\b)[A-Za-z0-9_][\w.-]*"),
    "a signing identity with a real team id":
        re.compile(r"Developer ID Application: (?!Your Name \(TEAMID\)|Name \(TEAMID\))"
                   r"[^\"'\n\[<$]*\([A-Z0-9]{10}\)"),
    "an address":
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*"
                   r"\.(?:com|org|net|io|dev|edu|gov|co|uk|us|me|ai|app)\b"),
}
# The one address this tree is meant to carry, and the shape documentation uses for one.
ADDRESSES_MEANT = re.compile(r"noreply@anthropic\.com|@example\.(?:com|org|net)$|^git@github\.com$")


def _tracked() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True,  # noqa: S603, S607
                             text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [f for f in out.stdout.split("\0") if f] if out.returncode == 0 else []


def _found(text: str) -> list[tuple[str, str]]:
    hits = []
    for what, shape in SHAPES.items():
        for m in shape.finditer(text):
            if what == "an address" and ADDRESSES_MEANT.search(m.group(0)):
                continue
            hits.append((what, m.group(0)))
    return hits


def test_the_shapes_catch_what_was_actually_here():
    """Rule 59: a guard is shown to fail before it is trusted to pass. Each of these is
    what the tree held, with the name changed, and each placeholder beside it is clean."""
    bad = [
        "// ../../../Volumes/SomeDrive/Documents/Developer/x/node_modules/typescript.js",
        "![The dialog with /Users/pat_1/code/requests typed in](images/a.jpg)",
        'IDENTITY="${X:-Developer ID Application: Pat Example (AB12CD34EF)}"',
        "run it as maclab@build.example.net",
        "C:\\Users\\pat\\AppData",
        "/home/pat/.local/jdk-21",
    ]
    for line in bad:
        assert _found(line), line
    good = [
        "/Volumes/YourDisk/DunneFlow", "/Users/you/code", "/home/reader/x",
        "DUNNEFLOW_IDENTITY='Developer ID Application: Your Name (TEAMID)'",
        "Co-Authored-By: Claude <noreply@anthropic.com>", "graph@2026-01-01T00-00-00Z.db",
        "icon_32x32@2x.png", "an (UNFINISHED) map", "C:\\Users\\you\\maps",
    ]
    for line in good:
        assert not _found(line), (line, _found(line))


def test_nothing_tracked_names_a_person_s_disk_identity_or_address():
    files = _tracked()
    if not files:
        pytest.skip("not a git checkout, so there is no list of tracked files to read")
    found: list[str] = []
    for rel in files:
        if rel.endswith(BINARY) or any(part in rel for part in THIRD_PARTY):
            continue
        if rel == "tests/test_no_personal_paths.py":
            continue                      # this file spells the shapes it looks for
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        hits = _found(text)
        if rel.endswith(".cjs"):
            # The bundle is the TypeScript compiler, inlined: its own text holds URLs with
            # `/home/` in them and its authors' addresses. What esbuild adds is a path on
            # the machine that built it, and that is what is looked for here.
            hits = [(what, said) for what, said in hits
                    if what.startswith(("a volume", "a home directory", "a Windows"))]
        found += [f"{rel}: {what}: {said}" for what, said in hits]
    assert not found, "\n".join(sorted(set(found))[:40])


def test_a_map_does_not_name_the_disk_it_was_made_on(tmp_path):
    """Rule 60, asked of everything an analysis writes. A program's output directory is
    handed on -- to a colleague, to a bug report -- and until 2026-11-12 the standards store
    carried each `--standards` root's absolute path, in a value nothing read.

    Every file the run wrote is searched for the directory the trees were in, as bytes.
    `analysis.json` is the one exception and it is deliberate: *Analyse it again* fills its
    dialog from the path there, and `SECURITY.md` says to leave that file out."""
    from dunneflow.runtime import self_argv

    here = tmp_path / "a-directory-only-this-machine-has"
    tree, std, out = here / "tree", here / "standards", tmp_path / "out"
    (tree / "pkg").mkdir(parents=True)
    std.mkdir()
    (tree / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tree / "pkg" / "a.py").write_text(
        'import os\n\n\ndef f():\n    """Reads a setting."""\n    return os.environ["X"]\n',
        encoding="utf-8")
    (tree / "README.md").write_text("# A program\n\nIt reads a setting.\n", encoding="utf-8")
    (std / "naming.md").write_text(
        "# Naming\n\nA function name MUST be a verb.\n", encoding="utf-8")
    done = subprocess.run(  # noqa: S603
        self_argv("analyze", str(tree), "--name", "p", "--output", str(out),
                  "--standards", str(std)),
        capture_output=True, text=True, timeout=600, check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    needle = here.name.encode()
    named = sorted(
        p.relative_to(out).as_posix() for p in out.rglob("*")
        if p.is_file() and needle in p.read_bytes())
    assert named == ["p/analysis.json"], named
