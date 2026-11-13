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
import re
import sys
from pathlib import Path

import pytest

from dunneflow import macapp, runtime
from dunneflow.cli import _out_root, build_parser
from dunneflow.detectors import (
    RulesMissing,
    core_extraction_inputs,
    core_fingerprint,
    fingerprint_files,
    lang_extraction_inputs,
    lang_fingerprint,
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
    here.write_text("a: 1", encoding="utf-8")
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
    assert core_fingerprint() != HASH_OF_NOTHING
    assert doc_rules_fingerprint() != HASH_OF_NOTHING
    assert core_fingerprint() != doc_rules_fingerprint()
    # And the third key, which is a version and a hash: the hash half is what moves when
    # somebody edits the reader, so it may not be the hash of nothing either.
    assert lang_fingerprint("python").split(":", 1)[1] != HASH_OF_NOTHING


@pytest.mark.parametrize(
    "inputs",
    [core_extraction_inputs, doc_extraction_inputs, lambda: lang_extraction_inputs("python")],
    ids=["core", "docs", "python"])
def test_every_extraction_input_is_a_file_that_exists(inputs):
    """The membership assertion the two `*_inputs` functions were split out for.

    A missing entry is now loud rather than silent, so this is no longer the only thing
    standing between a bad bundle and a hash of nothing -- but it is the one that says
    *which* file, at the moment somebody moves one.
    """
    found = inputs()
    assert found, "an extraction key found nothing"
    absent = [p for p in found if not p.is_file()]
    assert not absent, f"an extraction key names files that are not there: {absent}"


def test_every_rules_file_is_in_exactly_one_key():
    """The glob became a list, and a list is a thing somebody forgets to add to.

    `core_extraction_inputs` globbed `detectors/*.yaml` while every rules file governed
    every extraction there was. Splitting it made the language files the plugins' to
    declare — which is more precise and is also how a rules file comes to be in **no**
    key: written, loaded, and invisible to rule 12. So the directory is the authority and
    the keys are checked against it.

    `detectors/docs/` is out of this by the same rule one corpus over, and is asserted
    above.
    """
    from dunneflow import ingest

    on_disk = {p.name for p in (SRC / "detectors").glob("*.yaml")}
    keyed = {p.name for p in core_extraction_inputs() if p.suffix == ".yaml"}
    for lang in ingest.PLUGINS:
        keyed |= {p.name for p in lang_extraction_inputs(lang) if p.suffix == ".yaml"}
    assert on_disk <= keyed, (
        f"rules files in no cache key at all: {sorted(on_disk - keyed)} — they are loaded "
        "and hashed by nothing, so editing one leaves every cached graph stale and "
        "undiscarded (rule 95's shape, one directory over)"
    )


def test_a_plugins_own_files_are_in_the_bundle():
    """Rule 92: a defence assembled from an enumeration does not survive a new member.

    The spec bundled `extractors/python` and `extractors/docs` by name, which was the
    whole truth when those were the readers. A plugin arrives as a directory now, so what
    is asserted is that **every registered plugin's** fingerprint files travel — checked
    against the registry rather than against a list written beside it.
    """
    from dunneflow import ingest

    spec = SPEC.read_text(encoding="utf-8")
    assert "dunneflow/plugins" in spec, "plugins/ is not bundled at all"
    for lang in ingest.PLUGINS:
        for path in ingest.plugin_fingerprint_files(lang):
            top = path.relative_to(SRC).parts[0]
            assert top in spec, (
                f"{lang}'s fingerprint reads {path.name} out of {top}/, which the spec "
                f"does not bundle — frozen, that hashes nothing"
            )


def test_an_in_process_reader_is_found_in_the_spec_and_never_named():
    """Rule 92, the third time in this one file, and the quietest of the three.

    `datas` read `_tree(PKG / "extractors" / "python", …)` until 2026-09-18 — two lines
    under a comment arguing that the rules directory is *"globbed, never named, and that is
    rule 92 rather than economy"*, and four above one saying of the plugins that *"nothing
    here enumerates"* them. Both of those were rewritten when a second language found them.
    This one had not been, because Python was still the only reader running in this
    interpreter.

    **What it would cost is later and quieter than either.** A new in-process reader's
    manifest ships, its rules ship, the registry loads it, every other assertion in this
    file passes — and its own bytes are missing, so `lang_fingerprint` hashes nothing and
    the application meets its first file of that language in somebody else's hands.

    So the assertion is the property rather than the absence (rule 37): every reader the
    registry says runs in this process has its declared directory in the spec's output, and
    the spec's source does not spell it.
    """
    from dunneflow import ingest

    spec = SPEC.read_text(encoding="utf-8")
    assert "_reader_files()" in spec, "the in-process readers are not derived at all"
    for lang, plugin in sorted(ingest.PLUGINS.items()):
        rel = plugin.manifest.reader
        if not rel:
            continue                      # a reader on the far side of a pipe
        assert rel not in spec, (
            f"the spec names {lang}'s reader ({rel}) instead of finding it — rule 92"
        )
        assert (SRC / Path(rel)).is_dir(), (
            f"{lang} declares a reader at {rel} and this tree has no such directory"
        )


def test_a_plugin_ships_the_bytes_it_is_stamped_from_and_not_its_workshop():
    """The bundle is derived from the manifests, never from the directory listing.

    `_tree(PKG / "plugins")` was the whole truth while a plugin was one `plugin.json`. The
    TypeScript reader brought a `node_modules` of several thousand files, a lockfile and a
    source tree, none of which the application runs — and all of which a tree would have
    signed and shipped.

    Deriving it from `fingerprint` buys the stronger property, which is why it is asserted
    here rather than the absence: **what ships and what is stamped are the same bytes**, so
    a file a plugin needs at runtime and does not fingerprint cannot exist. Two answers
    that merely agree today are what this replaces.
    """
    spec = SPEC.read_text(encoding="utf-8")
    assert "_tree(PKG / \"plugins\"" not in spec, (
        "the plugin directory is bundled wholesale again — that ships node_modules"
    )
    assert "fingerprint" in spec, "the bundled list is no longer derived from the manifests"

    # And the thing a grep cannot see: the workshop exists, so the rule has something to
    # exclude. Skipped where it does not, because an assertion that cannot fail is worse
    # than none (rule 37).
    from dunneflow import ingest

    workshops = [p for p in (SRC / "plugins").glob("*/node_modules") if p.is_dir()]
    if workshops:
        for lang in ingest.PLUGINS:
            shipped = {p.name for p in ingest.plugin_fingerprint_files(lang)}
            assert "package.json" not in shipped and "tsconfig.json" not in shipped


def test_the_two_keys_do_not_share_a_reader():
    """Editing a prose rule must not discard the code graph, and the reverse.

    Stated in `core_fingerprint`'s docstring as the reason `detectors/docs/` and
    `prose.py` are absent from the code key. Asserted here because both lists now come
    from `resource_root()`, and a resource root is exactly the sort of change that makes
    two globs start overlapping.
    """
    code = {p.relative_to(SRC)
            for p in (*core_extraction_inputs(), *lang_extraction_inputs("python"))}
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

    **+ Analyse a directory...** is the only way a first-time reader gets a map at all,
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


@pytest.mark.skipif(sys.platform != "linux", reason="asserts this platform's own layout")
def test_the_output_root_of_an_application_on_linux(monkeypatch):
    """`$XDG_DATA_HOME`, and the specification's three states rather than two.

    Same claim as the macOS test one specification over: an application's own data goes
    where the platform says it goes, and never in a directory a sync client watches. The
    XDG default is `~/.local/share`; Nextcloud, Dropbox and Drive all sync a *named*
    directory under `$HOME` and none of them syncs that one.

    **The relative case is the one worth a test.** The specification says a relative path in
    one of these variables is invalid and must be ignored, and here that is not deference:
    it resolves against the working directory, and a desktop entry gives a process no
    working directory worth the name. Honoured, it would scatter maps roots wherever the
    launcher started and report no programs from each of them in turn (rule 49).
    """
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    root = runtime.platform_output_root()
    assert root == Path.home() / ".local" / "share" / "DunneFlow"
    assert root.is_absolute()
    assert "Documents" not in root.parts

    monkeypatch.setenv("XDG_DATA_HOME", "")
    assert runtime.platform_output_root() == root, "empty is unset, per the specification"

    monkeypatch.setenv("XDG_DATA_HOME", "/srv/maps")
    assert runtime.platform_output_root() == Path("/srv/maps") / "DunneFlow"

    monkeypatch.setenv("XDG_DATA_HOME", "relative/share")
    said = runtime.platform_output_root()
    assert said == root, (
        f"a relative XDG_DATA_HOME was honoured and put the maps root at {said}"
    )
    assert said.is_absolute()


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
RELEASE_PS1 = SRC.parent.parent / "packaging" / "release.ps1"
RELEASE_LINUX = SRC.parent.parent / "packaging" / "release-linux.sh"
DESKTOP_IN = SRC.parent.parent / "packaging" / "linux" / "dunneflow.desktop.in"
INSTALL_SH = SRC.parent.parent / "packaging" / "linux" / "install.sh"
ENTITLEMENTS = SRC.parent.parent / "packaging" / "entitlements.plist"


def test_the_spec_bundles_every_extraction_input():
    """A file the fingerprint hashes must travel as **data**, not only in the archive.

    This is the whole of blocker 1's other half: the extraction keys name the
    detectors' loader and both extractor trees, and a module that exists only inside a
    PyInstaller archive has no file to read. The spec is parsed rather than run, so this
    costs nothing and still fails the moment a reader is added to a key and not to the
    bundle.
    """
    spec = SPEC.read_text(encoding="utf-8")
    wanted = {p.relative_to(SRC).parts[0] for p in
              (*core_extraction_inputs(), *lang_extraction_inputs("python"),
               *doc_extraction_inputs())}
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

    **The third assertion used to be the string `dunneflow/extractors/python`**, which
    pinned the enumeration rule 92 was about rather than the layout this test is named for:
    it passed because the spec named Python's reader, and it would have gone on passing
    while a second in-process reader went unbundled. It asks the derived destination now,
    which is the same claim about the thing that actually ships.
    """
    from dunneflow import ingest

    spec = SPEC.read_text(encoding="utf-8")
    assert '"dunneflow/detectors"' in spec
    assert '"dunneflow/web/static"' in spec
    assert 'f"dunneflow/{rel}"' in spec, (
        "an in-process reader is no longer placed under the package root's own name"
    )
    for lang, plugin in sorted(ingest.PLUGINS.items()):
        if rel := plugin.manifest.reader:
            assert (SRC / Path(rel)).is_dir(), f"{lang}'s reader is not where it says"


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

    **Three refusals now, and the third is the same rule on another platform.**
    `target_arch` is a Mach-O idea; a Windows executable holds the one architecture its
    interpreter was built for. So a `DUNNEFLOW_ARCH` set out of habit off macOS is refused by
    name rather than *accepted and ignored*, which is how somebody comes to believe they
    built a thing they did not. Counted rather than listed, so adding a fourth way out of
    this function means coming back here and saying what it is.
    """
    source = SPEC.read_text(encoding="utf-8")
    tree = ast.parse(source)
    func = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "_target_arch")
    # Every way out of the function: the three refusals, and the two answers.
    raises = [n for n in ast.walk(func) if isinstance(n, ast.Raise)]
    assert len(raises) == 3, (
        "a universal build must refuse an unknown target, a thin interpreter, and a macOS "
        "answer asked for on a platform that has no such choice to make"
    )
    for node in raises:
        assert ast.unparse(node.exc.func) == "SystemExit"
    # And the platform refusal must be reached *before* anything macOS-only is touched:
    # `PyInstaller.utils.osx` needs `macholib`, which is genuinely absent off a Mac, so an
    # import at the top of the file would make this spec unreadable there rather than
    # merely inapplicable.
    # **Asserted on the guard's name, and then on what that name means.** This read the
    # literal `sys.platform != 'darwin'` until Linux arrived and the spec started naming its
    # three platforms once at the top -- at which point the test failed over a rename while
    # the property it defends was untouched. Reading a name is only safe if the name's
    # definition is read too: a `_MACOS` quietly redefined as anything else would otherwise
    # satisfy the ordering below while guarding nothing (rule 37).
    body = ast.unparse(func)
    assert body.index("not _MACOS") < body.index("PyInstaller.utils.osx"), (
        "the spec reaches for a macOS-only module before it has refused the platform"
    )
    assert "_MACOS = sys.platform == 'darwin'" in ast.unparse(tree), (
        "_MACOS no longer asks which platform this is, so the guard above guards nothing"
    )
    # And the answer is asked of the real interpreter, never of the virtual environment's
    # stub, which says nothing about what is behind it.
    assert "_base_executable" in ast.unparse(func)
    assert "target_arch=_target_arch()" in source


