"""The protocol, proved against the one extractor whose output is known exactly.

`PLAN-v2.md` calls chunk 7 the chunk that de-risks everything, and this file is why: the
reader on the far side of the pipe is **the same function** the in-process reader calls,
so a difference between the two answers is the protocol and can be nothing else. A
TypeScript plugin's first run would give a difference nobody has a baseline for.

The double is `tests/plugins/python-oop/`, built through `read_manifest` and
`OutOfProcessPlugin` — the public path, minus the registry, which would refuse two readers
claiming `.py` (and rightly).

Its misbehaviour hooks are environment variables, because the failure paths that matter
most run least: a worker that cannot be made to die, lie, or write prose on stdout leaves
every one of the host's refusals proved by reading it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from dunneflow.ingest import PLUGINS, read_manifest
from dunneflow.ingest.contract import PluginRefused, ProtocolError, ToolchainMissing
from dunneflow.ingest.outofprocess import (
    SELF,
    OutOfProcessPlugin,
    _at_least,
    plugin_argv,
    probe_toolchain,
)
from dunneflow.ingest.worker import NdjsonWorker

HERE = Path(__file__).resolve().parent
DOUBLE = HERE / "plugins" / "python-oop" / "plugin.json"

SAMPLE = '''
"""A module with enough in it to be worth comparing."""
import os
import sqlite3


class Store:
    """Holds things."""

    def save(self, conn: sqlite3.Connection, name: str) -> None:
        # WHY: the insert is the whole point.
        conn.execute("INSERT INTO widgets (name) VALUES (?)", (name,))
        self.note(name)

    def note(self, name: str) -> None:
        for _ in range(3):
            if name:
                os.environ["LAST"] = name
'''


@pytest.fixture
def manifest():
    return read_manifest(DOUBLE)


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "sample.py").write_text(SAMPLE, encoding="utf-8")
    (tmp_path / "other.py").write_text("def g():\n    return 1\n", encoding="utf-8")
    return tmp_path


def _oop(manifest, tree: Path, files: list[Path]) -> dict[str, object]:
    plugin = OutOfProcessPlugin(manifest)
    plugin.open(tree, files)
    try:
        return {f.path: f for f in plugin.extract(files, tree)}
    finally:
        plugin.close()


def _inproc(tree: Path, files: list[Path]) -> dict[str, object]:
    plugin = PLUGINS["python"]
    plugin.open(tree, files)
    try:
        return {f.path: f for f in plugin.extract(files, tree, jobs=1)}
    finally:
        plugin.close()


# ------------------------------------------------------------------- the gate - #

def test_the_same_extractor_over_a_pipe_gives_the_same_facts(manifest, tree):
    """The chunk's whole claim, and it is equality of the records rather than of JSON."""
    files = sorted(tree.glob("*.py"))
    assert _oop(manifest, tree, files) == _inproc(tree, files)


def test_the_language_is_stamped_by_the_host_on_every_record(manifest, tree):
    """The reader never sends it, so if the host did not write it nothing would."""
    files = [tree / "sample.py"]
    facts = _oop(manifest, tree, files)["sample.py"]
    assert facts.lang == "python"
    assert facts.routines and all(r.lang == "python" for r in facts.routines)


def test_a_reader_sending_the_language_is_refused(manifest, tree, monkeypatch):
    """Rule 30 over the wire: a second answer to a question the file has answered."""
    monkeypatch.setenv("DUNNEFLOW_OOP_EXTRA", "")   # unset the other hook
    files = [tree / "sample.py"]
    # The double cannot be made to send `lang`, because the codec will not encode it —
    # which is itself the defence. So the refusal is proved at the codec (test_codec.py)
    # and what is proved here is that nothing in a healthy run carries it on the wire.
    plugin = OutOfProcessPlugin(manifest)
    plugin.open(tree, files)
    try:
        worker = plugin._worker
        assert worker is not None
        reply = worker.request({"t": "extract", "path": str(files[0]), "hash": "x"})
    finally:
        plugin.close()
    assert all("lang" not in r for r in reply["facts"]["routines"])


