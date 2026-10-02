#!/usr/bin/env bash
#
# How a DunneFlow release is made: built for both architectures, signed with a Developer ID,
# notarised by Apple, stapled, wrapped in a disk image, and installed.
#
#     ./packaging/release.sh all
#
# One verb per step, so any of them can be run alone while something is being worked out:
#
#     venv      make (or refresh) the universal2 build environment
#     build     freeze DunneFlow.app for arm64 *and* x86_64
#     sign      Developer ID, hardened runtime, secure timestamp
#     notarize  submit the .app to Apple, wait for the answer, staple it
#     dmg       build, sign, notarise and staple the disk image
#     verify    say whether the result is a thing another Mac will open — and whether
#               its maps are ones this checkout can read (rule 12)
#     install   put the stapled .app in /Applications
#     all       every one of the above, in that order
#
# **Two things have to exist before this works, and neither is a command this script can run
# on your behalf.** Both are once-only:
#
#   1. A universal2 interpreter, which uv's Pythons and Homebrew's are not:
#
#        curl -LO https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg
#        sudo installer -pkg python-3.12.10-macos11.pkg -target /
#
#   2. Notarisation credentials in your keychain, from an App Store Connect API key:
#
#        xcrun notarytool store-credentials dunneflow \
#            --key ~/.appstoreconnect/AuthKey_XXXXXXXXXX.p8 \
#            --key-id XXXXXXXXXX --issuer <issuer-uuid>
#
# After that the key, its id and the issuer id are the keychain's business. The only thing
# this file knows is the profile name.
#
# **Nothing here uses `codesign --deep`.** Apple deprecates it, and it signs everything nested
# with the *outer* bundle's entitlements, which is the opposite of what an entitlements file
# that says "nothing is asked for" is trying to guarantee. Every Mach-O file is found and
# signed on its own, innermost first, and the bundle last.

set -euo pipefail

# --- what this makes, and who signs it -------------------------------------------------------
# APP_NAME is `BUNDLE(name=…)` in packaging/dunneflow.spec, and tests/test_frozen.py asserts
# the two spellings agree -- two places that can drift is one place too many.
APP_NAME="DunneFlow.app"
VOLUME_NAME="DunneFlow"
IDENTITY="${DUNNEFLOW_IDENTITY:-Developer ID Application: Thomas Williams (G3RLJWV327)}"
PROFILE="${DUNNEFLOW_NOTARY_PROFILE:-dunneflow}"
FRAMEWORK_PYTHON="${DUNNEFLOW_UNIVERSAL_PYTHON:-/Library/Frameworks/Python.framework/Versions/3.12/bin/python3}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist"
APP="$DIST/$APP_NAME"
# **The executable inside the bundle, spelled once.** It is `EXE(name=…)` in the spec and it
# is lowercase: the bundle supplies the name a reader sees, so the binary does not have to.
# `require_universal` reconstructed it as `${APP_NAME%.app}` — `DunneFlow` — and got away
# with it because APFS is case-insensitive *by default*. Formatted case-sensitive, which is
# an option at the volume and the default on some CI images, every step after `build` would
# have refused a perfectly good bundle with "there is no executable — run '$0 build' first"
# (rule 49, and the spec's own NTFS note one platform over). `tests/test_frozen.py` pins
# this against `EXE(name=…)`.
BIN="$APP/Contents/MacOS/dunneflow"
BUILD_VENV="$ROOT/.venv-universal"

cd "$ROOT"

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
die()  { printf '\n\033[1;31m!! %s\033[0m\n' "$*" >&2; exit 1; }

# The version is read off the bundle Apple will actually be shown, never spelled a second time
# here: the spec's CFBundleShortVersionString is the one answer (rule 51).
app_version() {
    [ -d "$APP" ] || die "there is no $APP_NAME yet — run '$0 build' first"
    /usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Contents/Info.plist"
}

dmg_path() { echo "$DIST/DunneFlow-$(app_version).dmg"; }