def test_the_windows_script_and_the_spec_name_the_same_executables():
    """`release.ps1`'s subject, and rule 41's shape again: a claim and a population.

    The PowerShell script freezes, checks, zips and installs two executables by name; the
    spec decides what those names are. Disagree and `verify` reports that the build is
    missing a file that is sitting right there under another name.

    **The two names must differ by more than case**, and that is not style. NTFS is
    case-insensitive, so `DunneFlow.exe` and `dunneflow.exe` are one file there -- the
    second `EXE()` would overwrite the first, and the build would end with one binary where
    the spec says two and no error anywhere.
    """
    tree = ast.parse(SPEC.read_text(encoding="utf-8"))
    names = [ast.literal_eval(k.value)
             for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "EXE"
             for k in n.keywords if k.arg == "name" and isinstance(k.value, ast.Constant)]
    windows = [n for n in names if n != "dunneflow"]
    assert "dunneflow-cli" in names, "the spec no longer builds a console executable"

    script = RELEASE_PS1.read_text(encoding="utf-8")
    for name in windows:
        assert f"'{name}.exe'" in script, f"release.ps1 does not name {name}.exe"
    lowered = [n.lower() for n in windows]
    assert len(set(lowered)) == len(lowered), (
        "two executables whose names differ only in case are one file on NTFS"
    )
    # Nothing in this script may reach a network. A release that is not to be published has
    # to be one that *cannot* be, by reading it (rule 13 -- a claim a query can answer).
    for word in ("Invoke-RestMethod", "Invoke-WebRequest", "curl", "Start-BitsTransfer"):
        assert word not in script, f"release.ps1 reaches the network with {word}"


