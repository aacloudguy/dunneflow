# 1. Installing

There are two ways to have DunneFlow, and which one you want depends on whether you
intend to change it.

## The application

`DunneFlow.dmg` — open it, drag **DunneFlow** to Applications, double-click it. It opens
your browser on [the start page](03-the-start-page.md) and that is the whole of the
setup. There is no Python to install, no terminal, and no configuration file.

It is a macOS application built for both Apple silicon and Intel, signed with a Developer
ID and notarised by Apple, so Gatekeeper opens it without argument on any Mac.

It asks the system for no special permissions at all. It reads the directory you point it
at, writes its maps, and opens a folder picker when you ask for one. That is everything.

> **Not yet released.** At the time of writing the application is built and signed but
> not yet notarised, and Windows has not been started. Until then, use the checkout
> below.

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

Where they go depends on which of the two you are running:

| | Maps go to |
|---|---|
| The application | `~/Library/Application Support/DunneFlow` |
| A checkout | `output/`, beside the source you cloned |

`~/Library/Application Support` is the correct place for an application's own data, and
it is deliberately **not** `~/Documents`: a map holds the source of whatever you read it
from, and Documents is swept into iCloud Drive on a signed-in Mac. DunneFlow is a local
tool and nothing it holds should leave the machine by accident.

The cost of that correctness is that the folder is hard to find, so the start page prints
the path, and **Show me** opens it in the Finder.

## Moving them somewhere else

Application Support is on your startup disk. If maps are filling it, **Move…** on the
start page points DunneFlow at a different directory — an external disk, a bigger volume —
and offers to carry the maps you already have across.

Three things about it:

- **The directory has to exist already**, and be on a disk that is connected. DunneFlow
  will not create it. A path on a disk that is not mounted would quietly be created on
  your startup disk instead, which is the opposite of what you asked for.
- **Keep maps on a locally-attached disk.** They are SQLite databases, and network shares
  do not lock reliably.
- **The move copies, verifies, and only then deletes.** If anything fails part-way, your
  originals are untouched and the partial copies are cleaned up.

If you later start DunneFlow while that disk is unplugged, it says so in as many words,
names the disk, and falls back to the standard location rather than silently making a new
empty one where the old one used to be. See [when it refuses](15-when-it-refuses.md).

---

Next: [2. Getting the code](02-getting-the-code.md)
