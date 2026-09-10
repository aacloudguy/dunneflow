"""What a packaged DunneFlow has to get right, tested without packaging one.

Every question here has two answers -- one for a source checkout and one for a frozen
application -- and only the first is ever exercised by running the tests. So the second
world is put on by monkeypatching `sys.frozen` and `sys._MEIPASS`, which is exactly what
PyInstaller sets and nothing else does.

The guards at the foot are the ones that matter longest. A build defect here does not
raise: it produces a confident wrong answer -- a fingerprint of nothing, a page of 404s,
a subprocess that never starts -- and the next person to add a data path will add it the
way every one of these was written, with `Path(__file__)`.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from dunneflow import macapp, runtime
from dunneflow.cli import _out_root, build_parser
from dunneflow.detectors import (
    RulesMissing,
    code_extraction_inputs,
    fingerprint_files,
    rules_fingerprint,
)
from dunneflow.detectors.prose import doc_extraction_inputs, doc_rules_fingerprint
from dunneflow.web.analysis import argv

SRC = Path(runtime.__file__).parent

# The sha256 of nothing, shortened the way `fingerprint_files` shortens. This is what the
# function used to return for an empty input, and it is the whole reason for the refusal:
# it looks exactly like a fingerprint and compares equal to itself for ever, so rule 12's
# guarantee would have been enforced by a constant.
HASH_OF_NOTHING = "e3b0c44298fc1c14"


@pytest.fixture
def as_frozen(monkeypatch, tmp_path):
    """Put the module under test in the world PyInstaller makes.

    `_MEIPASS` is the unpacked bundle, and the spec places this package's data under
    `dunneflow/` inside it -- so the fixture builds that directory rather than pointing at
    the bare temporary path, because the layout is the thing being asserted about.
    """
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    (tmp_path / "dunneflow").mkdir()
    # **The pointer is a file in the developer's real home, and this fixture makes tests
    # read it.** `default_output_root()` consults it once `frozen()` is true, so without
    # this line every assertion about the frozen root depends on whether whoever is running
    # the suite has ever moved their own maps -- which is exactly how this was found: a
    # manual test left a pointer at a scratchpad directory and `test_the_output_root_of_an
    # _application` began failing with a path from another session. Pointed at the
    # temporary directory so the tests are hermetic and no test can write to the real one.
    monkeypatch.setattr(runtime, "platform_output_root", lambda: tmp_path / "AppSupport")
    return tmp_path


# --------------------------------------------------------------------------- #
# The fingerprint, which is the blocker that would have failed silently


def test_a_fingerprint_of_nothing_is_refused():
    with pytest.raises(RulesMissing) as exc:
        fingerprint_files([])
    # The sentence has to name where this build looked, because the answer to it is a
    # change to a spec file and nothing else (rule 89).
    assert str(SRC) in str(exc.value)


def test_a_named_and_absent_input_is_refused(tmp_path):
    """The frozen failure is this one, not the empty list.

    `doc_extraction_inputs()` returns `Path(__file__)` unconditionally, so frozen the list
    is never empty -- it holds a path that is not a file. An emptiness check alone passes
    that straight through to a `FileNotFoundError` raised from inside a hash.
    """
    here = tmp_path / "real.yaml"
    here.write_text("a: 1")
    with pytest.raises(RulesMissing) as exc:
        fingerprint_files([here, tmp_path / "gone.yaml"])
    assert "gone.yaml" in str(exc.value)
    assert "1 of 2" in str(exc.value)


def test_a_directory_is_not_a_rule_file(tmp_path):
    """`is_file()` rather than `exists()`, and the difference is a real mistake.

    A `datas` entry that names a directory where a file was meant unpacks as a directory,
    which exists -- and then `read_bytes()` raises `IsADirectoryError` from inside the
    hash, one frame further on than the `FileNotFoundError` above.
    """
    (tmp_path / "docs").mkdir()
    with pytest.raises(RulesMissing):
        fingerprint_files([tmp_path / "docs"])


def test_neither_fingerprint_is_the_hash_of_nothing():
    assert rules_fingerprint() != HASH_OF_NOTHING
    assert doc_rules_fingerprint() != HASH_OF_NOTHING
    assert rules_fingerprint() != doc_rules_fingerprint()


@pytest.mark.parametrize("inputs", [code_extraction_inputs, doc_extraction_inputs],
                         ids=["code", "docs"])
def test_every_extraction_input_is_a_file_that_exists(inputs):
    """The membership assertion the two `*_inputs` functions were split out for.

    A missing entry is now loud rather than silent, so this is no longer the only thing
    standing between a bad bundle and a hash of nothing -- but it is the one that says
    *which* file, at the moment somebody moves one.
    """
    found = inputs()
    assert found, f"{inputs.__name__} found nothing"
    absent = [p for p in found if not p.is_file()]
    assert not absent, f"{inputs.__name__} names files that are not there: {absent}"


def test_the_two_keys_do_not_share_a_reader():
    """Editing a prose rule must not discard the code graph, and the reverse.

    Stated in `rules_fingerprint`'s docstring as the reason `detectors/docs/` and
    `prose.py` are absent from the code key. Asserted here because both lists now come
    from `resource_root()`, and a resource root is exactly the sort of change that makes
    two globs start overlapping.
    """
    code = {p.relative_to(SRC) for p in code_extraction_inputs()}
    docs = {p.relative_to(SRC) for p in doc_extraction_inputs()}
    # By relative path and never by name: both keys hold a file called `__init__.py`, and
    # they are two different files. That is `fingerprint_files`' own labelling argument,
    # and comparing names here would report an overlap that does not exist.
    assert code & docs == {Path("detectors/annotations.yaml")}


# --------------------------------------------------------------------------- #
# The two worlds


def test_this_is_not_a_frozen_build():
    assert runtime.frozen() is False
    assert runtime.resource_root() == SRC


def test_the_bundle_keeps_the_package_as_its_last_segment(as_frozen):
    """`fingerprint_files` labels each input relative to this root.

    So a bundle laid out with `dunneflow/` under `_MEIPASS` yields the labels the checkout
    yields -- `detectors/python.yaml`, not `python.yaml` -- and the two builds agree on a
    fingerprint at the same commit. Laid out any other way they would refuse each other's
    maps under rule 12, which is the opposite of what that rule is for.
    """
    assert runtime.frozen() is True
    assert runtime.resource_root() == as_frozen / "dunneflow"
    assert runtime.resource_root().name == SRC.name


def test_self_argv_names_a_module_only_where_there_is_an_interpreter(as_frozen):
    """`-m dunneflow.cli` is meaningless to a frozen binary; it *is* DunneFlow."""
    assert runtime.self_argv("analyze", "/tmp/x") == [sys.executable, "analyze", "/tmp/x"]


def test_self_argv_from_a_checkout():
    assert runtime.self_argv("analyze") == [sys.executable, "-m", "dunneflow.cli", "analyze"]


def test_the_analysis_subprocess_runs_this_same_build(as_frozen, tmp_path):
    """Blocker 3, at the surface it would have broken.

    **+ Analyze a directory...** is the only way a first-time reader gets a map at all,
    and it is the one build where it is the only way in.
    """
    cmd = argv(tmp_path, "x", tmp_path, docs=True)
    assert "-m" not in cmd
    assert cmd[0] == sys.executable
    assert cmd[1] == "analyze"
    assert "--progress-json" in cmd and "--quiet" in cmd


def test_the_output_root_from_a_checkout():
    assert runtime.default_output_root() == Path("output")


@pytest.mark.skipif(sys.platform != "darwin", reason="the other two branches are untested")
def test_the_output_root_of_an_application():
    """Application Support, never Documents -- and that is not tidiness.

    `source.db` holds the private source of whatever was read, and `~/Documents` is swept
    into iCloud Drive on a signed-in Mac. That would be egress by accident, out of a tool
    whose posture is deterministic and local (design rule 14).

    Asked of `platform_output_root`, which is where this claim lives now: once the root
    became movable, `default_output_root()` answers *what this reader chose* and this
    answers *where it goes when they have not chosen*. Only the second is a claim about
    Apple's layout, and only the second can be asserted without a pointer in the way.
    """
    root = runtime.platform_output_root()
    assert root == Path.home() / "Library" / "Application Support" / "DunneFlow"
    assert root.is_absolute()
    assert "Documents" not in root.parts


def test_an_application_that_has_chosen_nothing_gets_the_platform_root(as_frozen):
    """The two only come apart once somebody moves their maps, and this is the *before*.

    Worth its own test because it is the state every reader starts in, and because the
    fixture now points `platform_output_root` at a temporary directory -- so this also
    pins that a frozen build with no pointer consults nothing else.
    """
    assert runtime.read_root_pointer() is None
    assert runtime.default_output_root() == runtime.platform_output_root()


# --------------------------------------------------------------------------- #
# The guards


def _module_sources():
    for path in sorted(SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def test_only_runtime_finds_this_package_by_its_own_file():
    """`Path(__file__)` means *my files* in four places, and frozen it is wrong in all of them.

    A module imported out of a PyInstaller archive has a `__file__` naming a path that
    does not exist, so a glob under it comes back empty and a read of it raises. The four
    that mattered were the two rule directories, the two extractor trees they reach, and
    `web/`'s `static` and `vendor` -- a server that starts perfectly and serves 404s.

    The next one will be added by somebody who has not read any of that, which is what
    this is for. `runtime.py` is the one exemption because answering this question is what
    it is (rule 51).
    """
    offenders = []
    for path in _module_sources():
        if path.name == "runtime.py":
            continue
        # Parsed, never scanned. The first spelling of this guard read the file line by
        # line and reported **its own explanation of the rule** as a violation -- rule 34,
        # which is about exactly this: the thing being looked for hides in the prose about
        # it. An AST holds code and nothing else.
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Name) and node.id == "__file__":
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno}")
    assert not offenders, (
        "these derive a location from `__file__` rather than `runtime.resource_root()`, "
        "which is empty in a packaged application:\n  " + "\n  ".join(offenders))


def test_freeze_support_is_the_first_thing_main_does():
    """Blocker 2, asserted structurally rather than by running sixteen servers.

    macOS spawns, so every pool worker re-executes this program. In a checkout that
    re-executes the interpreter; in a frozen application it re-executes *the application*.
    Nothing in the parent raises, so `walk.py`'s serial fallback never sees it -- the
    parent is fine and the children are the program.

    A guard can only see that a call is written, never that it ran (rule 86). What it
    *can* see is that nothing is written in front of it, which is the whole requirement.
    """
    tree = ast.parse((SRC / "cli.py").read_text(encoding="utf-8"))
    main = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    body = [n for n in main.body if not isinstance(n, ast.Expr)
            or not isinstance(n.value, ast.Constant)]      # past the docstring
    first = body[0]
    assert isinstance(first, ast.Expr) and isinstance(first.value, ast.Call), \
        f"main() begins with {ast.dump(first)[:60]}, not a call"
    assert ast.unparse(first.value.func) == "multiprocessing.freeze_support"


def test_nothing_on_the_analysis_path_spells_out_the_interpreter():
    """One place decides how to run this build again, and it is `runtime.self_argv`.

    `sys.executable` beside a hand-written `-m` is the shape blocker 3 had. It is right in
    a checkout, which is why it survived: it fails only where it is the only way in.
    """
    offenders = []
    for path in _module_sources():
        if path.name == "runtime.py":
            continue
        # An AST, for the reason one guard up: written out as prose, `sys.executable`
        # beside a `-m` is a description of the defect and not the defect.
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Attribute) and node.attr == "executable"
                    and isinstance(node.value, ast.Name) and node.value.id == "sys"):
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno}")
    assert not offenders, (
        "these build a command for this program by hand; `runtime.self_argv` is the one "
        "place that knows how:\n  " + "\n  ".join(offenders))


# --------------------------------------------------------------------------- #
# The default that moved


def test_the_output_root_says_so_when_nobody_chose_it(capsys):
    """Two answers to one question, and the fallback names the one it took.

    `--output` defaulted to the literal `output`, relative to whatever working directory
    the command was run from. That is right for a checkout and meaningless for a
    double-clicked application. A default that quietly moves between the two is the sort of
    silence that costs a session hunting for a map that was written somewhere else.
    """
    args = build_parser().parse_args(["analyze", "src"])
    assert args.output is None, "the default is resolved at use, not by argparse"
    assert _out_root(args) == runtime.default_output_root()
    said = capsys.readouterr().err
    assert "no --output given" in said
    assert str(runtime.default_output_root()) in said


def test_a_chosen_output_root_is_taken_in_silence(capsys):
    args = build_parser().parse_args(["analyze", "src", "--output", "/tmp/somewhere"])
    assert _out_root(args) == Path("/tmp/somewhere")
    assert capsys.readouterr().err == ""


# --------------------------------------------------------------------------- #
# The bundle, read out of the spec rather than out of a build


SPEC = SRC.parent.parent / "packaging" / "dunneflow.spec"
ENTRY = SRC.parent.parent / "packaging" / "dunneflow_app.py"
RELEASE = SRC.parent.parent / "packaging" / "release.sh"
ENTITLEMENTS = SRC.parent.parent / "packaging" / "entitlements.plist"


def test_the_spec_bundles_every_extraction_input():
    """A file the fingerprint hashes must travel as **data**, not only in the archive.

    This is the whole of blocker 1's other half: `code_extraction_inputs()` names the
    detectors' loader and both extractor trees, and a module that exists only inside a
    PyInstaller archive has no file to read. The spec is parsed rather than run, so this
    costs nothing and still fails the moment a reader is added to a key and not to the
    bundle.
    """
    spec = SPEC.read_text(encoding="utf-8")
    wanted = {p.relative_to(SRC).parts[0] for p in
              (*code_extraction_inputs(), *doc_extraction_inputs())}
    for top in sorted(wanted):
        assert top in spec, f"{top}/ is hashed into a cache key and is not in the spec"
    # The page and the engine, which are not hashed but are 404s without this.
    assert 'web" / "static"' in spec and 'web" / "vendor"' in spec
    # Which DunneFlow read the map. Without it a shipped binary records no version at all.
    assert "copy_metadata" in spec


def test_the_bundle_layout_matches_what_resource_root_expects():
    """`<_MEIPASS>/dunneflow/…`, and it is what makes the two builds agree.

    `fingerprint_files` labels every input relative to `resource_root()`. Same last
    segment, same labels, same fingerprint — so a map made by the binary opens in the
    checkout and back. Laid out any other way the two would refuse each other's maps under
    rule 12, which is the opposite of what that rule is for.
    """
    spec = SPEC.read_text(encoding="utf-8")
    assert '"dunneflow/detectors"' in spec
    assert '"dunneflow/web/static"' in spec
    assert "dunneflow/extractors/python" in spec


def test_the_entry_point_calls_freeze_support_before_anything_else():
    """Not `main()`'s copy — *this* file's, and it has to be first.

    macOS spawns, so a frozen worker re-executes the application. Anything imported ahead
    of this line runs in every one of them.
    """
    tree = ast.parse(ENTRY.read_text(encoding="utf-8"))
    body = [n for n in tree.body
            if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    assert isinstance(body[0], ast.Import)
    assert body[0].names[0].name == "multiprocessing"
    call = body[1]
    assert isinstance(call, ast.Expr) and isinstance(call.value, ast.Call)
    assert ast.unparse(call.value.func) == "multiprocessing.freeze_support"


def test_no_arguments_means_serve_and_only_in_the_application():
    """The double-click's decision belongs to the application, not to the CLI.

    A command-line tool run with no arguments should say what it takes. An application
    that has just been double-clicked has no way to say anything back, and printing usage
    into a window nobody opened is the same as doing nothing.
    """
    entry = ENTRY.read_text(encoding="utf-8")
    assert 'sys.argv.append("serve")' in entry
    # And the CLI still refuses, so `dunneflow` from a checkout keeps its usage message.
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


# --------------------------------------------------------------------------- #
# The universal build, and the one thing in the bundle that cannot be both


def test_nothing_asks_pyyaml_for_its_c_loader():
    """Which is what makes `excludes=["_yaml"]` in the spec safe rather than lucky.

    PyPI has no universal2 PyYAML wheel for any version, so the C extension is the single
    file in the bundle that cannot be built for arm64 *and* x86_64. Excluding it costs
    nothing **only while every call site is `yaml.safe_load`**, which uses the pure-Python
    `SafeLoader` whatever `_yaml` does; ask for `CSafeLoader` and the exclusion becomes an
    `ImportError` in a frozen build and nowhere else.

    Read out of the syntax rather than out of the text, because this file's own explanation
    of the rule contains every word a scan would look for -- rule 34, which `test_frozen.py`
    has already paid for three times.
    """
    banned = {"CLoader", "CSafeLoader", "CBaseLoader", "CFullLoader",
              "CDumper", "CSafeDumper", "__with_libyaml__"}
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in banned:
                offenders.append(f"{path.name}:{node.lineno} {ast.unparse(node)}")
            elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("yaml"):
                for alias in node.names:
                    if alias.name in banned:
                        offenders.append(f"{path.name}:{node.lineno} {alias.name}")
            elif isinstance(node, ast.Name) and node.id in banned:
                offenders.append(f"{path.name}:{node.lineno} {node.id}")
    assert not offenders, (
        "the spec drops PyYAML's C extension from the bundle, and these use it: "
        + ", ".join(offenders))


def test_the_spec_drops_the_extension_that_cannot_be_universal():
    """The other half of the pair above, and it is the half that is easy to lose.

    A guard saying *nothing uses `_yaml`* is worth nothing if the spec has quietly started
    shipping it again: the build would succeed on this machine and refuse to go universal
    with a message about an architecture, which names the symptom and not the cause.
    """
    tree = ast.parse(SPEC.read_text(encoding="utf-8"))
    excludes = [n for n in tree.body
                if isinstance(n, ast.Assign)
                and any(getattr(t, "id", "") == "excludes" for t in n.targets)]
    assert excludes, "the spec no longer names an `excludes` list"
    dropped = ast.literal_eval(excludes[0].value)
    # Both, and the wrapper is the one that matters: excluding the extension alone leaves
    # `yaml.cyaml` importing something that is not there, which is an ImportError where
    # `yaml/__init__.py` used to have a fallback.
    assert "yaml._yaml" in dropped and "yaml.cyaml" in dropped


def test_a_universal_build_refuses_rather_than_coming_out_single_arch(monkeypatch):
    """Rule 49, in the one place where the plausible value would be found by somebody else.

    `DUNNEFLOW_ARCH=universal2` under an arm64-only interpreter has to raise. If it fell
    back to the host architecture the build would report success, sign, notarise and ship,
    and the failure would arrive as *"the application cannot be opened"* on a colleague's
    Intel Mac with nothing on this machine to look at.
    """
    source = SPEC.read_text(encoding="utf-8")
    tree = ast.parse(source)
    func = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "_target_arch")
    # Every way out of the function: the two refusals, and the two answers.
    raises = [n for n in ast.walk(func) if isinstance(n, ast.Raise)]
    assert len(raises) == 2, "a universal build must refuse an unknown target and a thin one"
    for node in raises:
        assert ast.unparse(node.exc.func) == "SystemExit"
    # And the answer is asked of the real interpreter, never of the virtual environment's
    # stub, which says nothing about what is behind it.
    assert "_base_executable" in ast.unparse(func)
    assert "target_arch=_target_arch()" in source


def test_the_release_script_and_the_spec_name_the_same_bundle():
    """Two spellings of one name is rule 41's shape: a claim and a population that can drift.

    `release.sh` signs, notarises, staples, images and installs a bundle by name; the spec
    decides what that name is. Disagree and every step after `build` reports that there is
    nothing to sign.
    """
    tree = ast.parse(SPEC.read_text(encoding="utf-8"))
    bundle = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "BUNDLE")
    spec_name = next(ast.literal_eval(k.value) for k in bundle.keywords if k.arg == "name")

    script = RELEASE.read_text(encoding="utf-8")
    assert f'APP_NAME="{spec_name}"' in script, f"release.sh does not name {spec_name}"
    # The commands, without the prose. The script explains at its head that it never uses
    # `codesign --deep`, so a scan of the whole file reports that sentence as the violation
    # it describes -- rule 34, arriving in the guard written for a different rule.
    commands = "\n".join(line for line in script.splitlines()
                          if not line.lstrip().startswith("#"))
    # And it signs with what the entitlements file claims, rather than with --deep, which
    # would apply the outer bundle's entitlements to everything nested inside it.
    assert "packaging/entitlements.plist" in commands
    assert "--options runtime" in commands
    assert "--deep --strict" in commands and "--sign" in commands
    assert "codesign --deep" not in commands


def test_the_entitlements_file_asks_for_nothing():
    """An empty list of claims, and it is a claim in its own right.

    Nothing in DunneFlow has been shown to need the hardened runtime relaxed, and the four
    entitlements every PyInstaller guide carries are copied from each other rather than
    measured. A key added here without a reproduced failure recorded beside it is a guess
    wearing a uniform, so the guard is that the dictionary stays empty until somebody
    changes this test on purpose.
    """
    text = ENTITLEMENTS.read_text(encoding="utf-8")
    body = text.split("<dict>", 1)[1].split("</dict>", 1)[0]
    assert body.strip() == "", f"an entitlement was added: {body.strip()!r}"
    assert "com.apple.security.cs.disable-library-validation" in text, (
        "the file has to keep saying which entitlements were considered and why not")


# --------------------------------------------------------------------------- #
# The Dock, and the entitlements it must not cost


def test_only_a_packaged_macos_build_takes_the_main_thread():
    """A checkout is a terminal program and must keep its main thread and its Ctrl-C.

    `run_as_application` moves the HTTP server onto a background thread and hands the main
    one to `[NSApp run]`. That is right for a double-clicked application and an intrusion
    into somebody's shell, so the gate is frozen **and** macOS — the two non-macOS branches
    of `runtime` are untested and this is not the place to guess at them.
    """
    assert macapp.available() is False, "a checkout would take the main thread"


def test_a_packaged_build_is_a_dock_application(as_frozen, monkeypatch):
    """The symptom this exists for: no running indicator under the Dock icon.

    `lsappinfo` gave the cause exactly — `type="Foreground"` but **`!cgsConnection`**. The
    plist was never the problem (`LSBackgroundOnly` was already false); a command line tool
    in a bundle simply never touches AppKit, so the window server has nothing to indicate.
    Measured on the built app before and after: `!cgsConnection` present, then gone, with a
    LaunchServices `checkin time` appearing beside it.
    """
    monkeypatch.setattr(sys, "platform", "darwin")
    assert macapp.available() is True


def test_the_dock_costs_no_entitlement():
    """**`packaging/entitlements.plist` asks for nothing, and this must not change that.**

    That file is empty because it was measured to be — and one of the measurements is that
    *"CPython 3.12 has no JIT and nothing builds a ctypes closure"*. A `CFUNCTYPE` wrapping a
    **Python callable** is exactly such a closure: libffi writes a trampoline into
    executable memory, which under the hardened runtime needs
    `allow-unsigned-executable-memory`. Everything in `macapp` is a call *out* to a function
    that already exists, so nothing is compiled at run time.

    This is why there is no `NSApplicationDelegate`: installing one means defining an
    Objective-C class whose methods are Python functions, which is the closure this refuses
    to build. Quit works instead through `NSApplication`'s own default handling of the quit
    Apple Event — verified by quitting the built app and watching the port come free.
    """
    src = Path(macapp.__file__ or "").read_text(encoding="utf-8")
    body = src.split('"""', 2)[2]          # past the module docstring, which explains it all
    for closure in ("CFUNCTYPE", "PYFUNCTYPE"):
        assert closure not in body, (
            f"macapp builds a ctypes closure ({closure}) — that needs "
            "allow-unsigned-executable-memory, and packaging/entitlements.plist is empty "
            "because it was measured to be. Either find another way, or add the "
            "entitlement *and* record the failure that earned it."
        )


