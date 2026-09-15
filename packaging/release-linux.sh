#!/usr/bin/env bash
#
# How a DunneFlow build is made on Linux: frozen, checked, wrapped, and put where the
# application menu can find it.
#
#     ./packaging/release-linux.sh all
#
# One verb per step, so any of them can be run alone while something is being worked out:
#
#     build      freeze dist/dunneflow/ for this machine's architecture
#     verify     say what another machine of this kind will make of it
#     tar        dist/DunneFlow-<version>-linux-<arch>.tar.gz
#     install    into ~/.local — binary, desktop entry, icon theme
#     uninstall  take all three back out again
#     all        build, verify, tar, install
#
# **Six verbs against release.sh's eight, and the differences are stated rather than
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
# (`release.sh` reads macOS's `CFBundleShortVersionString` instead, which is a literal in the
# spec's `info_plist`. That is a second answer to the same question and is left alone here:
# it is the version Apple is shown, and changing where it comes from is a macOS decision.)
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
    echo
    echo "   $(du -sh "$APP" | cut -f1)  $APP"
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

    echo "-- the map this build writes, against the checkout's"
    # **The one check here that is not a size** (rule 12). The fingerprint puts the reader
    # in the cache key, so the binary and the checkout agree on one only if
    # `resource_root()` laid the bundle out the way the spec promises. Disagree, and the
    # two builds silently refuse each other's maps — which is the opposite of what that
    # rule is for, and is invisible until somebody hands a colleague a map.
    #
    # **It is compared, not printed.** The first version of this step printed the
    # checkout's fingerprint, ran the binary, and said "the binary analysed a tree and
    # wrote a map" — which is rule 37 exactly: a guard that checks a name appears has not
    # checked that anything happened. The two numbers were never put beside each other,
    # so it would have passed on a build whose maps the checkout cannot open.
    #
    # The binary's own `query` reads the stamp back, so the whole right-hand side of the
    # comparison comes from the artifact rather than from anything in this tree.
    local work mine stamped
    work="$(mktemp -d)"
    mine="$(uv run python -c 'from dunneflow.detectors import rules_fingerprint
print(rules_fingerprint())')"
    "$BIN" analyze "$ROOT/src/dunneflow/web" --name _fpcheck --no-docs --no-render \
        --output "$work" --quiet >/dev/null \
        || die "the binary could not analyse anything"
    stamped="$("$BIN" query "$ROOT" --name _fpcheck --output "$work" \
                --sql "SELECT value FROM meta WHERE key = 'extractor'" | tail -1 | tr -d ' \r')"
    rm -rf "$work"
    echo "   checkout: $mine"
    echo "   binary:   $stamped"
    # The binary stamps `<schema>:<fingerprint>`; the checkout function answers the second
    # half alone. Matched on the suffix so the schema version stays visible in the line
    # above rather than being stripped out of the evidence (rule 13).
    [ "${stamped#*:}" = "$mine" ] || die \
"the binary and this checkout disagree about the extractor fingerprint.
They cannot read each other's maps (rule 12). The usual cause is the bundle layout: the
spec must place this package's data under `dunneflow/`, because `fingerprint_files` labels
every input relative to `runtime.resource_root()`."
    echo "   they agree — each build can open the other's maps"

    echo "-- the desktop entry"
    if command -v desktop-file-validate >/dev/null; then
        local probe; probe="$(mktemp -d)/dunneflow.desktop"
        sed "s|@EXEC@|/nonexistent/dunneflow|" \
            "$ROOT/packaging/linux/dunneflow.desktop.in" > "$probe"
        desktop-file-validate "$probe" && echo "   valid"
    else
        echo "   desktop-file-validate is not installed — the entry was not checked"
    fi

    echo "-- the icon ladder"
    local n; n="$(find "$ROOT/packaging/icon/hicolor" -name 'dunneflow.png' | wc -l)"
    echo "   $n sizes committed"
    [ "$n" -gt 0 ] || die "no icons — build them first:
  uv run --with pillow python packaging/icon/build_supplied_icon.py \\
      packaging/icon/rabbit-head.png"
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
}

