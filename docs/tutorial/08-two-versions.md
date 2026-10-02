# 8. Two versions

The map we have been reading holds three readings of DunneFlow: the source as it stands,
and two snapshots taken from older commits. The one the dashboard compares with by default
is the commit *before the Windows fix* — the last one before DunneFlow was first run on
Windows and turned out to fail on every TypeScript file there.

That makes this chapter a fair test. Between that commit and today are sixteen more: the
Windows fix itself, a change to how a console script is bound, two batches of dashboard
repairs found while photographing this tutorial, a new Setting, and a day's work clearing
the backlog — how a call is bound to what its scope can see, counts that say what they
count, and a large map that opens in minutes rather than half an hour. **Can DunneFlow tell
you what changed, without being told?**

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

![Table mode with entrypoints_from_manifests selected. The comparison strip reads "BASE DunneFlow 0.2.0 compared with dunneflow-before-windows · DunneFlow at 1017ef4 - before the Windows fix 0.2.0", followed by a button reading "assuming the compared version is newer" and the note "captured: compared first". The table's banner reads "SHOWING resolve.entrypoints.entrypoints_from_manifests row 886 of 1,550 as sorted here" with a Go to it button, and its summary line reads "against 2026-10-02 19:59:47: −23 deleted · ○ 64 behave differently · ≈ 32 edited only · 1,431 unchanged · 1 added — in 2026-10-02 19:59:47 only, so not listed here", with −23 in red. The navigator's CHANGES group, 95, reads "1 added · 23 deleted · 64 behaving differently · 1 module explained differently · 6 structures declaring differently · 32 edited without changing what they do". The inspector on the right shows entrypoints_from_manifests with IN 2 and OUT 10 call sites](images/08-comparison-direction.jpg)

It does not know which version is newer, and **it will not guess from the timestamps.**

The only instant DunneFlow records is when the *bytes were read*. That says nothing about
when the code is from. These two readings were made five seconds apart from trees a day
apart, and the older tree happened to be read first — because that is the order somebody
typed the commands in. Read them the other way round and nothing about the code would
change. Capture order and code order are different facts.

Both snapshots also report version `0.2.0`, so the version numbers cannot break the tie
either. So the strip says, in as many words:

> assuming the compared version is newer

…and makes it a **button**. Click it and you get three states: the tool's assumption, *you
chose: the compared version is newer*, and *you chose: the compared version is older*. The
direction is yours, because it decides whether every changed row reads as **arrived** or as
**gone** — and getting that backwards would invert the meaning of the entire screen.

Here the assumption is wrong. The compared version is the snapshot from before the fix, so
it is the *older* one, and the twenty-three routines today's code has and it does not are
shown as **−23 deleted**. Click the button until it says so:

![The comparison strip after choosing: "BASE DunneFlow 0.2.0 compared with dunneflow-before-windows · DunneFlow at 1017ef4 - before the Windows fix 0.2.0", the button now outlined and reading "you chose: the compared version is older", and the note "captured: compared first"](images/08-you-chose.png)

Beside it, separately, the one thing that *can* be observed:

> captured: compared first

An observation, placed next to the assumption and never dressed up as a correction to it.
*We may infer, so long as we say we did.*

With the direction set correctly, the summary reads:

> against 2026-10-02 19:59:47: **+23 added** · ○ **64 behave differently** · ≈ **32 edited
> only** · **1,431 unchanged** · **1 deleted**

That is the state chapters 5 to 7 were photographed in.

## What it found

Here is the payoff. Without being told anything about Windows, DunneFlow reports:

**23 added**

| | |
|---|---|
| `cacheKey` | the TypeScript reader's one spelling of a path, whichever way the platform writes it |
| `_import_prefixes`, `exact` | the dotted names a manifest above the analysed tree spells that tree by, and a lookup by exactly the name given |
| `say`, `_held`, `_relaxed`, `_relaxed_lane` | dashboard repairs, and the leading-underscore Setting |
| `_locally_bound`, `_visible`, `_in_module`, `_one`, `_constructor` | what a name can reach from where it is called, and which class a call builds |
| `plural`, `are`, `_gap`, `_settled` | counts that agree with their nouns, a blank line only between results, and where a tree's name was found |
| `_reach` | a cut in a long flow, made at the shallowest point |
| `isGlobalFetch` | the global `fetch`, held in a `const`, is still a network call |
| `_reach_graph`, `_routine_ids`, `_walk`, `_boundaries_reached_query` | reachability walked in memory, so a very large map opens faster |
| `resolve.cli`'s module scope | the file gained a constant, and module-level code is a routine here |