def test_a_linux_build_makes_no_app_bundle():
    """`BUNDLE` is macOS's, and it was guarded by *not Windows*.

    That was true while there were two platforms and silently wrong the moment there were
    three: asked for on Linux it produces a directory with a plist in it that nothing can
    launch, and PyInstaller reports success. A negation is a fine way to say *the other one*
    and no way at all to say *the other two*.

    Read out of the `if` that encloses the call rather than out of the file's text, so a
    second `BUNDLE` added under a different guard cannot hide behind the first one's.
    """
    tree = ast.parse(SPEC.read_text(encoding="utf-8"))
    guarded = [n for n in ast.walk(tree)
               if isinstance(n, ast.If)
               and any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "BUNDLE"
                       for c in ast.walk(n))]
    assert guarded, "the spec no longer builds a macOS bundle at all"
    for node in guarded:
        assert ast.unparse(node.test) == "_MACOS", (
            f"BUNDLE is built under `{ast.unparse(node.test)}`, which is not a test for macOS"
        )


def test_the_linux_script_and_the_spec_name_the_same_things():
    """Rule 41 a third time: a claim in a shell script, a population in the spec.

    The script copies a directory and links a binary by name; the spec decides both names.
    Disagree and `install` reports that a file it is sitting on top of is missing.

    **The icon is the third name and the one with no compiler behind it.** An ELF carries
    none, so what a reader sees in the menu is whatever the desktop entry's `Icon=` resolves
    to in the icon theme -- a *string*, matched against filenames on disk. Spelled two ways,
    the entry is valid, the install succeeds, every check passes, and the menu shows a
    generic grey square.
    """
    tree = ast.parse(SPEC.read_text(encoding="utf-8"))
    names = [ast.literal_eval(k.value)
             for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "COLLECT"
             for k in n.keywords if k.arg == "name" and isinstance(k.value, ast.Constant)]
    assert names == ["dunneflow"], f"the spec collects into {names}"

    script = RELEASE_LINUX.read_text(encoding="utf-8")
    assert f'APP="$DIST/{names[0]}"' in script, "release-linux.sh looks for another directory"
    assert 'BIN="$APP/dunneflow"' in script, "release-linux.sh looks for another executable"

    entry = DESKTOP_IN.read_text(encoding="utf-8")
    icon = next(line.split("=", 1)[1].strip()
                for line in entry.splitlines() if line.startswith("Icon="))
    ladder = sorted((SRC.parent.parent / "packaging" / "icon" / "hicolor").rglob("*.png"))
    assert ladder, "the hicolor ladder is not committed"
    for png in ladder:
        assert png.stem == icon, (
            f"the desktop entry asks the icon theme for {icon!r} and the committed ladder "
            f"holds {png.stem!r} — the menu would draw a generic square"
        )

    # Nothing in this script may reach a network, on `release.ps1`'s argument: a release
    # that is not to be published has to be one that *cannot* be, by reading it (rule 13).
    for word in ("curl", "wget", "http://", "https://", "scp ", "rsync "):
        assert word not in script, f"release-linux.sh reaches the network with {word!r}"


