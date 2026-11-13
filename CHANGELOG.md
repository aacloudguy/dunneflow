# Changelog

What changed between releases, for somebody deciding whether to upgrade and what it will
cost them. The session-by-session record of how each thing was found is kept outside this
repository; what is still owed is [`BACKLOG.md`](BACKLOG.md).

## 0.3.0

### Before you upgrade

- **A map made by 0.2.0 has to be analysed again.** The store went from schema 16 to 20
  and there is no migration between them. Opened for reading, an old map is refused with
  a sentence saying so. Opened by `analyze`, it is emptied and rebuilt from the tree. A
  snapshot sealed for comparison under 0.2.0 cannot be compared against a 0.3.0 one; seal
  a new pair.
- **`packaging/release.sh` no longer has a default signing identity.** Set
  `DUNNEFLOW_IDENTITY` before `sign` or `dmg`.
- **A script that POSTs to the dashboard must send `X-DunneFlow: 1`**, and must address
  it as `127.0.0.1` or `localhost`. The page does both by itself.

### New readers

- **Go**, on `go/types`. Interface calls name the bodies that may answer; a method is a
  boundary by its receiver's type (`os.Root`, `net.Dialer`); Cobra's command tree is drawn.
- **Rust**, on `syn`, vendored so nothing is fetched. Trait calls name the bodies that may
  answer. A Tauri command is a way in, and the front end's `invoke("name")` is linked to it
  across the two languages.
- **Java**, on javac's public tree API. Dispatch is said as dispatch and never guessed.
  Dependencies are read from this machine's Maven and Gradle caches where they are there,
  and never fetched. A tree of any size is attributed in batches.
- **C and C++ on libclang**, replacing the token reader. Macros are followed to what they
  expand to; a way in marked on a declaration is bound to its definition by the compiler's
  own identity for it.

### New in every language

- **`LOCAL_IPC`**: a Unix-domain socket or a named pipe is another process on this
  machine, and is no longer counted as the network.
- **Every unresolved call says where it stops**: outside the program and where, untyped
  and why, or dispatched and to how many bodies. Reach, `touches`, `impact` and
  `UNREACHABLE` cross a dispatched call into each body that may answer it.
- **What a type says and no spelling does** (Java): a call on a Spring Data repository is
  a database touch, a JAX-RS client call is a network touch where its jar is on the
  machine, and a method that fills a servlet's or Netty's slot is a way in.
- **A boundary a signature names** is shown beside what a body touches, and is never
  counted as a touch.
- A command no client sends is reported as dead code is. A map no model touched says
  nothing about models.

### Fixed

- **A Python call was drawn to the wrong routine when the program had exactly one of that
  name.** `rows.append(x)` was shown as a probable call to the program's only `append`,
  and likewise `get`, `update`, `count` and the other methods of Python's own types. On
  this tool's own map that was 893 of 1,146 inferred edges. Such a call is now resolved
  only by evidence (its class, a base class, an import) and is otherwise said to be
  untyped. A few true edges are lost with the false ones; see Known limits.
- **Code mode kept saying "reading what behaves differently…"** when the comparison
  answered after the file had been drawn. It now repaints when the answer arrives.

### Security

Reviewed as a whole for the first time; [`SECURITY.md`](SECURITY.md) says what is
defended and what is not. Five things were confirmed and fixed:

- The dashboard answered requests carrying another site's `Host` or `Origin`, so a page
  open in the same browser could read a map or start an analysis. Every request is now
  checked, and every response carries a content security policy.
- A reader's toolchain was started in the directory `analyze` was run from, where a
  `go.mod` naming a newer Go made `go` try to download and run it.
- A symbolic link out of the tree was read like any file, and a named pipe hung the
  analysis. Only files of the tree are read, and what is passed over is counted.
- `mcp`'s `open` took a path as a program name, and its `query` had no time limit.
- `query --docs` could write to the document store.

And three were not confirmed, and hardened all the same: what a `compile_commands.json`
may pass to clang, how a program's text is escaped on the dashboard, and what the lint
refuses to let into this codebase.

### Known limits

In [`BACKLOG.md`](BACKLOG.md), each with what would settle it: Go dependencies read as
*unknown* rather than *outside* (32); `--include-tests` does not bring back Rust's inline
test items (37); four rules files hold a common method name that needs measuring (38); a
Kotlin file in a Java tree is a missing class to javac (47). A Python method that shares a
name with one of Python's own, called on a value nothing types, reads as untyped (stated
residues). The Windows and Linux builds are unsigned, and each archive is published with
its SHA-256.

## 0.2.0

The second line of DunneFlow: the same tool as 0.1.0, rebuilt so that reading is modular.
TypeScript, C++ and Kotlin beside Python, the MCP server, and reading very large trees in
parts.

## 0.1.0

The first release. Kept on the `v1` branch and the `v1-final` tag.
