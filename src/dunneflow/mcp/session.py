"""Which map is open, and the two doors onto a different one.

**One base at a time, switchable — `serve`'s shape exactly**, and the argument is the same:
this is an application about one version of one program, and the facts a tool answers with
all hang off a `_Base` that is built once and swapped whole. An agent gets the topbar's two
controls as tools rather than as a restart.

`_Live` is reused rather than reimplemented, and it was already headless: it holds the
stores, the locks and the two slots, it takes no HTTP object, and `tests/test_base_switch.py`
has been constructing one with no server since it was written. `_Handler` knows `_Live`;
`_Live` has never known `_Handler`. This module is the second thing on the near side of
that line.

**Nothing here is a second answer to a question `serve` already asks.** Program-versus-root
is `where()`, which decides by whether a directory *holds a map* and never by what it is
called (rule 30). Why there is nothing to serve is `no_map_here`, whose three sentences are
three different facts with three different things to do about them. A failed switch is
`why(exc)`. All of them are imported.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .. import revisions
from ..store import Store
from ..web.serve import NothingOpen, _Base, _Live, no_map_here, where
from . import Refused


class Session:
    """One reader's place in one output root."""

    def __init__(self, given: Path, revision: str | None = None,
                 log: Callable[[str], None] = lambda _msg: None) -> None:
        out_dir, out_root = where(given)
        self.out_root = out_root
        self._log = log
        self.live = _Live(out_dir / "source.db", out_dir, out_root)

        graph_db = revisions.resolve(out_dir, revisions.GRAPH, revision)
        if graph_db is not None:
            self.live.open(graph_db)
            self._say_open()
            return

        # **Cold is a state, not a failure — but only at a root.** A directory the reader
        # *named* that holds no map is a mistake worth refusing by name; a root with
        # nothing in it yet is where a double-clicked application begins, and `programs`
        # and `analyze` are exactly the tools for it. That is `serve`'s own test: `cold`
        # is `out_dir == out_root and not revision`.
        if out_dir != out_root or revision:
            raise FileNotFoundError(no_map_here(out_dir, out_root, revision))
        self._log(f"{out_root} holds no map yet; nothing is open")

    def _say_open(self) -> None:
        """One sentence, on stderr, naming what this process is now reading.

        Written once because it is said from two places and would otherwise be two
        slightly different sentences about one fact.
        """
        base = self.live.current
        where_ = self.live.out_dir.name
        self._log(f"reading {where_} at {base.revision or 'its only revision'}")

    # ---- what is open --- #

    @property
    def base(self) -> _Base:
        """The version on screen, or a refusal that says what to do about there not being one.

        Deliberately not softened to `None`. Sixty use sites in `serve.py` were left alone
        by that decision and this is the sixty-first: a tool that reaches for the base has
        no sensible answer without one.

        **`NothingOpen` carries no message**, which is the part worth knowing: the
        dashboard's sentence lives in `_refuse_without_base`, in the handler, because that
        is where it is delivered. So `why(exc)` over one produces `NothingOpen: ` and
        nothing else — a refusal with no reason in it, which is the empty answer this whole
        gate exists to prevent (rule 49). The sentence is minted here instead, once, and it
        names the two tools that can act on it (rule 89).
        """
        try:
            return self.live.current
        except NothingOpen as exc:
            raise Refused(
                "nothing is open — this server was started on an output root rather than "
                "on a program. Ask `programs` for what is here, then `open` one of them."
            ) from exc

    @property
    def store(self) -> Store:
        return self.base.store

    @property
    def opened(self) -> bool:
        return self.live.opened

    def close(self) -> None:
        self.live.close()

    # ---- the two doors --- #

    def programs(self) -> dict[str, Any]:
        """Every map under this root, with its revisions, and which one is open.

        `program_dirs` is the same question `analyze` asks to keep a program's own output
        out of its own corpus, and `serve` asks to fill the topbar: a directory holding a
        `graph*.db`, recognised by content and never by being called `output` (rule 30).

        The root itself is excluded when it is one of them only in the sense that it is
        listed under its own name — a root that holds a map *is* a program, which is what
        `where()` already decided on the way in.
        """
        here = self.live.out_dir if self.live.opened else None
        found = []
        for directory in sorted(revisions.program_dirs(self.out_root)):
            revs = [revisions.revision_of(p) or ""
                    for p in revisions.known(directory, revisions.GRAPH)]
            found.append({
                "program": directory.name,
                "revisions": revs,
                "open": directory == here,
            })
        return {"root": str(self.out_root), "programs": found,
                "opened": self.live.out_dir.name if self.live.opened else ""}

    def open(self, program: str = "", revision: str = "") -> dict[str, Any]:
        """Read a different program, a different revision, or both.

        **The failure is reported rather than raised**, because that is how `_Live` reports
        one: `switch_program` and `switch` are written to run on a thread nobody can catch
        from, so they end by *noting* a state. Calling them straight through is right here —
        an agent that gets its answer when the switch is done needs no polling — but the
        report is still where the outcome lives, so it is read back rather than assumed
        (rule 86: a guard can only see that a function was called, never what it returned).

        Nothing is closed or repointed until the new base is built, which is `open()`'s own
        rule: a stale program leaves the reader looking at what they had, with the store's
        own sentence in the report (rule 20).
        """
        if not program and not revision:
            raise Refused("name a program, a revision, or both — this changes nothing")

        out_dir = (self.out_root / program) if program else self.live.out_dir
        if program and not revisions.holds_a_map(out_dir):
            # Refused by name, and the sentence lists what is here: a refusal has to name
            # something the reader can act on, and a program name is not guessable (rule 89).
            raise FileNotFoundError(no_map_here(out_dir, self.out_root, revision or None))

        graph_db = revisions.resolve(out_dir, revisions.GRAPH, revision or None)
        if graph_db is None:
            raise FileNotFoundError(no_map_here(out_dir, self.out_root, revision or None))

        label = revisions.revision_of(graph_db) or out_dir.name
        if not self.live.claim(label):
            return {"opened": False,
                    "reason": "a switch is already running; this one was refused rather "
                              "than queued behind it"}

        if out_dir != self.live.out_dir:
            self.live.switch_program(out_dir, out_dir.name)
            # A program switch opens that program's **newest** revision, so a named one is
            # a second hop. Two calls rather than a third method, because the two things
            # `switch_program` does that `switch` does not — repointing the sidecars and
            # clearing every cache — are exactly what a program change needs and a
            # revision change must not do.
            report = self.live.progress()
            if report.get("state") == "done" and revision:
                if not self.live.claim(label):
                    return {"opened": False, "reason": "the slot was taken mid-switch"}
                self.live.switch(graph_db, revision)
        else:
            self.live.switch(graph_db, label)

        report = self.live.progress()
        if report.get("state") != "done":
            return {"opened": False,
                    "reason": report.get("reason", "the switch did not finish"),
                    "unfinished": bool(report.get("unfinished"))}
        base = self.base
        self._say_open()
        return {"opened": True, "program": self.live.out_dir.name,
                "revision": base.revision, "root": base.root}
