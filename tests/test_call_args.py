"""What a caller actually passed, recorded as written.

Three claims, and they fail in three different ways.

**As written, not re-rendered.** `ast.unparse` would give back an expression that is
equivalent and not identical -- normalised spacing, canonical quotes, a wrapped argument
flattened onto one line. A reader goes looking in the file for the string this shows
them, so it is the file's own text that is recorded (rule 8: whole, never shortened at
ingest).

**Identity, and no position in it.** Two identical expressions in one routine are two
call sites, and the arguments of one must not land on the other. `make_id` is explicit
that a line number would retire every fact below an inserted import, so the discriminator
is an ordinal among identical expressions in the same caller and the id does not move
when the code around it does.

**Nothing dropped.** A `*args` or `**kwargs` is not one argument and cannot be bound to a
parameter by position, which is a reason to mark it and not a reason to omit it -- a call
that passed a splat and shows nothing has been reported as passing less than it does.
"""

from __future__ import annotations

from pathlib import Path

from dunneflow.extractors.python.extract import extract_file
from dunneflow.schema import call_site_id

WRITTEN = '''import os


def emit(a, b=1, *rest, key=None, **kw):
    return a


def caller(d, xs):
    emit(1, 2)
    emit(  d["k"]  , b=2)
    emit(*xs, **d)
    emit(
        {"a": 1},
        b=[
            1,
            2,
        ],
    )
    emit("naïve ✓", b=3)
    emit(1, 2)
'''


def _extract(tmp_path: Path, src: str, name: str = "m.py"):
    pkg = tmp_path / "pkg"
    pkg.mkdir(exist_ok=True)
    f = pkg / name
    f.write_text(src, encoding="utf-8")
    return extract_file(f, tmp_path)


def _emits(facts):
    return [c for c in facts.calls if c.callee_expr == "emit"]


def test_an_argument_is_recorded_as_the_caller_wrote_it(tmp_path):
    calls = _emits(_extract(tmp_path, WRITTEN))
    args = calls[1].args
    # The padding inside the subscript survives; the padding around the argument is not
    # part of the argument. `ast.unparse` would return `d['k']` -- single quotes, a
    # different string from the one in the file.
    assert [a.expr for a in args] == ['d["k"]', "2"]
    assert args[1].keyword == "b"
    assert args[0].keyword is None


def test_a_wrapped_argument_is_kept_whole(tmp_path):
    calls = _emits(_extract(tmp_path, WRITTEN))
    wrapped = calls[3].args[1]
    assert wrapped.keyword == "b"
    # Four lines, and all four of them. Rule 8: a value shortened before it reaches the
    # store is lost for good rather than merely unshown.
    assert wrapped.expr.count("\n") == 3
    assert wrapped.expr.startswith("[")
    assert wrapped.expr.rstrip().endswith("]")


def test_a_non_ascii_line_does_not_shorten_the_arguments_after_it(tmp_path):
    """`col_offset` is a byte offset, and a character slice is silently short.

    Written from the defect: on `emit("naïve ✓", b=3)` a character slice returns `)`
    for the second argument -- a plausible expression, and not the one that is there.
    Two multi-byte characters, so the slice is two positions adrift.
    """
    calls = _emits(_extract(tmp_path, WRITTEN))
    args = calls[4].args
    assert [a.expr for a in args] == ['"naïve ✓"', "3"]


def test_a_splat_is_marked_and_never_dropped(tmp_path):
    calls = _emits(_extract(tmp_path, WRITTEN))
    args = calls[2].args
    assert [a.expr for a in args] == ["*xs", "**d"]
    assert all(a.splat for a in args)
    # `**d` arrives as a keyword whose name is None. It is a splat, not a keyword
    # called nothing, and reading it as one would offer a binding that cannot exist.
    assert all(a.keyword is None for a in args)


def test_two_identical_calls_are_two_sites_with_their_own_arguments(tmp_path):
    src = '''def emit(a):
    return a


def caller(x, y):
    emit(x); emit(y)
'''
    calls = _emits(_extract(tmp_path, src))
    assert len(calls) == 2
    # Same expression, same line. Without an ordinal these are one site and one of the
    # two argument lists is lost.
    assert calls[0].line == calls[1].line
    assert calls[0].site_id != calls[1].site_id
    assert [a.expr for a in calls[0].args] == ["x"]
    assert [a.expr for a in calls[1].args] == ["y"]


