# 15. When it refuses

DunneFlow is designed to be mostly deterministic, meaning if you run it over and over, 
you get the same results. When working with large language models, probabilistic output
means that your results can be different every time. In the case of DunneFlow, the 
application is designed so that it refuses rather than guessing, and every refusal names
something you can act on. That is not fastidiousness: a fallback that produces a plausible
value hides the failure it was written for, and a map that looks right and is wrong is worse
than no map.

Here is every refusal you are likely to meet.

---

## "was written by a different version of DunneFlow"

```
error: output/some-project/graph@2026-09-09T15-32-15Z.db was written by a different
version of DunneFlow and cannot be read safely -- re-run `dunneflow analyze` to rebuild it
```

**What happened.** DunneFlow was updated. A map records which version of the extractor and
which detector rules read it, and a newer build will not read an older store's facts as if
they were its own.

**What to do.** Analyse the tree again. It is quick — extraction is cached against file
content, so unchanged files are not re-parsed.

**If it names `standards.db`,** re-run the analysis with `--standards` pointing at the same
standards directory:

```bash
uv run dunneflow analyze <tree> --name <program> --standards <standards-dir>
```

This one catches people out, because a rebuild that omits `--standards` produces a map that
analyses perfectly and then **refuses to boot** when you try to serve it. If you no longer
have the standards directory, delete `standards.db` and the conformance lane will say in
its own words that there is nothing to check against.

