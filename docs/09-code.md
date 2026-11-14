# 9. Code

The source, as it was measured.

![Code mode showing cli.py with the comparison overlay switched off: the header reads "cli · 2,559 lines · 65 definitions · 257 marks" with "◇ changes", "margin 257" and "detach ⧉" buttons, and under it "Not showing the difference from 2026-11-13 03:56:47." The source is scrolled to cmd_serve, lines 2437 to 2462 tinted because the routine is the selection: "def cmd_serve(args: argparse.Namespace) -> int:", its docstring, "import webbrowser" and "from .web.serve import already_serving, serve, where", a long comment, then the first lines of its body, with cmd_serve and default_output_root underlined as links. In the margin beside lines 2439 and 2441 are the marks "import webbrowser" and "import .web.serve.already_se…". At the foot, "SOURCE Read from the content-addressed sidecar — the file as measured at 2026-11-13T03:56:51Z, not as the tree stands now." The navigator is filtered to the search "cmd_serve" and the inspector shows cli.cmd_serve](images/09-code.jpg)

## Where the text comes from

The line at the foot of the file, below the last line of source, reveals the origin:

> **SOURCE** — Read from the content-addressed sidecar — the file as measured at
> 2026-11-13T03:56:51Z, not as the tree stands now.

DunneFlow keeps the bytes it read, held by content hash. That is not a cache. It is what
lets you open a sealed snapshot months later, on a machine that has never held the tree,
and read the code that the map is actually about. If you edit the file on disk, this pane
does not change, because everything else on the screen is a
measurement of the old bytes.

## Links are lookups, not guesses

A name in the source that is underlined is a **link to the routine the resolver actually
resolved it to**, from the graph. It is not a text match on the name. Click it and you
select that routine, everywhere.

Where a call cannot be pinned to a column (because the same expression occurs more than
once on the line) the link goes to the margin instead of underlining a guess. DunneFlow
records that a call happened on a line; it does not record *where* on the line, and
inventing a position would be inventing a fact.

## The margin

The narrow column on the left carries what the line does that the line does not say:
which import it resolves through, which boundary it touches. The header counts them
(*257 marks*) and **▾ margin** folds the whole column away when you would rather just
read the code. The button carries the count, because *fold the margin* and *fold the
margin holding 257 things* are different offers.

**detach** opens the file in its own window, which is what you want when you are reading
code and driving the graph at the same time.

## Searching the text

The Code group in the navigator has its own search box, and it is a **different question**
from the one in the top bar. That one searches names and meanings. This one searches the
text: a word inside a comment, inside a string literal, on a line that is neither.

It answers files first, reading every file with a count on each, never truncated, and only
fetches one file's lines when you open it. A broad word touches most of the program, and
finding every line in every file up front would be ten queries a file for an answer you
did not ask for.

Each hit says where it sits, including which routine and which class, resolved from the line range with
innermost first.

![The Code group's own search box holding "webbrowser", with its Aa, |ab| and .* toggles; under it "4 lines in 2 files, of 181 files, 81,283 lines. The first is open; open any."; then cli.py open at the first hit, with "‹ 4 lines in 2 files", "◆ changes" and "open ▸", the comparison sentence "Against 2026-11-13 03:56:47: 559 lines added and 76 lines deleted", and lines 2435–2439 of the file, the last three — def cmd_serve, its docstring, and import webbrowser — highlighted](images/09-code-search.png)

The count is said against the whole program — *of 181 files, 81,283 lines* — so a word
that turns up in two files out of a hundred and eighty reads as rare, which it is.
The button on the left is the way back out, and it says where it goes: once a search has
answered it reads **‹ 4 lines in 2 files** and goes back to what the search found, and
with no answer it reads **‹ files** and goes back to the list. **open ▸** puts the file in
the main pane.

## When you are comparing

With a compared version set, the difference is drawn over the lines.

The picture at the top of this chapter was taken with one set and the overlay switched
off, which the line under the header says: *Not showing the difference from 2026-11-13
03:56:47.* Switched on, the same file reads *Against 2026-11-13 03:56:47: 559 lines added
and 76 lines deleted*, and then lists the forty-two routines in `cli.py` the comparison has
something to say about; that picture is in [comparing two
versions](14-comparing-two-versions.md).

The line-level difference is what `git diff` gives you and gives you better. The half
above it is the one nothing else can: **which routines behave differently, and in what
respect,** what they call, what they touch, what they take or return.

The overlay has its own switch, **◆ changes** in the header, because a file with four hundred marked lines is a file
whose *code* is harder to read than it was. See [comparing two
versions](14-comparing-two-versions.md).

---

Next: [10. Diagram](10-diagram.md)
