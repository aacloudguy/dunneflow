"""The two things the server asks the operating system for, on the third platform.

`pick_folder` and `reveal_dir` are the only places in `web/` that are not portable by
construction, and until Linux they had no test at all on any platform -- they were pressed
by hand against a real desktop and left. That is the right first move (rule 48) and a poor
resting place: what a hand press cannot reach is the *ladder*, and Linux is the platform
where both of them have one.

**`sys.platform` is monkeypatched rather than skipped around**, so every one of these runs
on all three machines. The Linux reader is a piece of this program's logic wherever it is
built, and a suite that only exercises it on Linux would let a macOS session break it
silently -- which is exactly how the stop rungs came to be guarded three ways (rule 51).
What cannot be monkeypatched is a desktop, so the commands are faked and the real presses
are recorded in `HANDOFF.md` with what came back.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from dunneflow.web import serve as serve_mod


class _Ran:
    """A stand-in for `subprocess.run` that records what it was asked and answers to order.

    Keyed on the command name rather than on the whole argv, because what these tests are
    about is *which rung ran*, and pinning every flag would make them a copy of the source
    that fails when a flag is reworded (rule 41).
    """

    def __init__(self, answers: dict[str, tuple[int, str, str]]) -> None:
        self.answers = answers
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        if argv[0] not in self.answers:
            raise FileNotFoundError(2, "No such file or directory", argv[0])
        code, out, err = self.answers[argv[0]]
        return subprocess.CompletedProcess(argv, code, out, err)

    @property
    def ran(self) -> list[str]:
        return [argv[0] for argv in self.calls]


@pytest.fixture
def on_linux(monkeypatch):
    """This build, reading as a Linux one, with a desktop session in the environment."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)


# --------------------------------------------------------------------------- #
# Is there a screen at all


def test_a_session_is_read_from_the_environment_not_the_platform(monkeypatch):
    """Rule 30: the honest question is whether there is a screen, not which OS this is.

    A Linux build serving over SSH with no forwarding is the same state as one on a headless
    box, and in both the reader is looking at a browser somewhere else entirely.
    """
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert serve_mod._desktop_session() is False

    monkeypatch.setenv("DISPLAY", ":0")
    assert serve_mod._desktop_session() is True

    monkeypatch.delenv("DISPLAY")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert serve_mod._desktop_session() is True, "a Wayland session has no DISPLAY"


def test_nothing_is_spawned_when_there_is_no_session(monkeypatch):
    """**The check is before the spawn, and that is what makes a cancel readable.**

    Measured on zenity 3.44.2: a cancel exits 1 with an empty stderr and a failure to open
    the display exits 1 with a line on it -- one code, told apart only by text a healthy
    desktop also writes for its own reasons. Refusing the failure that actually happens, in
    advance and by name, is what leaves exit 1 meaning one thing.

    So this asserts the *absence of a call*, not the sentence: a refusal that still opened a
    subprocess would pass a test that only read the words.
    """
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    ran = _Ran({})
    monkeypatch.setattr(serve_mod.subprocess, "run", ran)

    picked, reason = serve_mod.pick_folder()
    assert (picked, reason) == ("", serve_mod.NO_SESSION)
    assert serve_mod.reveal_dir(Path("/tmp")) == (False, serve_mod.NO_SESSION_REVEAL)
    assert ran.calls == [], f"a headless refusal still spawned {ran.ran}"


# --------------------------------------------------------------------------- #
# Which dialog, and in which order


def test_the_desktop_chooses_which_dialog_is_tried_first(monkeypatch):
    """A GTK dialog on Plasma works and looks like it came from somewhere else.

    Both orders hold every picker -- this promotes one rather than excluding the other, so a
    Plasma session with only zenity installed still gets a dialog (design rule 2's shape: the
    preference is about which one, never about whether).
    """
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    assert [n for n, _ in serve_mod._picker_order()][0] == "zenity"

    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    assert [n for n, _ in serve_mod._picker_order()][0] == "kdialog"

    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "plasmawayland:KDE")
    assert [n for n, _ in serve_mod._picker_order()][0] == "kdialog", (
        "XDG_CURRENT_DESKTOP is a colon-separated list and KDE is not always first"
    )

    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "XFCE")
    order = serve_mod._picker_order()
    assert [n for n, _ in order] == ["zenity", "kdialog"]
    assert len(order) == len(serve_mod._LINUX_PICKERS), "a picker was dropped, not demoted"


# --------------------------------------------------------------------------- #
# The picker's three outcomes