def test_a_linux_install_never_lands_inside_the_maps_root(monkeypatch):
    """**The one genuinely Linux-shaped trap in the packaging**, and it has no counterpart.

    On macOS the application is in `/Applications` and its data in `~/Library/Application
    Support/DunneFlow`; on Windows, `%LOCALAPPDATA%\\DunneFlow` beside a program somewhere
    else. Neither pair can collide. On Linux the obvious place for an application's files
    under `$HOME` and the obvious place for its data are **the same directory** --
    `~/.local/share/DunneFlow` -- and that is exactly what `platform_output_root()` answers.

    Installed there, the program would sit inside the tree its own `Move…` offers to
    relocate and inside the corpus its own analyses walk, and nothing would say so until a
    reader moved their maps to an external disk and took the application with them.

    Asserted against the function rather than against a spelling, so moving the maps root
    moves this test with it -- and **asked of the Linux branch on whatever machine is
    running**, rather than of this one. Written against `platform_output_root()` as it
    answers here, it would have failed on a Mac for the reason it exists: there the two
    directories are nowhere near each other, which is the whole point being made.
    """
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    script = RELEASE_LINUX.read_text(encoding="utf-8")
    installs = [line.split("=", 1)[1].strip().strip('"')
                for line in script.splitlines()
                if line.startswith(("LIBDIR=", "BINLINK=", "DESKTOP=", "ICONS="))]
    assert len(installs) == 4, f"the install targets changed shape: {installs}"

    maps = runtime.platform_output_root()
    assert maps.parent.name == "share" and maps.name == "DunneFlow", (
        f"this test is written against {maps} and the maps root has moved"
    )
    for target in installs:
        landed = Path(target.replace("$PREFIX", str(Path.home() / ".local")))
        assert maps not in landed.parents and landed != maps, (
            f"{target} installs into the reader's maps root — the application would be "
            f"inside the directory it offers to move"
        )


