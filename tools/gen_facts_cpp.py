"""`schema.py` as C++, generated, for `gen_facts_ts.py`'s reason a sixth time.

The C and C++ reader's types come from the same reflection, the same two roots and the same
host-owned exclusions as every other reader's. `tests/test_cpp_reader.py` regenerates this
file and compares it **without needing a compiler**.

**What C++ needs, each one a way the wire goes wrong** (Java's list, in C++'s terms):

- **The standard library has no JSON**, and the reader vendors nothing but libclang's
  headers. So the encoder is generated too: every record writes itself, and
  `json::write_string` is the one place a string is escaped.
- **A field starts at the schema's own default and is written only when it differs.**
- **A required string or enum is a `std::optional` that starts empty, and writing an empty
  one throws.** A forgotten field fails in the reader's own tests rather than reaching the map
  as an empty name (rule 49). A required number or boolean is always written.
- **An enum is its wire spelling**, a `std::string`, with the members as constants in a
  namespace of the enum's name. The wire is the address; a C++ `enum class` would be a second
  spelling to keep in step with it.
- **Field names are `schema.py`'s own.** A name that is a C++ keyword gets a trailing
  underscore in C++, and the wire still spells it as the schema does.

    uv run python tools/gen_facts_cpp.py            # print
    uv run python tools/gen_facts_cpp.py --write    # write src/facts.hpp and the fingerprint

**The fingerprint** is `plugin.json`, `reader.cpp`, every file under `src/` and every file
under `vendor/`, named and never globbed. `--write` keeps that list in `plugin.json`, and a
test asserts it equals what is on disk.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import typing
from enum import Enum
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gen_facts_ts as ts  # noqa: E402  — its reflection, never a second copy of it

from dunneflow import schema  # noqa: E402
from dunneflow.runtime import resource_root  # noqa: E402

PLUGIN = resource_root() / "plugins" / "cpp"
OUT = PLUGIN / "src" / "facts.hpp"
MANIFEST = PLUGIN / "plugin.json"

# Fingerprinted ahead of the trees, in this order; `src/` and `vendor/` follow, sorted.
_FIXED = ["plugin.json", "reader.cpp"]

_KEYWORDS = frozenset({
    "default", "private", "public", "protected", "class", "struct", "union", "enum",
    "namespace", "template", "typename", "operator", "new", "delete", "this", "virtual",
    "static", "const", "volatile", "register", "auto", "return", "if", "else", "for",
    "while", "do", "switch", "case", "break", "continue", "goto", "try", "catch", "throw",
    "int", "long", "short", "char", "bool", "float", "double", "void", "signed",
    "unsigned", "true", "false", "inline", "extern", "friend", "explicit", "export",
    "using", "typedef", "sizeof", "alignof", "decltype", "and", "or", "not", "xor",
    "concept", "requires",
})

HEADER = '''// `schema.py`'s types, as this reader has to emit them.
//
// GENERATED — DO NOT EDIT. `uv run python tools/gen_facts_cpp.py --write`.
// `tests/test_cpp_reader.py` regenerates it and compares, so a drift between this file and
// `schema.py` fails the suite rather than the map.
//
// A field starts at the schema's default and is written only when it differs from it, so
// leaving it alone sends nothing and the host applies the same default (`codec.encode` does
// the same on the other side). A required string or enum is an empty `std::optional`, and
// writing an empty one throws: a forgotten field fails here, not in the map.
//
// `lang` is absent from `Routine` and `DataStructure` on purpose: it is the host's to write
// (`ingest.stamp_lang`).

#pragma once

#include <cstdint>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#include "json.hpp"

namespace facts {{

// `schema.SCHEMA_VERSION`. A plugin declaring another is refused by name.
constexpr int64_t SCHEMA_VERSION = {version};

inline void required(const char* what) {{
    throw std::logic_error(std::string(what) + " is required and was never set");
}}
'''


def _field(name: str) -> str:
    return name + "_" if name in _KEYWORDS else name


def _cpp(hint: Any, where: str) -> str:
    origin = get_origin(hint)
    if origin is Literal:
        return "std::string"
    if origin is tuple:
        args = get_args(hint)
        if args and Ellipsis not in args and len(set(args)) == 1:
            return f"std::vector<{_cpp(args[0], where)}>"
        if len(args) == 2 and args[1] is Ellipsis:
            return f"std::vector<{_cpp(args[0], where)}>"
        raise TypeError(f"{where}: a tuple this generator has not been taught")
    if origin is list:
        return f"std::vector<{_cpp(get_args(hint)[0], where)}>"
    if origin is dict:
        return f"std::map<std::string, {_cpp(get_args(hint)[1], where)}>"
    if origin is not None or isinstance(hint, typing._SpecialForm):  # noqa: SLF001
        arms = [a for a in get_args(hint) if a is not type(None)]
        if len(arms) == 1:
            return _cpp(arms[0], where)
        raise TypeError(f"{where}: a union this generator has not been taught")
    if isinstance(hint, type):
        if issubclass(hint, Enum):
            return "std::string"
        if hint is bool:
            return "bool"
        if hint is int:
            return "int64_t"
        if hint is float:
            return "double"
        if hint is str:
            return "std::string"
        if dataclasses.is_dataclass(hint):
            return hint.__name__
    raise TypeError(f"{where}: {hint!r} is a shape this generator has not been taught")


def _is_optional(hint: Any) -> bool:
    return type(None) in get_args(hint)


def _literal(value: Any) -> str:
    """A schema default, spelt in C++."""
    if isinstance(value, Enum):
        return json.dumps(value.value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    raise TypeError(f"a default of {value!r} this generator has not been taught")


def _ident(name: str) -> str:
    """An enum member's C++ constant: its Python name, which is already an identifier."""
    return name + "_" if name in _KEYWORDS else name


