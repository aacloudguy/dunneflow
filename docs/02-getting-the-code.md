# 2. Getting the code

**DunneFlow never asks a version control system anything.** It does not know what git is.
It has no Perforce client, no Lore integration, no credentials and no remotes. It doesn't
need it.

What it reads is **a directory of files on your disk**. How that directory got there is
your business, and that is deliberate rather than an omission: a tree handed to you on a
memory stick, a nightly build dropped on a share, a release tarball from a vendor, and a
`git clone` are all the same problem, and a tool that only understood one of them would
be useless for the case where you most need it: code you have been given and cannot ask
questions about.

So there are two steps and they are separate. **Get a directory. Point DunneFlow at it.**

## Git

```bash
git clone https://github.com/some-org/some-project ~/code/some-project
```

Another option:
```bash
gh repo clone some-org/some-project
```

Two things to check before you analyse it.

**Are you on the branch the work is actually on?** Cloning gets you the default branch,
which on many projects is months behind where people are working. A map of a stale branch
analyses perfectly and tells you about a program nobody is running.

```bash
git clone -b feat/the-branch-they-use https://github.com/some-org/some-project
```

**Is the whole tree there?** A shallow clone (`--depth 1`) is fine. DunneFlow only reads
the working tree, never the history. But a sparse checkout is not: files that are not on
disk are files DunneFlow cannot see, and it will confidently map a smaller program.

### A second version to compare against

[Comparing two versions](14-comparing-two-versions.md) needs two directories, not one
directory at two times. The cheapest way to get one is a worktree:

```bash
git worktree add ~/code/some-project-2026-09-08 <commit-or-tag>
```

That gives you a second complete tree sharing one object store, so it costs almost no
disk. Name it for **what it is** by including a date, a tag, or a release, because DunneFlow records
the name of the directory it read and that is what you will recognise the two versions by
later. `some-project-2026-09-08` reads well in the version strip; `tmp2` does not.

## Perforce

```bash
p4 client -o some-project-ws | p4 client -i
p4 sync //depot/some-project/...@2026-09-08
```

Sync to a workspace on local disk, then point DunneFlow at the workspace root. For a
second version to compare against, sync a second workspace at a different changelist or
label. Name the directory for the changelist or the release rather than for the
order you happened to make them in.

Perforce workspaces are often partial by design, through the client view. The same
warning as sparse checkouts applies: what is not on disk is not in the map.

## Lore

Pull to a shared store on the local system. DunneFlow will use the local directory.

```bash
cd ~
lore shared-store create lore://127.0.0.1:41337
lore clone lore://127.0.0.1:41337/my-project my-project-b --use-shared-store
cd ~/my-project-b
lore status
ls
```

## No version control at all

A zip, a tarball, a folder someone AirDropped you, a vendor drop. Unpack it and point
DunneFlow at it. This is the case DunneFlow is best at and the one nothing else can help
with: there is no history to read, no blame, no commit messages, only the code, which is
the only thing DunneFlow was ever reading. Whether the code was written by a team of humans or
AI agents, the goal of DunneFlow is to help understand the flow of the application from
this source code.

## What DunneFlow records about where it came from

A map is built to be **handed over** to a colleague as a copy, kept after the tree has
moved on, and can be opened on a machine that has never held the code. What DunneFlow
writes down about your application environment is a short and deliberate list.

**Not recorded: the path to the tree you analysed.** Every stored path inside a map is
relative and the root is never written down. It is one machine's directory layout, it is
wrong the moment anything moves, and it is wrong on every machine a copy reaches. It
might also leak the names of directories that include project names, so excluding these
names is a security choice.

There is exactly one exception, and it is on purpose: **a standards directory you named
with `--standards` is recorded by its full path**, because a rule quoted out of somebody
else's document is worth nothing without saying which document, on which machine, at which
moment. It lives in `standards.db` and nothing else in the map holds a path like it.

**Recorded: the leaf of the directory** each version was read from, such as `some-project-2026-09-08`,
not the path that led to it. Two versions of one program are two directories, so the leaf
is what you recognise them by.

That leaf is the **project's** directory, not the one you pointed at. Analyse
`~/code/some-project/src` and the map says `some-project`, because `src` identifies
nothing because every src-layout program in the world has one.

![The version strip: BASE DunneFlow 0.3.0 compared with dunneflow-before-parts · DunneFlow at 0804aa7 - before parts 0.1.0, a button reading "the compared version is older — from their versions", and "captured: compared first".](images/02-version-strip.png)

That strip is DunneFlow reading itself. The base was analysed from `DunneFlow/src/dunneflow`
and is called `DunneFlow`, the project's directory; the version it is compared with was read
from a worktree called `dunneflow-before-parts`, and carries the label it was given when it
was sealed. The green figures beside each are the versions the program states about itself,
and the button after them says which of the two is the older — read, as it says, from those
two versions.

**Recorded: the version the program states about itself**, if it states one, whether from
`pyproject.toml`, or a module-level `__version__`, each with the file that proves it.
Where the source says nothing, a version may be guessed from the directory's own name
(`app-1.2.3`, `some-project-2026-09-08`) and is marked as a guess everywhere it appears.

This is why the directory name matters. It is the only handle you get.

---

Next: [3. The start page](03-the-start-page.md)
