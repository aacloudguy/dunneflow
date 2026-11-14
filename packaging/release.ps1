<#
.SYNOPSIS
  How a DunneFlow build for Windows is made: frozen, checked, and zipped to hand over.

.DESCRIPTION
  ./packaging/release.ps1 all

  One verb per step, so any of them can be run alone while something is being worked out:

      build    freeze DunneFlow.exe and dunneflow-cli.exe into dist/dunneflow
      verify   say whether the result is a thing another Windows machine will run
      zip      wrap dist/dunneflow as DunneFlow-<version>-windows-x64.zip
      install  put the build under %LOCALAPPDATA%\Programs\DunneFlow
      all      every one of the above, in that order

  **This is the sibling of `release.sh` and it is deliberately much shorter**, because
  four of that file's seven verbs answer questions macOS asks and Windows does not.

    * There is no `venv`. A Windows executable holds one architecture -- the interpreter's
      -- so there is nothing to build a second environment for, and `uv run` is enough.
      macOS needs one only because a universal2 binary needs a universal2 interpreter and
      neither uv's Pythons nor Homebrew's is one.
    * There is no `sign` and no `notarize`, and that is a **stated gap rather than an
      oversight**. An unsigned Windows binary meets SmartScreen, which shows the reader a
      warning they can click past; an unsigned macOS bundle meets Gatekeeper, which is a
      refusal they cannot. The two are not the same risk and do not need the same answer.
      Signing here would want an Authenticode certificate, which is a purchase and a
      decision, not a build step -- so `verify` says out loud that the result is unsigned
      rather than leaving somebody to find out from a dialog.
    * There is no `dmg`. A `.zip` is what Windows opens without being taught anything, and
      an installer is a second program to maintain for a tool that keeps all of its state in
      one directory it can be told about.

  **Nothing here reaches a network.** No upload, no submission, no publish. The result is a
  file on this disk and stays one until somebody moves it deliberately.
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('build', 'verify', 'zip', 'install', 'all')]
    [string]$Verb = 'all'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# --- what this makes ----------------------------------------------------------------------
# `DunneFlow` and `dunneflow-cli` are `EXE(name=…)` in packaging/dunneflow.spec, and
# tests/test_frozen.py asserts the spellings agree -- two places that can drift is one too
# many. `dunneflow` is COLLECT's name, which is the directory they land in.
$AppExe  = 'DunneFlow.exe'
$CliExe  = 'dunneflow-cli.exe'
$Collect = 'dunneflow'

$Root    = Split-Path -Parent $PSScriptRoot
$Dist    = Join-Path $Root 'dist'
$Build   = Join-Path $Dist $Collect

Set-Location $Root

function Say  { param([string]$m) Write-Host "`n== $m" -ForegroundColor White }
function Note { param([string]$m) Write-Host "   $m" -ForegroundColor DarkGray }
function Die  { param([string]$m) Write-Host "`n!! $m" -ForegroundColor Red; exit 1 }

function Get-Version {
    <# The version, from the one place that answers it -- never a literal here. #>
    $line = Select-String -Path (Join-Path $Root 'pyproject.toml') -Pattern '^version\s*=\s*"(.+)"'
    if (-not $line) { Die 'pyproject.toml states no version' }
    return $line.Matches[0].Groups[1].Value
}

function Invoke-Build {
    Say 'build — freezing for this architecture'
    # **The icon is checked here as well as in the spec**, because the spec's refusal arrives
    # after PyInstaller has printed two hundred lines and is easy to scroll past.
    $ico = Join-Path $Root 'packaging\icon\dunneflow.ico'
    if (-not (Test-Path $ico)) {
        Die ("$ico is not there. Build it first:`n" +
             '  uv run --with pillow python packaging/icon/build_supplied_icon.py packaging/icon/rabbit-head.png')
    }
    # **A running DunneFlow is asked about first, and named.** Windows will not let an open
    # file be replaced, so PyInstaller's cleanup fails on whichever DLL the running process
    # happens to hold -- and reports it as `UnauthorizedAccessException` on `libcrypto-3.dll`,
    # which names a file the reader has never heard of and no action they can take (rule 89).
    # macOS has no equivalent: a bundle can be rebuilt out from under a running copy.
    $running = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                 Where-Object { $_.Name -eq $AppExe -or $_.Name -eq $CliExe })
    if ($running.Count -gt 0) {
        $ids = ($running | ForEach-Object { "$($_.Name) ($($_.ProcessId))" }) -join ', '
        Die ("DunneFlow is running and Windows will not let an open file be replaced: $ids.`n" +
             '   Quit it from the taskbar, or: Get-Process DunneFlow,dunneflow-cli | Stop-Process')
    }

    & uv run pyinstaller (Join-Path $Root 'packaging\dunneflow.spec') --noconfirm
    if ($LASTEXITCODE -ne 0) { Die 'pyinstaller failed' }
    Note "built into $Build"
}