def test_the_windows_script_can_be_read_by_the_powershell_windows_ships_with():
    """A `.ps1` holding non-ASCII **must** carry a UTF-8 BOM, or 5.1 will not parse it.

    Windows PowerShell -- the built-in one, which is what `powershell` means on every Windows
    machine -- reads a BOM-less script as **ANSI**, not UTF-8. An em dash inside a
    double-quoted string then decodes as two characters, the closing quote is consumed with
    them, and the failure is reported as *"The string is missing the terminator"* forty lines
    further down, where there is nothing wrong.

    Found by a probe script of this session's own writing failing exactly that way; the
    release script carries the same characters and had only ever been run under `pwsh`, which
    reads UTF-8 either way and so could never have shown it. PowerShell 7 accepts the BOM, so
    it costs nothing and satisfies both.

    Asserted as a **condition**, not a flat "there is a BOM": a script that is pure ASCII does
    not need one, and a guard that demanded it anyway would be a rule about a file rather than
    about the failure it prevents.
    """
    raw = RELEASE_PS1.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    body = raw[3:] if bom else raw
    non_ascii = [ch for ch in body.decode("utf-8") if ord(ch) > 127]
    if non_ascii:
        assert bom, (
            f"release.ps1 holds {len(non_ascii)} non-ASCII characters "
            f"({''.join(sorted(set(non_ascii)))}) and no BOM — Windows PowerShell will read "
            "them as ANSI and fail to parse the file"
        )


