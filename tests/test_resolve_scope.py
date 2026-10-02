"""What a name can reach: closures, local bindings, and the classes a call builds.

BACKLOG 24 and 14, both found while photographing the tutorial on 2026-10-02:

* `render.snapshot.render_maps` writes `say = emit or (lambda _: None)` and calls `say(...)`.
  The map bound all five calls, INFERRED, to `web.analysis.run.say` -- a closure in another
  module, and the only routine in the program with that name. Two defects in one edge: a
  local binding was matched by name, and a closure was offered to the whole program.
* `BindingNote(...)`, a dataclass in the caller's own module, was EXTERNAL once per call
  site, because the resolver's index held routines and nothing else.

Every test here builds a real tree and runs the real extractor, because the first half of
the first fix lives in the reader and a hand-written row would assume it.
"""

from __future__ import annotations

from pathlib import Path

from dunneflow.resolve.calls import resolve_calls
from dunneflow.schema import Confidence
from dunneflow.store import Store
from dunneflow.walk import analyze_tree


def _read(tmp_path: Path, files: dict[str, str]) -> Store:
    root = tmp_path / "src" / "pkg"
    root.mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    for name, body in files.items():
        (root / name).write_text(body, encoding="utf-8")
    store = Store(tmp_path / "g.db")
    analyze_tree(root.parent, store)
    resolve_calls(store)
    return store


def _call(store: Store, caller: str, expr: str):
    rows = store.query(
        "SELECT c.callee_id, c.external, c.confidence, c.constructs, c.bound_locally,"
        "       r.qualname AS callee"
        "  FROM calls c JOIN routines k ON k.id = c.caller_id"
        "  LEFT JOIN routines r ON r.id = c.callee_id"
        " WHERE k.name = ? AND c.callee_expr = ?", (caller, expr))
    assert rows, f"no call to {expr} from {caller}"
    return rows[0]


RUNNER = (
    "def run(note):\n"
    "    def say(msg):\n"
    "        note(msg)\n"
    "    say('start')\n"
    "    def finish():\n"
    "        say('done')\n"
    "    finish()\n"
)


def test_a_local_binding_never_resolves_to_a_routine_elsewhere(tmp_path):
    """The `render_maps` case exactly: the one `say` in the program is not the one held."""
    store = _read(tmp_path, {
        "runner.py": RUNNER,
        "snapshot.py": (
            "def render_maps(emit=None):\n"
            "    say = emit or (lambda _: None)\n"
            "    say('rendering')\n"
        ),
    })
    try:
        row = _call(store, "render_maps", "say")
        assert row["bound_locally"] == 1
        assert row["callee_id"] is None, f"bound to {row['callee']}"
    finally:
        store.close()


def test_a_parameter_called_is_not_matched_by_name(tmp_path):
    """`note(msg)` calls what `run` was handed, and a routine called `note` is not it."""
    store = _read(tmp_path, {
        "runner.py": RUNNER,
        "other.py": "def note(x):\n    return x\n",
    })
    try:
        assert _call(store, "say", "note")["callee_id"] is None
    finally:
        store.close()


def test_a_closure_is_reachable_from_its_scope_and_nowhere_else(tmp_path):
    """Inside `run`, and from a sibling closure, `say` is the closure. Outside, it is not."""
    store = _read(tmp_path, {
        "runner.py": RUNNER + (
            "\n"
            "def elsewhere():\n"
            "    say('x')\n"
        ),
    })
    try:
        inside = _call(store, "run", "say")
        assert inside["callee"] == "pkg.runner.run.say"
        assert inside["confidence"] == Confidence.CERTAIN.value
        assert _call(store, "finish", "say")["callee"] == "pkg.runner.run.say"
        assert _call(store, "elsewhere", "say")["callee_id"] is None
    finally:
        store.close()


def test_a_closure_never_answers_a_bare_name_in_another_module(tmp_path):
    """The program-wide name index must not hold closures at all."""
    store = _read(tmp_path, {
        "runner.py": RUNNER,
        "caller.py": "def go():\n    say('hi')\n",
    })
    try:
        assert _call(store, "go", "say")["callee_id"] is None
    finally:
        store.close()


