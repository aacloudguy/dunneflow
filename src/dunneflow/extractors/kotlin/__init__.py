"""Kotlin, read without a compiler — the fourth language, and the second hand-written one.

Stdlib only, in process, on the same discipline as `extractors/cpp/` and for a different
reason. C++ refused a semantic read on evidence: the demo corpus cannot tell a compiler how
it is built without being built first. Kotlin's compiler *could* be asked, and asking it
would mean a JVM on every machine that reads a `.kt` file and a
`kotlin-compiler-embeddable` jar inside a bundle whose entire runtime dependency list is
`pyyaml`. The trade is stated rather than assumed: **what that would buy is resolved calls**,
and what it would cost is the frozen application.

**Kotlin is a far more regular language to read than C++**, and the reader is smaller for it.
There is no preprocessor, no header/implementation split, no line splicing and no most vexing
parse. Every function is introduced by `fun`, every type by `class`, `object`, `interface` or
`enum class`, and a file's package is stated at the top rather than inferred from where the
file sits.

Three things it does have that C++ does not, and each is handled where it belongs:

* **Expression bodies.** `fun f() = expr` has no braces and is still a routine — the single
  most common shape in idiomatic Kotlin, and a brace-tree reader that looks only for `{`
  finds none of them.
* **Lambdas everywhere.** `apply { }`, `let { }`, `forEach { }` and trailing-lambda call
  syntax mean most braces in a Kotlin file open no declaration at all. `scopes.py` keys on
  the declaration keyword rather than on the brace.
* **String templates.** `"$x"` carries code inside a literal, so the mask tracks `${` nesting
  and the literal is reported as `INTERPOLATED`.

`supplies_edges` is `false` and every call is left external, named with a count — the same
shippable state the architecture describes and C++ already occupies.

## Built in dependency order, and this package does not yet export a reader

`extract_file` is what `ingest._IN_PROCESS` will name. It is not re-exported until it exists,
and `plugins/kotlin/plugin.json` is written **last**, so the registry never loads a reader
that would find nothing (rule 49).
"""

from __future__ import annotations

__all__: list[str] = []
