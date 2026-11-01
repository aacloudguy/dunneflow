# 4. Your first map

Press **+ Analyse a directory…** on the start page. (The same dialog is on the program
menu inside the dashboard, second from the bottom, just above **× Close this map**, so you
never have to leave a map to read another one.)

![The Analyse a directory dialog, opened over DunneFlow's own cover: a "Directory to read" field showing the example /Users/you/code/some-project/src with a Choose… button, a "Call it" field reading "the directory's own name", a ticked "Read the documentation too" checkbox, a greyed Analyse button beside Cancel, and the line "It runs behind this page — the map you are reading stays open and stays true."](images/04-analyse-dialog.jpg)

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

![The dialog with /Volumes/BackupDrive/Documents2025/Developer/requests typed in, "Call it" now showing requests, the directory's own name, and the Analyse button enabled](images/04-analyse-preflight.jpg)

When it refuses, it says which refusal it is. Each is different problem and each has
its own sentence. The most common one on your first run:

![The dialog with the path to DunneFlow's own src/dunneflow typed in and "Call it" showing dunneflow, refusing in red: "dunneflow is the program being read — its graph is open here, and an analysis may discard and re-extract it. Switch to another program first, or run this from a terminal." Analyse is greyed.](images/15-refuse-served-program.jpg)

That one is not caution. An analysis into the name that is currently open would rewrite
the very graph the server is holding, and empty the map under you while you were reading
it. The others, might be a relative path, a directory that is not there, or a standards directory
nested inside the tree, each of these get their own sentence too. See
[when it refuses](15-when-it-refuses.md).

Analysing into a name that **already exists** is allowed, and the dialog says plainly
that it rewrites that program's working snapshot:

![The dialog with /Volumes/BackupDrive/Documents2025/Developer/OpenUSD typed in and "Call it" showing OpenUSD, and a note: "There is already a program called OpenUSD. Analysing into it rewrites its working snapshot rather than adding a second point in time — seal it first if you want to keep both." Analyse is enabled.](images/04-already-exists.png)

That is a note and not a refusal, so **Analyse** stays enabled.

**One analysis runs at a time.** Open the dialog while another is going and it says so, names
the run and the step it is on, and offers to stop it — or to wait, because the dialog stays
open and **Analyse** comes back by itself when the run finishes:

![The dialog with a requests directory typed in, refusing in red "an analysis of OpenUSD-cold is already running", above a panel reading "An analysis of OpenUSD-cold is running — reading the source tree, step 1 of 7, going 38.1 s." with a Stop it button and "Or leave it — this dialog stays, and Analyse works again as soon as it finishes."](images/04-dialog-blocked.png)

## While it runs

The panel appears bottom-right and stays there. You can dismiss it, keep reading, and
come back. An analysis is not a switch, and the map you already have open stays open and
stays true for the whole run.

![The dashboard, still showing DunneFlow's cover, with a progress panel in the bottom-right corner reading "ANALYSING OpenUSD-cold — writing the map — step 7 of 7 · 1 m 13 s", a collapsed "What was left out of this map (4)", "The map on screen is untouched. Keep reading." and a Stop it button](images/04-analysis-running.jpg)

Close up:

![The progress panel: "ANALYSING OpenUSD-cold — writing the map — step 7 of 7 · 1 m 17 s", with a progress bar nearly full, a collapsed "What was left out of this map (4)", the line "The map on screen is untouched. Keep reading.", and a Stop it button beside "What it has written stays, marked unfinished."](images/04-progress-panel.png)

The steps are counted for *this* run, not from a fixed list, because the flags you set
remove work. A full run is:

1. reading the source tree
2. reading the documents
3. capturing the document bodies
4. reading the standards *(only if you gave it a standards directory)*
5. resolving calls and command trees
6. capturing the source bodies
7. looking for anomalies
8. writing the map

So a run with no standards directory counts seven, as the panels above do.

The panel carries **What was left out of this map** while the run is still going, so what a
run declined is not something you have to wait for the end to learn. It is the next section.

If nothing has moved for more than three-quarters of a minute, the panel tells you that and
does nothing about it. This one is from an earlier, slower build reading the same tree:

![The progress panel for OpenUSD-cold at "resolving calls and command trees — step 4 of 7 · 2 m 14 s", with a note: "Nothing new for 1 m 3 s. Some steps are quiet for a while — resolving a large program says nothing until it is done — so this may be working. It may also be stuck."](images/04-progress-quiet.png)

Resolution is legitimately quiet for minutes on a large program, so whether that is a
wedged job or a long step is your call, not the tool's.

## What it read, and what it left out

A run ends by saying both, and the second half is as much the point as the first. This is
DunneFlow reading itself — two of the five languages it reads, because when this was taken
its own source held neither C++ nor Kotlin, nor yet the Go of its own Go reader:

```
files 142 (parsed 142, cached 0, removed 0, failed 0) in 3.5s
  read: python 131 · typescript 11
    typescript plugins/typescript/tsconfig.json: 11 files
    typescript opened in 0.1s
  unread: 8 .js, 6 .json, 6 .yaml, 2 .html, 1 .cjs, 1 .css, 1 .mjs — no reader here
  claims those suffixes
  strings not judged: 3,475 python, 112 typescript — outside the 3–200,000 character
  bound a reader applies before sending
  calls resolved to somewhere outside this map: 262 typescript — a library, a type
  declaration or a file no reader claimed; external, and right
  calls whose far end the reader could not name at all: 200 typescript — left external
  rather than guessed by name
  pruned 1 directory: vendor
```

That is the command line's. **The dialog gets the same lines**, under **What was left out
of this map** in the panel: closed by default, with the count of lines on it, and open for
the asking while the run goes and after it ends. When a run finishes, the panel says what it
read and offers to open it:

![The panel after a run of requests: "READ requests — 22 files · 290 routines · 31 documents · 5.6 s", "Opening it reloads the page, because a program switch cannot keep the selection, the trail or the version you are on.", a collapsed "What was left out of this map (4)", and Open it and Not now buttons](images/04-analysis-read.png)

Opened, it is the list a terminal would have printed:

![The same finished panel for requests with "What was left out of this map (4)" open: "unread: 5 .png, 4 .cnf, 4 .key, 3 .csr, 3 .pem, 2 .yaml, 1 .ai, 1 .bat, 1 .crt, 1 .css, 1 .html, 1 .in, 1 .ini, 1 .srl, 1 .svg, 1 .toml, 1 .typed — no reader here claims those suffixes", "left out as tests: 15 python — analyse again with --include-tests to read them", "strings not judged: 162 python — outside the 3–200,000 character bound a reader applies before sending" and "pruned 2 directories: .git, .github"](images/04-left-out.png)

Once the map is open, **About this map** holds the same record for good, together with the
one line the panel leaves out — which languages were read, and how many files of each.

**`read:` is per language, and that is not decoration.** *142 files* says nothing about
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
| `calls resolved to somewhere outside this map` | the reader's own compiler followed the call to a library or a file no reader claimed. External, and right |
| `calls whose far end the reader could not name at all` | left external rather than guessed at by name |
| `pruned N directories` | `node_modules`, `__pycache__`, anything beginning with a dot, and any directory that holds somebody else's map |

If you ever find yourself asking *why is this map smaller than the directory*, the answer
is one of those lines, and it was printed.

## Stopping it

**Stop it** ends the run. What it had already written stays on disk, **marked
unfinished** and that mark is the point of the whole mechanism.

![The panel after stopping, over the dashboard: "STOPPED OpenUSD-cold3 — stopped on signal 15. What it had written is left marked unfinished — analysing OpenUSD-cold3 again completes it.", and "Analyse it again" and "Close" buttons](images/04-analysis-stopped.jpg)

**Analyse it again** opens the dialog with the directory and the name already filled in —
the same directory the stopped run was reading — so finishing it is one more press of
**Analyse**. The dialog notes that a program by that name already exists, which is true:
the unfinished one.

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
- **`map@<instant>/`** Fourteen Markdown documents about the program — entrypoints,
  flows, routines, data, boundaries, governance, database, network, anomalies, glossary,
  naming, traceability, mirror and constants — and a README that indexes them. Seven are
  subjects [Document mode](08-document.md) shows you in the browser; the other seven have
  surfaces of their own in the dashboard.

The Markdown is readable on its own with no tooling at all, which matters when you want
to send someone the answer rather than the application.

Then the dashboard opens. That is [the shell](05-the-shell.md).

---

Next: [5. The shell](05-the-shell.md)
