# 8. Two versions

The map we have been reading holds two readings of DunneFlow: the source as it stands, and
a snapshot taken from the commit *before* Linux support landed.

That makes this chapter a fair test. Linux support was a real piece of work — five commits,
a new picker, a new reveal path, a maps root that asks the platform instead of assuming
macOS. **Can DunneFlow tell you what changed, without being told?**

## Making the pair

```bash
uv run dunneflow analyze <the older tree>/src/dunneflow --name dunneflow
uv run dunneflow revisions output/dunneflow --seal --label "DunneFlow at 875499c - before Linux"
uv run dunneflow analyze src/dunneflow --name dunneflow
```

Analyse the older tree, **seal** it, then analyse the newer one. Sealing is what stops the
next analysis overwriting it: a sealed snapshot is never re-analysed in place, so it stays
readable after the tree it came from is gone.

## Which one is newer?

Here is the first thing DunneFlow does that most tools would not.

![The comparison strip reading "BASE DunneFlow 0.1.0 compared with DunneFlow-before-Linux · DunneFlow at 875499c — before Linux 0.1.0", followed by a button reading "you chose: the compared version is older" and the note "captured: compared first". The table's summary line reads "against 2026-09-15 22:14:26: +3 added · 5 behave differently · ≈ 7 edited only · 910 unchanged", with +3 in green. The navigator's CHANGES group reads "3 added · 5 behaving differently · 1 module explained differently · 7 edited without changing what they do"](images/06-comparison-direction.jpg)

It does not know which version is newer, and **it will not guess from the timestamps.**

The only instant DunneFlow records is when the *bytes were read*. That says nothing about
when the code is from — I made both of these snapshots within three seconds of each other,
from trees a week apart. Capture order and code order are different facts.

Both snapshots also report version `0.1.0`, so the version numbers cannot break the tie
either. So the strip says, in as many words:

> assuming the compared version is newer

…and makes it a **button**. Click it and you get three states: the tool's assumption, *you
chose: the compared version is newer*, and *you chose: the compared version is older*. The
direction is yours, because it decides whether every changed row reads as **arrived** or as
**gone** — and getting that backwards would invert the meaning of the entire screen.

Beside it, separately, the one thing that *can* be observed:

> captured: compared first

An observation, placed next to the assumption and never dressed up as a correction to it.
*We may infer, so long as we say we did.*

With the direction set correctly, the summary reads:

> against 2026-09-15 22:14:26: **+3 added** · ○ **5 behave differently** · ≈ **7 edited
> only** · **910 unchanged**

## What it found

Here is the payoff. Without being told anything about Linux, DunneFlow reports:

**3 added**

| | |
|---|---|
| `_desktop_session` | is there a screen to put a window on? |
| `_picker_order` | which dialog to try first |
| `_reveal_linux` | show a directory, by the two means a Linux desktop offers |

Exactly the three routines the work added. Not approximately — exactly.

**5 behaving differently**

`platform_output_root`, `pick_folder`, `reveal_dir`, `common`, and module-level code. Those
are precisely the five places that had to change to make room for the new ones: where maps
go, how a folder is chosen, how a directory is revealed, and the command-line help.

**7 edited only**

And this is the band that proves the tool is doing something a text diff cannot. Among them:
`_interrupt_group` and `_kill_group`.

Both of those functions *were* edited in the Linux work — four hand-written exception
tuples were replaced with one shared name. Every line of both changed. And DunneFlow puts
them in **edited only**, meaning: the text moved, the behaviour did not.

That is correct, and it is the single most useful sentence a change report can produce.
A reviewer looking at 174 changed lines wants to know which of them are *interesting*, and
"these two are a rename, those five are real" is the answer.

**1 module explained differently**

`web/roots.py`. Its module docstring was rewritten — the paragraph naming
`~/Library/Application Support` became one naming all three platforms. No code changed at
all.

That is a band of its own because a docstring sits outside the routine's body: rewrite one
and a naive comparison either misses it entirely or reports it as a change to the module.
Neither is true. *The explanation changed* is its own fact.

## The three bands are the feature

| | |
|---|---|
| **added / deleted** | it is here and it was not, or the reverse |
| **behaves differently** | what it *does* changed — calls, arguments, boundaries |
| **edited only** | the text changed and the behaviour did not |
| **explained differently** | the prose changed and the code did not |

Four answers where a text diff has one. And the reason for the split is the same reason
severity and confidence are kept apart on the cover: collapsing two different facts into
one row means you can no longer tell them apart, and the one you needed was the one that
got lost.

## Reading it in the code

Switch to **Code** with a comparison live and you get both lanes at once — the text lane
(*174 lines added and 4 lines deleted*) and the fact lane (*6 routines here the comparison
has something to say about*), stacked, with the file underneath and the changed lines
marked.

The deleted lines are shown **where they belong, with their own numbers**, and the pane says
so — they are not in the file you are reading, and pretending otherwise would corrupt every
line number below them.

---

That is the tour. Back to the [index](README.md), or on to the
[reference guide](../README.md) for the parts this walked past.
