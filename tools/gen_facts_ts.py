"""`schema.py` as TypeScript, generated — because transcribing it is how a fact stops existing.

`PLAN-v2.md` §1c: *"`dunneflow ingest-schema --json` emits a descriptor of `schema.py`, and
the TypeScript plugin's types are generated from it at build time, so a `SCHEMA_VERSION`
bump breaks the plugin's build rather than its output."* This is that generator, and it
exists because the hand-written version was wrong within an hour: the reader filled a
`NetworkCall.library` field that `schema.py` has not got, the codec dropped it and named it
in `FileFacts.errors` — which `WalkStats` counts as a **failed file**, so every TypeScript
file with a network call in it would have been reported as unreadable. A type error at
build time instead.

**Python and not Node**, so `tests/test_typescript.py` can regenerate and compare without
starting a toolchain. `npm run schema` shells to it, and the test is what actually holds
the committed file to the schema — a generator nobody runs is a transcription with extra
steps.

    uv run python tools/gen_facts_ts.py            # print
    uv run python tools/gen_facts_ts.py --write    # write the plugin's facts.ts
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
import typing
from enum import Enum
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dunneflow import schema  # noqa: E402
from dunneflow.runtime import resource_root  # noqa: E402

OUT = resource_root() / "plugins" / "typescript" / "src" / "facts.ts"

# The reader's half of the contract. `DocFacts` and its parts are the *other* walk's, and a
# source reader that could name them would be a source reader that could emit them.
ROOT = schema.FileFacts

HEADER = '''/**
 * `schema.py`'s types, as this reader has to emit them.
 *
 * **GENERATED — do not edit.** `uv run python tools/gen_facts_ts.py --write`, or
 * `npm run schema`. `tests/test_typescript.py` regenerates it and compares, so a drift
 * between this file and `schema.py` fails the suite rather than the map.
 *
 * Transcribing it by hand was tried and was wrong inside an hour: the reader filled a
 * `NetworkCall.library` field that does not exist, the codec dropped it and named the drop
 * in `FileFacts.errors`, and `WalkStats` counts a file with an error as a **failed** file —
 * so every TypeScript file holding a network call would have been reported unreadable, in a
 * map that otherwise looked perfect. Generated, it is a compile error.
 *
 * A field left at its default is omitted on the wire, which is what `codec.encode` does on
 * the other side: Society's 43,926 `CallArg`s each carrying `"splat":false` is most of a
 * payload. So a field with a default is optional here and the reader writes only what it
 * set.
 *
 * `lang` is absent from `Routine` and `DataStructure` on purpose — it is the host's to
 * write (`ingest.stamp_lang`), and a reader that sent it would be offering a second answer
 * to a question the file has already answered.
 */

/** `schema.SCHEMA_VERSION`. A plugin declaring another number is refused by name. */
export const SCHEMA_VERSION = {version};
'''


def _ts_type(hint: Any, where: str) -> str:
    """One Python annotation as a TypeScript type. Refuses what it has not been taught."""
    origin = get_origin(hint)
    if origin is Literal:
        return " | ".join(f'"{a}"' for a in get_args(hint))
    if origin in (list, tuple):
        args = get_args(hint)
        inner = _ts_type(args[0], where) if args else "unknown"
        return f"{inner}[]"
    if origin is dict:
        args = get_args(hint)
        return f"Record<string, {_ts_type(args[1], where) if len(args) > 1 else 'unknown'}>"
    if origin is not None or isinstance(hint, typing._SpecialForm):  # noqa: SLF001
        arms = [a for a in get_args(hint) if a is not type(None)]
        if len(arms) == 1:
            return _ts_type(arms[0], where)
        raise TypeError(f"{where}: a union this generator has not been taught")
    if isinstance(hint, type):
        if issubclass(hint, Enum):
            return hint.__name__
        if hint is bool:
            return "boolean"
        if hint is int or hint is float:
            return "number"
        if hint is str:
            return "string"
        if dataclasses.is_dataclass(hint):
            return hint.__name__
    raise TypeError(f"{where}: {hint!r} is a shape this generator has not been taught")


def _optional(hint: Any) -> bool:
    """Does `None` belong to this type? Then the field may be `null` as well as absent."""
    origin = get_origin(hint)
    if origin is None and not isinstance(hint, typing._SpecialForm):  # noqa: SLF001
        return False
    return type(None) in get_args(hint)


def _reachable(root: type) -> tuple[list[type], list[type]]:
    """Every record and every enumeration the root can carry, in discovery order."""
    records: list[type] = []
    enums: list[type] = []
    seen: set[type] = set()

    def walk(cls: type) -> None:
        if cls in seen:
            return
        seen.add(cls)
        records.append(cls)
        for name, hint in typing.get_type_hints(cls).items():
            for part in _parts(hint):
                if isinstance(part, type) and issubclass(part, Enum):
                    if part not in enums:
                        enums.append(part)
                elif isinstance(part, type) and dataclasses.is_dataclass(part):
                    walk(part)
            del name

    def _parts(hint: Any) -> list[Any]:
        args = get_args(hint)
        if not args:
            return [hint]
        if get_origin(hint) is Literal:
            return []
        out: list[Any] = []
        for a in args:
            out.extend(_parts(a))
        return out

    walk(root)
    # The root last, so a reader reads its parts before the thing that holds them.
    records.remove(root)
    return [*records, root], enums


def _host_owned(cls: type) -> frozenset[str]:
    from dunneflow.ingest.codec import _HOST_OWNED

    return _HOST_OWNED.get(cls, frozenset())


def generate() -> str:
    records, enums = _reachable(ROOT)
    lines = [HEADER.replace("{version}", str(schema.SCHEMA_VERSION))]

    for enum in sorted(enums, key=lambda e: e.__name__):
        members = " | ".join(f'"{m.value}"' for m in list(enum))  # type: ignore[call-overload]
        lines.append(f"export type {enum.__name__} = {members};\n")

    for cls in records:
        owned = _host_owned(cls)
        lines.append(f"export interface {cls.__name__} {{")
        for f in dataclasses.fields(cls):
            if f.name in owned:
                continue
            hint = typing.get_type_hints(cls)[f.name]
            required = f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
            ts = _ts_type(hint, f"{cls.__name__}.{f.name}")
            if _optional(hint):
                ts = f"{ts} | null"
            lines.append(f"  {f.name}{'' if required else '?'}: {ts};")
        lines.append("}\n")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help=f"write {OUT}")
    args = ap.parse_args()
    text = generate()
    if args.write:
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT} — {len(text.splitlines())} lines")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