def test_a_nested_def_is_still_called_by_its_name(tmp_path):
    """The local-binding rule must not swallow the closure the routine itself defines."""
    store = _read(tmp_path, {"runner.py": RUNNER})
    try:
        assert _call(store, "run", "say")["bound_locally"] == 0
    finally:
        store.close()


CLASSES = (
    "from dataclasses import dataclass\n"
    "\n"
    "@dataclass(frozen=True)\n"
    "class Note:\n"
    "    text: str\n"
    "\n"
    "class Plain:\n"
    "    def __init__(self, x):\n"
    "        self.x = x\n"
    "\n"
    "class Child(Plain):\n"
    "    pass\n"
    "\n"
    "class Failure(Exception):\n"
    "    pass\n"
    "\n"
    "def make():\n"
    "    Note('a')\n"
    "    Plain(1)\n"
    "    Child(2)\n"
    "    raise Failure('no')\n"
)


def test_a_dataclass_of_this_program_is_not_external(tmp_path):
    """BACKLOG 14: built here, defined here, and once per call site EXTERNAL until now."""
    store = _read(tmp_path, {"model.py": CLASSES})
    try:
        row = _call(store, "make", "Note")
        assert row["external"] == 0
        assert row["callee_id"] is None
        assert row["constructs"] == "pkg.model.Note"
    finally:
        store.close()


def test_a_class_with_a_constructor_binds_to_it(tmp_path):
    store = _read(tmp_path, {"model.py": CLASSES})
    try:
        row = _call(store, "make", "Plain")
        assert row["callee"] == "pkg.model.Plain.__init__"
        assert row["confidence"] == Confidence.CERTAIN.value
    finally:
        store.close()


def test_an_inherited_constructor_is_followed_to_the_base(tmp_path):
    """Rule 11 for constructors: `Child(2)` runs `Plain.__init__`."""
    store = _read(tmp_path, {"model.py": CLASSES})
    try:
        assert _call(store, "make", "Child")["callee"] == "pkg.model.Plain.__init__"
    finally:
        store.close()


def test_a_class_whose_constructor_is_outside_is_still_this_programs(tmp_path):
    """`Failure` inherits `Exception.__init__`, but what it builds is defined here."""
    store = _read(tmp_path, {"model.py": CLASSES})
    try:
        row = _call(store, "make", "Failure")
        assert (row["external"], row["constructs"]) == (0, "pkg.model.Failure")
    finally:
        store.close()


def test_an_imported_class_is_found_through_its_import(tmp_path):
    store = _read(tmp_path, {
        "model.py": CLASSES,
        "use.py": (
            "from .model import Note\n"
            "from . import model\n"
            "\n"
            "def build():\n"
            "    Note('x')\n"
            "    model.Plain(3)\n"
        ),
    })
    try:
        assert _call(store, "build", "Note")["constructs"] == "pkg.model.Note"
        assert _call(store, "build", "model.Plain")["callee"] == "pkg.model.Plain.__init__"
    finally:
        store.close()


def test_a_class_from_outside_the_program_stays_external(tmp_path):
    """`OrderedDict()` is the standard library's, whatever this program defines."""
    store = _read(tmp_path, {
        "model.py": CLASSES,
        "use.py": (
            "from collections import OrderedDict\n"
            "\n"
            "def build():\n"
            "    OrderedDict()\n"
        ),
    })
    try:
        row = _call(store, "build", "OrderedDict")
        assert (row["external"], row["constructs"]) == (1, "")
    finally:
        store.close()


def test_the_resolution_figures_count_constructions_on_their_own(tmp_path):
    """Resolved plus external plus constructions is the whole, and no figure is short."""
    root = tmp_path / "src" / "pkg"
    root.mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "model.py").write_text(CLASSES, encoding="utf-8")
    store = Store(tmp_path / "g.db")
    try:
        analyze_tree(root.parent, store)
        stats = resolve_calls(store)
        assert stats.constructions == 2
        assert stats.resolved + stats.external + stats.constructions == stats.total
    finally:
        store.close()
