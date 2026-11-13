# Security

DunneFlow reads source it did not write, on the reader's own machine, and serves what it
found to their browser and to their agent. This says what it defends against, what it does
not, and how to report a problem. `ARCHITECTURE.md` says how each surface works;
`RULES.md` carries the false results the rules came from.

## What is trusted, and what is not

| | |
|---|---|
| **The tree being read** | **Not trusted.** Its file names, comments, strings, documents, build files and `compile_commands.json` are somebody else's text. Reading it must never run it, never fetch for it, and never let it say what is read from outside it. |
| **Other pages in the reader's browser** | **Not trusted.** The dashboard is on `127.0.0.1`, and so is every page the browser has open. |
| **The agent on the far side of `dunneflow mcp`** | Trusted to act for the reader, **and assumed to repeat what it reads.** Every tool result quotes the program, so the handshake says those words are data. |
| **The toolchains on `PATH`** (`go`, `cargo`, `java`, `node`, `clang++`, and libclang) | Trusted. A reader for a language is built and run with that language's own toolchain as this machine has it. A hostile `PATH` is outside what this tool can defend. |
| **A map** (`graph@….db` and its sidecars) | Trusted as the reader's own file. Opening a map somebody else made is opening their database. |

## What is defended, and where

- **Reading a tree does not run it.** No reader imports, builds or executes the program
  it reads; no annotation processor, build script or plugin runs (`-proc:none`, cgo off,
  `--offline --locked`). A compilation database may give clang include paths, defines, the
  language, the target and warnings, and nothing else; what it held beyond that is left out
  and named in the run's notes.
- **Nothing is fetched.** No reader, probe or build opens a network connection. Every
  toolchain is started in the reader's own directory with `GOTOOLCHAIN=local` and its
  manifest's environment, so a tree cannot ask for a toolchain to be downloaded.
- **Only files of the tree are read.** A symbolic link is followed only to a regular
  file inside the tree. A pipe, a socket or a device is never opened. Each one passed over
  is counted in the summary.
- **The dashboard answers this machine's reader only.** It binds loopback, refuses a
  request whose `Host` is not its own address and port, and refuses a `POST` that did not
  come from its own page. Every response carries a content security policy that loads
  script from the server alone, and forbids framing.
- **A program's text is shown as text.** Everything from the tree is escaped before it
  reaches the page, Markdown is rendered with raw HTML off and images never fetched.
- **A read does not write.** Read commands open stores `mode=ro`; `mcp`'s `query`
  classifies the statement as well, counts rows without holding them, and stops a statement
  after twenty seconds. `mcp`'s `open` takes a program name from the listing, never a path.

## What is not defended

- **Files a toolchain opens by name.** A header an `#include` reaches, or a `tsconfig.json`
  a project extends, is read by that language's own compiler, which follows links as it
  always does. What is stored from outside the tree is a name, not the file.
- **`dunneflow query --sql`.** It is the reader's own escape hatch on their own maps. The
  stores are read-only, and a statement may still `ATTACH` another database.
- **A rendered `.md` map in a Markdown viewer.** The map quotes the program. What a viewer
  does with raw HTML inside a quotation is the viewer's.
- **Resource exhaustion by a very large tree.** `analyze` refuses a tree over 20,000 files
  and says how to split it. There is no cap on one file's size.
- **Windows and Linux builds are not signed.** The macOS application is signed and
  notarised. Check a download against the SHA-256 published beside it.

## Before you share a map

A program's output directory is made to be read on the machine that wrote it. Its stores
hold paths relative to the tree that was read, and its sidecars hold that tree's source
and documents in full: sharing the directory is sharing the program.

One file in it names this machine: **`analysis.json`**, the record of the last run, holds
the absolute path of the tree and the command line that read it, because *Analyse it
again* fills its dialog from them. It is written `0600`. Leave it out of anything you
hand on.

## Reporting a problem

Open a private security advisory on the repository
(`https://github.com/aacloudguy/dunneflow/security/advisories/new`) rather than a public
issue. Say what you ran, on which platform, and what happened; a tree that reproduces it
is worth more than a description.