# Every Mach-O file inside the bundle *except its main executable*, deepest first. Found rather
# than listed: a dependency added tomorrow brings its own dylibs, and a hand-written list would
# leave them ad-hoc signed inside a bundle whose outer signature says otherwise. The main
# executable is left out because signing the bundle signs it -- doing it twice is not wrong,
# only a second answer to a question that already has one.
mach_o_files() {
    find "$APP/Contents" \
            -type f -perm +111 -o -type f -name '*.so' -o -type f -name '*.dylib' \
        | grep -v "^$APP/Contents/MacOS/" \
        | sort -u | while read -r f; do
            if file -b "$f" | grep -q 'Mach-O'; then echo "$f"; fi
        done | awk '{ print length($0), $0 }' | sort -rn | cut -d' ' -f2-
}

# --- venv ------------------------------------------------------------------------------------
step_venv() {
    say "universal2 build environment"
    [ -x "$FRAMEWORK_PYTHON" ] || die \
"no universal2 interpreter at $FRAMEWORK_PYTHON.

A universal build needs one, and uv's managed Pythons and Homebrew's are single-arch by
construction. Install python.org's:

    curl -LO https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg
    sudo installer -pkg python-3.12.10-macos11.pkg -target /

It installs beside everything else and disturbs nothing: this script is the only thing that
ever calls it."

    local archs
    archs="$("$FRAMEWORK_PYTHON" -c 'import sys; print(sys._base_executable or sys.executable)')"
    lipo -archs "$archs" | grep -q x86_64 && lipo -archs "$archs" | grep -q arm64 || die \
        "$FRAMEWORK_PYTHON is $(lipo -archs "$archs"), not universal2"

    if [ ! -d "$BUILD_VENV" ]; then
        "$FRAMEWORK_PYTHON" -m venv "$BUILD_VENV"
    fi
    # `-e .` rather than a copy, so the build always freezes the working tree; the dist-info it
    # leaves behind is what `copy_metadata('dunneflow')` in the spec picks up, which is how the
    # binary can still say which DunneFlow read a map.
    "$BUILD_VENV/bin/pip" install --quiet --upgrade pip
    "$BUILD_VENV/bin/pip" install --quiet -e . "pyinstaller>=6.22.2"
    echo "ready: $("$BUILD_VENV/bin/python" -V) at $BUILD_VENV"
}

# --- build -----------------------------------------------------------------------------------
step_build() {
    say "freezing for arm64 and x86_64"
    [ -x "$BUILD_VENV/bin/pyinstaller" ] || die "no build environment — run '$0 venv' first"
    DUNNEFLOW_ARCH=universal2 "$BUILD_VENV/bin/pyinstaller" \
        "$ROOT/packaging/dunneflow.spec" --noconfirm --distpath "$DIST" \
        --workpath "$ROOT/build"
    echo
    echo "$(du -sh "$APP" | cut -f1)  $APP"
    lipo -archs "$BIN"
}

# **Nothing single-arch may be signed, notarised, imaged or installed.**
#
# A default is a habit and a guard is a guarantee, and this is the failure a habit cannot
# catch: an arm64 bundle builds, signs, notarises, installs and runs perfectly on the
# machine that made it. The whole of the failure lands on somebody else's Intel Mac, weeks
# later, as "the application cannot be opened" -- with nothing here to look at. That is
# rule 49's shape at the scale of a release, so the check is on the artifact rather than on
# which command someone remembered to run.
#
# Asked of the executable, which is what `lipo` can answer for; `step_verify` walks every
# Mach-O in the bundle and is the fuller version of this question.
require_universal() {
    local archs
    [ -f "$BIN" ] || die "there is no executable in $APP_NAME — run '$0 build' first"
    archs="$(lipo -archs "$BIN" 2>/dev/null)"
    case " $archs " in
        *" arm64 "*) case " $archs " in *" x86_64 "*) return 0 ;; esac ;;
    esac
    die "$APP_NAME is $archs, not universal — this must not be $1.
Run '$0 build', which builds for arm64 and x86_64. A DUNNEFLOW_ARCH=host build is for the
verification gate and for nothing that leaves this machine."
}

