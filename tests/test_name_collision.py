"""A name rebound in sequence is not a collision (`NAME_COLLISION`, slice F of chunk 5b).

The only BROKEN finding in all of Unreal's `Runtime` was `predicate` in
`TraceLog/create_standalone.py`. It is defined inside `_main_trace`, passed to
`_collect_source`, and then defined again under `if analysis:` and passed again. The program
has no defect, and *only the last one exists at run time; every call resolves to it* was
false twice over: the first definition is used before the second exists, and the second
exists on one arm only. The command that gates CI on BROKEN failed a healthy tree.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from dunneflow import anomalies
from dunneflow.anomalies import detect
from dunneflow.store import Store
from tests.test_anomalies import _analyze

# The shape from create_standalone.py, cut down: used between, and the second one an arm
# apart. Either alone must be enough, so each has a case of its own below.
REBOUND = '''
def collect(where, keep):
    return [x for x in where if keep(x)]


def main(src, extra, analysis):
    def predicate(path):
        return not path.startswith("lz4")
    files = collect(src, predicate)
    if analysis:
        def predicate(path):
            return path != "Store"
        files += collect(extra, predicate)
    return files
'''

USED_BETWEEN = '''
def main(items):
    def pick(x):
        return x
    first = pick(items)
    def pick(x):
        return -x
    return first, pick(items)
'''

ARM_APART = '''
def main(flag):
    if flag:
        def pick(x):
            return x
    else:
        def pick(x):
            return -x
    return pick
'''

# Nothing between, both on the same footing: the first really is unreachable.
TRUE_DUPLICATE = '''
def main(items):
    def pick(x):
        return x
    def pick(x):
        return -x
    return pick(items)
'''

# The same name nested in two different routines is two qualnames, never one group.
TWO_SCOPES = '''
def one(items):
    def pick(x):
        return x
    return pick(items)


def two(items):
    def pick(x):
        return -x
    return pick(items)
'''

# At module scope the later one replaces the earlier for every caller: the finding, even
# with a call between, because a module is not run line by line by its callers.
MODULE_SCOPE = '''
def pick(x):
    return x


def pick(x):
    return -x
'''

MODULE_SCOPE_CALLED = MODULE_SCOPE + '''

def use(items):
    return pick(items)
'''


def _collisions(tmp_path: Path, source: str) -> list[anomalies.Anomaly]:
    store: Store = _analyze(tmp_path, {"prog.py": source})
    try:
        return [a for a in detect(store).items if a.kind == "NAME_COLLISION"]
    finally:
        store.close()


@pytest.mark.parametrize("source", [REBOUND, USED_BETWEEN, ARM_APART],
                         ids=["create_standalone", "used-between", "arm-apart"])
def test_a_sequential_rebinding_is_not_a_collision(tmp_path: Path, source: str) -> None:
    assert _collisions(tmp_path, source) == []


def test_a_true_duplicate_is_still_broken(tmp_path: Path) -> None:
    found = _collisions(tmp_path, TRUE_DUPLICATE)
    assert [a.subject for a in found] == ["prog.main.pick"]
    assert found[0].severity == anomalies.BROKEN


def test_the_same_name_in_two_scopes_is_two_names(tmp_path: Path) -> None:
    assert _collisions(tmp_path, TWO_SCOPES) == []


def test_module_scope_is_never_excused(tmp_path: Path) -> None:
    found = _collisions(tmp_path, MODULE_SCOPE)
    assert [a.subject for a in found] == ["prog.pick"]


def test_the_message_says_every_call_resolves_only_when_one_does(tmp_path: Path) -> None:
    """Rule 13: *every call resolves to it* is a claim about `calls`, so it is printed only
    when a call names it. A call to a name defined twice is a lost edge and binds nothing,
    so the test is the name, not `callee_id`, or no collision would ever have a caller."""
    called = _collisions(tmp_path / "a", MODULE_SCOPE_CALLED)[0].detail
    assert "every call resolves to it" in _collisions(tmp_path / "c", TRUE_DUPLICATE)[0].detail
    uncalled = _collisions(tmp_path / "b", MODULE_SCOPE)[0].detail
    assert "every call resolves to it" in called
    assert "every call resolves to it" not in uncalled
    assert "No call in the map resolves to any of them." in uncalled


def test_each_half_of_the_judgement_is_load_bearing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mutation check: with the arms ignored, ARM_APART is reported; with no use between
    seen, USED_BETWEEN is. Each case is caught by its own half and nothing else."""
    monkeypatch.setattr(anomalies, "_decision_arms", lambda _s, _r: [])
    assert _collisions(tmp_path / "arms", ARM_APART), "the arm test decided nothing"
    assert _collisions(tmp_path / "arms2", USED_BETWEEN) == []
    monkeypatch.undo()

    real = anomalies.Store.query

    def no_use(self: Store, sql: str, *a: Any) -> Any:
        if "LEFT JOIN call_args" in sql:
            return []
        return real(self, sql, *a)

    monkeypatch.setattr(anomalies.Store, "query", no_use)
    assert _collisions(tmp_path / "use", USED_BETWEEN), "the use test decided nothing"
    assert _collisions(tmp_path / "use2", ARM_APART) == []
