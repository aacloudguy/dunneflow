"""`schema.py` as Rust, generated, for `gen_facts_ts.py`'s reason two languages over.

A transcription of `schema.py` is how a fact stops existing (`gen_facts_ts.py` says how it
went the first time), so the Rust reader's types come from the same reflection, the same
two roots and the same host-owned exclusions, and `tests/test_rust_reader.py` regenerates
this file and compares it **without needing Rust**.

**What Rust needs that Go did not, and each is a way the wire goes wrong.**

- **There is no serde.** It would be a fifth vendored crate and a proc-macro, which is
  a build step running somebody's code to read code. So the encoder is generated here as
  well: every record writes itself into a `String`, and `json::write_str` is the one place
  a string is escaped.
- **A field's default is its Rust zero, or it is omitted**, which is Go's rule: a field
  with a default is written only when it differs from `Default::default()`, so a reader
  that leaves it alone sends nothing and the host applies the schema's default. A
  required field is always written.
- **Every enum derives `Default` as its first member**, so that a record can be built
  with `..Default::default()`. That is a plausible value standing where a forgotten one
  should fail (rule 49), and it is said here so that it is a known cost: a *required*
  enum field is always written, so a reader that forgets one sends the first member,
  and the reader's own tests are what catch it.

    uv run python tools/gen_facts_rs.py            # print
    uv run python tools/gen_facts_rs.py --write    # write src/facts.rs and the fingerprint

**And the fingerprint.** The plugin vendors its parser, so its `fingerprint` is every file
under `src/` and `vendor/` plus the manifests — over 200 names, which no person should
maintain and no glob may stand for (`contract.py`: a fingerprint names files). `--write`
rewrites that list in `plugin.json`, and the test asserts it equals what is on disk.

The id vectors are `gen_facts_go.py`'s and are language-neutral; they are not rewritten
here.
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

PLUGIN = resource_root() / "plugins" / "rust"
OUT = PLUGIN / "src" / "facts.rs"
MANIFEST = PLUGIN / "plugin.json"

# Fingerprinted ahead of the trees, in this order; the trees follow, sorted.
_FIXED = ["plugin.json", "Cargo.toml", "Cargo.lock", ".cargo/config.toml"]

HEADER = '''// `schema.py`'s types, as this reader has to emit them.
//
// GENERATED — DO NOT EDIT. `uv run python tools/gen_facts_rs.py --write`.
// `tests/test_rust_reader.py` regenerates it and compares, so a drift between this file
// and `schema.py` fails the suite rather than the map.
//
// A field with a default is written only when it is not its Rust zero, and leaving it
// unset means the schema's default: the key is absent and the host applies it, as
// `codec.encode` does on the other side. A required field is always written.
//
// `lang` is absent from `Routine` and `DataStructure` on purpose: it is the host's to
// write (`ingest.stamp_lang`).

#![allow(dead_code, unused_imports, clippy::all)]

use crate::json::{write_str, ToJson};
use std::collections::BTreeMap;

/// `schema.SCHEMA_VERSION`. A plugin declaring another is refused by name.
pub const SCHEMA_VERSION: i64 = {version};
'''


def _camel(name: str) -> str:
    """`line_start` -> `LineStart`, `ELSE_IF` -> `ElseIf`. Derived, so nobody's address."""
    return "".join(p[:1].upper() + p[1:].lower() for p in name.split("_") if p)


def _rust_field(name: str) -> str:
    """A field name, raw where it is a Rust keyword (`type`, `async`, `ref` …)."""
    keywords = {"type", "async", "ref", "mod", "move", "match", "fn", "impl", "self",
                "static", "struct", "trait", "use", "where", "loop", "in", "for", "if",
                "else", "let", "mut", "pub", "return", "super", "crate", "enum", "extern",
                "const", "as", "break", "continue", "dyn", "false", "true", "unsafe",
                "while", "await", "box", "final", "override", "yield", "abstract", "do",
                "macro", "priv", "typeof", "unsized", "virtual", "try"}
    return f"r#{name}" if name in keywords else name


