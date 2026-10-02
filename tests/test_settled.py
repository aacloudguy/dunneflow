"""An analysis says where its climb for a manifest settled (BACKLOG 12).

Without `--part-of` the climb has no ceiling, and inventing one would be a rule with no
evidence. What it can always do is say what it did: a run that took the tree's name and its
documentation from four levels up printed nothing about it.
"""

from __future__ import annotations

import json
from pathlib import Path

from dunneflow import cli


def _tree(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nname = "pkg"\n', encoding="utf-8")
    (root / "src" / "pkg" / "__init__.py").write_text("def f():\n    return 1\n",
                                                       encoding="utf-8")
    return root


def test_the_sentence_names_levels_and_files_never_a_path(tmp_path):
    root = _tree(tmp_path)
    said = cli._settled(root / "src" / "pkg", root, [root / "pyproject.toml"],
                        docs_moved=True)
    assert "2 levels above" in said and "pyproject.toml" in said
    assert "documentation" in said and str(tmp_path) not in said
    assert cli._settled(root, root, [root / "pyproject.toml"], docs_moved=True) == ""


def test_a_run_from_a_subdirectory_says_where_it_took_its_name_from(tmp_path, capsys):
    root = _tree(tmp_path)
    out = tmp_path / "maps"
    assert cli.main(["analyze", str(root / "src"), "--name", "pkg", "--output", str(out),
                     "--progress-json", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert "1 level above the directory analysed" in captured.err
    done = [json.loads(x) for x in captured.out.splitlines() if x.startswith("{")][-1]
    assert done["state"] == "done" and "1 level above" in done["settled"], done