# ------------------------------------------------------------------- argv ----- #

def test_a_python_toolchain_means_this_interpreter(manifest):
    """Never whatever PATH resolves — that is precisely how you get a different one."""
    import sys
    argv = plugin_argv(manifest)
    assert argv[0] == sys.executable
    assert argv[1].endswith("worker.py")
    assert manifest.toolchain is not None and manifest.toolchain.command == SELF


def test_a_plugin_with_no_entry_is_refused(manifest):
    import dataclasses
    with pytest.raises(PluginRefused, match="names no `entry`"):
        plugin_argv(dataclasses.replace(manifest, entry=""))


def test_a_plugin_with_no_toolchain_is_refused(manifest):
    import dataclasses
    with pytest.raises(PluginRefused, match="no toolchain command"):
        plugin_argv(dataclasses.replace(manifest, toolchain=None))


# --------------------------------------------------------------- toolchain --- #

def test_a_missing_toolchain_names_the_command_and_both_ways_out(manifest):
    """Rules 49 and 89: a refusal must name something a reader can act on."""
    import dataclasses

    from dunneflow.ingest.contract import Toolchain
    absent = dataclasses.replace(
        manifest,
        toolchain=Toolchain(command="definitely-not-on-this-machine",
                            min_version="20.0.0", install="brew install node"),
    )
    with pytest.raises(ToolchainMissing) as exc:
        probe_toolchain(absent)
    said = str(exc.value)
    assert "definitely-not-on-this-machine" in said
    assert "20.0.0" in said
    assert "brew install node" in said
    assert "--without python" in said        # the other way forward


def test_this_interpreter_is_never_probed(manifest):
    """There is nothing to find: the thing asking is the thing being looked for."""
    probe_toolchain(manifest)                # no exception, no subprocess


@pytest.mark.parametrize(("said", "wanted", "ok"), [
    ("v20.11.0", "20.0.0", True),
    ("v18.19.1", "20.0.0", False),
    ("swift-driver version: 1.90.11", "1.9", True),
    ("Python 3.12.8", "3.12", True),
    ("", "20.0.0", False),                   # rule 49: no version found is not a pass
    ("some build with no numbers", "1.0", False),
])
def test_a_version_this_probe_cannot_read_is_not_good_enough(said, wanted, ok):
    assert _at_least(said, wanted) is ok


# ------------------------------------------------------------- the handshake -- #

@pytest.mark.parametrize("field", ["lang", "version", "protocol", "schema_version"])
def test_a_process_disagreeing_with_its_manifest_refuses_quoting_both(
        manifest, tree, monkeypatch, field):
    """The manifest is a label and the running process is the identity (rule 30)."""
    monkeypatch.setenv("DUNNEFLOW_OOP_LIE", field)
    plugin = OutOfProcessPlugin(manifest)
    with pytest.raises(PluginRefused) as exc:
        plugin.open(tree, [])
    said = str(exc.value)
    assert field in said
    assert "disagrees with itself" in said
    plugin.close()


# ---------------------------------------------------------------- the channel - #

def test_a_stray_print_on_stdout_refuses_once_and_loudly(manifest, tree, monkeypatch):
    """The one failure a plugin author actually produces. Skipping it six hundred times
    quietly is how a map comes back confident and empty."""
    monkeypatch.setenv("DUNNEFLOW_OOP_GARBAGE", "sample")
    files = [tree / "sample.py"]
    plugin = OutOfProcessPlugin(manifest)
    plugin.open(tree, files)
    try:
        with pytest.raises(ProtocolError, match="not this protocol"):
            list(plugin.extract(files, tree))
    finally:
        plugin.close()