def _ordered(records: list[type]) -> list[type]:
    """Every record after the records its fields hold: C++ declares before it uses.

    Stable otherwise — discovery order is kept wherever it does not have to move, so the
    file changes only where the schema does (rule 66).
    """
    out: list[type] = []

    def place(cls: type) -> None:
        if cls in out:
            return
        for hint in typing.get_type_hints(cls).values():
            for part in _parts(hint):
                if part in records and part is not cls:
                    place(part)
        out.append(cls)

    for cls in records:
        place(cls)
    return out


def _parts(hint: Any) -> list[Any]:
    args = get_args(hint)
    if not args:
        return [hint]
    out: list[Any] = []
    for a in args:
        out.extend(_parts(a))
    return out


def generate() -> str:
    records: list[type] = []
    enums: list[type] = []
    for root in ts.ROOTS:
        found, found_enums = ts._reachable(root)  # noqa: SLF001
        records += [c for c in found if c not in records]
        enums += [e for e in found_enums if e not in enums]
    out = [HEADER.format(version=schema.SCHEMA_VERSION)]

    for enum in sorted(enums, key=lambda e: e.__name__):
        out.append(f"// `schema.{enum.__name__}`, by its wire spelling.")
        out.append(f"namespace {enum.__name__} {{")
        for m in list(enum):  # type: ignore[call-overload]
            out.append(f"inline const std::string {_ident(m.name)} = {json.dumps(m.value)};")
        out.append(f"}}  // namespace {enum.__name__}\n")

    for cls in _ordered(records):
        owned = ts._host_owned(cls)  # noqa: SLF001
        hints = typing.get_type_hints(cls)
        fields = [f for f in dataclasses.fields(cls) if f.name not in owned]
        out.append(f"// `schema.{cls.__name__}`.")
        out.append(f"struct {cls.__name__} {{")
        plan: list[tuple[str, str, str, str]] = []  # (wire, c++ name, type, how)
        for f in fields:
            hint = hints[f.name]
            where = f"{cls.__name__}.{f.name}"
            ct = _cpp(hint, where)
            cf = _field(f.name)
            if f.default_factory is not dataclasses.MISSING:
                if f.default_factory() not in ([], {}):
                    raise TypeError(f"{where}: a non-empty default factory")
                decl, how = f"{ct} {cf};", "nonempty"
            elif f.default is not dataclasses.MISSING:
                if f.default is None:
                    decl, how = f"std::optional<{ct}> {cf};", "present"
                else:
                    lit = _literal(f.default)
                    decl, how = f"{ct} {cf} = {lit};", "differs|" + lit
            elif ct.startswith(("std::vector<", "std::map<")):
                decl, how = f"{ct} {cf};", "always"
            elif ct in ("int64_t", "bool", "double"):
                decl, how = f"{ct} {cf} = {'false' if ct == 'bool' else '0'};", "always"
            elif _is_optional(hint):
                decl, how = f"std::optional<{ct}> {cf};", "nullable"
            else:
                decl, how = f"std::optional<{ct}> {cf};", "required"
            out.append(f"    {decl}")
            plan.append((f.name, cf, ct, how))
        out.append("")
        out.append("    void write_json(std::string& out) const {")
        out.append("        out += '{';")
        out.append("        bool first = true;")
        for wire, cf, _ct, how in plan:
            put = f'json::field(out, first, "{wire}", {cf});'
            if how == "always":
                out.append(f"        {put}")
            elif how == "required":
                out.append(f'        if (!{cf}) required("{cls.__name__}.{wire}");')
                out.append(f'        json::field(out, first, "{wire}", *{cf});')
            elif how == "nullable":
                out.append(f'        json::field(out, first, "{wire}", {cf});')
            elif how == "present":
                out.append(f'        if ({cf}) json::field(out, first, "{wire}", *{cf});')
            elif how == "nonempty":
                out.append(f"        if (!{cf}.empty()) {put}")
            else:
                default = how.split("|", 1)[1]
                out.append(f"        if ({cf} != {default}) {put}")
        out.append("        out += '}';")
        out.append("    }")
        out.append("};\n")

    out.append("}  // namespace facts")
    return "\n".join(out).rstrip("\n") + "\n"


def fingerprint() -> list[str]:
    """Every file the reader is built from, named. The trees are `src/` and `vendor/`."""
    names = list(_FIXED)
    for tree in ("src", "vendor"):
        names += sorted(p.relative_to(PLUGIN).as_posix()
                        for p in (PLUGIN / tree).rglob("*") if p.is_file())
    return names


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help=f"write {OUT} and the fingerprint")
    args = ap.parse_args()
    text = generate()
    if not args.write:
        print(text)
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} — {len(text.splitlines())} lines")
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    data["fingerprint"] = fingerprint()
    MANIFEST.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {MANIFEST} — {len(data['fingerprint'])} fingerprinted files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