function Invoke-Verify {
    Say 'verify — is this a thing another machine will run?'
    foreach ($exe in @($AppExe, $CliExe)) {
        $p = Join-Path $Build $exe
        if (-not (Test-Path $p)) { Die "$exe is missing from the build" }
        Note ('{0,-20} {1,6:N1} MB' -f $exe, ((Get-Item $p).Length / 1MB))
    }

    # **The console half must actually speak.** That is the whole reason it exists: a
    # GUI-subsystem binary is given no standard streams, so `DunneFlow.exe --version` prints
    # nothing at all and the verification gate in CLAUDE.md would have nothing to read.
    $said = & (Join-Path $Build $CliExe) --help 2>&1 | Out-String
    if ($said -notmatch 'analyze') { Die "$CliExe printed nothing usable — check console=True in the spec" }
    Note "$CliExe speaks: $(($said -split "`n")[0].Trim())"

    # **Rule 12, and it is the one check that is not a size or a signature.** The binary and
    # the checkout must agree on every stamp, or the two builds have quietly stopped being
    # able to read each other's maps -- which is the opposite of what that rule is for.
    #
    # **Asked in Python, from Python, and that is the lesson rather than the style.** This
    # step used to write `from dunneflow.detectors import rules_fingerprint` into a `-c`
    # argument. Chunk 5 split that function into a core stamp and one per language, and
    # from then until chunk 13 this line raised `ImportError` — in the step written to
    # defend rule 12, on no test path, saying nothing. A Python question kept at a shell
    # call site rots as the Python moves (rule 51), and there were three scripts asking it
    # three ways.
    #
    # The tree it reads is `tests\fixtures\polyglot` and not `canonical\`: one reader per language
    # means the probe has to hold every language, and `canonical\` is Python to the last
    # file, so the TypeScript stamp went uncompared and the step passed anyway (rule 37).
    & uv run python (Join-Path $Root 'tools\fingerprints.py') (Join-Path $Build $CliExe)
    if ($LASTEXITCODE -ne 0) {
        Die ('the binary and this checkout cannot read each other''s maps (rule 12). The ' +
             'sentence above says which stamp moved and what it costs; the usual cause is ' +
             'something the spec bundles as data having moved, or not being bundled at all.')
    }

    # **Said out loud, because a dialog is a poor place to learn it.** Design rule 1, one
    # subject over: a reader who is not told will meet SmartScreen and assume the file is
    # broken rather than merely unsigned.
    $sig = Get-AuthenticodeSignature (Join-Path $Build $AppExe)
    if ($sig.Status -eq 'Valid') {
        Note "signed by $($sig.SignerCertificate.Subject)"
    } else {
        Note "UNSIGNED ($($sig.Status)) — the first reader to open this will meet SmartScreen."
        Note '   That is a warning they can click past, not a refusal. See this file''s header.'
    }
}

function Invoke-Zip {
    $version = Get-Version
    $name = "DunneFlow-$version-windows-x64.zip"
    $out = Join-Path $Dist $name
    Say "zip — $name"
    if (-not (Test-Path $Build)) { Die 'nothing to zip; run `build` first' }
    if (Test-Path $out) { Remove-Item -Force $out }
    Compress-Archive -Path $Build -DestinationPath $out -CompressionLevel Optimal
    Note ('{0}  ({1:N1} MB)' -f $out, ((Get-Item $out).Length / 1MB))
    # Its SHA-256, beside it: this build is unsigned, so the digest published with the
    # archive is what a reader checks a download against (SECURITY.md). In `sha256sum`'s
    # format, with the bare file name, so one tool checks all three platforms' files.
    $digest = (Get-FileHash -Algorithm SHA256 -Path $out).Hash.ToLower()
    $leaf = Split-Path -Leaf $out
    [System.IO.File]::WriteAllText("$out.sha256", "$digest  $leaf`n")
    Note "$digest  SHA-256"
    Note 'This is a local file. Nothing here uploads it anywhere.'
}

function Invoke-Install {
    # `%LOCALAPPDATA%\Programs` is where a per-user application goes on Windows -- no
    # elevation, and the same drive as `platform_output_root()`'s `%LOCALAPPDATA%\DunneFlow`,
    # which is where its maps land.
    $target = Join-Path $env:LOCALAPPDATA 'Programs\DunneFlow'
    Say "install — $target"
    if (-not (Test-Path $Build)) { Die 'nothing to install; run `build` first' }
    # The same open-file rule as `build`, one directory over: this one replaces the copy a
    # reader actually launches, so it is the more likely of the two to be in use.
    $running = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                 Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($target) })
    if ($running.Count -gt 0) {
        $ids = ($running | ForEach-Object { "$($_.Name) ($($_.ProcessId))" }) -join ', '
        Die "the installed DunneFlow is running and cannot be replaced: $ids. Quit it first."
    }
    if (Test-Path $target) { Remove-Item -Recurse -Force $target }
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Copy-Item -Recurse -Force (Join-Path $Build '*') $target
    Note "installed. Double-click $(Join-Path $target $AppExe), or run:"
    Note "  $(Join-Path $target $CliExe) analyze <path> --name <program>"
}

switch ($Verb) {
    'build'   { Invoke-Build }
    'verify'  { Invoke-Verify }
    'zip'     { Invoke-Zip }
    'install' { Invoke-Install }
    'all'     { Invoke-Build; Invoke-Verify; Invoke-Zip; Invoke-Install }
}

Write-Host ''
