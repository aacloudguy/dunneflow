# 5. Table and Code

Two views, one after the other, because they answer the same question at two distances:
*what is in here*, and *what does this actually say*.

## Table

Every routine in the program as a row.

![Table mode. A banner reads "SHOWING resolve.entrypoints.entrypoints_from_manifests row 886 of 1,550 as sorted here" with a "Go to it" button. Below it ROW DENSITY offers Compact, Comfortable and Spacious, with the note "Drag a column edge to resize — widths store in rem, so the scale control moves them too" and a "changes" button. The next line reads "against 2026-10-02 19:59:47: +23 added · 64 behave differently · ≈ 32 edited only · 1,431 unchanged · 1 deleted — in 2026-10-02 19:59:47 only, so not listed here". The table has ROUTINE, WHY, CONNECTIONS and CHANGED columns, and the selected row, entrypoints_from_manifests, is at the top of it: 2← 6→, a hollow circle under CHANGED, and a WHY cell that is a whole paragraph, beginning "Bind, mint and record every way in the manifests declared." and going on to explain the tree argument and why a collision is refused rather than overwritten. Below it entrypoints_from_packaging begins "Every way in the manifests at one…", 0← 2→. The comparison strip at the top reads "you chose: the compared version is older"](images/05-table.jpg)

*The screenshots in this chapter were taken with the comparison's direction already turned
round, which is why the strip says **you chose: the compared version is older** and the
counts say **+23 added**. Chapter 8 is about that button. Left alone, it says
**assuming the compared version is newer** and the same 23 routines are counted as
**−23 deleted**.*

### It brings your selection into view once

> **SHOWING** `resolve.entrypoints.entrypoints_from_manifests` row 886 of 1,550 as sorted here — **Go to it**

You are still on the routine you picked in chapter 3, and the table knows. It says where the
row is, and *as sorted here* is meant literally: sort by another column and the row has
another number.

Arriving with a selection, the table scrolls to it once — a selection 886 rows down is an answer
nobody can see, so it is brought into view. **After that it leaves you alone.** Scroll away
to read the rows around it and nothing drags you back on the next repaint; an automatic move
may not fight a deliberate one. When you want your row again, **Go to it** is the button,
and the cost of asking is one click.

### The WHY column

This is the column that makes Table worth having. It is what the author of each routine
said about it — the docstring, the comment above it, the words a person chose.

Read the selected row in the screenshot and you will see it is not a one-liner: it says why
the routine takes the analysed tree, and why two declarations landing on one id are refused
rather than overwritten. `entrypoints_from_packaging`, under it, carries a paragraph about
why this is the one place a stored path legitimately climbs out of the analysed tree, and
what would break if it did not. That
prose was in the source; DunneFlow just put it next to the name it belongs to.

**This is the argument for reading documentation as a first-class input.** A list of
1,550 function names is not orientation. A list of 1,550 function names with what their authors
said about them is a different artefact entirely.

### Row density and column widths

Compact, Comfortable, Spacious — and the note beside them:

> Drag a column edge to resize — widths store in `rem`, so the scale control moves them too.

Every dimension in DunneFlow is stored in `rem` rather than pixels. That means the
interface-scale setting moves *everything*, including columns you resized by hand. It is a
small thing that is invisible when it works and infuriating when it does not.

## Code

Press **Code**. Now you are looking at the file.

![Code mode showing resolve/entrypoints.py. The header reads "resolve.entrypoints · 357 lines · 13 definitions · 21 marks" with buttons for changes, margin 21 and detach. Below: "Against 2026-10-02 19:59:47: 66 lines added and 17 lines deleted. The deleted lines are shown where they belong, with their own numbers — they are not in the file you are reading." Then "5 routines here the comparison has something to say about. This is the lane a text diff cannot give: what a routine does, not which of its lines moved." listing _target_routine as "behaves differently — call_args, calls, params, comments, docstring", entrypoints_from_manifests as "behaves differently — call_args, calls, params, docstring", entrypoints_from_packaging as "behaves differently — call_args", and _import_prefixes and exact as "added". The source begins with the module docstring, "Ways in that are declared rather than written -- bound, minted and recorded." In the navigator, CODE reads "entrypoints.py: 357 lines, 37 clickable". A footer reads "SOURCE Read from the content-addressed sidecar — the file as measured at 2026-10-02T19:59:52Z, not as the tree stands now."](images/05-code-and-the-fact-lane.jpg)