def test_a_site_id_does_not_move_when_the_code_above_it_does(tmp_path):
    # The same file, edited -- not two files. A different name is a different module
    # and so a different caller, which would make this pass for the wrong reason.
    before = _emits(_extract(tmp_path, WRITTEN))
    after = _emits(_extract(tmp_path, "import sys\n\n" + WRITTEN))
    assert [c.line for c in before] != [c.line for c in after]
    assert [c.site_id for c in before] == [c.site_id for c in after]


def test_the_ordinal_is_per_caller_and_per_expression(tmp_path):
    calls = _emits(_extract(tmp_path, WRITTEN))
    caller_id = calls[0].caller_id
    assert [c.site_id for c in calls] == [
        call_site_id(caller_id, "emit", i) for i in range(len(calls))
    ]


def test_every_call_site_carries_an_identity(tmp_path):
    """Assert the total, not the cases.

    The failure this guards against is a *new* place that appends a `CallSite` without
    going through the one door that assigns the id -- so counting the ones we know about
    would pass over exactly the defect.
    """
    facts = _extract(tmp_path, WRITTEN)
    assert facts.calls
    assert all(c.site_id for c in facts.calls)
    assert len({c.site_id for c in facts.calls}) == len(facts.calls)


def test_a_synthetic_dispatch_carries_an_identity_and_no_arguments(tmp_path):
    """argparse binds a handler; the call it stands for is nowhere to read.

    `p.set_defaults(func=_cmd)` is recorded as an edge because `args.func(args)` is
    invisible to static analysis. It has an identity like every other site, and no
    arguments -- which is the honest answer rather than an omission.
    """
    src = '''import argparse


def _cmd(args):
    return args


def build(sub):
    p = sub.add_parser("serve")
    p.set_defaults(func=_cmd)
'''
    facts = _extract(tmp_path, src)
    dispatch = [c for c in facts.calls if c.callee_expr == "_cmd"]
    assert len(dispatch) == 1
    assert dispatch[0].site_id
    assert dispatch[0].args == []


# --------------------------------------------------------------------------- #
# In the store. An argument hangs off a call site rather than off a file, so the two
# ways it can go wrong are an orphan left behind and a row that names no live site.
# --------------------------------------------------------------------------- #


def test_the_arguments_reach_the_store_attached_to_their_call(analyzed):
    rows = analyzed.query(
        "SELECT a.idx, a.expr, a.keyword, a.splat FROM call_args a"
        " JOIN calls c ON c.site_id = a.site_id"
        " WHERE c.callee_expr = 'requests.post' ORDER BY a.idx"
    )
    assert [(r["expr"], r["keyword"]) for r in rows] == [
        ("url", None), ('{"a": 1}', "json"), ("5.0", "timeout")
    ]
    assert not any(r["splat"] for r in rows)


def test_every_stored_argument_names_a_call_that_is_still_there(analyzed):
    orphans = analyzed.query(
        "SELECT COUNT(*) AS n FROM call_args a"
        " WHERE NOT EXISTS (SELECT 1 FROM calls c WHERE c.site_id = a.site_id)"
    )[0]["n"]
    assert orphans == 0
    blank = analyzed.query("SELECT COUNT(*) AS n FROM calls WHERE site_id = ''")[0]["n"]
    assert blank == 0


def test_re_extracting_a_file_takes_its_arguments_with_it(tmp_path):
    """`call_args` has no `file` column, so the purge has to reach it through `calls`.

    Written from the order it fails in: empty `calls` for the file first and the
    arguments can no longer be named at all, and they sit in the store for ever
    attached to a site that no longer exists.
    """
    from dunneflow.store import Store
    from dunneflow.walk import analyze_tree

    tree = tmp_path / "prog"
    tree.mkdir()
    (tree / "m.py").write_text(
        "def emit(a):\n    return a\n\n\ndef go():\n    emit(1)\n", encoding="utf-8")
    store = Store(tmp_path / "graph.db")
    try:
        analyze_tree(tree, store)
        assert store.query("SELECT COUNT(*) AS n FROM call_args")[0]["n"] >= 1
        store.forget_file("m.py")
        assert store.query("SELECT COUNT(*) AS n FROM calls")[0]["n"] == 0
        assert store.query("SELECT COUNT(*) AS n FROM call_args")[0]["n"] == 0
    finally:
        store.close()
