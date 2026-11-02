# 1. Installing

There are two ways to have DunneFlow: 1. the application, or 2: a checkout. Which one you
want depends on whether you intend to change it. The application comes in a Mac build, a
Windows build and a Linux build; everything after this chapter is the same on all three.

**The application is on the [releases page](https://github.com/aacloudguy/dunneflow/releases/latest)**:
one download for each platform, and a `SHA256SUMS` file beside them if you want to check
what arrived is what was published.

## The application, on a Mac

`DunneFlow-<version>.dmg` - open it, drag **DunneFlow** to Applications, double-click it. It opens
your browser on [the start page](03-the-start-page.md) and that is the whole of the
setup. There is no Python to install, no terminal, and no configuration file.

It is a macOS application built for both Apple silicon and Intel, signed with a Developer
ID and notarised by Apple, so Gatekeeper opens it without argument on any Mac.

It asks the system for no special permissions at all. It reads the directory you point it
at, writes its maps, and opens a folder picker when you ask for one. That is everything.

## The application, on Windows

`DunneFlow-<version>-windows-x64.zip` — unzip it anywhere and double-click **DunneFlow**.
It opens your browser on the start page, exactly as the Mac build does. There is no Python
to install and nothing to configure.

There are **two programs in that folder** and the difference matters:

| | |
|---|---|
| `DunneFlow.exe` | What you double-click. It opens no console window. |
| `dunneflow-cli.exe` | The [command line](16-the-command-line.md). Use this one from PowerShell. |

They are the same program built two ways. Windows gives a double-clickable program no
console to print to, so `DunneFlow.exe` from a terminal would do the work and show you none
of it, which is why the second one exists. Reach for `dunneflow-cli.exe` any time you want
to see output.

> **It is not signed**, so the first time you run it Windows SmartScreen will say it does
> not recognise the publisher. **More info → Run anyway.** That is a warning, not a block,
> and it appears once. (The Mac build *is* signed and notarised; the three platforms are
> at different stages.)

### One thing that behaves differently

**The folder picker opens behind your browser.** Press **Choose…** — the button says
*Opening…* while the chooser starts — and then **Alt-Tab to it**, or click its icon in the
taskbar. It is there; it simply is not in front.

That is Windows rather than DunneFlow: a program running in the background is not allowed to
bring a window to the front, and DunneFlow is in the background the whole time you are
looking at a browser. The Mac build can ask the system to come forward and does.

Typing the path by hand always works and is never the slower route if you already know it.

## The application, on Linux

`DunneFlow-<version>-linux-<arch>.tar.gz` - unpack it and install it:

```bash
tar -xzf DunneFlow-<version>-linux-<arch>.tar.gz
./dunneflow/install.sh
```

That puts the program in `~/.local/lib/dunneflow`, the name a terminal types in
`~/.local/bin`, and a menu entry and icons in the two places a desktop looks for them.
DunneFlow then appears in your applications menu; launching it opens your browser on the
start page, exactly as the other two builds do. There is no Python to install and nothing
to configure.

**Nothing needs root** and nothing lands outside your own home directory. If you would
rather put it somewhere else, `./dunneflow/install.sh --prefix /some/where` does that.

You can also skip installing entirely and just run `./dunneflow/dunneflow` from wherever you
unpacked it. That works — you simply do not get a menu entry, and the archive unpacks into
its own `dunneflow/` directory rather than over whatever you were standing in.

There is **one program here, not two**. The Windows build needs a second executable to
print to a terminal; a Linux one does not, so `dunneflow` is both the thing your menu
launches and the [command line](16-the-command-line.md).

> **It is not signed**, and on Linux that is the ordinary state of things rather than
> something to click past. There is no Gatekeeper and no SmartScreen, and nothing on the
> machine will refuse to run it. There is no warning to dismiss.

To take that back out again, removing the binary, the entry and all ten icons, which is not
something you could undo by looking at it:

```bash
~/.local/lib/dunneflow/install.sh uninstall
```

**The installed copy carries its own uninstaller**, so that still works long after you have
deleted the tarball you installed from.

**Your maps are never touched by the uninstaller.** They are your work, and they outlive any build. It
removes only what the install put there, and it says what it removed.

### One thing that behaves differently

**The folder picker needs a dialog program installed.** A Mac and a Windows machine each
ship exactly one thing that can ask you for a folder. A Linux desktop ships whichever its
toolkit brought, so DunneFlow looks for **zenity** or **kdialog** and uses whichever it
finds, preferring the one that matches your desktop.

If neither is installed the installer names them both, and typing the path by hand still
works. The field is the control and the picker is a convenience over it. If you are
reaching DunneFlow over SSH with no display, it says that instead, because there is no
screen to put a window on.

Unlike the Windows chooser, this one **comes to the front on its own**.

## Which languages it reads, and the one thing you may have to install

DunneFlow reads **Python**; **TypeScript** — `.ts`, `.tsx`, `.mts`, `.cts`, JSX and TSX
included; **C++** — `.cpp`, `.cc`, `.cxx`, `.hpp`, `.h`, `.inl` and their siblings;
**Kotlin** — `.kt` and `.kts`; **Go** — `.go`; **Rust** — `.rs`; and **Java** — `.java`.

**Four of the seven need something installed.** Python, C++ and Kotlin DunneFlow reads
itself.
TypeScript it reads by asking TypeScript's own compiler, which needs **Node.js 20 or newer**
on the machine; Go by asking Go's own type checker, which needs **Go 1.22 or newer**; and
Rust with a reader built by **Rust 1.79 or newer** (`cargo`, as `rustup` installs it); and
Java by asking javac, which needs a **JDK 17 or newer** — a JDK, with its compiler, and not
only a Java runtime. The Go, Rust and Java readers are built on your machine the first time
each is needed — about a second for Go, ten for Rust and a few for Java — and no build is
repeated or downloads anything. A package your program imports from outside the tree being
read is counted as outside it, not fetched; for Rust, a dependency already in your local
cargo cache is *read*, and for Java a jar already in your local Maven or Gradle cache is, so
the map can say what each outside call reaches, and one that is not there is said to be
missing.

That asymmetry is deliberate rather than untidy. A language is best read by the thing that
already understands it, and the alternative — bundling a parser for every language — is
what makes a tool either enormous or wrong. So the compiler that reads your TypeScript is
the compiler TypeScript ships, the checker that reads your Go is the one Go ships, and a
name either of them resolves is a name *it* resolved and not one DunneFlow guessed at.

**One thing to expect in a Go map in particular.** A function written once per platform —
`run_linux.go` and `run_windows.go` — is drawn to its **Linux** definition, so that a call
through it is connected and the map is the same on every machine that reads it. The other
platforms' versions are still in the map; they are drawn as uncalled.

**And in a Rust map.** The same holds for a function written once per `#[cfg(target_os)]`:
it is drawn to its Linux definition. Rust's edges come from the paths the source writes
rather than from a compiler, so a call is connected only where its path, or a type written
down in the source, names one definition; every call that is not says where it stopped and
why, in the inspector and in `touches`. Test code is left out as it is for every language —
`#[test]` functions, `#[cfg(test)]` blocks, and whole files that a `#[cfg(test)] mod`
declaration names — and the summary counts each kind.

**C++ and Kotlin are read without a compiler, and it is worth knowing why before you read
one of those maps.** For C++ the reason is that a compiler needs to know how your program is
built — every include path and every defined symbol — before it will read a single file, and
most large C++ trees cannot supply that without being built first. For Kotlin the compiler
*could* be asked, and asking it would mean a Java runtime on every machine that reads a `.kt`
file. Neither is read by guessing instead; both are read by *reading*, and what you get is
honest about the difference:

| It tells you | It does not tell you |
|---|---|
| every routine, and where its body is | which of three overloads a call meant |
| what it touches — files, the environment, the network, a database | where a call goes inside your own program |
| every loop, branch, guard and handler | what a C++ macro expands to |
| what registers it — a `UFUNCTION` with Blueprint, an `@AndroidEntryPoint` with Android | anything from a file it did not itself read |

Calls in a C++ or Kotlin map are all **external**, and the run says so with a count rather
than leaving you to notice. That is the tool being clear about what it did, not a setting to
change.

**One thing to expect in a Kotlin map in particular.** Kotlin's house style is
`items.forEach { … }` rather than a `for` loop, and a collection operator is a *call* — so a
per-element rate hidden inside one is not drawn as a loop, where the same rate written as a
`for` is. The map is not wrong about it; it simply does not see it, and that is worth knowing
before you read the Algorithms page of a Kotlin program.

If Node or Go is not there, DunneFlow reads everything else and says, at the end of the run
and in the map, what it could not read and why:

```
  read: python 132
  not read, no toolchain: 11 files of typescript — typescript needs `node` ≥ 20.0.0 and
  nothing answers `node --version` on this machine. Install it (brew install node, or
  nodejs.org), or run again with `--without typescript` and the map will say those files
  were declined.
```

Both halves of that are real. Install Node and the whole tree is read; or decline the
language yourself and get the same map of everything else, with the count of what you left
out recorded as your choice rather than the machine's:

```
files 131 (parsed 131, cached 0, removed 0, failed 0) in 1.0s
  read: python 131
  declined by you: 11 typescript — this build has a reader for that language;
  drop --without to read them
```

**A declined language is never a silent one.** *You declined TypeScript* and *nothing here
reads TypeScript* are two different facts with opposite remedies, so they are two different
sentences. And a map analysed without a language says so in **About this map**, on the
row headed *It was told* — because a map read `--without typescript` and a map of a
program actually written in one language hold exactly the same rows, and only one of them
is the second thing.

![About this map for DunneFlow read with both languages: Program dunneflow 2026-10-02T21:37:19Z, Read by 0.2.0 · extractor 16:9befb90ff994e280, 142 files · 1,552 routines · 53 documents, Read from Python 131 · TypeScript 11, and under Left out of it the unread suffixes (8 .js, 6 .json, 6 .yaml, 2 .html, 1 .cjs, 1 .css, 1 .mjs), the strings not judged (3,475 python, 112 typescript), 262 typescript calls resolved outside this map, 200 whose far end could not be named, and "pruned 1 directory: vendor". Inferred facts: none; Read by a model: none.](images/01-about-this-map.png)

That one was read with both languages, so it has no *It was told* row: **Read from** names
what was read and how much of it, and **Left out of it** names everything that was not —
suffixes no reader claims, strings outside the bound a reader judges, calls whose far end is
outside the map, and directories pruned on the way in.

**Everything else needs nothing.** If the tree you point it at has no TypeScript in it,
Node is never looked for.

## Where maps are kept

A map is not small. One snapshot of a 628-file program is about 160 MB, and each further
version of the same program adds about 130 MB. Maps include a graph and a document store per snapshot,
which are the two that are not shared.

The copies DunneFlow keeps of what it read are the cheap part, and they are the reason it
can still show you the code after the tree has moved on: for that same program they are
4 MB of source and 20 MB of prose, held once by content and shared by every snapshot,
however many you capture.

Where they go depends on which of the three you are running:

| | Maps go to |
|---|---|
| The application, on a Mac | `~/Library/Application Support/DunneFlow` |
| The application, on Windows | `%LOCALAPPDATA%\DunneFlow` |
| The application, on Linux | `~/.local/share/DunneFlow`, or `$XDG_DATA_HOME/DunneFlow` if you set one |
| A checkout | `output/`, beside the source you cloned |

Each of those is the correct place for an application's own data on its platform, and none
of them is `~/Documents` or `Documents`: a map holds the source of whatever you read it
from, and Documents is swept into iCloud Drive or OneDrive on a signed-in machine.
DunneFlow is a local tool and nothing it holds should leave the machine by accident.

The cost of that correctness is that the folder is hard to find, so the start page prints
the path, and **Show me** opens it, whether in the Finder, in File Explorer, or in whichever file
manager your Linux desktop uses.

## Moving them somewhere else

Maps are kept on your startup disk by default, on all three platforms. If they are filling
it, **Move…** on the start page points DunneFlow at a different directory, whether in an external
disk or other bigger volume, and offers to carry the maps you already have across.

Four things about it:

- **The directory has to exist already**, and be on a disk that is connected. DunneFlow
  will not create it. A path on a disk that is not mounted would quietly be created on
  your startup disk instead, which is the opposite of what you asked for.
- **On Windows, the chooser here opens behind your browser too.** Alt-Tab to it, or type
  the path — the field takes either.
- **Keep maps on a locally-attached disk.** They are SQLite databases, and network shares
  do not lock reliably.
- **The move copies, verifies, and only then deletes.** If anything fails part-way, your
  originals are untouched and the partial copies are cleaned up.

If you later start DunneFlow while that disk is unplugged, it says so in as many words,
names the disk, and falls back to the standard location rather than silently making a new
empty one where the old one used to be. See [when it refuses](15-when-it-refuses.md).

---

Next: [2. Getting the code](02-getting-the-code.md)