**If you have sealed snapshots,** they are stale too. Rebuilding is three commands, oldest
first — see [comparing two versions](14-comparing-two-versions.md#getting-a-second-version).

---

## "holds facts from a reader this build is not"

```
error: output/some-project/graph@….db holds facts from a reader this build is not:
typescript (read by 1.1.0:92eb0d173e9807a7). Re-run `dunneflow analyze` -- it re-reads
only the language that changed, and leaves the rest of the map alone.
```

**What happened.** The refusal above is about the whole map; this one is about **one
language in it**. DunneFlow records, per file, which reader produced its facts, and the
reader for one language moved while the rest of the tool stayed where it was.

**What to do.** Analyse again. The sentence means what it says: the language it names is
re-read and every other language's rows are left exactly where they are, so on a repository
that is mostly Python with a little TypeScript this costs seconds rather than a full
rebuild.

**Why it names the language.** *This map is stale*, said over a Python map whose forty
TypeScript files are the problem, sends you looking in the wrong place. The name is the
part you can act on.

---

## "needs `node` … and nothing answers `node --version` on this machine"

```
typescript needs `node` ≥ 20.0.0 and nothing answers `node --version` on this machine.
Install it (brew install node, or nodejs.org), or run again with `--without typescript`
and the map will say those files were declined.
```

**What happened.** DunneFlow reads TypeScript by asking TypeScript's own compiler, which
needs Node.js — see [installing](01-installing.md#which-languages-it-reads-and-the-one-thing-you-may-have-to-install).
It asks before it reads anything, so nothing is half-written when this appears.

**What to do.** Either of the two things the sentence offers, and they are both real:

```bash
# read the whole tree
brew install node            # or nodejs.org

# or read the rest of it, and say so
uv run dunneflow analyze <tree> --name <program> --without typescript
```

**`--without` is not a way of hiding the problem**, which is the only reason it is offered.
The run prints what it declined and how many files that was, and the map records it on
**About this map**'s *It was told* row — so a map with no TypeScript in it can still be told
apart from a program with no TypeScript in it. Declining every language DunneFlow reads is
refused rather than obeyed: that is a map with no code in it, and if what you wanted was the
documentation alone, the thing to reach for is `--no-docs`'s opposite — analyse normally and
read the Document lane.

**It is not asked for at all** if the tree you point at holds no TypeScript.

---

## "stores absolute paths"

```
error: output/some-project/graph@….db stores absolute paths, from before DunneFlow made
them relative to the tree they were read from -- run `dunneflow migrate output/some-project`
to rewrite it in place
```

**What to do.** Exactly what it says.

```bash
uv run dunneflow migrate output/some-project
```

It rewrites the stored paths in place — on a large program, about 115,000 paths across five
stores in a little over a second. **In place rather than by re-analysis**, deliberately: a
sealed snapshot exists to be readable after its source tree is gone, and rebuilding would
orphan exactly those.

A reader will never quietly repair a store on the way past. It refuses and names the
command.

---

## "was never finished"

```
error: some-project was never finished: an analysis stopped while reading the documents.
What it holds is part of a program, not a program. Analysing it again completes it — the
extraction is cached, so it takes seconds rather than the whole run.
```

**What happened.** An analysis was interrupted — you pressed **Stop it**, or the machine
slept, or it was killed.

**Why it matters.** A half-written graph *opens perfectly and lies*. One stopped twelve
seconds in reported 628 files, 4,786 routines and **zero** resolved calls, over a real
timestamp and a real tool version.

**What to do.** Analyse it again. It picks up where it stopped.

**One command proceeds anyway, and warns:** `dunneflow query`. Its contract is that you get
the rows that are there, so it tells you the map is unfinished and answers.

---

## "is the program being read"

> dunneflow is the program being read — its graph is open here, and an analysis may discard
> and re-extract it. Switch to another program first, or run this from a terminal.

![The analyse dialog over the dashboard, with DunneFlow's own src/dunneflow typed into "Directory to read" and "Call it" showing dunneflow, refusing in red: "dunneflow is the program being read — its graph is open here, and an analysis may discard and re-extract it. Switch to another program first, or run this from a terminal." Analyse is greyed out; Cancel is not](images/15-refuse-served-program.jpg)

**What happened.** You asked the dashboard to analyse into the name it is currently
serving.

**Why.** The server is holding that graph open. An analysis aimed at it can empty the map
under you while you are reading it.

**What to do.** Switch the program menu to something else first, or run `dunneflow analyze`
from a terminal against a server that is not serving it.

---

## "maps are kept in … which is not there right now"

```
maps are kept in /Volumes/YourDisk/DunneFlow, which is not there right now —
reconnect that disk, or choose somewhere else
```

**What happened.** You moved your maps to another disk and it is not connected.

**What to do.** Reconnect it, or press **Choose somewhere else** on the start page.

DunneFlow falls back to the standard location so that the application opens rather than
doing nothing — but it says so on the terminal *and* in a banner on the start page. What it
will not do is create the missing directory. On a Mac `/Volumes` is an ordinary folder on
your startup disk, so a helpful `mkdir` would put a new empty maps root on the very disk you
were trying to keep clear, and then report no programs in it; on Linux `/mnt` and `/media`
are the same folder-on-the-boot-disk trap; on Windows it would either fail on a drive letter
that is not there or write to one that now points somewhere else. None of those is an answer
worth guessing at.

---

## "no folder picker is installed" (Linux)

```
no folder picker is installed — zenity or kdialog would give you one;
type the whole path instead
```

**What happened.** You pressed **Choose…** on a Linux machine with neither dialog program
installed. A Mac and a Windows machine each ship exactly one thing that can ask you for a
folder; a Linux desktop ships whichever its toolkit brought, and yours brought neither.

**What to do.** Type the path into the field — it takes one and always has, and the picker
was only ever a convenience over it. If you would rather fix it once, install either
package; DunneFlow prefers whichever matches your desktop.

---

## "there is no desktop session here" (Linux)

```
there is no desktop session here to open a window in — type the whole path instead
```

**What happened.** DunneFlow is running somewhere with no display — over SSH without
forwarding, or on a headless machine — and you asked for a window. There is no screen to
put one on. You are reading the dashboard in a browser somewhere else entirely, which is a
perfectly good way to use it.

**What to do.** Type the path. **Show me** refuses for the same reason and says so in its
own words — *there is no desktop session here to show a directory in* — because there is no
file manager to bring forward either.

This is checked *before* anything is launched rather than after it fails, which is what
lets a cancelled dialog mean only that you cancelled it.

---

## Refusals from the analyse dialog

Each is its own sentence because each is a different problem, and each appears under the
fields as you type, with **Analyse** greyed out until it is settled.

![The ANALYSE A DIRECTORY dialog with requests/src typed into "Directory to read", over the hint "The whole path, as this machine sees it — the server reads the tree itself, so a path relative to your terminal would mean nothing to it."; "Call it" shows src, borrowed from the directory; "Read the documentation too" is ticked; and in red, "requests/src is a relative path — give the whole path, because the server's directory is not yours". Analyse is greyed out](images/15-refuse-relative.png)

| It says | What to do |
|---|---|
| *…is a relative path — give the whole path, because the server's directory is not yours* | The server reads the tree itself, so a path relative to your terminal means nothing to it. Use **Choose…** or type the full path. |
| *…does not exist* | Check the path. |
| *…is a file, not a directory to analyse* | Point at the directory that contains the code. |
| *…is inside the output root — that is where maps are written* | You have pointed it at its own output. Point it at source. |
| *no name was given, and the directory has none to borrow* | Fill in **Call it**. |
| *…is not a name a directory can have* | One plain name, no slashes. |
| *a file called … is already sitting where that program's directory would go* | Move or rename that file. |

And one **note** rather than a refusal, which still lets you proceed:

> There is already a program called some-project. Analysing into it rewrites its working
> snapshot rather than adding a second point in time — seal it first if you want to keep
> both.

---

## Refusals about a standards directory

`--standards` admits somebody else's naming rules. Three ways a program can end up reading
*itself* as its own standard, each refused by name:

| It says | Why |
|---|---|
| *…is inside the output root* | That is DunneFlow's own output. |
| *…is inside the documentation root — it is already read* | It is already in the corpus; admitting it twice would mint rules from your own prose. |
| *…is inside the analysed tree* | A standard the program carries is the program's documentation, not an outside standard. |

Keep the standards directory outside the tree you are analysing and outside the output
root. Its provenance is recorded, so keep it somewhere permanent rather than in a scratch
folder.

---

## "409" from a cold server

If a request arrives before any map is open, the server refuses with a 409 and a sentence
saying so, rather than answering out of nothing. You will normally see this only if you
have bookmarked a dashboard URL and come back to a freshly started server.

**What to do.** Go to `/start` and open a program.

---

## The graph looks wrong, not broken

Some things are not refusals but are worth recognising.

**A four-thousand-file program with almost no internal calls.** Usually a partial checkout
— a sparse git checkout or a narrow Perforce client view. What is not on disk is not in the
map. See [getting the code](02-getting-the-code.md).

**An entry point with a reach of 1 or 2** when you know it does more. DunneFlow is missing a
registration idiom — a framework that registers handlers in a way its detectors do not yet
recognise. Teaching it one is usually a config edit in `detectors/*.yaml` rather than a code
change.

**Something DunneFlow reports that turns out to be a limitation of DunneFlow rather than of
your program.** That is expected often enough that the worklist has a key for it: press `3`
on a finding to triage it as a defect in the tool. The first time DunneFlow was run against
a live codebase, six confident findings in a row were its own bugs.

---

Next: [16. The command line](16-the-command-line.md)