### It is not reading your disk

The footer is the important part:

> **SOURCE** Read from the content-addressed sidecar — the file as measured at
> 2026-10-02T19:59:52Z, not as the tree stands now.

DunneFlow kept a copy of every file it read. What you are looking at is the source *as it
was when the map was made* — not what is on disk this second. If you had edited
`entrypoints.py` since, this pane would still show you the version the rest of the map is about,
because a map that mixed the two would be quietly lying in the most confusing way possible.

It also means this works after the tree is gone entirely.

### Every resolved call is clickable

> 357 lines · 13 definitions · **21 marks**

Two things are drawn over the source, and they answer different questions. The
navigator's CODE group counts the first: *357 lines, 37 clickable*. Those are the calls
DunneFlow resolved, underlined where they are written, and clicking one goes to the callee.
Not by matching the name — by looking up the answer the resolver already worked out.

The **marks** are the second: the margin, which says what a line *is*. A boundary with its
direction, a SQL operation with its table, a constant, an import, a governance id. **margin
21** folds them down to a glyph beside the line number when you want the room for the code.

Where DunneFlow *cannot* be sure which text on a line is the call — because the same
expression occurs twice on it — the link goes in the margin too, instead of underlining a
guess. Inventing a column would be inventing a position.

### The lane a text diff cannot give

This is the paragraph to read twice:

> **5 routines here the comparison has something to say about.** This is the lane a text
> diff cannot give: what a routine *does*, not which of its lines moved.

| | |
|---|---|
| ○ `_target_routine` | behaves differently — call_args, calls, params, comments, docstring |
| ○ `entrypoints_from_manifests` | behaves differently — call_args, calls, params, docstring |
| ○ `entrypoints_from_packaging` | behaves differently — call_args |
| + `_import_prefixes` | added |
| + `exact` | added |

And separately, the text lane: *66 lines added and 17 lines deleted.*

Those are two different facts about the same change and DunneFlow reports both. 83 lines
moved; **5 routines actually do something different.** A text diff can only ever give you
the first number, and the first number is the one that tells you least.

Look at what the first two carry that the third does not: **params**. Their signatures
changed — `entrypoints_from_manifests` now takes the analysed tree — and that is a much
sharper statement than "this function was edited". It is the kind of thing you want to
know before you review something.

Scroll down to line 279 and the change itself is in the file, where it belongs:

![A close-up of resolve/entrypoints.py, lines 270 to 285, inside entrypoints_from_manifests, every line tinted because the routine is the selection. Line 279 reads "module, _, attr = entry.target.partition(":")". Under it, on a red background with the old line number 232 and a minus sign, is the deleted line "routine_id = _target_routine(store, module, attr or "main")". Under that, on green with plus signs, the new lines 280 and 281: "routine_id = _target_routine(store, module, attr or "main"," and "_import_prefixes(reading.where, tree))". Line 282 continues "elif entry.target_kind == TargetKind.FILE:", and the longest lines run off the right-hand edge](images/05-margin-mark.png)

The deleted line keeps **its own number, 232** — its place in the older file — because it is
not in the file you are reading and must not borrow a number that is. The two added lines
are what this change was: the call that finds the routine a console script names is now
told which directories it climbed through, by `_import_prefixes`, one of the two routines
the fact lane lists as added.

[Chapter 8](08-two-versions.md) is about this properly.

---

Next: [6. Document](06-document.md)