def test_a_chosen_directory_comes_back_with_no_reason(on_linux, monkeypatch):
    """Outcome one. Pressed for real against zenity 3.44.2; see `HANDOFF.md`."""
    monkeypatch.setattr(serve_mod.subprocess, "run",
                        _Ran({"zenity": (0, "/home/reader/src\n", "")}))
    assert serve_mod.pick_folder() == ("/home/reader/src", "")


def test_a_cancel_is_an_empty_path_and_an_empty_reason(on_linux, monkeypatch):
    """Outcome two, and the one a collapsed pair would report as an error in the panel.

    Exit 1 is zenity's and kdialog's word for *the person closed this dialog*. Pressed by
    closing a real one from the window manager's button: exit 1, stdout empty, **stderr
    empty**.
    """
    monkeypatch.setattr(serve_mod.subprocess, "run", _Ran({"zenity": (1, "", "")}))
    assert serve_mod.pick_folder() == ("", "")


def test_a_failure_carries_the_dialogs_own_first_line(on_linux, monkeypatch):
    """Outcome three. Any code but 0 and 1 is something neither this nor the reader asked
    for, and the dialog's own sentence is better than one invented here (rule 30)."""
    monkeypatch.setattr(serve_mod.subprocess, "run", _Ran({
        "zenity": (2, "", "zenity: symbol lookup error: undefined symbol\nsecond line"),
    }))
    picked, reason = serve_mod.pick_folder()
    assert picked == ""
    assert reason == "zenity: symbol lookup error: undefined symbol"


def test_a_picker_that_is_not_installed_falls_through_to_the_next(on_linux, monkeypatch):
    """**The one failure that is not an answer**, so it is the one that keeps going.

    A reader on a desktop with kdialog and no zenity must not be told the picker failed
    while the picker that would have worked sits one entry down the list.
    """
    ran = _Ran({"kdialog": (0, "/srv/code", "")})     # zenity raises FileNotFoundError
    monkeypatch.setattr(serve_mod.subprocess, "run", ran)
    assert serve_mod.pick_folder() == ("/srv/code", ""), (
        "an absent first picker reported instead of standing aside"
    )
    assert ran.ran == ["zenity", "kdialog"], "the second picker was never reached"


def test_no_picker_installed_names_what_would_give_them_one(on_linux, monkeypatch):
    """Rule 89: a refusal names something that can act on the thing being refused.

    The reader's alternative is to type the path and it always works (design rule 2) -- but
    they may prefer to fix it once, and they cannot if nobody says what to install.
    """
    ran = _Ran({})
    monkeypatch.setattr(serve_mod.subprocess, "run", ran)
    picked, reason = serve_mod.pick_folder()
    assert picked == ""
    assert reason == serve_mod.NO_LINUX_PICKER
    assert "zenity" in reason and "kdialog" in reason
    assert ran.ran == ["zenity", "kdialog"], "a picker was never tried"


def test_the_root_directory_survives_being_tidied(on_linux, monkeypatch):
    """`/` is a directory whose entire spelling is its separator.

    Stripped, it becomes the empty string -- which this function spends three outcomes
    distinguishing from a path, so a reader who picked `/` would be told they had cancelled.
    Absurd as a source tree, and cheap to not get wrong.
    """
    monkeypatch.setattr(serve_mod.subprocess, "run", _Ran({"zenity": (0, "/\n", "")}))
    assert serve_mod.pick_folder() == ("/", "")

    monkeypatch.setattr(serve_mod.subprocess, "run",
                        _Ran({"zenity": (0, "/srv/code/\n", "")}))
    assert serve_mod.pick_folder() == ("/srv/code", ""), "a trailing separator should go"


def test_a_picker_that_never_answers_is_not_waited_on_for_ever(on_linux, monkeypatch):
    """A dialog nobody ever saw must not hold a server thread until the process dies."""
    def times_out(argv: list[str], **_kw: object) -> object:
        raise subprocess.TimeoutExpired(argv, 180)
    monkeypatch.setattr(serve_mod.subprocess, "run", times_out)
    picked, reason = serve_mod.pick_folder()
    assert picked == "" and "did not answer" in reason


# --------------------------------------------------------------------------- #
# The reveal ladder


