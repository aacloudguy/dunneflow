# 8. Two versions

The map we have been reading holds three readings of DunneFlow: the source as it stands,
and two snapshots taken from older commits. The one the dashboard compares with by default
is the commit *before the Windows fix* — the last one before DunneFlow was first run on
Windows and turned out to fail on every TypeScript file there.

That makes this chapter a fair test, and a much harder one than it was when the pair was
first made. Between that commit and the one this map was read from are 154 more: the
Windows fix itself, and then everything release 0.3.0 is — four new readers, for Go, Rust,
Java and C++, each a program written in the language it reads, and the work in the Python
around them that it took to hold what they send. **Can DunneFlow tell you what changed,
without being told?**

## Making the pair

```bash
git worktree add ../dunneflow-before-windows 290c39b^
uv run dunneflow analyze ../dunneflow-before-windows/src/dunneflow --name dunneflow
uv run dunneflow revisions output/dunneflow --seal --label "DunneFlow at 1017ef4 - before the Windows fix"
uv run dunneflow analyze src/dunneflow --name dunneflow
```

Analyse the older tree, **seal** it, then analyse the newer one. Sealing is what stops the
next analysis overwriting it: a sealed snapshot is never re-analysed in place, so it stays
readable after the tree it came from is gone. The third reading in this map, *before
parts*, was made the same way, first; the user guide's chapter on comparing versions uses
it.

## Which one is newer?

Here is the first thing DunneFlow does that most tools would not.

![Table mode with entrypoints_from_manifests selected. The comparison strip reads "BASE DunneFlow 0.3.0 compared with dunneflow-before-windows · DunneFlow at 1017ef4 - before the Windows fix 0.2.0", followed by a button reading "the compared version is older — from their versions" and the note "captured: compared first". The table's banner reads "SHOWING resolve.entrypoints.entrypoints_from_manifests row 1,791 of 2,552 as sorted here" with a Go to it button, and its summary line reads "against 2026-11-13 03:56:47: +1,147 added · ○ 228 behave differently · ¶ 2 explained differently · ≈ 186 edited only · 989 unchanged · 123 deleted — in 2026-11-13 03:56:47 only, so not listed here", with +1,147 in green. The navigator's CHANGES group, 1,907, is open under its summary, with The whole comparison and then one band to a row: ADDED 1147, DELETED 123, BEHAVING DIFFERENTLY 228, EXPLAINED DIFFERENTLY 2, EDITED, BEHAVING THE SAME — NOT IN THE COUNT 186, MODULES EXPLAINED DIFFERENTLY 41, STRUCTURES ONLY IN THE BASE 318, STRUCTURES ONLY IN THE COMPARED 10, STRUCTURES DECLARING DIFFERENTLY 29 and STRUCTURES EXPLAINED DIFFERENTLY 9. The table is scrolled to the selection: entrypoints_from_manifests is the highlighted first row, 2← 6→, marked ○ in CHANGED. The inspector on the right shows entrypoints_from_manifests with IN 2 and OUT 10 call sites](images/08-comparison-direction.jpg)

It will not work out which version is newer **from the timestamps.**

The only instant DunneFlow records is when the *bytes were read*. That says nothing about
when the code is from. The three readings in this map were made four seconds apart from
trees weeks apart, and the oldest tree happened to be read first — because that is the
order somebody typed the commands in. Read them the other way round and nothing about the
code would change. Capture order and code order are different facts.

What it can read is the version each program states about itself. The snapshot's
`pyproject.toml` says `0.2.0` and today's says `0.3.0`, and the strip prints both, so it
says, in as many words:

> the compared version is older — from their versions

*From their versions* is the half that matters: it is the tool saying what the direction
rests on. Had both said `0.2.0` — as they did when this pair was first made — there would
be nothing to read, and the same place would say **assuming the compared version is
newer**: a default, and labelled as one.

Either way it is a **button**. Click it and you get your own choice, *you chose: the
compared version is newer*; again, *you chose: the compared version is older*; and a third
click hands the decision back to the versions. The direction is yours to overrule, because
it decides whether every changed row reads as **arrived** or as **gone** — and getting that
backwards would invert the meaning of the entire screen.

Click it once to see that happen:

![The comparison strip after one click: "BASE DunneFlow 0.3.0 compared with dunneflow-before-windows · DunneFlow at 1017ef4 - before the Windows fix 0.2.0", the button now outlined and reading "you chose: the compared version is newer", and the note "captured: compared first"](images/08-you-chose.png)

The summary under it turns round with it — **−1,147 deleted**, **123 added** — which is
what this screen would be telling you if the snapshot really were the newer of the two.
Nothing was asked of the server again: the two sets are the same two sets, and only the
words and the colours laid over them changed. Click twice more to hand it back.

Beside the button, separately, is the one thing that *can* be observed:

> captured: compared first

An observation, placed next to the reading and never dressed up as a correction to it.
*We may infer, so long as we say we did.*

Read the right way round, the summary is:

> against 2026-11-13 03:56:47: **+1,147 added** · ○ **228 behave differently** · ¶ **2
> explained differently** · ≈ **186 edited only** · **989 unchanged** · **123 deleted**

That is the state chapters 5 to 7 were photographed in.

## What it found

Here is the payoff. Without being told anything about Windows, or about a release,
DunneFlow reports:

**1,147 added**

