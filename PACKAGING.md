# DunneFlow — packaging, and the frozen application

`CLAUDE.md` carries the verification gates; this file carries **how the application is
built, signed and shipped on all three platforms** — the spec, the release scripts, and the
measurement behind every decision in them.

**Read this before touching `packaging/`, `runtime.py`, or anything a frozen build reads as
a file.** Most of what is here was paid for by a build that succeeded and was wrong: a
universal build that came out arm64 and would have been found by a colleague on an Intel
Mac; a bundled compiler shipping without the headers it opens by path, which did not refuse
but answered with less; an entitlement copied from four guides that copied each other, and
that nothing indicated.

## Packaging — the frozen application

**Three platforms, one spec.** `packaging/dunneflow.spec` builds for whichever it is run on,
and the sections below are macOS's unless they say otherwise; **Windows** and **Linux** are at
the foot of this one.

**`_MACOS`, `_WINDOWS` and `_LINUX` are asked once, and that is rule 94.** The spec named only
`_WINDOWS` and said everything else by negation, which was an exact statement of the truth
while there were two platforms: `BUNDLE` under `if not _WINDOWS` would have built a `.app` on
Linux and PyInstaller would have reported success, and `ICON` would have refused the build over
a missing `.icns` it would then never have used. A negation is a fine way to say *the other
one* and no way at all to say *the other two*.

```bash
DUNNEFLOW_ARCH=host uv run pyinstaller packaging/dunneflow.spec --noconfirm
```

That is the **development** build: this machine's architecture, ad-hoc signed, ~11 s, and it
**must never leave this machine** — every step in `release.sh` refuses it by name. Building for
one architecture is now something you have to ask for; see `DUNNEFLOW_ARCH` below.

A **release** is `packaging/release.sh`, one verb per step so any of them can be run alone:

```bash
./packaging/release.sh venv      # the universal2 build environment
./packaging/release.sh build     # DUNNEFLOW_ARCH=universal2 — arm64 and x86_64
./packaging/release.sh sign      # Developer ID, hardened runtime, secure timestamp
./packaging/release.sh notarize   # submit the .app, wait, staple it
./packaging/release.sh dmg       # build, sign, notarise and staple DunneFlow-<version>.dmg
./packaging/release.sh verify    # architectures, signature, Gatekeeper, staple, stamps
./packaging/release.sh install   # ditto the stapled .app into /Applications
./packaging/release.sh all
```

**`DUNNEFLOW_ARCH` has two answers and no third, and `universal2` is the default.** It was the
other way round until 2026-09-10, which made the fast build the easy one and the shippable
build the one you had to remember — and forgetting is silent, because an arm64 bundle installs
and runs perfectly on the machine that built it. Measured before flipping it: **12.9 s universal
against 11.5 s host**, so the cheap default was not buying anything. `host` is the other answer,
for the verification gate in `GROUND-TRUTH.md`.

The spec **refuses rather than falling back** (rule 49): asked for `universal2` under an
interpreter that cannot produce one it raises and names both ways out. A universal build that
quietly came out arm64 would sign, notarise and ship, and be found by a colleague on an Intel
Mac rather than here.

**And a default is a habit, so the artifact is checked rather than the command.**
`require_universal` gates `sign`, `notarize`, `dmg` and `install` — the four steps whose output
reaches somebody else — because the one failure a default cannot prevent is a `host` build being
signed and shipped by hand. Asked of the executable with `lipo`; `verify` walks all 53 Mach-O
files in the bundle, which is the fuller form of the same question.

**A universal build needs a universal interpreter, and it cannot be uv's.** uv's managed
Pythons and Homebrew's are single-arch by construction; python-build-standalone ships no
universal2 build at all. `python-3.12.10-macos11.pkg` from python.org is the last universal2
3.12 — 3.12.11 is source-only — and `release.sh venv` builds `.venv-universal` from it. It is a
build-only interpreter and disturbs neither uv nor the project environment.

