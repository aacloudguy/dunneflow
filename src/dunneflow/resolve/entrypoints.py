"""Ways in that are declared rather than written -- bound, minted and recorded.

Packaging metadata is the most reliable entrypoint source there is: a `[project.scripts]`
entry or a `package.json` `bin` is not a heuristic, it is the literal contract between the
program and whoever installs it. Anything found here outranks a decorator or a naming
convention, and `Entrypoint.declared` is the field that says so.

**This module reads no manifest.** `resolve/manifests` does that, one provider per
filename, and hands back `ManifestEntry` records that name a target without having looked
for it. What happens here is the half that needs the store: minting an id, finding the
routine a target names, and writing the row. Keeping the two apart is what lets a provider
be six lines of parsing with its own sentence, and it is why there is **one** binder for
six manifests rather than six that will disagree (rule 51).

**Three states for a way in, never two** (design rule 21). Declared and bound is what a
reader clicks through; declared and **unbound** is a real answer with a reason; not
declared at all is everything a language reader recognised in code.

`binding_note` is where the second of those is worded and decided, and it gives **five
answers of which one is a fault** -- see rule 98, which this chunk was the second in two
to pay for. `src/main.rs` is Rust and this build reads no Rust; `packages/api-types`
declares a file that is read and holds no routine. Neither is a defect in the program
being read, and `anomalies` asks the same function rather than matching its wording.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..ingest import LANG_SUFFIX
from ..schema import Entrypoint, make_id, stored_path
from ..store import Store
from . import languages, manifests
from .manifests import ManifestEntry, ManifestReading, TargetKind


def _target_routine(store: Store, module: str, attr: str) -> str | None:
    """Find the routine a `module:attr` console-script target names.

    **A module name is relative to its own package root, and a nested manifest's root is
    not the analysed tree's.** `../beads-main/integrations/beads-mcp/pyproject.toml`
    declares `beads-mcp = "beads_mcp.server:main"`, and that module is stored as
    `integrations.beads-mcp.src.beads_mcp.server` because module names here are derived
    from the tree that was analysed. An exact match answers *no* and the map then says a
    real front door leads nowhere -- which is a claim about beads that is not true.

    So: the exact name first, and a **dotted-suffix** match only if that fails. This is
    not rule 5's forbidden bare-name match -- `beads_mcp.server` is a dotted path, matched
    at a segment edge, and the match is taken **only when exactly one routine has it**
    (`LIMIT 2`, which is `_resolve_routine`'s own remedy beside this one). Two copies of a
    package in one monorepo leave the declaration unbound and saying so, which is the
    right answer rather than a coin toss.
    """
    row = store.query(
        "SELECT id FROM routines WHERE module = ? AND name = ? LIMIT 1", (module, attr)
    )
    if row:
        return str(row[0]["id"])
    # A Typer/Click application object rather than a function: the way in is the
    # module that builds it.
    row = store.query(
        "SELECT id FROM routines WHERE module = ? AND name = '<module>' LIMIT 1", (module,)
    )
    if row:
        return str(row[0]["id"])
    for name in (attr, "<module>"):
        found = store.query(
            "SELECT id FROM routines WHERE module LIKE ? AND name = ? LIMIT 2",
            (f"%.{module}", name),
        )
        if len(found) == 1:
            return str(found[0]["id"])
    return None


def _target_file(store: Store, where: str, target: str) -> str | None:
    """Find the module scope of the file a declaration points at.

    A `bin` or a `[[bin]]` names a **file**, and the way in is that file's module scope --
    the same answer `_target_routine` gives an application object, for the same reason:
    what runs when the command is typed is everything at that file's top level.

    The path is resolved **relative to the manifest**, never to the analysed tree.
    `./cli.js` in `packages/api-types/package.json` means a file beside that manifest, and
    joining it to the root would find a different file or none at all. `PurePosixPath`
    the whole way, because a stored path is POSIX by rule 93 and a manifest's own
    separators are too -- both `package.json` and `Cargo.toml` spell a path with forward
    slashes whatever platform wrote the file.
    """
    row = store.query(
        "SELECT id FROM routines WHERE file = ? AND name = '<module>' LIMIT 1",
        (_resolved(where, target),),
    )
    return str(row[0]["id"]) if row else None


def _resolved(where: str, target: str) -> str:
    """A manifest's target, as the key the store holds it under.

    **Relative to the manifest, never to the analysed tree.** `./src/index.ts` in
    `packages/api-types/package.json` means a file beside that manifest; joined to the
    root it would name a different file or none at all.

    `./src/index.ts` and `src/index.ts` are the same file and two different keys, so both
    arrive here and one spelling leaves (rule 60 -- a stored path is a key before it is a
    location, and rule 93 for its separator). One function, because the binder above and
    the sentence `binding_note` prints must resolve a declaration the same way or the map
    says a file is missing that it bound a moment ago (rule 51).
    """
    base = stored_path(Path(where).parent) if "/" in where else ""
    joined = f"{base}/{target}" if base and base != "." else target
    return stored_path(Path(joined))


@dataclass(frozen=True, slots=True)
class BindingNote:
    """Why a declared way in reached no routine, and whether that is a **known limit**.

    Two halves of one judgement, returned together so they cannot disagree (rule 13). The
    sentence is what a reader is shown; `known_limit` is what `anomalies` decides on, and
    a guard that matched the wording instead would be rule 30 in the guard.
    """

    sentence: str
    known_limit: bool


def _declaration(store: Store, ep_id: str) -> tuple[TargetKind, str, str]:
    """One declared way in's target, its kind, and the manifest that declared it.

    The manifest's own path is needed because a target is relative **to it** --
    `./src/index.ts` in `packages/api-types/package.json` is not `./src/index.ts` from the
    root -- and `Entrypoint` carries no `file`. One query, so the two callers below cannot
    resolve the same declaration two ways.
    """
    row = store.query(
        "SELECT target_kind, target_expr, file FROM entrypoints WHERE id = ?", (ep_id,)
    )
    if not row:
        return TargetKind.NONE, "", ""
    return (TargetKind(row[0]["target_kind"]), str(row[0]["target_expr"] or ""),
            str(row[0]["file"] or ""))


def binding_note(store: Store, ep_id: str) -> BindingNote:
    """Why this declaration reached no routine -- **five answers, and four are not faults**.

    A blank beside a declared way in reads as *this program is broken*, and four times in
    five it means something duller and entirely expected. DunneNote declares three Rust
    binaries, and every one is a real way into that application this map cannot open;
    `packages/api-types` declares `./src/index.ts`, which is 289 lines of
    `export type { X } from './X'` and declares no routine because there is nothing to
    declare. Reporting either as *leads nowhere* is a claim about somebody else's program
    that is not true -- chunk 11's 83 false BROKENs, one surface over, and this one was
    **found the same way**: by running it and reading the anomaly it produced.

    The one place this is worded and decided (rule 51): `flows`, `waysin`, the Markdown
    renderer, `cmd_analyze` and `anomalies` all ask here.

    Only the fourth is a fault. A manifest naming a file the walk never found is a
    declaration that has gone stale, and that is worth a reader's attention.
    """
    kind, target, where = _declaration(store, ep_id)
    if kind == TargetKind.NONE or not target:
        return BindingNote(
            "the declaration names a target rather than a file, and this tool cannot "
            "turn one into a place to open", True)

    suffix = Path(target).suffix.lower()
    if kind == TargetKind.FILE:
        lang = LANG_SUFFIX.get(suffix) if suffix else None
        if lang is None:
            return BindingNote(
                f"no reader here claims `{suffix}`" if suffix
                else f"`{target}` names no file this tool can read", True)
        if lang not in languages.read(store):
            return BindingNote(f"`{target}` is {lang}, and this map holds none of it",
                               True)
        rel = _resolved(where, target)
        if not store.query("SELECT 1 FROM files WHERE path = ?", (rel,)):
            return BindingNote(
                f"`{target}` is not a file this map holds — the declaration names "
                f"`{rel}`, and the walk found no such file", False)
        return BindingNote(
            f"`{rel}` is read and declares no routine — a file of re-exports, or one "
            f"with nothing at its top level", True)

    return BindingNote(f"`{target}` named no routine in this map", False)


def _mint(entry: ManifestEntry, reading: ManifestReading) -> str:
    """The id of one declared way in.

    **The package root's declarations keep the bare name, and a member's does not.** A
    root declaration is the program's own and its name is the contract a reader types;
    `make_id("script", name)` has minted those since v1 and every stored map agrees. A
    member's `bin` is identified by the member *and* the name, because two members may
    each declare `serve` and `INSERT OR REPLACE` would keep whichever was walked last --
    a way in disappearing with no error anywhere (rule 35's shape).

    Keeping the root form unqualified is also what holds the golden: Society's `src/`
    holds no nested manifest at all, so its four script ids are byte-identical to v1's.
    """
    return (make_id("script", entry.name) if reading.at_root
            else make_id("script", reading.where, entry.name))


def entrypoints_from_manifests(readings: list[ManifestReading], store: Store
                               ) -> list[Entrypoint]:
    """Bind, mint and record every way in the manifests declared.

    Returns what was written, root declarations first, so a caller reporting on the run
    reads the program's own before its members'.

    **A collision is refused, not overwritten.** Two declarations landing on one id is
    two ways in the map can only hold one of, and `INSERT OR REPLACE` would make the
    second win silently. The first is kept and the second is named in the store's note
    for its manifest, because a refusal a reader cannot see is the failure rule 49 is
    about.
    """
    found: list[Entrypoint] = []
    taken: dict[str, str] = {}
    for reading in sorted(readings, key=lambda r: (not r.at_root, r.where)):
        for entry in reading.entries:
            ident = _mint(entry, reading)
            if ident in taken:
                continue
            taken[ident] = reading.where
            if entry.target_kind == TargetKind.MODULE_ATTR:
                module, _, attr = entry.target.partition(":")
                routine_id = _target_routine(store, module, attr or "main")
            elif entry.target_kind == TargetKind.FILE:
                module = ""
                routine_id = _target_file(store, reading.where, entry.target)
            else:
                module = ""
                routine_id = None
            ep = Entrypoint(
                id=ident, kind=entry.kind, name=entry.name, routine_id=routine_id,
                module=module, evidence=entry.evidence, target_kind=entry.target_kind,
                # **The target, carried as a field.** `resolve/cli.py` and
                # `render/markdown.py` both used to recover it with
                # `evidence.rsplit("= ", 1)[-1]` -- parsing a sentence written for a
                # person to get back a value that was in hand when the sentence was
                # built. `target_expr` has existed since the family was written.
                target_expr=entry.target,
                declared=True,
            )
            found.append(ep)
            store.add_entrypoint(ep, file=reading.where)
    store.conn.commit()
    return found


def collisions(readings: list[ManifestReading]) -> list[str]:
    """Declarations that two manifests give one identity, in sentences.

    Computed rather than recorded during the write, so the sentence can be printed by a
    caller that never opened the store -- and so the rule has one statement rather than
    a write path and a report that can drift apart (rule 13).
    """
    taken: dict[str, str] = {}
    out: list[str] = []
    for reading in sorted(readings, key=lambda r: (not r.at_root, r.where)):
        for entry in reading.entries:
            ident = _mint(entry, reading)
            if ident in taken:
                out.append(f"{reading.where}: `{entry.name}` is already declared by "
                           f"{taken[ident]} — the first is kept")
            else:
                taken[ident] = reading.where
    return out


def entrypoints_from_packaging(root: Path, store: Store,
                               relative_to: Path | None = None) -> list[Entrypoint]:
    """Every way in the manifests **at one directory** declare, read and bound.

    The generalisation of the function that read `[project.scripts]` out of
    `pyproject.toml` and nothing else. The signature is unchanged and so is its meaning:
    `root` is where packaging metadata lives, and `relative_to` is the tree every stored
    path is relative to -- **not** always `root`, because a `src/` layout puts the
    metadata one directory above the code. So this is the one place a stored path
    legitimately climbs out of the analysed tree, and it is written `../pyproject.toml`
    rather than made relative to a second root of its own.

    That matters because `queries.py` selects `COALESCE(r.file, e.file)` -- these values
    land in the *same* column as a routine's file, and a column holding two kinds of path
    is a column a reader cannot act on. One meaning per channel.

    `cmd_analyze` does not call this: it has the nested manifests the walk found as well,
    and hands both lists to `entrypoints_from_manifests`. This is the one-directory case,
    which is what a caller holding only a package root wants.
    """
    at_root = sorted(root / n for n in manifests.MANIFEST_FILES if (root / n).is_file())
    readings = manifests.read_all(at_root, [], relative_to=relative_to or root)
    return entrypoints_from_manifests(readings, store)


def record_manifests(readings: list[ManifestReading], store: Store) -> None:
    """Write the `manifests` table: what was read, and what each file declared."""
    store.replace_manifests([
        (r.where, r.filename, r.name, r.version.value if r.version else "",
         len(r.entries), int(r.at_root), " · ".join(r.notes))
        for r in readings
    ])
