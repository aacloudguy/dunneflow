"""No sentence a reader is shown names the corpus a rule was learned on.

BACKLOG 25: `13-mirror.md` is written into every map, and until 2026-10-02 it told every
program's reader about *"things Lictores was never asked to name"*, the `vestiarium.db`
story and `Comitia of Lictores` -- DunneFlow's own map said so about DunneFlow. Six more
strings did the same in the glossary page, the Documents blurb, the comparison bands, a
vocabulary hint, the constant inspector and the schema's SQL comments.

**Comments and docstrings are exempt from the first three tests, and that is the line
they draw.** The ~300 places the source cites Comitia are the evidence each rule was
minted from (Tom, 2026-10-02: product strings only). *Comitia* and the other names in this
file are stand-ins, and the last two tests are what keep the real ones out of every
tracked file (Tom, 2026-11-12). What is checked is what can reach a screen or a page: every Python
string constant that is not a docstring, and the dashboard's code with its comments taken
out. Generalised rather than deleted, so the sentence still says what it says.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "dunneflow"
CORPUS = re.compile(r"lictores|comitia|vestiarium|groma|rollcall|unreal", re.I)

# Values, not prose: a directory name the walk skips is a fact about trees, and it is
# spelled the way the tool that writes it spells it.
ALLOWED = {("walk.py", ".groma")}


def _docstrings(tree: ast.AST) -> set[int]:
    out: set[int] = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = n.body[0] if n.body else None
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                out.add(id(first.value))
    return out


def test_no_python_string_a_reader_can_see_names_a_corpus():
    hits = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = _docstrings(tree)
        for n in ast.walk(tree):
            if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                    and id(n) not in docs and CORPUS.search(n.value)
                    and (path.name, n.value) not in ALLOWED):
                hits.append(f"{path.relative_to(SRC)}:{n.lineno}: {n.value[:80]!r}")
    assert not hits, "\n".join(hits)


def _without_comments(text: str) -> str:
    """Block and HTML comments become blank lines, so a line number still points home."""
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)


def test_no_dashboard_string_names_a_corpus():
    hits = []
    for path in sorted((SRC / "web" / "static").iterdir()):
        if path.suffix not in {".js", ".html", ".css"}:
            continue
        for i, line in enumerate(_without_comments(path.read_text(encoding="utf-8"))
                                 .splitlines(), 1):
            code = re.sub(r"(^|\s)//.*$", "", line)
            if CORPUS.search(code):
                hits.append(f"{path.name}:{i}: {code.strip()[:80]}")
    assert not hits, "\n".join(hits)


def test_the_guard_can_see_what_it_is_for():
    """Rule 42: a guard that names the right case may still not catch it."""
    assert CORPUS.search("things Lictores was never asked to name")
    assert CORPUS.search(_without_comments('x = `in <code>LICTORES_MAX_LEN</code>`;'))
    assert not CORPUS.search(_without_comments("/* on Lictores' pair */ x = 1;"))


# ---- and no tracked file spells the corpus's real names at all (2026-11-12) --- #
#
# The tests above are about what a reader of a *map* is shown. This one is about what a
# reader of this *repository* is shown. The program most of these rules were learned on is
# unpublished, and until release 0.3.0 its name, its package's and its components' stood in
# 1,112 places across 148 tracked files. Each is now a stand-in of the same length
# (`CLAUDE.md`, *House spelling*). The real names are held here as digests, so that the
# guard does not publish what it guards.
#
# **A digest of a word is not a secret**: anyone with a word list can find these, and the
# names are in this repository's history besides. What the digests do is keep the names out
# of the page you are reading, and out of a search of the tree.

import hashlib  # noqa: E402
import subprocess  # noqa: E402

REAL_NAMES = frozenset({
    "09cec7fc7f4e3072", "3566f7058747ac4c", "39e24d76527d2a02", "6ff8575db9fcc5c8",
    "7da49e2f4b1a9185", "a91f612f9947f57c", "b8c291baca729c70", "b9781ad21e18ccd2",
    "c700d1f95141812c", "d7b7427e9d0199da",
})
NAME_LENGTHS = (6, 7, 8, 10, 11)
# Other people's text, kept as they wrote it; and files that are not text.
_NOT_OURS = ("/vendor/", "licenses/", "THIRD-PARTY-NOTICES.md")
_NOT_TEXT = (".png", ".jpg", ".jpeg", ".gif", ".icns", ".ico", ".woff", ".woff2", ".wasm",
             ".pdf", ".cjs", ".lock")


def _digest(word: str) -> str:
    return hashlib.blake2b(word.encode(), digest_size=8).hexdigest()


def _names_in(run: str) -> bool:
    """Does this run of letters hold one of the names, anywhere in it? A name is found
    inside `X_MAX_LEN`, `chaos_x_kill` and `x2` because those break into runs of letters,
    and inside a longer run because every stretch of the right length is tried."""
    for n in NAME_LENGTHS:
        for i in range(len(run) - n + 1):
            if _digest(run[i:i + n]) in REAL_NAMES:
                return True
    return False


def test_the_digests_can_see_a_name_and_only_a_name():
    """Rule 59. The stand-ins are spelt here because they are public; each is one letter
    off nothing, so the check that they are *not* found is the control, and a digest of a
    stand-in is shown not to be in the set. That the set finds the real names is asserted
    where they can be spelt: the private records' `corpus-names/replace.py --check`."""
    for stand_in in ("comitia", "lictores", "lictor", "vestiarium", "conciliator",
                     "tribunus", "cantator", "praeco", "aedile", "rollcall"):
        assert not _names_in(stand_in), stand_in
    assert len(REAL_NAMES) == 10 and all(len(d) == 16 for d in REAL_NAMES)


def test_no_tracked_file_spells_the_corpus_s_real_names():
    try:
        out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, text=True,  # noqa: S603, S607
                             cwd=SRC.parents[1], timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        out = None
    if out is None or out.returncode != 0 or not out.stdout:
        import pytest
        pytest.skip("not a git checkout, so there is no list of tracked files to read")
    judged: dict[str, bool] = {}
    hits = []
    for rel in sorted(f for f in out.stdout.split("\0") if f):
        if rel.endswith(_NOT_TEXT) or any(part in rel for part in _NOT_OURS):
            continue
        try:
            text = (SRC.parents[1] / rel).read_text(encoding="utf-8").lower()
        except (OSError, UnicodeDecodeError):
            continue
        for run in set(re.findall(r"[a-z]{6,}", text)):
            if run not in judged:
                judged[run] = _names_in(run)
            if judged[run]:
                hits.append(f"{rel}: a word of {len(run)} letters")
    assert not hits, (
        f"{len(hits)} tracked files spell a name of the unpublished corpus. Use its "
        f"stand-in (CLAUDE.md, House spelling):\n" + "\n".join(hits[:30]))
