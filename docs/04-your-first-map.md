# 4. Your first map

Press **+ Analyse a directory…** on the start page. (The same dialog is on the program
menu inside the dashboard, second from the bottom, under **× Close this map** so you
never have to leave a map to read another one.)

![The Analyse a directory dialog: a "Directory to read" field with a Choose… button, a "Call it" field, a "Read the documentation too" checkbox, and Analyse and Cancel buttons](images/04-analyse-dialog.jpg)

## The two fields

**Directory to read** — the whole path, as this machine sees it. Not a path relative to
your terminal: the server reads the tree itself, so a relative path would mean nothing to
it. **Choose…** opens a folder picker if you would rather not type one. The typed field
never goes away — the picker is a convenience over a control that still works.

> **On Windows the picker opens behind your browser** — **Alt-Tab to it**, or click it in
> the taskbar. The button says *Opening…* while the chooser starts, and the first one after
> you launch DunneFlow takes a few seconds. This is Windows rather than DunneFlow: a program
> running in the background may not bring a window to the front, and DunneFlow is in the
> background while you are looking at a browser. Typing the path always works.
>
> **On Linux the picker comes to the front on its own**, but it has to be installed: it
> uses zenity or kdialog, whichever it finds. If neither is there it says so and names them
> both. Over SSH with no display it says that instead. Typing the path always works there
> too.

Point it at the directory that holds the code. For a Python project that is usually
`src/`, or the package directory, rather than the repository root.

**Call it** Shows the name of the directory the map is written to, beside the programs
already in the list. Leave it and DunneFlow uses the directory's own name.

**Read the documentation too** This is on by default. DunneFlow scans the Markdown, reStructuredText
and plain text beside the code and reads it as a separate, parallel corpus: it is what
fills the glossary, the naming lanes and Document mode's second lane. Turn it off if you
only want the code, and the analysis is quicker.

## The pre-flight

DunneFlow checks what you typed as you type it, and **Analyse** stays disabled until it
is satisfied.