def test_the_folder_picker_says_while_it_is_opening():
    """Design rule 16's neighbour: an untouched control and a working one looked identical.

    The dialog belongs to a helper process the server starts, and the first one on a machine
    pays to load the toolkit it draws with — measured at 0.6s warm and several seconds cold on
    Windows, against an `osascript` that is effectively instant. For all of that time the
    button was exactly as it is when nothing is wired to it, and it was **reported as a picker
    that does not open**.

    Both call sites, because there are two and only one of them was ever going to be
    remembered (rule 78). Asserted on the source, because the state is set before an `await`
    and no rendered DOM can show that it was.
    """
    js = SRC / "web" / "static"

    analyze = (js / "analyze.js").read_text(encoding="utf-8")
    body = analyze.split("async function pickDirectory", 1)[1].split("\n  }", 1)[0]
    assert "picking = true" in body, "the analyse dialog's picker never says it is opening"
    assert body.index("picking = true") < body.index("await fetch"), (
        "the picker says it is opening after the wait it is meant to cover"
    )
    assert "paintAnalyze()" in body.split("picking = true", 1)[1].split("await fetch", 1)[0], (
        "the state is set and never painted, which is the same as not setting it"
    )
    assert "a.picking" in analyze, "nothing renders the opening state"

    start = (js / "start.js").read_text(encoding="utf-8")
    handler = start.split("data-movepick", 1)[1].split("return;\n    }", 1)[0]
    assert "Opening" in handler, "the start page's picker never says it is opening"
    assert "finally" in handler, (
        "a throw would leave the start page saying 'Opening…' for ever"
    )


def test_every_step_that_signs_asks_for_the_identity_first_and_names_the_variable():
    """There is no default identity: the script is published, and a default was one
    person's name and Apple team id in every clone (removed 2026-11-12).

    `release.sh` checked for it in `sign` alone, with a message naming only the missing
    string, and `dmg` built the whole image before reaching a `codesign` that would fail the
    same way. A contributor needs to be told which variable carries *their* certificate, so
    every step that runs `codesign --sign` must call `require_identity` before it does any
    work, and the refusal must name `DUNNEFLOW_IDENTITY`.
    """
    script = RELEASE.read_text(encoding="utf-8")
    body = script[script.index("require_identity() {"):]
    body = body[:body.index("\n}\n")]
    assert "DUNNEFLOW_IDENTITY" in body, "the refusal does not name the variable to set"
    assert 'IDENTITY="${DUNNEFLOW_IDENTITY:-}"' in script, "the script signs as somebody by default"
    steps = re.findall(r"^(step_\w+)\(\) \{\n(.*?)^\}", script, re.M | re.S)
    signing = [(name, text) for name, text in steps if "--sign" in text]
    assert {name for name, _ in signing} >= {"step_sign", "step_dmg"}, signing
    for name, text in signing:
        assert "require_identity" in text, f"{name} signs without asking for the identity"
        assert text.index("require_identity") < text.index("--sign"), (
            f"{name} asks for the identity only after it has started signing")


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