# --- install ---------------------------------------------------------------------------
step_install() {
    say "installing into $PREFIX"
    [ -x "$BIN" ] || die "there is no build to install"

    # Replaced whole rather than copied over: a PyInstaller tree from an older build leaves
    # files the new one does not overwrite, and a stale `.so` beside a new binary is a
    # failure nobody can read.
    rm -rf "$LIBDIR"
    mkdir -p "$LIBDIR" "$(dirname "$BINLINK")" "$(dirname "$DESKTOP")"
    cp -a "$APP/." "$LIBDIR/"
    ln -sfn "$LIBDIR/dunneflow" "$BINLINK"
    echo "   $LIBDIR"
    echo "   $BINLINK -> $LIBDIR/dunneflow"

    # The entry, with the one line a committed file cannot hold.
    sed "s|@EXEC@|$LIBDIR/dunneflow|" "$ROOT/packaging/linux/dunneflow.desktop.in" \
        > "$DESKTOP"
    echo "   $DESKTOP"

    # The icon theme, copied in the layout it is already committed in, so this step has no
    # opinion about where an icon goes (rule 51 — `build_supplied_icon.py` decided that).
    local src="$ROOT/packaging/icon/hicolor" n=0
    [ -d "$src" ] || die "no icons — build them first:
  uv run --with pillow python packaging/icon/build_supplied_icon.py \\
      packaging/icon/rabbit-head.png"
    while IFS= read -r png; do
        local rel="${png#"$src"/}"
        mkdir -p "$ICONS/$(dirname "$rel")"
        cp "$png" "$ICONS/$rel"
        n=$((n + 1))
    done < <(find "$src" -name 'dunneflow.png')
    echo "   $n icons into $ICONS"

    # **Both caches, and neither failure is fatal.** A desktop that reads the directories
    # directly needs neither; one that caches needs the matching one, and which is which is
    # not knowable from here. A menu entry that appears at the next login rather than at
    # once is a slow install, not a broken one, so this reports and carries on.
    command -v update-desktop-database >/dev/null \
        && update-desktop-database "$(dirname "$DESKTOP")" 2>/dev/null \
        && echo "   desktop database updated" || true
    command -v gtk-update-icon-cache >/dev/null \
        && gtk-update-icon-cache -f -t "$ICONS" 2>/dev/null \
        && echo "   icon cache updated" || true

    echo
    case ":$PATH:" in
        *":$(dirname "$BINLINK"):"*) echo "   \`dunneflow\` is on your PATH" ;;
        # Rule 89: the refusal names the thing that acts on it. On Mint this directory is
        # added by ~/.profile only when it exists at login, so a first install is exactly
        # the case that needs saying.
        *) echo "   note: $(dirname "$BINLINK") is not on your PATH — the menu entry works"
           echo "   regardless; for the command, add it or log out and back in." ;;
    esac
}

# --- uninstall -------------------------------------------------------------------------
step_uninstall() {
    say "removing DunneFlow from $PREFIX"
    # **The maps are never touched, and that is the point of listing what goes.** They are
    # the reader's work and they outlive any build — `~/.local/share/DunneFlow`, or wherever
    # they moved it to. An uninstall that took them would be the one unrecoverable thing
    # this script could do.
    rm -rf "$LIBDIR"        && echo "   removed $LIBDIR"
    rm -f  "$BINLINK"       && echo "   removed $BINLINK"
    rm -f  "$DESKTOP"       && echo "   removed $DESKTOP"
    local n=0
    while IFS= read -r png; do rm -f "$png"; n=$((n + 1)); done \
        < <(find "$ICONS" -name 'dunneflow.png' 2>/dev/null)
    echo "   removed $n icons"
    command -v update-desktop-database >/dev/null \
        && update-desktop-database "$(dirname "$DESKTOP")" 2>/dev/null || true
    command -v gtk-update-icon-cache >/dev/null \
        && gtk-update-icon-cache -f -t "$ICONS" 2>/dev/null || true
    echo
    echo "   your maps were not touched — they are wherever DunneFlow was reading them,"
    echo "   by default \${XDG_DATA_HOME:-~/.local/share}/DunneFlow"
}

case "${1:-all}" in
    build)      step_build ;;
    verify)     step_verify ;;
    tar)        step_tar ;;
    install)    step_install ;;
    uninstall)  step_uninstall ;;
    all)        step_build; step_verify; step_tar; step_install ;;
    *)          die "unknown step '${1}'. One of: build verify tar install uninstall all" ;;
esac
