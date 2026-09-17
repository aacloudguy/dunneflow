# 5. Table and Code

Two views, one after the other, because they answer the same question at two distances:
*what is in here*, and *what does this actually say*.

## Table

Every routine in the program as a row.

![Table mode. A banner reads "SHOWING web.serve._reveal_linux row 834 of 925" with a "Go to it" button. Below it ROW DENSITY offers Compact, Comfortable and Spacious, with the note "Drag a column edge to resize — widths store in rem, so the scale control moves them too" and a "changes" button. The next line reads "against 2026-09-15 22:14:26: +3 added · 5 behave differently · ≈ 7 edited only · 910 unchanged". The table has ROUTINE, WHY and CONNECTED columns; anomalies._bounded and anomalies._looped_boundaries carry long explanatory paragraphs in the WHY column](images/05-table.jpg)

### It does not jump to your selection

> **SHOWING** `web.serve._reveal_linux` row 834 of 925 — **Go to it**

You are still on the routine you picked in chapter 3, and the table knows. What it does
*not* do is scroll there. It tells you where the row is and offers you a button.

This is the same principle as the diagram's **frame it**, and it runs through the whole
tool: **a list may not move the camera.** If you switched to Table to scan the whole
program, having it yank you to row 834 is exactly wrong. If you switched to Table to find
your selection, the button is right there. The tool declines to guess which you meant, and
the cost of asking is one click.

### The WHY column

This is the column that makes Table worth having. It is what the author of each routine
said about it — the docstring, the comment above it, the words a person chose.

Read a couple of the rows in the screenshot and you will see they are not one-liners.
`anomalies._looped_boundaries` carries a paragraph about which loops get reported and why,
with measured numbers in it. That prose was in the source; DunneFlow just put it next to
the name it belongs to.

**This is the argument for reading documentation as a first-class input.** A list of 925
function names is not orientation. A list of 925 function names with what their authors
said about them is a different artefact entirely.

### Row density and column widths

Compact, Comfortable, Spacious — and the note beside them:

> Drag a column edge to resize — widths store in `rem`, so the scale control moves them too.

Every dimension in DunneFlow is stored in `rem` rather than pixels. That means the
interface-scale setting moves *everything*, including columns you resized by hand. It is a
small thing that is invisible when it works and infuriating when it does not.

## Code

Press **Code**. Now you are looking at the file.

![Code mode showing web/serve.py. The header reads "web/serve.py · 3,894 lines · 124 definitions · 176 marks" with buttons for changes, margin 176 and detach. Below: "Against 2026-09-15 22:14:26: 174 lines added and 4 lines deleted. The deleted lines are shown where they belong, with their own numbers — they are not in the file you are reading." Then "6 routines here the comparison has something to say about. This is the lane a text diff cannot give: what a routine does, not which of its lines moved." listing module, pick_folder and reveal_dir as "behaves differently — call_args, calls, comments" and _desktop_session, _picker_order and _reveal_linux as "added". The source begins with the module docstring, and line 22 "import os" is marked as added. A footer reads "SOURCE Read from the content-addressed sidecar — the file as measured at 2026-09-15T22:14:29Z, not as the tree stands now."](images/05-code-and-the-fact-lane.jpg)

### It is not reading your disk

The footer is the important part:

> **SOURCE** Read from the content-addressed sidecar — the file as measured at
> 2026-09-15T22:14:29Z, not as the tree stands now.

DunneFlow kept a copy of every file it read. What you are looking at is the source *as it
was when the map was made* — not what is on disk this second. If you had edited
`serve.py` since, this pane would still show you the version the rest of the map is about,
because a map that mixed the two would be quietly lying in the most confusing way possible.

It also means this works after the tree is gone entirely.

### Every resolved call is clickable

> 3,894 lines · 124 definitions · **176 marks**

The marks are the calls DunneFlow resolved, and clicking one goes to the callee. Not by
matching the name — by looking up the answer the resolver already worked out.

Where it *cannot* be sure which text on the line is the call — because the same expression
occurs twice on one line — the mark goes in the margin instead of underlining a guess.
Inventing a column would be inventing a position.

### The lane a text diff cannot give

This is the paragraph to read twice:

> **6 routines here the comparison has something to say about.** This is the lane a text
> diff cannot give: what a routine *does*, not which of its lines moved.

| | |
|---|---|
| ○ `<module>` | behaves differently — call_args, calls, comments |
| ○ `pick_folder` | behaves differently — boundaries, call_args, calls, comments |
| ○ `reveal_dir` | behaves differently — call_args, calls, comments |
| + `_desktop_session` | added |
| + `_picker_order` | added |
| + `_reveal_linux` | added |

And separately, the text lane: *174 lines added and 4 lines deleted.*

Those are two different facts about the same change and DunneFlow reports both. 174 lines
moved; **6 routines actually do something different.** A text diff can only ever give you
the first number, and the first number is the one that tells you least.

Look at what `pick_folder` carries that the others do not: **boundaries**. Its set of
touches on the outside world changed. That is a much sharper statement than "this function
was edited", and it is the kind of thing you want to know before you review something.

[Chapter 8](08-two-versions.md) is about this properly.

---

Next: [6. Document](06-document.md)