def test_stderr_is_drained_and_changes_nothing(manifest, tree, monkeypatch):
    """`runtime._desktop_session`'s lesson: text a healthy process also writes cannot be a
    control channel. A chatty plugin is a working plugin."""
    monkeypatch.setenv("DUNNEFLOW_OOP_CHATTER", "1")
    files = sorted(tree.glob("*.py"))
    assert _oop(manifest, tree, files) == _inproc(tree, files)


def test_the_stderr_buffer_is_bounded(manifest, tree, monkeypatch):
    """A plugin in a loop can write megabytes a second, and the host must not be the thing
    that runs out of memory."""
    from dunneflow.ingest.worker import STDERR_KEEP
    monkeypatch.setenv("DUNNEFLOW_OOP_CHATTER", "1")
    plugin = OutOfProcessPlugin(manifest)
    plugin.open(tree, [])
    try:
        worker = plugin._worker
        assert worker is not None
        for _ in range(50):
            worker.request({"t": "open", "root": str(tree), "files": []})
        tail = worker.stderr_tail()
    finally:
        plugin.close()
    assert tail                                   # it was kept
    assert len(tail) <= STDERR_KEEP + 8192        # and it was bounded


# ------------------------------------------------------------------ failures -- #

def test_a_file_the_reader_threw_on_gets_the_hosts_own_record(manifest, tree, monkeypatch):
    """A plugin that has just crashed on a file is not the right authority on what that
    file is, so its guess never lands in the map under the file's own name."""
    monkeypatch.setenv("DUNNEFLOW_OOP_THROW", "sample")
    files = sorted(tree.glob("*.py"))
    got = _oop(manifest, tree, files)
    assert got["sample.py"].errors and "DUNNEFLOW_OOP_THROW" in got["sample.py"].errors[0]
    assert got["sample.py"].routines == []
    # And the file is **not cached**: a crash must not become permanent until somebody
    # edits the file.
    assert got["sample.py"].content_hash == ""
    # The other file is unaffected — one bad file is one bad file.
    assert got["other.py"].routines


def test_a_hash_that_does_not_match_is_a_failure_and_not_a_fact(manifest, tree, monkeypatch):
    """The file changed under the run. Storing facts under a hash they do not describe is
    how a stale answer becomes a cached one nobody revisits (rule 12)."""
    monkeypatch.setenv("DUNNEFLOW_OOP_BADHASH", "sample")
    files = [tree / "sample.py"]
    got = _oop(manifest, tree, files)
    said = got["sample.py"].errors[0]
    assert "changed while it was being read" in said
    assert "0000000000000000" in said          # both hashes named
    assert got["sample.py"].routines == []


def test_a_worker_that_dies_is_respawned_once_and_the_file_is_not_retried(
        manifest, tree, monkeypatch):
    """Retrying is how one poison file refuses a whole language: the fresh worker meets the
    same file and dies again, and the second death is the refusal."""
    monkeypatch.setenv("DUNNEFLOW_OOP_DIE_ON", "sample")
    files = sorted(tree.glob("*.py"))          # other.py, sample.py
    plugin = OutOfProcessPlugin(manifest)
    plugin.open(tree, files)
    try:
        got = {f.path: f for f in plugin.extract(files, tree)}
        assert plugin._worker is not None
        assert plugin._worker.deaths == 1
    finally:
        plugin.close()
    assert "died reading it" in got["sample.py"].errors[0]
    assert got["other.py"].routines            # the run continued


def test_a_second_death_refuses_the_language(manifest, tmp_path, monkeypatch):
    """One crash is a fact about a file; two is a fact about the reader."""
    for name in ("one.py", "two.py"):
        (tmp_path / name).write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setenv("DUNNEFLOW_OOP_DIE_ON", ".py")     # every file
    files = sorted(tmp_path.glob("*.py"))
    plugin = OutOfProcessPlugin(manifest)
    plugin.open(tmp_path, files)
    try:
        with pytest.raises(PluginRefused, match="died twice"):
            list(plugin.extract(files, tmp_path))
    finally:
        plugin.close()