def test_the_bundle_version_is_read_from_pyproject_and_never_spelled():
    """The `.app`'s version is `pyproject.toml`'s, read, never a second literal (rule 51).

    `CFBundleShortVersionString` was `"0.1.0"` in the spec while pyproject said the same, and
    the two agreed by coincidence. `release.sh` names the `.dmg` off the plist, so bumping
    pyproject alone would have shipped the new tool in a disk image named for the old one.
    Read as syntax rather than text: the value must be a name, not a constant.
    """
    tree = ast.parse(SPEC.read_text(encoding="utf-8"))
    bundle = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "BUNDLE")
    plist = next(k.value for k in bundle.keywords if k.arg == "info_plist")
    assert isinstance(plist, ast.Dict)
    version = next(v for k, v in zip(plist.keys, plist.values, strict=True)
                   if isinstance(k, ast.Constant) and k.value == "CFBundleShortVersionString")
    assert not isinstance(version, ast.Constant), (
        f"the spec spells the bundle version as {ast.unparse(version)} — read it from "
        "pyproject.toml instead")
    assert "pyproject.toml" in SPEC.read_text(encoding="utf-8")


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


def test_the_linux_tarball_carries_everything_its_install_needs() -> None:
    """**A reader who downloaded the artifact must be able to install it from the artifact.**

    They could not, and nothing said so. `step_tar` archives `dist/dunneflow` alone, while
    `step_install` read the desktop entry from `packaging/linux/` and the icons from
    `packaging/icon/hicolor/` -- both in the *repository*. So the install command documented
    beside the tarball could only ever run in a checkout, and `verify` passed because it too
    was reading the repository. A check that reads the source when the question is about the
    artifact is rule 24 wearing a tick.

    What is asserted is the shape that fixes it: `build` stages the payload into the tree
    that gets archived, and the installer reads it from **there** rather than from `$ROOT`.
    Asserted over the scripts because the artifact is a Linux build this suite cannot make.
    """
    script = RELEASE_LINUX.read_text(encoding="utf-8")
    installer = INSTALL_SH.read_text(encoding="utf-8")

    assert "step_stage" in script, "nothing stages the installer's payload into the build"
    staged = script.split("step_stage() {", 1)[1].split("\n}", 1)[0]
    for needed in ("dunneflow.desktop.in", "icon/hicolor", "install.sh"):
        assert needed in staged, f"step_stage no longer stages {needed}"
    assert "step_stage" in script.split("step_build() {", 1)[1].split("\n}", 1)[0], (
        "build no longer stages -- a build that cannot be installed is not a build"
    )

    # The installer reads only from the directory it was handed. A `$ROOT` here is the
    # defect coming back: it would work in a checkout and fail from the tarball, which is
    # exactly the failure that is invisible to everyone who has the repository.
    assert "$ROOT" not in installer, (
        "install.sh reaches into the repository, so it cannot run from an unpacked tarball"
    )
    for reads in ('"$APP/share/dunneflow.desktop.in"', '"$APP/share/icons/hicolor"'):
        assert reads in installer, f"install.sh no longer reads {reads} from the build"

    # One installer, two callers (rule 51). `release-linux.sh` must delegate rather than
    # keep a second copy of the steps -- two copies drift, and only one of them ships.
    for verb in ("step_install() {", "step_uninstall() {"):
        body = script.split(verb, 1)[1].split("\n}", 1)[0]
        assert "install.sh" in body, f"{verb.strip(' {')} no longer delegates to install.sh"
        assert "cp -a" not in body, (
            f"{verb.strip(' {')} installs on its own again -- that is the second copy"
        )


def test_the_installed_copy_can_uninstall_itself() -> None:
    """The tarball gets deleted and `dist/` is scratch; the install has to outlive both.

    `release-linux.sh uninstall` therefore prefers the copy in `$LIBDIR` and falls back to
    the checkout's, rather than requiring the build that produced it. Without this an
    uninstall is only available to somebody who still has the tree they installed from,
    which on the download path is nobody.
    """
    body = (RELEASE_LINUX.read_text(encoding="utf-8")
            .split("step_uninstall() {", 1)[1].split("\n}", 1)[0])
    assert '"$LIBDIR/install.sh"' in body, (
        "uninstall no longer looks for the installed copy first"
    )
    assert "packaging/linux/install.sh" in body, "there is no fallback for a fresh checkout"


