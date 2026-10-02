# 7. Table

Every routine as a row.

![Table mode, compared with the version before the Windows fix: a banner reading "SHOWING cli.cmd_serve row 62 of 1,550 as sorted here [Go to it]", a ROW DENSITY control offering Compact, Comfortable and Spacious beside "Drag a column edge to resize — widths store in rem, so the scale control moves them too." and a "◆ changes" switch, the line "against 2026-10-02 19:59:47: +23 added · ○ 64 behave differently · ≈ 32 edited only · 1,431 unchanged · 1 deleted — in 2026-10-02 19:59:47 only, so not listed here", and a table of ROUTINE, WHY, CONNECTIONS and CHANGED with the cmd_serve row tinted: "Open the map. Read-only throughout -- serving can never damage what it shows.", 1← 7→, —. Above it, the tail of the previous row's long WHY; below it cmd_touches 1← 14→ marked ○ as behaving differently, then common 1← 1→, detail 2← 2→, doc_progress 0← 1→, done 1← 2→ and main 1← 2→, all unchanged.](images/07-table.jpg)

The graph answers *what is connected to what*. This answers *what is here, and what did
its author say about it* and it is the view to reach for when you want to read rather
than explore.

## What a row says

Four columns.

| | |
|---|---|
| **ROUTINE** | the qualified name |
| **WHY** | the comment or docstring attached to it — the part the code itself cannot tell you |
| **CONNECTIONS** | how many routines call it and how many it calls, as `3← 7→` |
| **CHANGED** | what the comparison found about it, or `—` |

Where a routine has no comment and no docstring the WHY cell is empty, and that is worth
noticing: it is the honest answer, not a gap. **CONNECTIONS** is the column to sort by when
you want the spine of a program you have never read. It is the same in-and-out degree the
graph draws, as a number you can rank.

Every row is an ordinary selection. Clicking one picks it in the stack and fills the
inspector, exactly as a navigator row does, and every other view follows.

## Finding yourself in it

A large program's table is four thousand rows and about a quarter of a million pixels
tall, with your selection somewhere in the middle of it. So the banner at the top always
states where you are:

> SHOWING `cli.cmd_serve` — row 62 of 1,550 as sorted here · **Go to it**

The rank is the useful part. *Row 3,214 of 4,734* tells you whether scrolling is worth
it; **Go to it** saves you the trouble either way. The number is taken from the same
sorted list the table is drawing, so it cannot disagree with what you would find by
scrolling — and *as sorted here* says so, because the same routine has a different row in
[Document mode](08-document.md), which counts in the document's own order.

## Sorting and column widths

Click a column heading to sort by it; click again to reverse. All four sort, and all four
resize by dragging the edge. Sorting by **CHANGED** puts what changed at the top on the
first click rather than four thousand unchanged rows.

Widths are stored in `rem`, which means the interface scale slider in the top bar moves
them too. You can set the table up the way you like it and it stays that way at every scale.

## Row density

**Compact**, **Comfortable** or **Spacious**. Comfortable is the default. Compact is
worth it when you are scanning for a name; spacious when you are actually reading the WHY
column, which on a well-commented program runs to paragraphs.

## When you are comparing

With a compared version set, each row marks itself with what the comparison found about
it, whether it was added, deleted, behaving differently, or edited only, and a line above
the table counts them: *against 2026-10-02 19:59:47: +23 added · ○ 64 behave differently ·
≈ 32 edited only · 1,431 unchanged · 1 deleted — in 2026-10-02 19:59:47 only, so not listed
here*. A deleted routine has no row in a table of what the base holds, so it is counted
rather than left out without a word. That mark is free: it is drawn from an answer the
dashboard already holds, which is why it has its own switch, **◆ changes**, separate from
the code browser's. See [comparing two
versions](14-comparing-two-versions.md).

---

Next: [8. Document](08-document.md)
