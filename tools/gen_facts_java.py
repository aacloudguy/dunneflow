"""`schema.py` as Java, generated, for `gen_facts_ts.py`'s reason a fifth time.

A transcription of `schema.py` is how a fact stops existing (`gen_facts_ts.py` says how it
went the first time). So the Java reader's types come from the same reflection, the same
two roots and the same host-owned exclusions. `tests/test_java_reader.py` regenerates this
file and compares it **without needing a JDK**.

**What Java needs that the others did not. Each one is a way the wire goes wrong.**

- **The JDK has no JSON**, and the reader vendors nothing. So the encoder is generated
  here too: every record writes itself, and `Json.writeString` is the one place a string
  is escaped.
- **A field starts at the schema's own default and is written only when it differs from
  it.** That is closer than Go's and Rust's language-zero rule, which only agrees with
  `schema.py` where the schema's default happens to be zero.
- **A required field that is an object, a string or an enum starts as `null`, and the
  encoder refuses to write a `null` one.** A forgotten field then fails in the reader's
  own tests, rather than reaching the map as the first enum member or an empty name
  (rule 49). A required number or boolean is a primitive and is always written.
- **Field names are `schema.py`'s own**, `snake_case` and all, because they are the wire's
  addresses. A name that is a Java keyword (`default`, `var`, `private`) gets a trailing
  underscore in Java, and the wire still spells it as the schema does.

    uv run python tools/gen_facts_java.py            # print
    uv run python tools/gen_facts_java.py --write    # write Facts.java and the fingerprint

**The fingerprint** is every file under `src/`, plus `plugin.json` and `Build.java`. These
are named and never globbed. `--write` keeps that list in `plugin.json`, and a test asserts
it equals what is on disk.
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

PLUGIN = resource_root() / "plugins" / "java"
PACKAGE = "dunneflow.reader"
OUT = PLUGIN / "src" / "dunneflow" / "reader" / "Facts.java"
MANIFEST = PLUGIN / "plugin.json"

# Fingerprinted ahead of the tree, in this order; `src/` follows, sorted.
_FIXED = ["plugin.json", "Build.java"]

_KEYWORDS = frozenset({
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", "class",
    "const", "continue", "default", "do", "double", "else", "enum", "extends", "final",
    "finally", "float", "for", "goto", "if", "implements", "import", "instanceof", "int",
    "interface", "long", "native", "new", "package", "private", "protected", "public",
    "return", "short", "static", "strictfp", "super", "switch", "synchronized", "this",
    "throw", "throws", "transient", "try", "void", "volatile", "while", "true", "false",
    "null", "var", "record", "yield", "sealed", "permits",
})

HEADER = '''// `schema.py`'s types, as this reader has to emit them.
//
// GENERATED — DO NOT EDIT. `uv run python tools/gen_facts_java.py --write`.
// `tests/test_java_reader.py` regenerates it and compares, so a drift between this file
// and `schema.py` fails the suite rather than the map.
//
// A field starts at the schema's default and is written only when it differs from it, so
// leaving it alone sends nothing and the host applies the same default (`codec.encode`
// does the same on the other side). A required object, string or enum starts as `null`,
// and writing a `null` one throws: a forgotten field fails here, not in the map.
//
// `lang` is absent from `Routine` and `DataStructure` on purpose: it is the host's to
// write (`ingest.stamp_lang`).

package {package};

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

@SuppressWarnings("unused")
public final class Facts {{
    private Facts() {{}}

    /** `schema.SCHEMA_VERSION`. A plugin declaring another is refused by name. */
    public static final long SCHEMA_VERSION = {version};
'''


def _field(name: str) -> str:
    return name + "_" if name in _KEYWORDS else name


def _java_type(hint: Any, where: str) -> str:
    origin = get_origin(hint)
    if origin is Literal:
        return "String"
    if origin is tuple:
        args = get_args(hint)
        if args and Ellipsis not in args and len(set(args)) == 1:
            return f"List<{_boxed(args[0], where)}>"
        if len(args) == 2 and args[1] is Ellipsis:
            return f"List<{_boxed(args[0], where)}>"
        raise TypeError(f"{where}: a tuple this generator has not been taught")
    if origin is list:
        return f"List<{_boxed(get_args(hint)[0], where)}>"
    if origin is dict:
        return f"Map<String, {_boxed(get_args(hint)[1], where)}>"
    if origin is not None or isinstance(hint, typing._SpecialForm):  # noqa: SLF001
        arms = [a for a in get_args(hint) if a is not type(None)]
        if len(arms) == 1:
            return _boxed(arms[0], where)
        raise TypeError(f"{where}: a union this generator has not been taught")
    if isinstance(hint, type):
        if issubclass(hint, Enum):
            return hint.__name__
        if hint is bool:
            return "boolean"
        if hint is int:
            return "long"
        if hint is float:
            return "double"
        if hint is str:
            return "String"
        if dataclasses.is_dataclass(hint):
            return hint.__name__
    raise TypeError(f"{where}: {hint!r} is a shape this generator has not been taught")


def _boxed(hint: Any, where: str) -> str:
    t = _java_type(hint, where)
    return {"boolean": "Boolean", "long": "Long", "double": "Double"}.get(t, t)


def _is_optional(hint: Any) -> bool:
    return type(None) in get_args(hint)


def _literal(value: Any, jtype: str) -> str:
    """A schema default, spelt in Java."""
    if isinstance(value, Enum):
        return f"{type(value).__name__}.{value.name}"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return f"{value}L"
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if value is None:
        return "null"
    raise TypeError(f"a default of {value!r} for a {jtype} this generator has not been taught")


def generate() -> str:
    records: list[type] = []
    enums: list[type] = []
    for root in ts.ROOTS:
        found, found_enums = ts._reachable(root)  # noqa: SLF001
        records += [c for c in found if c not in records]
        enums += [e for e in found_enums if e not in enums]
    out = [HEADER.format(package=PACKAGE, version=schema.SCHEMA_VERSION)]

    for enum in sorted(enums, key=lambda e: e.__name__):
        members = list(enum)  # type: ignore[call-overload]
        out.append(f"    /** `schema.{enum.__name__}`. */")
        out.append(f"    public enum {enum.__name__} implements Json.Writable {{")
        body = ",\n".join(f"        {m.name}({json.dumps(m.value)})" for m in members)
        out.append(body + ";\n")
        out.append("        /** The schema's own spelling, which is the wire's. */")
        out.append("        public final String wire;\n")
        out.append(f"        {enum.__name__}(String wire) {{")
        out.append("            this.wire = wire;")
        out.append("        }\n")
        out.append("        @Override")
        out.append("        public void writeJson(StringBuilder out) {")
        out.append("            Json.writeString(out, wire);")
        out.append("        }")
        out.append("    }\n")

    for cls in records:
        owned = ts._host_owned(cls)  # noqa: SLF001
        hints = typing.get_type_hints(cls)
        fields = [f for f in dataclasses.fields(cls) if f.name not in owned]
        out.append(f"    /** `schema.{cls.__name__}`. */")
        out.append(f"    public static final class {cls.__name__} implements Json.Writable {{")
        plan: list[tuple[str, str, str, str]] = []  # (wire, java, type, how)
        for f in fields:
            hint = hints[f.name]
            jt = _java_type(hint, f"{cls.__name__}.{f.name}")
            jf = _field(f.name)
            if f.default_factory is not dataclasses.MISSING:
                made = f.default_factory()
                if made not in ([], {}):
                    raise TypeError(f"{cls.__name__}.{f.name}: a non-empty default factory")
                init = "new ArrayList<>()" if jt.startswith("List<") else "new LinkedHashMap<>()"
                how = "nonempty"
            elif f.default is not dataclasses.MISSING:
                init = _literal(f.default, jt)
                how = "differs"
            else:
                if jt.startswith("List<"):
                    init, how = "new ArrayList<>()", "always"
                elif jt.startswith("Map<"):
                    init, how = "new LinkedHashMap<>()", "always"
                elif jt in ("long", "boolean", "double"):
                    init, how = "", "always"
                elif _is_optional(hint):
                    init, how = "null", "always"
                else:
                    init, how = "null", "required"
            decl = f"        public {jt} {jf}" + (f" = {init};" if init else ";")
            out.append(decl)
            plan.append((f.name, jf, jt, how + ("|" + init if how == "differs" else "")))
        out.append("")
        out.append("        @Override")
        out.append("        public void writeJson(StringBuilder out) {")
        out.append("            out.append('{');")
        out.append("            boolean[] first = {true};")
        for wire, jf, jt, how in plan:
            put = f'Json.field(out, first, "{wire}", {jf});'
            if how == "always":
                out.append(f"            {put}")
            elif how == "required":
                out.append(f"            if ({jf} == null) {{")
                out.append(f'                throw new IllegalStateException('
                           f'"{cls.__name__}.{wire} is required and was never set");')
                out.append("            }")
                out.append(f"            {put}")
            elif how == "nonempty":
                out.append(f"            if (!{jf}.isEmpty()) {{")
                out.append(f"                {put}")
                out.append("            }")
            else:
                default = how.split("|", 1)[1]
                test = (f"{jf} != {default}" if jt in ("long", "boolean", "double")
                        else f"!Objects.equals({jf}, {default})")
                out.append(f"            if ({test}) {{")
                out.append(f"                {put}")
                out.append("            }")
        out.append("            out.append('}');")
        out.append("        }")
        out.append("    }\n")

    out.append("}")
    return "\n".join(out).rstrip("\n") + "\n"


def fingerprint() -> list[str]:
    """Every file the reader is built from, named. The tree is `src/`."""
    names = list(_FIXED)
    names += sorted(p.relative_to(PLUGIN).as_posix()
                    for p in (PLUGIN / "src").rglob("*") if p.is_file())
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