**PyYAML's C extension is dropped from the bundle**, `excludes = ["yaml.cyaml", "yaml._yaml"]`,
and both names are needed: excluding the extension alone leaves `yaml.cyaml` importing something
that is not there, which is an `ImportError` where `yaml/__init__.py` has a fallback. It is the
one file in the bundle that cannot be built for both architectures — **PyPI has no universal2
PyYAML wheel for any version** — and it is never used: every call site here is `yaml.safe_load`,
which is the pure-Python `SafeLoader` whatever `_yaml` does. `test_frozen.py` holds both halves,
reading the *syntax* rather than the text, because this file's own explanation of the rule
contains every word a scan would look for (rule 34).

**`packaging/entitlements.plist` asks for nothing, and that is the measurement.** Every
PyInstaller guide carries the same four entitlements copied from each other, and none is
indicated: the picker spawns `/usr/bin/osascript`, whose `activate` and `choose folder` run
inside osascript itself so no Apple Event leaves this process; CPython 3.12 has no JIT and
nothing builds a ctypes closure; and every Mach-O file in the bundle is signed by the identity
that signs the bundle, so library validation has nothing to refuse. **Pressed rather than
assumed**: `POST /api/pickdir` against the signed app in `/Applications` spawned osascript as a
child and held the dialog open, with nothing denied in the AMFI log. A key added there needs the
failure that earned it recorded beside it. The file's own XML is stricter than most — a comment
before the `DOCTYPE`, or a double hyphen inside one, is `AMFIUnserializeXML: syntax error`, and
both were paid for.

**The Dock presence is bought without spending one, and that is why it is shaped as it is.**
`macapp.py` calls AppKit through `ctypes` so the application registers with the window server
— the frozen app showed a Dock icon with **no running indicator**, and `lsappinfo` named the
cause exactly: `type="Foreground"` but `!cgsConnection`, because a command line tool in a
bundle never touches AppKit. `LSBackgroundOnly` was already false; the plist was never it.
Every call is *out* to a function that already exists, so `allow-unsigned-executable-memory`
stays unnecessary — which is what rules out an `NSApplicationDelegate`, since defining an
Objective-C class with Python methods is precisely that closure. Quit is `NSApplication`'s own
default handling of the quit Apple Event, so ⌘Q and Dock → Quit work with no delegate at all;
the one-line version that only connects would have given a dot and an application nobody could
quit. `tests/test_frozen.py` asserts the module contains no `CFUNCTYPE`, so the claim above
cannot quietly stop being true. Measured on the Developer ID build with `flags=0x10000(runtime)`
and the dictionary empty: registers, serves, quits, nothing denied in the AMFI log.

**Nothing uses `codesign --deep`.** Apple deprecates it and it applies the *outer* bundle's
entitlements to everything nested, which is the opposite of what an empty entitlements file is
for. Every Mach-O file is found — never listed, so a dependency's dylib cannot arrive ad-hoc
signed inside a Developer ID bundle — and signed on its own, deepest first, the bundle last.
The `.app` is notarised and stapled **before** the `.dmg` is built, and the image is notarised
and stapled in its own right: a stapled image alone leaves the dragged-out app needing a network
round trip on first launch, and a reader opening an unfamiliar tool offline is the case this has
to survive.

**Four questions have two answers, and `runtime.py` is the only place either is given**
(rule 51): am I frozen, where do my files live, where do maps go, and how do I run myself.
Every one of them was `Path(__file__)` or a spelled-out `sys.executable` somewhere, and
frozen each is wrong in a different way. A fifth — *what does an application look like on
this operating system* — is `macapp.py` rather than a fifth branch here, because it is one
long macOS-only answer read by `serve` alone, and `runtime` stays four short ones read by
everything.

* **`resource_root()` keeps `dunneflow` as its last segment in both worlds**, and that is
  load-bearing rather than tidy. `fingerprint_files` labels every input relative to it, so
  the binary and the checkout agree on a fingerprint at the same commit — measured: the
  binary stamps `extractor = 9:e8c9ac8a851c41b7`, which is the checkout's, and the checkout
  opens the binary's maps. Laid out any other way the two builds refuse each other's maps
  under rule 12, which is the opposite of what that rule is for. A build-time constant was
  considered and rejected for exactly that.
