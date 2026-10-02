"""No sentence a reader is shown names the corpus a rule was learned on.

BACKLOG 25: `13-mirror.md` is written into every map, and until 2026-10-02 it told every
program's reader about *"things Mensores was never asked to name"*, the `tabularium.db`
story and `Society of Mensores` -- DunneFlow's own map said so about DunneFlow. Six more
strings did the same in the glossary page, the Documents blurb, the comparison bands, a
vocabulary hint, the constant inspector and the schema's SQL comments.

**Comments and docstrings are exempt, and that is the line this draws.** The ~300 places
the source cites Society are the evidence each rule was minted from (Tom, 2026-10-02:
product strings only). What is checked is what can reach a screen or a page: every Python
string constant that is not a docstring, and the dashboard's code with its comments taken
out. Generalised rather than deleted, so the sentence still says what it says.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "dunneflow"
CORPUS = re.compile(r"mensores|society|tabularium|groma|pantheon|unreal", re.I)

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
    assert CORPUS.search("things Mensores was never asked to name")
    assert CORPUS.search(_without_comments('x = `in <code>MENSORES_MAX_LEN</code>`;'))
    assert not CORPUS.search(_without_comments("/* on Mensores' pair */ x = 1;"))