def test_the_server_still_runs_when_there_is_no_window_server(monkeypatch):
    """A Dock icon is a nicety; a server that would not start without one is not.

    `run_as_application` answers `False` where AppKit cannot be loaded or
    `sharedApplication` returns NULL — over SSH, or in a session with no `WindowServer` —
    and `_run` must then serve exactly as it always did (rule 49's shape: the fallback is
    the *working* path, not a plausible-looking substitute).
    """
    monkeypatch.setattr(macapp, "_appkit", lambda: None)
    assert macapp.run_as_application(lambda: None, lambda: None) is False


def test_universal_is_the_default_and_host_must_be_asked_for():
    """Shipping-shaped by default, because forgetting is silent.

    Unset used to mean *this machine*, which made the fast build the easy one and the
    shippable build the one you had to remember. An arm64 bundle builds, signs, notarises,
    installs and runs perfectly on the machine that made it -- the entire failure lands on
    somebody else's Intel Mac, weeks later, with nothing here to look at. Measured before
    flipping it: 12.9s universal against 11.5s host, so the cheap default bought nothing.
    """
    src = SPEC.read_text(encoding="utf-8")
    tree = ast.parse(src)
    func = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "_target_arch")
    # **Asked of the syntax, never of the text** -- rule 34, and this test paid for it. The
    # first spelling asserted `"or 'universal2'" in ast.unparse(func)`, which passed happily
    # over a spec whose default had been deleted: the refusal message one line below reads
    # *"Leave it unset for 'universal2'"*, and `for` ends in `or`. A guard matching prose
    # about the thing rather than the thing is the failure `test_frozen` was written to
    # avoid, three tests up.
    #
    # So: find the assignment to `asked` and require it to be an `or` whose fallback is the
    # literal `universal2`. That cannot be satisfied by a sentence.
    assigned = next(
        (n for n in ast.walk(func)
         if isinstance(n, ast.Assign)
         and any(getattr(t, "id", "") == "asked" for t in n.targets)),
        None,
    )
    assert assigned is not None, "_target_arch no longer computes `asked`"
    assert isinstance(assigned.value, ast.BoolOp) and isinstance(assigned.value.op, ast.Or), (
        "`asked` is no longer an `... or <default>` — a forgotten flag now decides the "
        "architecture, and an arm64 build ships silently"
    )
    fallback = assigned.value.values[-1]
    assert isinstance(fallback, ast.Constant) and fallback.value == "universal2", (
        f"the default is {ast.unparse(fallback)}, not 'universal2' — a forgotten flag "
        "ships an arm64 app that only fails on somebody else's Intel Mac"
    )
    # And the way out is still there, or the verification gate has no fast build.
    reachable = {n.value for n in ast.walk(func)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "host" in reachable, (
        "DUNNEFLOW_ARCH=host is gone; the verification gate now pays for a universal build"
    )


def test_nothing_single_arch_can_be_signed_notarised_imaged_or_installed():
    """**A default is a habit; this is the guarantee.**

    The one failure a default cannot prevent is somebody building `host` for a quick check
    and then signing and installing it by hand. So the check is on the *artifact* rather
    than on which command was remembered, and it gates exactly the four steps whose output
    reaches another machine.

    Derived from the script rather than listed here: a fifth shipping step added tomorrow
    should fail this until it is gated too (rule 36 -- a hand-kept list agrees with a wrong
    implementation).
    """
    sh = (SPEC.parent / "release.sh").read_text(encoding="utf-8")
    assert "require_universal()" in sh, "the universal guard is gone from release.sh"

    bodies = {}
    for name in ("step_sign", "step_notarize", "step_dmg", "step_install", "step_verify",
                 "step_build", "step_venv"):
        start = sh.find(f"{name}() {{")
        assert start != -1, f"release.sh no longer defines {name}"
        bodies[name] = sh[start:sh.find("\n}\n", start)]

    for shipping in ("step_sign", "step_notarize", "step_dmg", "step_install"):
        assert "require_universal" in bodies[shipping], (
            f"{shipping} does not require a universal bundle — a DUNNEFLOW_ARCH=host build "
            "can be shipped by hand, and it will only fail on somebody else's Intel Mac"
        )
    # `build` makes the thing and `verify` reports on whatever is there; neither is a gate,
    # and putting one in `verify` would stop it being able to *tell you* what went wrong.
    for reporting in ("step_build", "step_verify"):
        assert "require_universal" not in bodies[reporting], (
            f"{reporting} refuses a thin bundle, so it can no longer be used to diagnose one"
        )