![The dialog with a valid path filled in, "Call it" auto-filled with the directory's own name, and the Analyse button now enabled](images/04-analyse-preflight.jpg)

When it refuses, it says which refusal it is. Each is different problem and each has
its own sentence. The most common one on your first run:

![The dialog refusing in red: "dunneflow is the program being read — its graph is open here, and an analysis may discard and re-extract it. Switch to another program first, or run this from a terminal."](images/15-refuse-served-program.jpg)

That one is not caution. An analysis into the name that is currently open would rewrite
the very graph the server is holding, and empty the map under you while you were reading
it. The others, might be a relative path, a directory that is not there, or a standards directory
nested inside the tree, each of these get their own sentence too. See
[when it refuses](15-when-it-refuses.md).

Analysing into a name that **already exists** is allowed, and the dialog says plainly
that it rewrites that program's working snapshot.

## While it runs

The panel appears bottom-right and stays there. You can dismiss it, keep reading, and
come back. An analysis is not a switch, and the map you already have open stays open and
stays true for the whole run.

![The start page with an analysis running: the program list is still usable, and a progress panel sits in the bottom-right corner reading "ANALYSING society — reading the source tree — 300/628 — step 1 of 7 · 4.0 s"](images/04-analysis-running.jpg)

Close up:

![The progress panel: "ANALYSING society — reading the documents — step 2 of 7 · 15.5 s", with a progress bar, the line "The map on screen is untouched. Keep reading.", and a Stop it button labelled "What it has written stays, marked unfinished."](images/04-progress-panel.png)

The steps are counted for *this* run, not from a fixed list, because the flags you set
remove work. A full run is:

1. reading the source tree
2. reading the documents
3. capturing the document bodies
4. reading the standards *(only if you gave it a standards directory)*
5. resolving calls and command trees
6. capturing the source bodies
7. writing the map
8. looking for anomalies

If the panel says nothing has moved for several minutes, it tells you that and does
nothing about it. Resolution is legitimately quiet for tens of seconds on a large
program, so whether that is a wedged job or a long step is your call, not the tool's.

## What it read, and what it left out

A run ends by saying both, and the second half is as much the point as the first. This is
DunneFlow reading itself, which is two languages:

```
files 118 (parsed 118, cached 0, removed 0, failed 0) in 1.7s
  read: python 107 · typescript 11
    typescript plugins/typescript/tsconfig.json: 11 files
    typescript opened in 0.3s
  unread: 8 .js, 5 .json, 4 .yaml, 2 .html, 1 .cjs, 1 .css, 1 .mjs — no reader here
  claims those suffixes
  strings not judged: 2,860 python, 110 typescript — outside the 3–200,000 character
  bound a reader applies before sending
  calls resolved to somewhere outside this map: 450 typescript — a library, a type
  declaration or a file no reader claimed; external, and right
  pruned 16 directories: __pycache__ ×14, node_modules, vendor
```

**This is the command line's, and only the command line's.** `dunneflow serve` runs the
analysis with `--quiet` so that its machine-readable progress stream stays clean, and these
lines go with it — so a reader who analyses from the dialog gets the progress panel and the
map, and not this. If you want to know what a run left out, run it from a terminal. It is
the one thing in this guide the application does less well than the command, and it is
named here rather than glossed over.

**`read:` is per language, and that is not decoration.** *118 files* says nothing about
whether the TypeScript half of a tree was read at all — a repository whose TypeScript
reader never ran would report the same total as one with no TypeScript in it. The line
under it is the reader saying how it divided the work: TypeScript compiles per
`tsconfig.json`, so it says which ones it found and how many files went into each.

**Everything after `read:` is a filter, and no filter is silent.** Each line is a different
fact with a different remedy, which is why they are not merged into one:

| | |
|---|---|
| `unread: … no reader here claims those suffixes` | this build has no reader for them. Point at a Go repository today and the map is empty; this is the line that says so rather than leaving you with an empty map |
| `left out as tests` | per language, because a test is spelled differently in each — `test_a.py` and `a.test.ts` are the same idea and not the same rule. `--include-tests` reads them |
| `declined by you` | you passed `--without <lang>`. A different fact from the first line, with the opposite remedy |
| `skipped by the reader's own rule` | a `.d.ts` is TypeScript's header file, not a program |
| `strings not judged` | too short or too long to be worth scanning for SQL and filenames |
| `pruned N directories` | `node_modules`, `__pycache__`, anything beginning with a dot, and any directory that holds somebody else's map |

If you ever find yourself asking *why is this map smaller than the directory*, the answer
is one of those lines, and it was printed.

## Stopping it

**Stop it** ends the run. What it had already written stays on disk, **marked
unfinished** and that mark is the point of the whole mechanism.

![The panel after stopping: "STOPPED society — stopped on signal 15. What it had written is left marked unfinished — analysing society again completes it." with "Analyse it again" and "Close" buttons](images/04-analysis-stopped.jpg)

An analysis that is killed part-way leaves a graph that **opens perfectly and lies**. One
stopped twelve seconds into a large program reported 628 files, 4,786 routines and *zero*
resolved calls, over a timestamp and a tool version, looking for all the world like a
finished map of a program with no internal calls in it. So DunneFlow records whether its
own analysis finished, and every reader that vouches for a map checks:

```
error: society was never finished: an analysis stopped while reading the documents.
What it holds is part of a program, not a program. Analysing it again completes it —
the extraction is cached, so it takes seconds rather than the whole run.
```

Analysing again does complete it, and it is quick: extraction is cached against the
content of each file, so the second run only does the work the first one did not reach.

A stopped run is reported as **stopped**, not as failed. You did it intentionally.

## What you get

A directory under the maps root, holding:

- **`graph@<instant>.db`** The one source of truth. Every fact about the program, in
  SQLite. Nothing holds the whole program in memory; every question the dashboard asks is
  a query against this.
- **`docs@<instant>.db`** The documentation, in a parallel store. Never the same file:
  a documentation rescan never touches the graph, and a corpus stays a separately
  handable thing. Many people will hand you a charter and never a line of source.
- **`source.db`** and **`docsource.db`** The bodies of what was read, held by content
  hash. This is what lets [Code mode](09-code.md) show you the source months later, on a
  machine that has never held the tree.
- **`map@<instant>/`** Fifteen Markdown documents about the program: entrypoints,
  flows, routines, data, boundaries, governance, database, network, anomalies, glossary,
  naming, traceability, mirror, constants, and a README that indexes them. These are the
  same eight subjects [Document mode](08-document.md) shows you in the browser, plus the
  ones that only make sense written down.

The Markdown is readable on its own with no tooling at all, which matters when you want
to send someone the answer rather than the application.

Then the dashboard opens. That is [the shell](05-the-shell.md).

---

Next: [5. The shell](05-the-shell.md)
