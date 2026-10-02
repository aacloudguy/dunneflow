# 1. Pointing it at itself

Open DunneFlow with a map already showing — any map — and the first control in the top bar
is the program list. Its last two entries are not programs:

```
+ Analyse a directory…
× Close this map
```

Pick the first. You get the dialog that makes every map DunneFlow has.

## The dialog

Two fields and a checkbox.

**Directory to read** wants the whole path. Not a path relative to the terminal you started
from — the server reads the tree itself, and it is not standing where you are. **Choose…**
opens a folder picker if you would rather not type, and the typed field never goes away.

**Call it** names the directory the map gets written to. Leave it and it takes the
directory's own name.

**Read the documentation too** is on by default, and it is most of what makes the later
chapters interesting. DunneFlow reads the prose beside the code as a first-class input —
not to decorate the output, but because the words a program's authors chose are evidence
about *what* the program does, and often *why*.

## The refusal you meet first

Now type the path to DunneFlow's own source, which is the thing this tutorial is about.

![The Analyse a directory dialog over the dunneflow map. "Directory to read" holds /Volumes/BackupDrive/Documents2025/Developer/tour/DunneFlow/src/dunneflow, with a Choose… button beside it and the hint "The whole path, as this machine sees it — the server reads the tree itself, so a path relative to your terminal would mean nothing to it." "Call it" shows dunneflow, greyed, over the hint "This names the directory the map is written to, beside the programs already in the list." The "Read the documentation too" checkbox is ticked, and below it a refusal in red reads "dunneflow is the program being read — its graph is open here, and an analysis may discard and re-extract it. Switch to another program first, or run this from a terminal." The Analyse button is dimmed; Cancel is not, and beside them the dialog says "It runs behind this page — the map you are reading stays open and stays true."](images/01-refuses-itself.jpg)

> **dunneflow is the program being read** — its graph is open here, and an analysis may
> discard and re-extract it. Switch to another program first, or run this from a terminal.

This is the joke the whole tutorial is built on, and it is also a real answer. **Call it**
filled itself in with `dunneflow`, which is the name of the map you are currently reading.
Analysing into it would rewrite the graph this server is holding open — and DunneFlow
rebuilds a graph by discarding what was there, so the map could empty itself underneath
you while you looked at it.

Three things worth noticing, because they recur everywhere in this tool:

- **It refuses before you press anything.** The check runs as you type, and **Analyse** is
  dimmed rather than absent — you can see the control you are not allowed to use, and the
  sentence saying why is directly above it.
- **It says what to do instead**, and both options are real: switch programs first, or run
  it from a terminal, where no server is holding anything open.
- **It is a refusal, not a warning.** DunneFlow has a strong habit of declining to guess.
  You will meet that habit constantly; [chapter 15 of the
  reference](../15-when-it-refuses.md) is a catalogue of every refusal it can give you.

## Getting past it

Two ways, and they are the two the sentence named.

The honest one for a tutorial is the terminal, because it is also how you would do this the
first time, before any map exists:

```bash
uv run dunneflow analyze src/dunneflow --name dunneflow
uv run dunneflow serve output/dunneflow
```

The other is to switch the program list to something else first and then analyse. Same
result; the dialog stops objecting the moment the name you are writing to is not the name
being served.

## What it does while you wait

A few seconds for DunneFlow's 142 files. If you run it through the dialog rather than
the terminal you get a progress panel instead of scrolling text, and three things about it
are worth knowing:

- **The map you are reading stays open and stays true** for the whole run. The panel says
  so. An analysis is not a switch — it is not replacing what is on your screen, so it does
  not lock you out of the thing you were doing.
- **There is a stop button**, and it stops the whole job rather than the one process you
  can see. A killed analysis leaves a map that opens perfectly and lies about itself, so
  DunneFlow records whether its own analysis finished and every reader that vouches for a
  map checks.
- **The step list is computed for the run.** Turn off documentation and the run has fewer
  steps, rather than a progress bar that can never reach the end.

The reference chapter [Your first map](../04-your-first-map.md) walks the panel in detail.

## What you get

```
dunneflow: 1,550 routines · 3,261 internal calls · 526 boundary touches ·
           207 structures · 24 ways in
```

and a directory holding the graph, the documentation store, the source it read, and
fifteen written documents. The source matters more than it sounds: DunneFlow keeps a copy
of what it read, so it can still show you the code months later when the tree has moved on
— which is what makes comparing two versions possible at all.

---

Next: [2. The cover](02-the-cover.md)