def _rust_type(hint: Any, where: str) -> str:
    origin = get_origin(hint)
    if origin is Literal:
        return "String"
    if origin is tuple:
        args = get_args(hint)
        if args and Ellipsis not in args and len(set(args)) == 1:
            return f"[{_rust_type(args[0], where)}; {len(args)}]"
        if len(args) == 2 and args[1] is Ellipsis:
            return f"Vec<{_rust_type(args[0], where)}>"
        raise TypeError(f"{where}: a tuple this generator has not been taught")
    if origin is list:
        return f"Vec<{_rust_type(get_args(hint)[0], where)}>"
    if origin is dict:
        return f"BTreeMap<String, {_rust_type(get_args(hint)[1], where)}>"
    if origin is not None or isinstance(hint, typing._SpecialForm):  # noqa: SLF001
        arms = [a for a in get_args(hint) if a is not type(None)]
        if len(arms) == 1:
            return f"Option<{_rust_type(arms[0], where)}>"
        raise TypeError(f"{where}: a union this generator has not been taught")
    if isinstance(hint, type):
        if issubclass(hint, Enum):
            return hint.__name__
        if hint is bool:
            return "bool"
        if hint is int:
            return "i64"
        if hint is float:
            return "f64"
        if hint is str:
            return "String"
        if dataclasses.is_dataclass(hint):
            return hint.__name__
    raise TypeError(f"{where}: {hint!r} is a shape this generator has not been taught")


# `PartialEq` and not `Eq`: an `f64` cannot be `Eq`, and equality is all the zero test needs.
_DERIVES = "#[derive(Debug, Clone, Default, PartialEq)]"


def generate() -> str:
    records: list[type] = []
    enums: list[type] = []
    for root in ts.ROOTS:
        found, found_enums = ts._reachable(root)  # noqa: SLF001
        records += [c for c in found if c not in records]
        enums += [e for e in found_enums if e not in enums]
    out = [HEADER.replace("{version}", str(schema.SCHEMA_VERSION))]

    for enum in sorted(enums, key=lambda e: e.__name__):
        members = list(enum)  # type: ignore[call-overload]
        out.append(f"/// `schema.{enum.__name__}`.")
        out.append("#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]")
        out.append(f"pub enum {enum.__name__} {{")
        for i, m in enumerate(members):
            if i == 0:
                out.append("    #[default]")
            out.append(f"    {_camel(m.name)},")
        out.append("}\n")
        out.append(f"impl {enum.__name__} {{")
        out.append("    /// The schema's own spelling, which is the wire's.")
        out.append("    pub fn as_str(self) -> &'static str {")
        out.append("        match self {")
        for m in members:
            out.append(f'            {enum.__name__}::{_camel(m.name)} => "{m.value}",')
        out.append("        }")
        out.append("    }")
        out.append("}\n")
        out.append(f"impl ToJson for {enum.__name__} {{")
        out.append("    fn write_json(&self, out: &mut String) {")
        out.append("        write_str(out, self.as_str());")
        out.append("    }")
        out.append("}\n")

    for cls in records:
        owned = ts._host_owned(cls)  # noqa: SLF001
        hints = typing.get_type_hints(cls)
        fields = [f for f in dataclasses.fields(cls) if f.name not in owned]
        out.append(f"/// `schema.{cls.__name__}`.")
        out.append(_DERIVES)
        out.append(f"pub struct {cls.__name__} {{")
        for f in fields:
            rt = _rust_type(hints[f.name], f"{cls.__name__}.{f.name}")
            out.append(f"    pub {_rust_field(f.name)}: {rt},")
        out.append("}\n")
        out.append(f"impl ToJson for {cls.__name__} {{")
        out.append("    fn write_json(&self, out: &mut String) {")
        if any(f.default is not dataclasses.MISSING or f.default_factory is not dataclasses.MISSING
               for f in fields):
            out.append("        let zero = Self::default();")
        out.append("        out.push('{');")
        out.append("        let mut first = true;")
        for f in fields:
            required = (f.default is dataclasses.MISSING
                        and f.default_factory is dataclasses.MISSING)
            rf = _rust_field(f.name)
            put = (f'crate::json::field(out, &mut first, "{f.name}", &self.{rf});')
            if required:
                out.append(f"        {put}")
            else:
                out.append(f"        if self.{rf} != zero.{rf} {{")
                out.append(f"            {put}")
                out.append("        }")
        if not fields:
            out.append("        let _ = &mut first;")
        out.append("        out.push('}');")
        out.append("    }")
        out.append("}\n")

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
