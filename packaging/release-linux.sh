#!/usr/bin/env bash
#
# How a DunneFlow build is made on Linux: frozen, checked, wrapped, and put where the
# application menu can find it.
#
#     ./packaging/release-linux.sh all
#
# One verb per step, so any of them can be run alone while something is being worked out:
#
#     build      freeze dist/dunneflow/ for this machine's architecture, payload staged
#     stage      put the desktop entry, the icons and install.sh into the build
#     verify     say what another machine of this kind will make of it
#     tar        dist/DunneFlow-<version>-linux-<arch>.tar.gz
#     install    into ~/.local — binary, desktop entry, icon theme
#     uninstall  take all three back out again
#     all        build, verify, tar, install
#
# **Six verbs against release.sh's seven, and the differences are stated rather than
# pending.** There is no `venv`: an ELF holds one architecture, `FatELF` was proposed and
# never merged, and there is no `lipo` for Linux -- so a machine that wants both builds
# twice, on two machines, and `DUNNEFLOW_ARCH` has no answer here but `host`. There is no
# `sign` or `notarize`: Linux has no Gatekeeper, nothing refuses an unsigned binary, and
# there is no authority to sign against -- so `verify` **says the build is unsigned**
# rather than leaving somebody to assume it is not. There is no `dmg`; a `.tar.gz` is what
# every Linux opens untaught.
#
# **`uninstall` is the verb the other two do not have, and it is not symmetry for its own
# sake.** On macOS the whole uninstall is dragging one `.app` to the Trash, and on Windows
# it is deleting one folder. A Linux install is a binary tree, a desktop entry and ten icon
# files in three different places under `~/.local` — which is the correct layout and is not
# something a reader can undo by looking at it. A tool that can put ten files into somebody's
# home directory and not take them out again is a tool that gets uninstalled with `find`.
#
# **Nothing here needs root, and that is deliberate.** Everything goes under `~/.local`,
# which every freedesktop-conforming desktop searches: no `sudo`, nothing outside this
# reader's own home, and nothing that a second account on the same machine can see. It is
# also what keeps the maps root and the application apart — see `install` below, where that
# turns out to be the one genuinely Linux-shaped trap in this file.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist"
APP="$DIST/dunneflow"                       # COLLECT(name=…) in packaging/dunneflow.spec
BIN="$APP/dunneflow"                        # EXE(name=…) in the same file

# **Where an installed application goes, and where it must not go.** `~/.local/lib` for the
# program, `~/.local/bin` for the name a terminal types, and the two freedesktop trees for
# how a menu finds it.
#
# `~/.local/share/DunneFlow` is conspicuously absent, and that is the trap. It is the
# obvious place for an application's files on Linux -- and it is already taken, because it
# is exactly what `runtime.platform_output_root()` answers: the reader's **maps** root. On
# macOS the two are `/Applications` and `~/Library/Application Support` and could not
# collide; here the natural spelling of both is one directory. Installed there, the program
# would sit inside the tree its own `Move…` offers to relocate, and inside the corpus its
# own analyses walk.
PREFIX="${DUNNEFLOW_PREFIX:-$HOME/.local}"
LIBDIR="$PREFIX/lib/dunneflow"
BINLINK="$PREFIX/bin/dunneflow"
DESKTOP="$PREFIX/share/applications/dunneflow.desktop"
ICONS="$PREFIX/share/icons/hicolor"

cd "$ROOT"

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
die()  { printf '\n\033[1;31m!! %s\033[0m\n' "$*" >&2; exit 1; }

# The version is read off the thing being shipped, never spelled a second time here — and
# **the first spelling of this read nothing at all and said so in the filename**:
# `DunneFlow--linux-x86_64.tar.gz`. It asked the binary for `--version`, which this CLI does
# not have; `argparse` printed its usage message to stderr, the pipeline swallowed it, and an
# empty string went straight into a path. Rule 49 in a file name.
#
# What the artifact *does* carry is the dist-info, because the spec calls
# `copy_metadata('dunneflow')` — the very file `runtime.tool_version()` reads to stamp
# `tool_version` into every map this build writes. So the name of the archive and the version
# recorded inside the maps it ships cannot disagree; they are one file, read twice.
#
# (`release.sh` reads macOS's `CFBundleShortVersionString` instead, which the spec's
# `info_plist` takes from `pyproject.toml`. That is a second reading of the same answer and is
# left alone here: it is the version Apple is shown.)
app_version() {
    [ -d "$APP" ] || die "there is no build yet — run '$0 build' first"
    local meta
    meta="$(find "$APP" -path '*dunneflow-*.dist-info/METADATA' | head -1)"
    [ -n "$meta" ] || die \
"no dunneflow dist-info in $APP — the spec's copy_metadata('dunneflow') did not travel,
which also means tool_version() will report nothing in every map this build writes."
    sed -n 's/^Version: //p' "$meta" | head -1
}