* **`fingerprint_files` refuses an empty input and a named-but-absent one**, each with its
  own sentence. A hash of nothing is `e3b0c44298fc1c14` and looks exactly like a
  fingerprint; a `Path(__file__)` that is not a file raises `FileNotFoundError` from inside
  a hash. `RulesMissing` is the class, and it is always a build defect.
* **`multiprocessing.freeze_support()` is the first statement of both entry points.** macOS
  spawns, so a frozen pool worker re-executes *the application* — sixteen more servers, or
  sixteen more analyses. `walk.py`'s serial fallback cannot catch it: nothing in the parent
  raises, because the parent is fine and the children are the program.
* **`self_argv()`** is how the analysis subprocess runs this same build. `-m dunneflow.cli`
  means nothing to a binary, and that would have broken **+ Analyse a directory…** on the
  one build where it is the only way in.
* **`default_output_root()`** is `./output` from a checkout and, frozen, **whatever the
  reader chose** — `platform_output_root()` when they have not. That platform answer is
  `~/Library/Application Support/DunneFlow`, `%LOCALAPPDATA%\DunneFlow` or
  `$XDG_DATA_HOME/DunneFlow`, and never `~/Documents`: `source.db` holds the private source
  of whatever was read, and Documents is swept into iCloud Drive on a signed-in Mac — egress
  by accident, out of a tool whose posture is deterministic and local (design rule 14).
  **`$XDG_DATA_HOME` is three states rather than two**, and the third is the specification's
  own: unset or empty is the default `~/.local/share`, an absolute path is the answer, and a
  **relative** one is invalid and must be ignored. Not deference to a document — a relative
  path resolves against the working directory, and a desktop entry gives a process none worth
  the name, so honouring one would scatter maps roots wherever the launcher started and report
  no programs from each in turn (rule 49). `serve` **creates it only when nobody named a
  directory**; one the reader typed is never created, because a mistyped path would otherwise
  become a new empty root reporting no programs in a place they have never used (rule 49).
* **The root moves, and a one-line pointer at `<platform root>/root` remembers where.**
  Maps are not small and Application Support is on the boot disk, so `Move…` on the start
  page re-points and optionally carries the existing programs across (`web/roots.py`,
  `POST /api/root`) — copy every program, verify every copy, and only then delete, so a
  failure leaves the originals untouched and takes the partial copies with it.
  **Three states, never two**: no pointer, one that resolves, and one naming a disk that is
  not connected. The third **raises** `MapsRootGone`, and the reason is `cmd_serve`'s
  `mkdir(parents=True)`: `/Volumes` is an ordinary directory *on the boot disk*, so a
  pointer's target that got created would put a new empty maps root on precisely the drive
  the reader was clearing, and then report no programs in it (rule 49). **A pointer's target
  is never created.** `serve` falls back to the platform root and *says so* — on the terminal
  and in a banner on the start page, because a stated substitution is recoverable and a
  silent one is the failure. And **a checkout never reads or writes it**: the two worlds share
  a home directory, and a checkout that stamped the pointer once sent the packaged
  application to a scratchpad that no longer existed.

`packaging/dunneflow.spec` bundles as **data** everything something reads as a *file*: the
rules (loaded as YAML) and the detectors' loader plus both extractor trees (**hashed**, not
imported — rule 12 puts the reader in the key), `web/static`, `web/vendor`, and
`copy_metadata('dunneflow')` so `tool_version()` needs no frozen branch. Destination
`dunneflow/…`, per `resource_root()`. `packaging/dunneflow_app.py` defaults a bare argv to
`serve` — the **application's** decision, not the CLI's, which keeps its usage message.

### Windows

```powershell
./packaging/release.ps1 all        # build · verify · zip · install
```

**Four verbs against `release.sh`'s seven**, and the three that are missing are missing for
stated reasons rather than because nobody got to them. There is no `venv`: a Windows
executable holds one architecture, so `DUNNEFLOW_ARCH` has no answer there but `host` and the
spec **refuses a macOS answer by name** rather than accepting a word it would then ignore.
There is no `sign`/`notarize`: an unsigned Windows binary meets SmartScreen, which is a
warning a reader clicks past, where an unsigned bundle meets Gatekeeper, which is a refusal
they cannot — so `verify` **says the build is unsigned** rather than leaving somebody to
learn it from a dialog. There is no `dmg`; a `.zip` is what Windows opens untaught.

