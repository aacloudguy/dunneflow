# 15. When it refuses

DunneFlow refuses rather than guessing, and every refusal names something you can act on.
That is not fastidiousness: a fallback that produces a plausible value hides the failure it
was written for, and a map that looks right and is wrong is worse than no map.

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
will not do is create the missing directory: `/Volumes` is an ordinary folder on your
startup disk, so a helpful `mkdir` would put a new empty maps root on the very disk you
were trying to keep clear, and then report no programs in it.

---

## Refusals from the analyse dialog

Each is its own sentence because each is a different problem.

| It says | What to do |
|---|---|
| *…is a relative path — give the whole path* | The server reads the tree itself, so a path relative to your terminal means nothing to it. Use **Choose…** or type the full path. |
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