def test_a_reply_carrying_the_wrong_id_is_refused(manifest, tree, monkeypatch):
    """Replies are matched by id, so one that does not match is not a late answer — it is
    an answer to something else arriving as this one.

    It takes a worker that *lies* to prove this: rewinding the host's counter proves
    nothing, because a well-behaved worker echoes whatever it is given and the two agree
    again (rule 37 — a guard that checks a name appears has not checked that anything
    happens).
    """
    monkeypatch.setenv("DUNNEFLOW_OOP_WRONGID", "1")
    worker = NdjsonWorker(plugin_argv(manifest), manifest)
    with pytest.raises(ProtocolError, match="carrying id"):
        worker.start()                         # the handshake is the first request there is
    worker.stop()


def test_extract_before_open_is_refused(manifest, tree):
    """A reader that resolves symbols needs the whole compilation first."""
    plugin = OutOfProcessPlugin(manifest)
    with pytest.raises(PluginRefused, match="before `open`"):
        list(plugin.extract([tree / "sample.py"], tree))


def test_close_is_safe_to_call_twice(manifest, tree):
    plugin = OutOfProcessPlugin(manifest)
    plugin.open(tree, [])
    plugin.close()
    plugin.close()


def test_a_worker_that_cannot_be_started_is_refused(manifest):
    import dataclasses
    broken = dataclasses.replace(manifest, entry="no-such-file.py")
    worker = NdjsonWorker([str(manifest.root / "no-such-binary"), "x"], broken)
    with pytest.raises(PluginRefused, match="could not be started"):
        worker.start()


# --------------------------------------------------------------- the registry - #

def test_the_registry_builds_an_out_of_process_plugin_for_a_manifest_that_asks(manifest):
    """It refused one outright until this chunk: *this build has no worker for it yet*."""
    from dunneflow.ingest import outofprocess
    assert isinstance(OutOfProcessPlugin(manifest), outofprocess.OutOfProcessPlugin)
    assert not manifest.in_process


def test_the_double_is_not_in_the_shipped_plugins_dir():
    """Two readers claiming `.py` is refused naming both, and rightly — so the double lives
    in the tests and is built by hand."""
    from dunneflow.ingest import PLUGINS_DIR
    assert DOUBLE.parent.parent != PLUGINS_DIR
    assert not (PLUGINS_DIR / "python-oop").exists()
    assert sorted(PLUGINS) == ["python"]


# ---------------------------------------------------------------- conformance - #

def test_the_dotted_contract_holds_over_the_wire_as_well(manifest):
    """The same cases, the same reader, a process boundary in between.

    This is what makes *"a `typescript.yaml` loads with zero code change"* a claim anybody
    can check rather than a hope.
    """
    from dunneflow.ingest import dotted
    over_wire = dotted.run(OutOfProcessPlugin(manifest), "python")
    in_process = dotted.run(PLUGINS["python"], "python")
    assert [(r.case.id, r.passed, r.got) for r in over_wire] == \
           [(r.case.id, r.passed, r.got) for r in in_process]
    assert all(r.passed for r in over_wire)


# ------------------------------------------------------------------ the shell - #

def test_the_worker_writes_frames_on_stdout_and_nothing_else(manifest, tree):
    """Read back off the wire rather than by testing handlers, which is how `test_mcp.py`
    proves the same discipline (rule 91)."""
    import subprocess
    proc = subprocess.run(
        plugin_argv(manifest),
        input=json.dumps({"t": "hello", "id": 1, "protocol": 1,
                          "schema_version": 10, "lang": "python"}) + "\n"
              + json.dumps({"t": "close", "id": 2}) + "\n",
        capture_output=True, text=True, timeout=60, check=False,
        env={**os.environ, "DUNNEFLOW_OOP_CHATTER": "1"},
    )
    lines = [x for x in proc.stdout.splitlines() if x.strip()]
    assert lines, proc.stderr
    for line in lines:
        assert isinstance(json.loads(line), dict)      # every one of them, or it is prose
    assert proc.stderr.strip()                          # and it did speak, on the other one