| | | |
|---|---|---|
| `plugins/java` | 295 | the Java reader |
| `plugins/rust` | 249 | the Rust reader |
| `plugins/cpp` | 245 | the C and C++ reader |
| `plugins/go` | 134 | the Go reader |
| `plugins/typescript` | 6 | `cacheKey`, `isGlobalFetch`, `farEnd`, `decideArg`, `asWhenArg`, `matchCallWith` |
| the Python | 218 | `resolve` 39, `store.py` 25, `render` 24, `web` 24, `cli.py` 22, `detectors` 14, `runstate.py` 13, `ingest` 11, and the rest in ones and twos |

Nine hundred and twenty-three of them are four programs that did not exist: that is what
the release was, and it is the first four rows. The fifth row is where the Windows fix is.
On Windows the compiler asked for `C:/…/a.ts` and the reader looked up `C:\…\a.ts`, so a
cache missed and the file was parsed twice; `cacheKey` folds the two spellings into one.
And among the Python are the two you watched arrive in chapter 5, `_import_prefixes` and
`exact`: the dotted names a manifest above the analysed tree spells that tree by, and a
lookup by exactly the name given.

**123 deleted**

One hundred and fourteen of them are every routine under `extractors/cpp` — an earlier C++
reader, written in Python, twelve files of it. It is not in today's tree, and the 245
routines of `plugins/cpp` are. The comparison does not say one replaced the other; it says
one is gone and one has arrived, which is all the source says.

`_plural`, in `web/threads.py`, shows the same thing at the size of one routine. It was not
removed: it was lifted out into `words.py` so that every count in the program could share
it, and it is there as `plural`, in the added band. The comparison reports a move as one of
each, because nothing in the source says the two are the same thing — and it does not guess
that they are.

**228 behaving differently**

For the Windows fix, three: `Session.compilerHost` and `Session.sourceFile`, which now go
through `cacheKey` on every read and write of the cache, and `_reveal_linux`, which now
spells its path the POSIX way whatever machine it runs on. And among the constants beside
them is the TypeScript reader's `VERSION`, from `"1.2.0"` to `"1.3.0"`.

The rest are the places the other work had to reach: 62 in `web`, 38 in `extractors`, 28 in
`resolve`, 18 in `cli.py`, 17 in `render`, and so on down. `cmd_analyze` is one — its row
reads *boundaries, call_args, calls, comments, docstring* — and the five routines in
`resolve/entrypoints.py` are the ones chapter 5's fact lane listed. Each row says which of
its facts moved, so a routine that now reaches somewhere new reads differently from one
whose arguments merely changed: of the 228, 176 call something different, 171 pass
different arguments, 43 changed their parameters, 25 their SQL and 23 what they touch at a
boundary.

**186 edited only**

And this is the band that proves the tool is doing something a text diff cannot.
Sixty-nine of the 186 are module-level code — `canonical/__init__.py` and the rest — whose
text moved because something was added above or below it, and which does nothing it did
not do before. The other 117 are routines, and the row says what moved in each: for 78 a
docstring, for 29 a comment, for 4 both, and for 6 nothing the map keeps a fact about at
all.

DunneFlow puts every one of them in **edited only**, meaning: the text moved, the
behaviour did not. Nothing they call, pass, touch or declare is different.

That is the single most useful sentence a change report can produce. A reviewer looking at
a hundred and fifty commits wants to know which of the changed routines are *interesting*,
and "these 186 are not, those 228 are" is the answer.

**What it does not see**

`shell.js`, the dashboard's own script, had 1,165 lines added between these two commits, and
this map does not read JavaScript. The comparison can say nothing about those. It does not
pretend the change was smaller, either: *About this map*, in the user guide, lists every
kind of file it left out under **Left out of it**, and `.js` is on it.

## The four bands are the feature

| | |
|---|---|
| **added / deleted** | it is here and it was not, or the reverse |
| **behaves differently** | what it *does* changed — calls, arguments, boundaries |
| **edited only** | the text changed and the behaviour did not |
| **explained differently** | the prose changed and the code did not |

This pair has two routines in the fourth band, `_builtins` and `normalise` in
`resolve/traceability.py`, and forty-one modules — `render/mirror.py` is one — whose own
docstring was rewritten: what the file says about itself, counted apart from what its
routines do. In Python it is a comment *around* a routine that lands a routine here; a
docstring is inside the `def`, so rewording one moves the routine's text and it is counted
as edited only, tagged *docstring*. Either way a naive comparison misses the change
entirely or reports it as a change to the code. Neither is true. *The explanation changed*
is its own fact.

Four answers where a text diff has one. And the reason for the split is the same reason
severity and confidence are kept apart on the cover: collapsing two different facts into
one row means you can no longer tell them apart, and the one you needed was the one that
got lost.

## Reading it in the code

Switch to **Code** with a comparison live and you get both lanes at once — the text lane
and the fact lane, stacked, with the file underneath and the changed lines marked. You saw
it in chapter 5 on `resolve/entrypoints.py`: *112 lines added and 19 lines deleted*, and
*9 routines here the comparison has something to say about*.

The deleted lines are shown **where they belong, with their own numbers**, and the pane says
so — they are not in the file you are reading, and pretending otherwise would corrupt every
line number below them.

---

That is the map read from the inside. The next four chapters turn to what it *thinks* of
the program: [9. What looks wrong](09-what-looks-wrong.md).
