"""The packaged application's presence in the Dock.

**The symptom, because it is not obvious that this is a code problem at all.** A
double-clicked DunneFlow showed a Dock icon with **no running indicator** — the dot every
other application has under it. Reported by Tom, with the consequence stated better than the
cause: *"Most users will not understand how to find a running process and will just continue
launching it over and over."*

He was right, and it was worse than that. `lsappinfo` gives the reason exactly:

    pid = 26269 !cgsConnection !signalled type="Foreground" ... fileType="APPL"

`type="Foreground"` — LaunchServices already considered it a foreground application, and
`LSBackgroundOnly` was already false, so the plist was not the problem. **`!cgsConnection`**
is: the process had no connection to the window server. A command line tool inside a bundle
never touches AppKit, so nothing ever registers it, and the Dock has nothing to draw an
indicator for. No amount of `Info.plist` fixes that; a process has to *connect*.

`[NSApplication sharedApplication]` is what connects. Measured in isolation before anything
was built on it: a bare Python process that makes that one call loses its `!cgsConnection`.

**Why the event loop, and not just the connection.** The one-line version buys the dot and a
Dock icon that cannot be quit — no run loop means the quit Apple Event is never handled, so
Dock → Quit and ⌘Q hang and offer Force Quit instead. That is a worse place to leave a
reader than no dot at all: the icon now *looks* like an ordinary application and then breaks
the two gestures every ordinary application has. So the server moves to a background thread
and `[NSApp run]` takes the main one. Quit is then `NSApplication`'s own default handling of
`kAEQuitApplication`, which terminates the process — no delegate, no subclass.

**No delegate, and that is load-bearing rather than minimal.** Installing one means creating
an Objective-C class with Python method implementations, which means `ctypes.CFUNCTYPE`
callbacks, which means executable closures — and `packaging/entitlements.plist` asks for
nothing precisely because *"CPython 3.12 has no JIT and nothing builds a ctypes closure"*.
Everything here is a call *out* to functions that already exist; nothing is compiled at
runtime, so that file stays empty and stays earned.

**Two library handles, for the same reason.** `objc_msgSend` is called with two different
signatures, and on arm64 the argument registers depend on the declared types — a single
`_FuncPtr` cannot carry both, and `ctypes.CFUNCTYPE` is the usual way round that. It is
avoided here for the paragraph above: a second `CDLL` gives a second, independently typed
handle to the same symbol and builds nothing.

**Frozen and macOS only.** A checkout serves from a terminal where Ctrl-C is the way out and
a Dock icon would be an intrusion; `runtime`'s Windows and Linux branches are exercised
now, and what a running application should look like there is not this module's to guess.

Not in `runtime.py` despite being one of its questions. That module is four short answers
about *what this build is*, read by everything; this is one long answer about what an
application looks like on one operating system, read by `serve` alone. Keeping it here is
what stops `runtime` from becoming the place where anything platform-shaped goes.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import signal
import sys
import threading
from collections.abc import Callable

from .runtime import frozen

# `NSApplicationActivationPolicyRegular`. The application appears in the Dock and can own
# the menu bar -- which is the whole request. `Accessory` (1) is a menu-bar-only agent and
# `Prohibited` (2) is what this process effectively was.
_REGULAR = 0


def available() -> bool:
    """Should this build take the main thread and become a Dock application?

    Frozen and macOS. A checkout is a terminal program whose way out is Ctrl-C, and taking
    its main thread for an event loop would be an intrusion into somebody's shell for a
    Dock icon they did not ask for.
    """
    return frozen() and sys.platform == "darwin"


def _appkit() -> tuple[ctypes.CDLL, ctypes.CDLL] | None:
    """The two handles, or `None` if AppKit is not loadable.

    `None` rather than an exception: this is a presentation nicety, and an application that
    refused to start because a framework could not be found would have traded the whole
    tool for a dot. Every caller falls back to serving on the main thread.
    """
    objc_path = ctypes.util.find_library("objc")
    appkit_path = ctypes.util.find_library("AppKit")
    if not objc_path or not appkit_path:
        return None
    try:
        objc = ctypes.CDLL(objc_path)
        # Loaded for its side effect: the `NSApplication` class does not exist until
        # AppKit is in the process, and `objc_getClass` would answer NULL.
        ctypes.CDLL(appkit_path)
        # The second handle, independently typed. See the module docstring.
        objc_typed = ctypes.CDLL(objc_path)
    except OSError:
        return None
    return objc, objc_typed


def run_as_application(serve_forever: Callable[[], None],
                       stop: Callable[[], None]) -> bool:
    """Become a Dock application, run `serve_forever` on a thread, and take the main one.

    Returns `False` having done nothing if the window server cannot be reached -- which is
    a real state rather than a defensive one: a build run over SSH, or in a session with no
    `WindowServer`, has no Dock to appear in and must still serve.

    `stop` is what makes quitting orderly. The server thread is a daemon, so terminating
    would work without it; calling `shutdown()` first means the socket closes and the stores
    are released rather than being reclaimed by the process dying, which is the difference
    between a clean exit and one that merely looks like it from outside.
    """
    handles = _appkit()
    if handles is None:
        return False
    objc, objc_typed = handles

    objc.objc_getClass.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]

    # `id objc_msgSend(id, SEL)` -- the no-argument form.
    send = objc.objc_msgSend
    send.restype = ctypes.c_void_p
    send.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    # `BOOL objc_msgSend(id, SEL, NSInteger)` -- `setActivationPolicy:`.
    send_i = objc_typed.objc_msgSend
    send_i.restype = ctypes.c_bool
    send_i.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]

    cls = objc.objc_getClass(b"NSApplication")
    if not cls:
        return False
    app = send(cls, objc.sel_registerName(b"sharedApplication"))
    if not app:
        # **The connection is the thing, and it can fail.** `sharedApplication` returns NULL
        # where there is no window server to connect to, and pressing on would run an event
        # loop over nothing -- a server that appears to start and answers no requests.
        return False
    send_i(app, objc.sel_registerName(b"setActivationPolicy:"), _REGULAR)

    worker = threading.Thread(target=serve_forever, name="dunneflow-http", daemon=True)
    worker.start()

    # **Ctrl-C is handed back to the operating system, and only on this path.** Python's own
    # SIGINT handler runs between bytecodes on the main thread, and this main thread is
    # about to be inside `[NSApp run]` -- so a `KeyboardInterrupt` would not be raised until
    # some unrelated event woke the loop, which reads as Ctrl-C doing nothing. The default
    # disposition ends the process at once. Nothing is lost by that: every store this
    # process holds is open read-only (rule 20), so there is no write to interrupt.
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        send(app, objc.sel_registerName(b"run"))
    finally:
        # Reached when the reader quits from the Dock or the menu bar. `NSApplication`
        # handles `kAEQuitApplication` itself and usually ends the process before this line,
        # so it is the orderly path rather than the only one.
        stop()
    return True