arch() { uname -m; }

tar_path() { echo "$DIST/DunneFlow-$(app_version)-linux-$(arch).tar.gz"; }

# --- build -----------------------------------------------------------------------------
step_build() {
    say "freezing for $(arch)"
    # `host` is the only answer this platform takes, and the spec refuses a macOS one by
    # name rather than accepting a word it would then ignore. Said here too, so that a
    # `DUNNEFLOW_ARCH` inherited from a shell where somebody was building for a Mac does
    # not reach the spec and stop the build with a message about Mach-O.
    DUNNEFLOW_ARCH=host uv run pyinstaller packaging/dunneflow.spec --noconfirm
    [ -x "$BIN" ] || die "pyinstaller reported success and there is no $BIN"
    step_stage
    echo
    echo "   $(du -sh "$APP" | cut -f1)  $APP"
}

# --- stage -----------------------------------------------------------------------------
# **What makes the tarball installable, and it is the whole of the 2026-09-15 fix.**
# `install` used to read the desktop entry from `packaging/linux/` and the icons from
# `packaging/icon/hicolor/` — paths in the *repository*. `step_tar` ships `dist/dunneflow`
# and nothing else, so the install command documented beside the tarball could not run from
# it: a reader who downloaded the artifact got a directory they could execute and no way to
# reach their application menu. PyInstaller is not asked to carry these, because in a onedir
# build `datas` land under `_internal/` and these are not the program's inputs — they are
# the installer's.
#
# Staged into `$APP/share`, the checkout and the unpacked tarball hold **the same tree**,
# which is what lets one `install.sh` serve both (rule 51). Run as part of `build` rather
# than as a step somebody must remember: a build that cannot be installed is not a build.
step_stage() {
    local share="$APP/share"
    [ -f "$ROOT/packaging/linux/dunneflow.desktop.in" ] || die \
        "packaging/linux/dunneflow.desktop.in is missing — nothing to stage"
    [ -d "$ROOT/packaging/icon/hicolor" ] || die "no icons — build them first:
  uv run --with pillow python packaging/icon/build_supplied_icon.py \\
      packaging/icon/rabbit-head.png"

    rm -rf "$share"
    mkdir -p "$share/icons"
    cp "$ROOT/packaging/linux/dunneflow.desktop.in" "$share/dunneflow.desktop.in"
    cp -R "$ROOT/packaging/icon/hicolor" "$share/icons/hicolor"
    # The installer travels *inside* the thing it installs, so the copy in `~/.local/lib`
    # can uninstall itself long after the tarball has been deleted.
    cp "$ROOT/packaging/linux/install.sh" "$APP/install.sh"
    chmod +x "$APP/install.sh"
    echo "   staged $(find "$share" -name 'dunneflow.png' | wc -l | tr -d ' ') icons," \
         "the desktop entry and install.sh into $APP"
}

