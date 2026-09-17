#!/usr/bin/env bash
#
# Put DunneFlow into a Linux application menu, or take it back out again.
#
#     ./install.sh              install into ~/.local
#     ./install.sh uninstall    remove everything the install put there
#
# **This is the one installer, and it runs from two places.** A reader who downloaded
# `DunneFlow-<version>-linux-<arch>.tar.gz` runs the copy inside it; a reader with a
# checkout gets here through `release-linux.sh install`. Those were two different answers
# until 2026-09-15 and only one of them existed: `release-linux.sh` read the desktop entry
# from `packaging/linux/` and the icons from `packaging/icon/hicolor/`, **neither of which
# is in the tarball**, so the documented install command could not run from the artifact it
# was documented beside. Rule 51, with the second call site missing rather than wrong.
#
# What fixed it is not this file — it is that `release-linux.sh build` now *stages* the
# entry and the icons into the build output, so the checkout and the tarball hold the same
# tree and one script can read from `$APP/share` in both. This file only ever looks inside
# the application directory it was given.
#
# **Nothing here needs root.** Everything goes under `~/.local`, which every
# freedesktop-conforming desktop searches: no `sudo`, nothing outside this reader's own
# home, and nothing a second account on the same machine can see.

set -euo pipefail

VERB="install"
APP=""
PREFIX="${DUNNEFLOW_PREFIX:-$HOME/.local}"

while [ $# -gt 0 ]; do
    case "$1" in
        install|uninstall) VERB="$1"; shift ;;
        --app)    APP="${2:?--app needs a directory}"; shift 2 ;;
        --prefix) PREFIX="${2:?--prefix needs a directory}"; shift 2 ;;
        # Lines 2-7 are the usage block; line 8 opens the design note, which is for
        # somebody reading the file and not for somebody who typed --help.
        -h|--help) sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) printf 'unknown argument %s — one of: install, uninstall, --app, --prefix\n' \
                  "$1" >&2; exit 2 ;;
    esac
done

# **The default is this script's own directory, which is what makes the tarball work.**
# Unpacked, `install.sh` sits beside the executable and `share/`, so running it with no
# arguments at all is the whole install. `release-linux.sh` passes `--app` instead, because
# from a checkout this file is in `packaging/linux/` and the build is in `dist/`.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="${APP:-$HERE}"

LIBDIR="$PREFIX/lib/dunneflow"
BINLINK="$PREFIX/bin/dunneflow"
DESKTOP="$PREFIX/share/applications/dunneflow.desktop"
ICONS="$PREFIX/share/icons/hicolor"

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m!! %s\033[0m\n' "$*" >&2; exit 1; }

# Both caches, and neither failure is fatal. A desktop that reads the directories directly
# needs neither; one that caches needs the matching one, and which is which is not knowable
# from here. A menu entry that appears at the next login rather than at once is a slow
# install, not a broken one, so this reports and carries on.
refresh_caches() {
    command -v update-desktop-database >/dev/null \
        && update-desktop-database "$(dirname "$DESKTOP")" 2>/dev/null \
        && echo "   desktop database updated" || true
    command -v gtk-update-icon-cache >/dev/null \
        && gtk-update-icon-cache -f -t "$ICONS" 2>/dev/null \
        && echo "   icon cache updated" || true
}

do_install() {
    say "installing into $PREFIX"
    [ -x "$APP/dunneflow" ] || die \
"there is no DunneFlow executable at $APP/dunneflow.
Run this from inside the unpacked tarball, or pass --app <the built directory>."

    # **Refused rather than half-done** (rule 49). Without these the install still produces
    # a working binary and no menu entry, which looks like a desktop problem and is not.
    [ -f "$APP/share/dunneflow.desktop.in" ] || die \
"$APP/share/dunneflow.desktop.in is missing, so there is no menu entry to write.
A build stages it there; if you are running this from a checkout, build first:
  ./packaging/release-linux.sh build"
    [ -d "$APP/share/icons/hicolor" ] || die \
"$APP/share/icons/hicolor is missing, so the menu entry would draw a generic square.
A build stages it there; if you are running this from a checkout, build first:
  ./packaging/release-linux.sh build"

    # Replaced whole rather than copied over: a PyInstaller tree from an older build leaves
    # files the new one does not overwrite, and a stale `.so` beside a new binary is a
    # failure nobody can read.
    rm -rf "$LIBDIR"
    mkdir -p "$LIBDIR" "$(dirname "$BINLINK")" "$(dirname "$DESKTOP")"
    cp -a "$APP/." "$LIBDIR/"
    ln -sfn "$LIBDIR/dunneflow" "$BINLINK"
    echo "   $LIBDIR"
    echo "   $BINLINK -> $LIBDIR/dunneflow"

    # The entry, with the one line a committed file cannot hold. Pointed at `$LIBDIR` and
    # never at `$APP`: the tarball a reader unpacked in ~/Downloads is not where the
    # application is going to live, and an entry naming it would break the first time they
    # tidied up.
    sed "s|@EXEC@|$LIBDIR/dunneflow|" "$APP/share/dunneflow.desktop.in" > "$DESKTOP"
    echo "   $DESKTOP"

    # The icon theme, copied in the layout it is already staged in, so this step has no
    # opinion about where an icon goes (rule 51 — `build_supplied_icon.py` decided that).
    local src="$APP/share/icons/hicolor" n=0 rel
    while IFS= read -r png; do
        rel="${png#"$src"/}"
        mkdir -p "$ICONS/$(dirname "$rel")"
        cp "$png" "$ICONS/$rel"
        n=$((n + 1))
    done < <(find "$src" -name 'dunneflow.png')
    [ "$n" -gt 0 ] || die "no icons found under $src"
    echo "   $n icons into $ICONS"

    refresh_caches

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

do_uninstall() {
    say "removing DunneFlow from $PREFIX"
    # **This usually deletes the script that is running**, because the installed copy lives
    # in `$LIBDIR` and that is the copy `release-linux.sh uninstall` prefers. It is safe and
    # not luck: `rm` unlinks a name, and POSIX keeps the inode alive while any process holds
    # the file open — bash holds the script's own descriptor until it exits. Pressed, with
    # the tarball deleted first, so the installed copy was the only one left.
    # **The maps are never touched, and that is the point of listing what goes.** They are
    # the reader's work and they outlive any build — `~/.local/share/DunneFlow`, or wherever
    # they moved it to. An uninstall that took them would be the one unrecoverable thing
    # this script could do.
    rm -rf "$LIBDIR"  && echo "   removed $LIBDIR"
    rm -f  "$BINLINK" && echo "   removed $BINLINK"
    rm -f  "$DESKTOP" && echo "   removed $DESKTOP"
    local n=0
    while IFS= read -r png; do rm -f "$png"; n=$((n + 1)); done \
        < <(find "$ICONS" -name 'dunneflow.png' 2>/dev/null)
    echo "   removed $n icons"
    refresh_caches
    echo
    echo "   your maps were not touched — they are wherever DunneFlow was reading them,"
    echo "   by default \${XDG_DATA_HOME:-~/.local/share}/DunneFlow"
}

case "$VERB" in
    install)   do_install ;;
    uninstall) do_uninstall ;;
esac
