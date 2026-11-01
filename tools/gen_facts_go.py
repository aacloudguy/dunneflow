"""`schema.py` as Go, generated, for `gen_facts_ts.py`'s reason one language over.

A transcription of `schema.py` is how a fact stops existing: the TypeScript reader's
hand-written types were wrong within an hour, and the codec counted the result as a failed
file on every file that held a network call. So the Go reader's types come from the same
reflection, the same two roots and the same host-owned exclusions, and
`tests/test_go_reader.py` regenerates this file and compares it **without needing Go**.

**Three things Go needs that TypeScript did not, and each one is a way the wire goes wrong.**

- **A nil slice is `null` on the wire**, and the codec refuses `null` where a list is
  required. Every list here is `List[T]`, whose `MarshalJSON` writes `[]` for nil. A
  generic type rather than a rule to remember at every append, because the remembering is
  the part that fails.
- **A field's default is its Go zero value, or it is omitted.** A field with a default
  carries `omitempty`, so a reader that leaves it unset sends nothing and the host applies
  the schema's default, which is `codec.encode`'s rule from the other side. Where the
  default is not the zero value (`visibility: "public"`, `arms: 1`), leaving the field
  unset still means *the default*, because the key is absent. A Go reader that wants a
  zero there cannot say so, and none of the current fields has a meaningful zero.
- **An exported name is a capital letter.** The wire name is the `json` tag and is the
  schema's own spelling; the Go name is derived from it and is nobody's address.

    uv run python tools/gen_facts_go.py            # print
    uv run python tools/gen_facts_go.py --write    # write facts.go and the id vectors

**And the vectors the reader's second implementations are pinned to.**
`tests/fixtures/ids/vectors.json` is every id function and `hash_source` applied by the
host, and every decoding `text.go` must reproduce, decoded by Python itself. `ids_test.go`
asserts it from the Go side and `tests/test_go_reader.py` regenerates and compares it from
this one, so the file can be neither stale nor hand-edited.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
import typing
from enum import Enum
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gen_facts_ts as ts  # noqa: E402  — its reflection, never a second copy of it

from dunneflow import schema  # noqa: E402
from dunneflow.runtime import resource_root  # noqa: E402

OUT = resource_root() / "plugins" / "go" / "facts.go"
VECTORS = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "ids" / "vectors.json"

# Byte strings `text.go` must decode exactly as Python's `errors="replace"` does: every
# ill-formed shape the maximal-subpart rule distinguishes, plus newlines and a BOM.
_TEXT_CASES = [
    b"plain ascii", b"caf\xc3\xa9", b"\xe2\x82A", b"\xff\xfe", b"\xc0\xaf",
    b"\xe0\x80\x80", b"\xed\xa0\x80", b"\xf0\x9f\x98", b"\xf0\x9f\x98\x80",
    b"\xf4\x90\x80\x80", b"\xf5\x80", b"\x80\x80\x80", b"a\xe2\x82", b"\xef\xbb\xbfbom",
    b"one\r\ntwo\rthree\n", b"\r\r\n", b"\xc3", b"\xe1\x80\xe1\x80\x80",
]

HEADER = '''// `schema.py`'s types, as this reader has to emit them.
//
// GENERATED — DO NOT EDIT. `uv run python tools/gen_facts_go.py --write`.
// `tests/test_go_reader.py` regenerates it and compares, so a drift between this file and
// `schema.py` fails the suite rather than the map.
//
// A field with a default carries `omitempty`, and leaving it unset means the schema's
// default: the key is absent and the host applies it, as `codec.encode` does on the other
// side. Every list is `List[T]`, which never encodes as `null`.
//
// `lang` is absent from `Routine` and `DataStructure` on purpose: it is the host's to
// write (`ingest.stamp_lang`).

package main

import "encoding/json"

// SchemaVersion is `schema.SCHEMA_VERSION`. A plugin declaring another is refused by name.
const SchemaVersion = {version}

// List is a slice that encodes as `[]` when it is nil, because the codec refuses `null`
// where it expects a list.
type List[T any] []T

// MarshalJSON writes `[]` for a nil list.
func (l List[T]) MarshalJSON() ([]byte, error) {
	if l == nil {
		return []byte("[]"), nil
	}
	return json.Marshal([]T(l))
}
'''


def _go_name(snake: str) -> str:
    """`line_start` -> `LineStart`, `Field_` -> `Field`. Derived, so nobody's address."""
    return "".join(p[:1].upper() + p[1:] for p in snake.split("_") if p)