Twenty-three routines, and each one is a piece of the work in that stretch. The first is the
Windows fix: on Windows the compiler asked for `C:/…/a.ts` and the reader looked up
`C:\…\a.ts`, so a cache missed and the file was parsed twice. `cacheKey` folds the two
spellings into one. The next two are the console-script binding you watched in chapter 5,
and the rest are the dashboard repairs, the Setting chapter 10 shows, and the backlog.

**1 deleted**

`_plural`, in `web/threads.py`. It was not removed: it was lifted out into `words.py` so
that every count in the program could share it, and it is there as `plural`, in the added
band. The comparison reports a move as one of each, because nothing in the source says the
two are the same thing — and it does not guess that they are.

**64 behaving differently**

For the Windows fix, three: `Session.compilerHost` and `Session.sourceFile`, which now go
through `cacheKey` on every read and write of the cache, and `_reveal_linux`, which now
spells its path the POSIX way whatever machine it runs on. And among the constants beside
them is the TypeScript reader's `VERSION`, from `"1.2.0"` to `"1.3.0"`.

The rest are the places the other work had to reach. `cmd_analyze` now passes the analysed
tree to `entrypoints_from_manifests`, and the three routines in `resolve/entrypoints.py` are
the ones chapter 5's fact lane listed. `build_parser` and `cmd_naming` gained the new
Setting's command-line flag, and the routines in `resolve/naming.py`,
`resolve/conformance.py` and `web/vocabulary.py` carry its parameter through. The call
resolver's `_build_index` and `resolve`, the Python reader's `_record_call`, and
`resolve_calls` changed how a call is bound; the `anomalies.py` detectors and the
`web/threads.py` lanes changed how they count; `Store.reachable_from` and its neighbours
now walk the graph in memory. Each row says which of its facts moved — `call_args`, `calls`,
`boundaries`, `params`, `comments` — so a routine that now reaches somewhere new reads
differently from one whose arguments merely changed.

**32 edited only**

And this is the band that proves the tool is doing something a text diff cannot.
Twenty-seven of the thirty-two are module-level code — `cli.py`, `web/serve.py` and the
rest — whose text moved because something was added above or below it, and which does
nothing it did not do before. The other five are routines, and one of them is
`_Live.__init__`, in `web/serve.py`.

That one *was* edited: it gained four lines of comment and one line of code, which sets
up an empty dictionary for the Setting's answers to be kept in. And DunneFlow puts it in
**edited only**, meaning: the text moved, the behaviour did not. Assigning an empty
dictionary to an attribute is internal computation; nothing moves through it, and nothing
it calls or touches changed.

That is correct, and it is the single most useful sentence a change report can produce.
A reviewer looking at 885 added lines of Python and TypeScript wants to know which of them
are *interesting*, and "these thirty-two are not, those are" is the answer.

**What it does not see**

The commits added 1,467 lines to the program in all, and 582 of them are in files this map
does not read: 480 in the dashboard's JavaScript (`shell.js` alone has 420), and the rest
in its stylesheet, its page, the plugins' manifests and the TypeScript reader's built
bundle. The comparison can say nothing about those. It does not pretend the change was
smaller, either: *About this map*, in the user guide, lists every kind of file it left out
under **Left out of it**.

## The four bands are the feature

| | |
|---|---|
| **added / deleted** | it is here and it was not, or the reverse |
| **behaves differently** | what it *does* changed — calls, arguments, boundaries |
| **edited only** | the text changed and the behaviour did not |
| **explained differently** | the prose changed and the code did not |

This pair has no routine in the fourth band, but it has one module: `render/mirror.py`,
whose own docstring was rewritten — what the file says about itself, counted apart from
what its routines do. A docstring sits
outside the routine's body: rewrite one and a naive comparison either misses it entirely or
reports it as a change to the code. Neither is true. *The explanation changed* is its own
fact.

Four answers where a text diff has one. And the reason for the split is the same reason
severity and confidence are kept apart on the cover: collapsing two different facts into
one row means you can no longer tell them apart, and the one you needed was the one that
got lost.

## Reading it in the code

Switch to **Code** with a comparison live and you get both lanes at once — the text lane
and the fact lane, stacked, with the file underneath and the changed lines marked. You saw
it in chapter 5 on `resolve/entrypoints.py`: *66 lines added and 17 lines deleted*, and
*5 routines here the comparison has something to say about*.

The deleted lines are shown **where they belong, with their own numbers**, and the pane says
so — they are not in the file you are reading, and pretending otherwise would corrupt every
line number below them.

---

That is the map read from the inside. The next four chapters turn to what it *thinks* of
the program: [9. What looks wrong](09-what-looks-wrong.md).