# --- verify ----------------------------------------------------------------------------
step_verify() {
    say "what another Linux machine will make of this"
    [ -x "$BIN" ] || die "there is no build to verify"

    echo "-- architecture"
    file -b "$BIN" | sed 's/^/   /'

    echo "-- signature"
    # **Stated rather than skipped** (design rule 1). An unsigned binary is the normal and
    # correct state of a Linux build: there is no Gatekeeper to refuse it and no authority
    # to sign against. Saying so is what stops somebody reading this script's silence as a
    # signature it did not check.
    echo "   unsigned — Linux has no equivalent of Gatekeeper, and nothing here refuses an"
    echo "   unsigned binary. There is no notarisation step to be waiting on."

    echo "-- the glibc it needs"
    # The one portability fact a Linux binary actually has. PyInstaller does not bundle
    # libc, so a build made here runs on any distribution whose glibc is at least this new
    # and on none older — which is the whole of what "will this run elsewhere" means.
    local need
    need="$(objdump -T "$BIN" 2>/dev/null | sed -n 's/.*GLIBC_\([0-9.]*\).*/\1/p' \
            | sort -V | tail -1)"
    echo "   built against glibc ${need:-unknown}; older distributions will refuse it"

    echo "-- the maps this build writes, against the checkout's"
    # **The one check here that is not a size** (rule 12). The fingerprint puts the reader
    # in the cache key, so the binary and the checkout agree on one only if
    # `resource_root()` laid the bundle out the way the spec promises. Disagree, and the
    # two builds silently refuse each other's maps — which is the opposite of what that
    # rule is for, and is invisible until somebody hands a colleague a map.
    #
    # **It is compared, not printed.** The first version of this step printed the
    # checkout's fingerprint, ran the binary, and said "the binary analysed a tree and
    # wrote a map" — which is rule 37 exactly: a guard that checks a name appears has not
    # checked that anything happened.
    #
    # **And it is asked in Python, from Python.** The version after that one asked by
    # writing `from dunneflow.detectors import rules_fingerprint` on the line below;
    # chunk 5 split that function in two, and this step raised `ImportError` from then
    # until chunk 13 without a single test noticing — rule 51, in a here-doc. There is one
    # stamp per language now as well as the core one, so there is more to get wrong, not
    # less. `tools/fingerprints.py` is where the question lives; this step runs it.
    uv run python "$ROOT/tools/fingerprints.py" "$BIN" || die \
"the binary and this checkout cannot read each other's maps (rule 12). The sentence above
says which stamp moved and what it costs; the usual cause is something the spec bundles as
data having moved, or not being bundled at all."

    echo "-- what a reader can install from"
    # **Asked of the build, never of the repository, and that is the point of this step.**
    # The previous version validated `packaging/linux/dunneflow.desktop.in` and counted
    # `packaging/icon/hicolor/` — both of which are in the checkout and in no artifact — so
    # it passed cleanly on a tarball that could not be installed. A check that reads the
    # source when the question is about the artifact is rule 24 wearing a tick.
    local staged="$APP/share"
    [ -x "$APP/install.sh" ] || die \
        "$APP/install.sh is missing — a reader unpacking the tarball has no way in"
    [ -f "$staged/dunneflow.desktop.in" ] || die \
        "$staged/dunneflow.desktop.in is missing — the install would leave no menu entry"

    echo "-- the desktop entry"
    if command -v desktop-file-validate >/dev/null; then
        local probe; probe="$(mktemp -d)/dunneflow.desktop"
        sed "s|@EXEC@|/nonexistent/dunneflow|" "$staged/dunneflow.desktop.in" > "$probe"
        desktop-file-validate "$probe" && echo "   valid"
    else
        echo "   desktop-file-validate is not installed — the entry was not checked"
    fi

    echo "-- the icon ladder"
    local n; n="$(find "$staged/icons/hicolor" -name 'dunneflow.png' 2>/dev/null | wc -l)"
    echo "   $n sizes staged"
    [ "$n" -gt 0 ] || die "no icons staged — build them, then stage:
  uv run --with pillow python packaging/icon/build_supplied_icon.py \\
      packaging/icon/rabbit-head.png
  ./packaging/release-linux.sh stage"
}

# --- tar -------------------------------------------------------------------------------
step_tar() {
    say "wrapping it"
    [ -x "$BIN" ] || die "there is no build to wrap"
    local out; out="$(tar_path)"
    rm -f "$out"
    # From `dist/`, so the archive holds one top-level `dunneflow/` and unpacks into a
    # directory rather than over whatever the reader was standing in.
    tar -czf "$out" -C "$DIST" dunneflow
    echo "   $(du -sh "$out" | cut -f1)  $out"
    # **Its SHA-256, beside it.** This build is unsigned and says so, which leaves a reader
    # nothing to check a download against; the digest is published with the archive
    # (`SECURITY.md`). Written with the bare file name, so `sha256sum -c` works wherever
    # the two files are put together.
    ( cd "$(dirname "$out")" && sha256sum "$(basename "$out")" > "$(basename "$out").sha256" )
    echo "   $(cut -c1-64 "$out.sha256")  SHA-256"
}

# --- install ---------------------------------------------------------------------------
# **Delegated, not reimplemented.** The installer is `packaging/linux/install.sh`, which is
# also the copy that ships inside the tarball — so what a developer runs here and what a
# reader runs from the artifact are the same script doing the same thing (rule 51). This
# used to be forty lines of its own, and they were the only forty that could install
# DunneFlow at all.
step_install() {
    [ -x "$BIN" ] || die "there is no build to install"
    "$ROOT/packaging/linux/install.sh" install --app "$APP" --prefix "$PREFIX"
}

# --- uninstall -------------------------------------------------------------------------
# **Asked of the installed copy first**, because uninstalling must not require the build
# that produced it: `dist/` is a scratch directory and the tarball gets deleted, while
# `~/.local/lib/dunneflow/install.sh` is there for as long as there is anything to remove.
# The checkout's copy is the fallback, and removing nothing is not an error — it is the
# answer when there was nothing installed.
step_uninstall() {
    local installer="$LIBDIR/install.sh"
    [ -x "$installer" ] || installer="$ROOT/packaging/linux/install.sh"
    "$installer" uninstall --prefix "$PREFIX"
}

case "${1:-all}" in
    build)      step_build ;;
    stage)      step_stage ;;
    verify)     step_verify ;;
    tar)        step_tar ;;
    install)    step_install ;;
    uninstall)  step_uninstall ;;
    all)        step_build; step_verify; step_tar; step_install ;;
    *)          die "unknown step '${1}'. One of: build stage verify tar install uninstall all" ;;
esac