**Two executables, and the second is not a convenience.** `console=False` on macOS costs
nothing at a shell, because a Mach-O bundle run from a terminal inherits that terminal's
streams. A Windows GUI-subsystem binary is given **no standard streams at all**, so
`DunneFlow.exe analyze …` would do the work and print none of it — and the ground-truth gate in `GROUND-TRUTH.md`, which
exists to run ground truth *through the binary*, would have nothing to read. So the spec
builds both from one `Analysis` and one `COLLECT`, as Windows does for `python.exe` and
`pythonw.exe`:

| | |
|---|---|
| `DunneFlow.exe` | windowed. What a reader double-clicks. |
| `dunneflow-cli.exe` | console. The command line, and what the gate runs through. |

The names differ by more than case because **NTFS is case-insensitive**: `DunneFlow.exe` and
`dunneflow.exe` are one file there, and the second `EXE()` would overwrite the first with no
error anywhere. `tests/test_frozen.py` asserts that, and that nothing in `release.ps1`
reaches a network.

The icon is `packaging/icon/dunneflow.ico`, written from the **same composed canvas** as the
`.icns` by `build_supplied_icon.py` — Pillow writes it and runs anywhere, where `iconutil` is
macOS's alone, so off a Mac the `.icns` is left untouched and the script says so. Its ladder
is its own: Explorer's medium-icons view is **48px**, which nothing in the macOS ladder is.

Measured 2026-09-15 on Windows 11, Python 3.12.4: **33.7 MB** built, a **16.6 MB** zip, both
executables 3.1 MB, and `extractor 9:d6179cee25581502` stamped by the binary and computed by
the checkout alike — which is the one check that is not a size (rule 12, and see
**Packaging** above).

### Linux

```bash
./packaging/release-linux.sh all   # build · verify · tar · install
```

**Six verbs, and the three that are missing are missing for stated reasons.** There is no
`venv`: an ELF holds one architecture, `FatELF` was proposed and never merged, and there is no
`lipo` for Linux — so `DUNNEFLOW_ARCH` has no answer here but `host` and the spec **refuses a
macOS answer by name**. There is no `sign`/`notarize`: nothing on Linux refuses an unsigned
binary, so `verify` **says the build is unsigned** rather than leaving that to be assumed.
There is no `dmg`; a `.tar.gz` is what every Linux opens untaught.

**`uninstall` is the verb the other two scripts do not have**, and it is not symmetry. A macOS
uninstall is one `.app` in the Trash and a Windows one is a folder; this is **thirteen files in
four places** under `~/.local`, which no reader can undo by looking at it. The maps are never
touched — an uninstall that took them would be the one unrecoverable thing the script could do.

**One executable, not two.** `console=False` costs a Windows build its standard streams and so
buys a second `EXE()` there; an ELF has no subsystem flag and PyInstaller ignores the setting,
so `dunneflow` prints from a terminal exactly as the checkout does and the gate runs through it
unchanged.

**`~/.local/share/DunneFlow` is the one genuinely Linux-shaped trap in the packaging.** It is
the obvious place for an application's files under `$HOME` and it is already the reader's
**maps** root — `runtime.platform_output_root()`. On macOS the pair is `/Applications` and
`~/Library/Application Support` and cannot collide; here the natural spelling of both is one
directory, and installed there the program would sit inside the tree its own `Move…` offers to
relocate and inside the corpus its own analyses walk. So the binary goes to
`~/.local/lib/dunneflow`, the name a terminal types to `~/.local/bin`, and the entry and icons
to the two freedesktop trees. `tests/test_frozen.py` asserts no install target lands in
`platform_output_root()`. **Nothing needs root**, which is what keeps all of it inside one
reader's home.

