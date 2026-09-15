# 1. Installing

There are two ways to have DunneFlow — the application, or a checkout — and which one you
want depends on whether you intend to change it. The application comes in a Mac build and a
Windows build; everything after this chapter is the same on both.

## The application, on a Mac

`DunneFlow.dmg` — open it, drag **DunneFlow** to Applications, double-click it. It opens
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
of it — which is why the second one exists. Reach for `dunneflow-cli.exe` any time you want
to see output.

> **It is not signed**, so the first time you run it Windows SmartScreen will say it does
> not recognise the publisher. **More info → Run anyway.** That is a warning, not a block,
> and it appears once. (The Mac build *is* signed and notarised; the two platforms are at
> different stages.)

### One thing that behaves differently

**The folder picker opens behind your browser.** Press **Choose…** — the button says
*Opening…* while the chooser starts — and then **Alt-Tab to it**, or click its icon in the
taskbar. It is there; it simply is not in front.

That is Windows rather than DunneFlow: a program running in the background is not allowed to
bring a window to the front, and DunneFlow is in the background the whole time you are
looking at a browser. The Mac build can ask the system to come forward and does.

Typing the path by hand always works and is never the slower route if you already know it.

## The checkout

If you want to read DunneFlow's own source, change it, or run it on Linux, you need
Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/aacloudguy/dunneflow
cd dunneflow
uv sync
uv run dunneflow serve
```

`uv run dunneflow serve` with nothing after it opens the start page, exactly as the
application does.

## Where maps are kept

A map is not small. One snapshot of a 628-file program is about 168 MB, and it grows
each time you capture another version of the same program, because DunneFlow keeps the
source it read so it can still show you the code after the tree has moved on.

Where they go depends on which of the three you are running:

| | Maps go to |
|---|---|
| The application, on a Mac | `~/Library/Application Support/DunneFlow` |
| The application, on Windows | `%LOCALAPPDATA%\DunneFlow` |
| A checkout | `output/`, beside the source you cloned |

Each of those is the correct place for an application's own data on its platform, and
neither is `~/Documents` or `Documents`: a map holds the source of whatever you read it
from, and Documents is swept into iCloud Drive or OneDrive on a signed-in machine.
DunneFlow is a local tool and nothing it holds should leave the machine by accident.

The cost of that correctness is that the folder is hard to find, so the start page prints
the path, and **Show me** opens it — in the Finder, or in File Explorer.

## Moving them somewhere else

Maps are kept on your startup disk by default, on both platforms. If they are filling it,
**Move…** on the start page points DunneFlow at a different directory — an external disk, a
bigger volume — and offers to carry the maps you already have across.

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