def test_the_release_script_and_the_spec_name_the_same_executable():
    """The bundle's name is one question; the binary inside it is another, and it is lower.

    `release.sh` reconstructed it as `${APP_NAME%.app}` — `DunneFlow` — where the spec says
    `dunneflow`, and got away with it because APFS is **case-insensitive by default**. On a
    case-sensitive volume, which is an option at format time and the default on some CI
    images, `require_universal` would have refused every good build with *"there is no
    executable — run '$0 build' first"*, and `sign`, `notarize`, `dmg` and `install` are all
    behind it. Rule 49 with a plausible sentence on it, and the spec's own NTFS note is the
    same hazard one platform over.

    Read off `EXE(name=…)`, whose macOS answer is the `orelse` of a conditional: on Windows
    the executable *is* the name a reader sees, and inside a bundle the bundle supplies it.
    """
    tree = ast.parse(SPEC.read_text(encoding="utf-8"))
    exe = next(n for n in ast.walk(tree)
               if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "EXE")
    named = next(k.value for k in exe.keywords if k.arg == "name")
    # `"DunneFlow" if _WINDOWS else "dunneflow"` -- the second is this platform's.
    spec_name = ast.literal_eval(named.orelse if isinstance(named, ast.IfExp) else named)

    script = RELEASE.read_text(encoding="utf-8")
    assert f'BIN="$APP/Contents/MacOS/{spec_name}"' in script, (
        f"release.sh does not name the executable {spec_name} the way the spec builds it")
    # And every path *into* the bundle's `MacOS/` uses that one variable. Asked of those
    # paths rather than of the whole file: `${APP_NAME%.app}` is a fine way to name the
    # notarisation zip, and banning the expression outright would report that line as the
    # defect it is not (rule 34, in the guard rather than in the prose).
    commands = [line for line in script.splitlines() if not line.lstrip().startswith("#")]
    for line in commands:
        if "Contents/MacOS/" not in line or "grep -v" in line:
            continue
        assert f"Contents/MacOS/{spec_name}" in line, (
            f"{line.strip()} reaches into the bundle by a name the spec does not build — "
            f"the executable is {spec_name}, and only a case-insensitive filesystem hides "
            f"the difference")


def test_a_plugins_nested_files_ship_to_their_own_directories(tmp_path):
    """A vendored crate tree holds a dozen `lib.rs`; flattened they overwrite each other.

    `_plugin_files` is lifted out of the spec and run against a plugin of nested names,
    because what it returns *is* the bundle's layout and nothing else checks it before a
    build: every name is present either way, so only the destinations can tell.
    """
    import json as json_

    tree = ast.parse(SPEC.read_text(encoding="utf-8"))
    func = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "_plugin_files")
    pkg = tmp_path / "dunneflow"
    plugin = pkg / "plugins" / "nested"
    for name in ("own.rs", "vendor/a/src/lib.rs", "vendor/b/src/lib.rs"):
        (plugin / name).parent.mkdir(parents=True, exist_ok=True)
        (plugin / name).write_text(name, encoding="utf-8")
    (plugin / "plugin.json").write_text(json_.dumps(
        {"fingerprint": ["own.rs", "vendor/a/src/lib.rs", "vendor/b/src/lib.rs"]}))
    scope: dict = {"PKG": pkg, "Path": Path, "json": json_}
    # This repository's own spec, one function of it: not a tree being read.
    exec(compile(ast.Module(body=[func], type_ignores=[]), str(SPEC), "exec"), scope)  # noqa: S102
    shipped = {Path(src).relative_to(plugin).as_posix(): dest
               for src, dest in scope["_plugin_files"]()}
    assert shipped == {
        "plugin.json": "dunneflow/plugins/nested",
        "own.rs": "dunneflow/plugins/nested",
        "vendor/a/src/lib.rs": "dunneflow/plugins/nested/vendor/a/src",
        "vendor/b/src/lib.rs": "dunneflow/plugins/nested/vendor/b/src",
    }