def _go_type(hint: Any, where: str) -> str:
    origin = get_origin(hint)
    if origin is Literal:
        return "string"
    if origin is tuple:
        args = get_args(hint)
        if args and Ellipsis not in args and len(set(args)) == 1:
            return f"[{len(args)}]{_go_type(args[0], where)}"
        if len(args) == 2 and args[1] is Ellipsis:
            return f"List[{_go_type(args[0], where)}]"
        raise TypeError(f"{where}: a tuple this generator has not been taught")
    if origin is list:
        args = get_args(hint)
        return f"List[{_go_type(args[0], where)}]"
    if origin is dict:
        args = get_args(hint)
        return f"map[string]{_go_type(args[1], where)}"
    if origin is not None or isinstance(hint, typing._SpecialForm):  # noqa: SLF001
        arms = [a for a in get_args(hint) if a is not type(None)]
        if len(arms) == 1:
            return "*" + _go_type(arms[0], where)
        raise TypeError(f"{where}: a union this generator has not been taught")
    if isinstance(hint, type):
        if issubclass(hint, Enum):
            return _go_name(hint.__name__)
        if hint is bool:
            return "bool"
        if hint is int:
            return "int"
        if hint is float:
            return "float64"
        if hint is str:
            return "string"
        if dataclasses.is_dataclass(hint):
            return _go_name(hint.__name__)
    raise TypeError(f"{where}: {hint!r} is a shape this generator has not been taught")


def _aligned(rows: list[list[str]]) -> list[str]:
    """Rows of cells, padded the way `gofmt` pads a block: each column to its widest plus
    one space, the last left as it is. Done here so the file is `gofmt`-clean without Go
    on the machine that generates or compares it."""
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]) - 1)]
    return ["\t" + " ".join([*(c.ljust(w) for c, w in zip(r, widths, strict=False)), r[-1]])
            for r in rows]


def generate() -> str:
    records: list[type] = []
    enums: list[type] = []
    for root in ts.ROOTS:
        found, found_enums = ts._reachable(root)  # noqa: SLF001
        records += [c for c in found if c not in records]
        enums += [e for e in found_enums if e not in enums]
    out = [HEADER.replace("{version}", str(schema.SCHEMA_VERSION))]

    for enum in sorted(enums, key=lambda e: e.__name__):
        name = _go_name(enum.__name__)
        out.append(f"// {name} is `schema.{enum.__name__}`.")
        out.append(f"type {name} string\n")
        out.append(f"// The members of {name}.")
        out.append("const (")
        out += _aligned([[f"{name}{_go_name(m.name.lower())}", name, f'= "{m.value}"']
                         for m in list(enum)])  # type: ignore[call-overload]
        out.append(")\n")

    for cls in records:
        owned = ts._host_owned(cls)  # noqa: SLF001
        hints = typing.get_type_hints(cls)
        name = _go_name(cls.__name__)
        out.append(f"// {name} is `schema.{cls.__name__}`.")
        out.append(f"type {name} struct {{")
        rows = []
        for f in dataclasses.fields(cls):
            if f.name in owned:
                continue
            required = (f.default is dataclasses.MISSING
                        and f.default_factory is dataclasses.MISSING)
            go = _go_type(hints[f.name], f"{cls.__name__}.{f.name}")
            tag = f.name if required else f"{f.name},omitempty"
            rows.append([_go_name(f.name), go, f'`json:"{tag}"`'])
        out += _aligned(rows)
        out.append("}\n")

    return "\n".join(out).rstrip("\n") + "\n"


def vectors() -> str:
    """The pins, as the host computes them. JSON, sorted, newline-terminated."""
    import json

    parts = [["a"], ["a", "b"], ["", ""], ["mod.Type.Method", "x\u00e9"], []]
    ids = {
        "make_id": [[p, schema.make_id(*p)] for p in parts],
        "definition_id": [[f, q, o, schema.definition_id(f, q, o)]
                          for f, q, o in [("a.go", "a.main", 1), ("a.go", "a.init", 2),
                                          ("pkg/x.go", "pkg.x.T.M", 3)]],
        "entrypoint_id": [[f, list(p), schema.entrypoint_id(f, *p)]
                          for f, p in [("a.go", ("main",)), ("srv.go", ("GET", "/x")),
                                       ("a.go", ())]],
        "call_site_id": [[c, e, o, schema.call_site_id(c, e, o)]
                         for c, e, o in [("r1", "fmt.Println", 1), ("r1", "f", 2)]],
        "control_point_id": [[r, k, h, o, schema.control_point_id(r, k, h, o)]
                             for r, k, h, o in [("r1", "for", "for _, x := range xs", 1),
                                                ("r1", "if", "", 2)]],
        "hash_source": [[t, schema.hash_source(t)]
                        for t in ["", "package main\n", "x" * 300, "\u00e9\u20ac\U0001f600"]],
        "decode": [[b.hex(), b.decode("utf-8", errors="replace")
                    .replace("\r\n", "\n").replace("\r", "\n")] for b in _TEXT_CASES],
    }
    return json.dumps(ids, indent=1, ensure_ascii=True, sort_keys=True) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help=f"write {OUT}")
    args = ap.parse_args()
    text = generate()
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT} — {len(text.splitlines())} lines")
        VECTORS.parent.mkdir(parents=True, exist_ok=True)
        VECTORS.write_text(vectors(), encoding="utf-8")
        print(f"wrote {VECTORS}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