# **The default identity is the maintainer's, and on anybody else's Mac it is not there.** A
# contributor building their own release has a certificate of their own, and the script
# cannot guess its name -- so it says which variable carries it and how to read that name off
# the keychain, rather than failing inside `codesign` with an error about a string they did
# not choose. Asked by both steps that sign, and before either does any work: `dmg` used to
# build the whole image first and only then reach `codesign`.
require_identity() {
    local have
    have="$(security find-identity -v -p codesigning 2>/dev/null)"
    printf '%s\n' "$have" | grep -qF "\"$IDENTITY\"" && return 0
    local yours
    yours="$(printf '%s\n' "$have" | sed -n 's/.*"\(Developer ID Application: [^"]*\)".*/      \1/p')"
    local whose="That is the default, and it is the maintainer's certificate."
    [ -n "${DUNNEFLOW_IDENTITY:-}" ] && whose="That is what DUNNEFLOW_IDENTITY names."
    die "no codesigning identity named
      $IDENTITY
is in this keychain. $whose
To sign with your own, set DUNNEFLOW_IDENTITY to its name:
      DUNNEFLOW_IDENTITY='Developer ID Application: Your Name (TEAMID)' $0 ${1:-sign}
${yours:+The Developer ID identities this keychain does hold:
$yours
}A Mac App Store or Apple Development certificate will not do: Gatekeeper accepts only a
Developer ID outside the store. Notarising also needs your own notary profile, named by
DUNNEFLOW_NOTARY_PROFILE (see this file's header). '$0 build' needs neither."
}

# --- sign ------------------------------------------------------------------------------------
step_sign() {
    say "signing as ${IDENTITY}"
    [ -d "$APP" ] || die "there is no $APP_NAME to sign — run '$0 build' first"
    require_universal "signed"
    require_identity sign

    # PyInstaller ad-hoc signs what it builds; --force is what replaces that.
    local f
    while read -r f; do
        [ -n "$f" ] || continue
        codesign --force --timestamp --options runtime \
                 --entitlements "$ROOT/packaging/entitlements.plist" \
                 --sign "$IDENTITY" "$f"
        echo "  signed  ${f#"$APP/"}"
    done < <(mach_o_files)

    codesign --force --timestamp --options runtime \
             --entitlements "$ROOT/packaging/entitlements.plist" \
             --sign "$IDENTITY" "$APP"
    echo "  signed  $APP_NAME"
    codesign --verify --deep --strict --verbose=2 "$APP"
}

# --- notarize --------------------------------------------------------------------------------
step_notarize() {
    say "notarising $APP_NAME"
    [ -d "$APP" ] || die "there is no $APP_NAME to notarise"
    require_universal "notarised"
    local zip="$DIST/${APP_NAME%.app}-notarize.zip"
    # ditto, not zip(1): a .app is a directory of symlinks and extended attributes, and zip(1)
    # flattens both. What Apple receives has to be what was signed.
    ditto -c -k --keepParent "$APP" "$zip"
    xcrun notarytool submit "$zip" --keychain-profile "$PROFILE" --wait
    rm -f "$zip"
    xcrun stapler staple "$APP"
    xcrun stapler validate "$APP"
}

# --- dmg -------------------------------------------------------------------------------------
step_dmg() {
    local dmg stage
    dmg="$(dmg_path)"
    say "disk image $(basename "$dmg")"
    require_universal "put in a disk image"
    require_identity dmg
    xcrun stapler validate "$APP" >/dev/null 2>&1 || die \
        "the .app is not stapled — run '$0 notarize' before building the image.
A disk image built around an un-notarised app is a notarised wrapper on a refused program."

    stage="$(mktemp -d)"
    ditto "$APP" "$stage/$APP_NAME"
    ln -s /Applications "$stage/Applications"      # so the window is a drag-and-drop
    rm -f "$dmg"
    hdiutil create -volname "$VOLUME_NAME" -srcfolder "$stage" -ov -format UDZO -quiet "$dmg"
    rm -rf "$stage"

    # The image is signed and notarised in its own right. The .app inside is already stapled,
    # so a reader who drags it out has a program that opens with no network at all; stapling
    # the image as well is what makes the *download* open without one.
    codesign --force --timestamp --sign "$IDENTITY" "$dmg"
    xcrun notarytool submit "$dmg" --keychain-profile "$PROFILE" --wait
    xcrun stapler staple "$dmg"
    xcrun stapler validate "$dmg"
    echo
    echo "$(du -sh "$dmg" | cut -f1)  $dmg"
}

# --- verify ----------------------------------------------------------------------------------
step_verify() {
    say "what another Mac will make of this"
    [ -d "$APP" ] || die "there is no $APP_NAME to verify"

    echo "-- architectures"
    lipo -archs "$BIN" | sed 's/^/   dunneflow: /'
    local f
    while read -r f; do
        [ -n "$f" ] || continue
        echo "   ${f#"$APP/Contents/"}: $(lipo -archs "$f")"
    done < <(mach_o_files)

    echo "-- signature"
    codesign --verify --deep --strict --verbose=2 "$APP"
    codesign -dv --verbose=4 "$APP" 2>&1 | grep -E 'Authority|TeamIdentifier|flags=|Timestamp' \
        | sed 's/^/   /'

    echo "-- gatekeeper"
    # This is the one that answers the question. Until the app is notarised *and* stapled it
    # says "rejected", and that is the honest answer rather than a failure of this script.
    spctl -a -vvv -t exec "$APP" || true

    echo "-- staple"
    xcrun stapler validate "$APP" || true
    local dmg; dmg="$(dmg_path)"
    [ -f "$dmg" ] && xcrun stapler validate "$dmg" || true

    echo "-- the maps this build writes, against the checkout's"
    # **The one check here that is not about the signature** (rule 12) — and until chunk 13
    # this step did not have it, although `CLAUDE.md` described it as the gate's one
    # non-ground-truth number. Linux had it and Windows had it; the platform this tool is
    # developed on, and the only one whose builds are signed and handed to anybody, had
    # never compared a stamp.
    #
    # The fingerprint puts the reader in the cache key, so the binary and the checkout
    # agree on one only if `resource_root()` laid the bundle out the way the spec promises.
    # Disagree, and the two builds silently refuse each other's maps, which is invisible
    # until somebody hands a colleague a map. There is one stamp per language as well as
    # the core one, and `tools/fingerprints.py` is the one place either is asked for —
    # a Python question written into a shell script is a call site that rots, and both of
    # the other two scripts had been raising `ImportError` since chunk 5 renamed the
    # function they named (rule 51).
    uv run python "$ROOT/tools/fingerprints.py" "$BIN" || die \
"the binary and this checkout cannot read each other's maps (rule 12). The sentence above
says which stamp moved and what it costs; the usual cause is something the spec bundles as
data having moved, or not being bundled at all."
}

# --- install ---------------------------------------------------------------------------------
step_install() {
    say "installing into /Applications"
    [ -d "$APP" ] || die "there is no $APP_NAME to install"
    require_universal "installed"
    local target="/Applications/$APP_NAME"
    if [ -e "$target" ]; then
        rm -rf "$target" 2>/dev/null || die \
            "could not replace $target — it is open, or it needs 'sudo rm -rf \"$target\"'"
    fi
    # ditto rather than cp -R: it keeps the extended attributes the signature is partly held in.
    ditto "$APP" "$target" || die "could not write $target — try again with sudo"
    echo "   $target"
    codesign --verify --strict "$target" && echo "   signature intact after the copy"
}

case "${1:-all}" in
    venv)     step_venv ;;
    build)    step_build ;;
    sign)     step_sign ;;
    notarize|notarise) step_notarize ;;
    dmg)      step_dmg ;;
    verify)   step_verify ;;
    install)  step_install ;;
    all)      step_venv; step_build; step_sign; step_notarize; step_dmg; step_verify
              step_install ;;
    *)        die "unknown step '${1}'. One of: venv build sign notarize dmg verify install all" ;;
esac