The icon is `packaging/icon/hicolor/` — ten PNGs at the freedesktop sizes, written from the
**same composed canvas** as the `.icns` and the `.ico`. Never from `dunneflow.svg` beside it:
that is `build_icon.py`'s geometric candidate, which was not the one chosen, and shipping it as
`scalable/` would put a different mark on Linux than the one in the Dock. Its ladder is its own
— 22 and 96 are hicolor's and are in neither of the others. **An ELF carries no icon at all**,
so what a reader sees is whatever the desktop entry's `Icon=` name resolves to in the theme; a
test pins the entry's spelling against the committed filenames, because spelled two ways the
entry is valid, the install succeeds, every check passes, and the menu draws a generic square.

`packaging/linux/dunneflow.desktop.in` is a template, not a file: a per-user install lives under
the reader's own home and no committed line can know that path. **`StartupNotify=false` is
measured rather than conventional** — this process maps no window, so the launcher's busy
cursor would spin for the twenty seconds a desktop waits before giving up. There is no
`StartupWMClass` for the same reason. The problem a Dock indicator buys on macOS is answered
here by the program instead: `already_serving` joins a second launch to the first one's server
and opens the browser at it, so a double-click while it is running is not a second server.

Measured 2026-09-15 on Linux Mint (XFCE, X11), Python 3.12.3: **9.5 s** to build, **32 MB**
built, a **13 MB** tarball, `glibc 2.14` the floor, and `extractor 9:d6179cee25581502` stamped
by the binary and computed by the checkout alike — the same fingerprint the Windows build
stamps. Both directions pressed: each build opened the other's map, 925 routines either way.

**`verify` compares those fingerprints rather than printing them.** The first version printed
the checkout's, ran the binary, and said *"the binary analysed a tree and wrote a map"* —
rule 37, in the step written to defend rule 12. The version after *that* one asked by writing
`from dunneflow.detectors import rules_fingerprint` into a here-doc, and chunk 5 split that
function in two: the step raised `ImportError` for eight chunks, on no test path, saying
nothing (rule 51, in a shell script). All three platforms run `tools/fingerprints.py` now and
none of them spells a Python symbol; a test asserts both halves. And `tar` named its first archive `DunneFlow--linux-x86_64.tar.gz`: `app_version`
asked the binary for `--version`, which this CLI has not got, and an empty string went into a
path (rule 49, in a file name). It reads the dist-info the spec bundles — the same file
`tool_version()` stamps into every map.

**The 1,447 tests prove the source tree, not the artifact**, so the ground truth is run
*through the binary*. Taken 2026-09-09 on `../society-2026-08-29/src` with
`--standards ../dunnecorp-standards`, 628 files in **37.7 s**: the four executables at
**1,381 · 423 · 292 · 112**, `naming.md` byte-identical to the `CORP` fixture with its three
rules in the checked lane, the research paper yielding **zero** naming rules, and the
conformance verdicts at **4 checked · 1 no population · 10 not checkable**.

**Signed, notarised and shipping on all three platforms.** The identity is
`Developer ID Application: Thomas Williams (G3RLJWV327)`, and a released build reports
`flags=0x10000(runtime)`, the full Apple authority chain and a secure timestamp; the `.app`
and the `.dmg` are each notarised and stapled in their own right. The two once-only steps
below have been done on this machine and are kept here because they are once-only *per
machine*; they are also in `packaging/release.sh`'s own header:

```bash
curl -LO https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg
sudo installer -pkg python-3.12.10-macos11.pkg -target /       # the universal2 interpreter

xcrun notarytool store-credentials dunneflow \
    --key ~/.appstoreconnect/AuthKey_XXXXXXXXXX.p8 \
    --key-id XXXXXXXXXX --issuer <issuer-uuid>                 # from App Store Connect
```

After that the key, its id and the issuer id are the keychain's business; `release.sh` knows
only the profile name.

*This paragraph said "still to do: notarisation, the universal build, an icon, and Windows"
until 2026-09-15, by which point all four were done and shipped — it was four milestones
stale in the one file every session loads, and it was found by a chapter of the user guide
disagreeing with it.* What is still open is stated in `BACKLOG.md` and nowhere else, so
there is one place to read it.