def test_the_bus_rung_is_asked_first_and_waits_for_its_answer(on_linux, monkeypatch):
    """**`--print-reply` is what makes the first rung's exit code mean anything** (rule 76).

    Without it `dbus-send` does not wait: it exits 0 for having *sent* a message, so a
    desktop with no file manager on the bus would report a successful reveal and the second
    rung would never run. An echo is not an act.
    """
    assert "--print-reply" in serve_mod._REVEAL_BUS
    ran = _Ran({"dbus-send": (0, "", "")})
    monkeypatch.setattr(serve_mod.subprocess, "run", ran)

    assert serve_mod.reveal_dir(Path("/tmp/maps")) == (True, "")
    assert ran.ran == ["dbus-send"], "xdg-open ran although the reveal had already happened"
    assert "org.freedesktop.FileManager1.ShowFolders" in ran.calls[0]


def test_the_directory_reaches_the_bus_percent_encoded(on_linux, monkeypatch):
    """The bus takes a URI and a command line takes a path, and they are not one spelling.

    A directory with a space in it is the ordinary case that separates them -- handed over
    raw it is either a malformed URI or two arguments, depending which rung gets it.
    """
    ran = _Ran({"dbus-send": (0, "", "")})
    monkeypatch.setattr(serve_mod.subprocess, "run", ran)
    serve_mod.reveal_dir(Path("/tmp/my maps"))
    assert any(a == "array:string:file:///tmp/my%20maps" for a in ran.calls[0]), ran.calls[0]


def test_xdg_open_carries_it_when_the_bus_cannot(on_linux, monkeypatch):
    """Plenty of sessions have no file manager on the bus, and that is what rung two is for.

    Pressed against a real desktop with the bus rung shimmed to fail: Thunar opened anyway.
    """
    ran = _Ran({"dbus-send": (1, "", "Error ...ServiceUnknown"), "xdg-open": (0, "", "")})
    monkeypatch.setattr(serve_mod.subprocess, "run", ran)

    assert serve_mod.reveal_dir(Path("/tmp/maps")) == (True, "")
    assert ran.ran == ["dbus-send", "xdg-open"]


def test_an_exhausted_ladder_reports_the_last_rungs_reason(on_linux, monkeypatch):
    """The reason a reader can act on is the one from the rung every desktop has.

    Keeping the earliest complaint would answer *"dbus-send is not installed"* on a machine
    where the interesting fact is what `xdg-open` said -- and the first rung failing is the
    ordinary case, not the diagnosis (rule 89).
    """
    ran = _Ran({"xdg-open": (3, "", "xdg-open: no method available")})
    monkeypatch.setattr(serve_mod.subprocess, "run", ran)

    shown, why = serve_mod.reveal_dir(Path("/tmp/maps"))
    assert shown is False
    assert why == "xdg-open: no method available"
    assert "dbus-send" not in why


def test_a_ladder_with_nothing_installed_still_says_something(on_linux, monkeypatch):
    """Both rungs absent is a real state -- a minimal container, a server with no desktop
    packages -- and an empty reason would render as a blank where a sentence belongs."""
    monkeypatch.setattr(serve_mod.subprocess, "run", _Ran({}))
    shown, why = serve_mod.reveal_dir(Path("/tmp/maps"))
    assert shown is False and why, "the reveal refused without saying why"


# --------------------------------------------------------------------------- #
# The other two platforms, unchanged


@pytest.mark.parametrize("platform,command", [("darwin", "open"), ("win32", "explorer")])
def test_the_platforms_that_are_one_command_stay_one_command(monkeypatch, platform, command):
    """Linux gained a ladder; the other two did not gain one with it.

    Worth pinning because the Linux branch was added *inside* `reveal_dir` rather than beside
    it, and the cheapest way to write that wrongly is to route everything through the ladder.
    `explorer` exiting 1 on success is why the return code is still not read on Windows.
    """
    monkeypatch.setattr(sys, "platform", platform)
    ran = _Ran({command: (1, "", "")})
    monkeypatch.setattr(serve_mod.subprocess, "run", ran)

    assert serve_mod.reveal_dir(Path("/tmp/maps")) == (True, "")
    assert ran.ran == [command]


def test_a_platform_with_no_answer_refuses_in_a_sentence(monkeypatch):
    """Rule 49's inverse: a platform nobody has built for says so rather than doing nothing.

    FreeBSD is the honest example -- everything else here would work there, and neither of
    these two would, so the tool says which.
    """
    monkeypatch.setattr(sys, "platform", "freebsd14")
    ran = _Ran({})
    monkeypatch.setattr(serve_mod.subprocess, "run", ran)

    assert serve_mod.pick_folder() == ("", serve_mod.NO_PICKER)
    assert serve_mod.reveal_dir(Path("/tmp/maps")) == (False, serve_mod.NO_REVEAL)
    assert ran.calls == [], "a refusal on an unknown platform still spawned something"
