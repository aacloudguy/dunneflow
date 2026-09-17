"""`analyze.js` must not reach for anything `shell.js` happens to define.

**The defect this is written from, because the title alone will let you agree with it and
reimplement it.** `pollAnalysis` called `loadPrograms()` -- a bare global, defined at the
top level of `shell.js` and nowhere else. Two pages load `analyze.js`: the shell, which
defines that global, and the start page, which loads only `analyze.js` and `start.js`.

So it worked in every test, in every session on the shell, and threw
`ReferenceError: loadPrograms is not defined` on the start page -- on the **one tick that
ever sees `state === "done"`**, before the panel repainted and before the poll loop
returned. Three analyses in a packaged build finished perfectly, wrote complete maps, and
reported themselves frozen at "step 7 of 7" and "step 2 of 7" with a *Stop it* button and
the sentence *"What it has written stays, marked unfinished."* The start page never left
*"No map has been made yet."*

Rule 51's shape, in a language with no import statement to make the dependency visible:
a rule kept at a call site rots as callers are added, and here the second *host* was the
second caller. `analyze.js`' header states the contract -- five host functions and nothing
else -- and this asserts it rather than trusting the sentence, because the sentence was
already there and true when line 416 was written.

**It asserts the calls, not the words** (rule 37). A guard that checked `shell.js` names do
not *appear* in `analyze.js` would fail on every one of the header's own prose mentions and
pass a call written as `window.loadPrograms()`. What is scanned is identifiers in call
position, minus the ones `analyze.js` declares itself.

**And it reads code, never the file** -- rule 34, which `test_frozen.py` paid for one scan
over. The first version of this test failed on its own evidence: the paragraph above names
`loadPrograms()` to explain the defect, and a scan of the *text* reported it as the defect.
Three more came from `analyze.js`' own prose and one from `wire(host) {`, which is a method
being defined and not a function being called. Comments and string literals are stripped
before anything is counted, and a method shorthand counts as a declaration.
"""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "src" / "dunneflow" / "web" / "static"

# Declared at the top level of a file: `function f()`, `const x =`, `let y`, `var z`, at
# column zero. Anchored, because a nested `const` inside `analyze.js`' own IIFE is not a
# global and a nested one in `shell.js` is not reachable from another file either.
TOP_LEVEL = re.compile(r"^(?:async\s+)?(?:function\s+|const\s+|let\s+|var\s+|class\s+)"
                       r"([A-Za-z_$][\w$]*)", re.M)

# An identifier in call position that is **not** a property access. `HOST.changed()` and
# `md.render()` are somebody's method and are not what this is about; `loadPrograms()` is.
# The negative lookbehind on `.` is the whole distinction, and without it this reports the
# four false positives that made the first version of this scan useless.
BARE_CALL = re.compile(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(")

# Declared anywhere in `analyze.js`, at any depth -- everything inside its IIFE is its own.
DECLARED = re.compile(r"(?:function|const|let|var|class)\s+([A-Za-z_$][\w$]*)")

# `wire(host) { ... }` in the returned object literal is a method being **defined**, and to
# `BARE_CALL` it is indistinguishable from a call. Counted as a declaration, which is what
# it is.
METHOD = re.compile(r"^\s*([A-Za-z_$][\w$]*)\s*\([^()]*\)\s*\{", re.M)

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def _code(text: str) -> str:
    """The file with its prose taken out. **Comments only, and that is a retreat.**

    The first version stripped string literals too, and it was a JavaScript parser written
    in regular expressions -- which is a thing that looks right until it is measured. It
    swallowed `shell.js` whole: a regex literal there (`/[&<>"]/g`) carries a double quote,
    which opened a string the scanner then closed thousands of lines later, and
    `Analyze.wire` vanished from a 20,000-line file with no error anywhere. Rule 49's shape
    in a test -- a plausible-looking result hiding the failure -- and the tell was that the
    guard found *nothing*, which is exactly what a broken guard and a clean file look like
    from here (rule 38: an instrument that cannot see cannot report).

    Comments are what actually carried the false positives, so comments are what goes.
    Line comments are left alone deliberately: `//` inside a string is a URL, and stripping
    to end of line would delete real code to remove prose that was never there. What is left
    is `wire(host) {`, which `METHOD` names for what it is.
    """
    return _BLOCK_COMMENT.sub(" ", text)

# What the language and the browser supply. Not an allowlist of things this file may reach
# for: a name here is one no host can fail to have, which is the property that matters.
BUILTIN = {
    "if", "for", "while", "switch", "catch", "return", "typeof", "function", "await",
    "String", "Number", "Boolean", "Object", "Array", "Date", "Math", "JSON", "Promise",
    "Error", "parseInt", "parseFloat", "isNaN", "encodeURIComponent", "decodeURIComponent",
    "fetch", "setTimeout", "clearTimeout", "setInterval", "clearInterval", "requestAnimationFrame",
}


def _text(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_analyze_js_calls_nothing_only_shell_js_defines() -> None:
    """The contract, asserted rather than described.

    A name in this report is one of two things and both are defects: a host function that
    should have been added to the five and wired by *both* pages, or a helper that should
    have been declared in `analyze.js`. Which one it is, is a judgement -- that it cannot
    stay as it is, is not.
    """
    analyze = _code(_text("analyze.js"))
    shell = _code(_text("shell.js"))

    shell_globals = set(TOP_LEVEL.findall(shell))
    mine = set(DECLARED.findall(analyze)) | set(METHOD.findall(analyze))
    called = set(BARE_CALL.findall(analyze))

    leaked = sorted((called & shell_globals) - mine - BUILTIN)
    assert not leaked, (
        "analyze.js calls " + ", ".join(f"{n}()" for n in leaked) + " — declared only at the "
        "top level of shell.js. The start page loads analyze.js without shell.js, so this "
        "throws a ReferenceError there and nowhere else. Take it through the host contract "
        "in analyze.js' header, and wire it on BOTH start.js and shell.js."
    )


def test_the_host_contract_is_the_only_way_out() -> None:
    """Both hosts wire every function `analyze.js` asks of one.

    The other half, and it fails in the opposite direction: a call to `HOST.somethingNew()`
    that only the shell wires is the same defect wearing the contract's uniform. `HOST`'s
    defaults make it silent -- a wired-nothing host gets no-ops by construction -- so the
    thing to check is that each page's `wire({...})` names every key the module uses.
    """
    analyze = _code(_text("analyze.js"))
    used = set(re.findall(r"HOST\.([A-Za-z_$][\w$]*)", analyze))
    assert used, "no HOST.* calls found — this guard has stopped watching anything (rule 38)"

    for page in ("shell.js", "start.js"):
        body = _code(_text(page))
        # `\n\s*\}\)` rather than `\n\}\)`: the shell wires at column zero and the start page
        # inside an IIFE, so the closing brace is indented on one of the two.
        block = re.search(r"Analyze\.wire\(\{(.*?)\n\s*\}\)", body, re.S)
        assert block, f"{page} does not wire Analyze — every host must"
        wired = set(re.findall(r"^\s*([A-Za-z_$][\w$]*)\s*:", block.group(1), re.M))
        missing = sorted(used - wired)
        assert not missing, (
            f"{page} wires no {', '.join(missing)} — analyze.js calls it, and HOST's "
            "defaults would make the omission silent on that page alone."
        )


def test_changed_is_actually_called() -> None:
    """`changed()` was wired by both pages and called by nobody.

    That is what left room for the global: the hook existed, was documented, and was dead,
    so the refresh it was for got written a second way. Rule 35's shape -- a declaration
    nothing assigns is an empty view with no symptom -- one indirection over. A contract
    entry nothing invokes is not a contract, it is a comment.
    """
    analyze = _text("analyze.js")
    assert "HOST.changed()" in analyze, (
        "nothing calls HOST.changed() — it is wired by both hosts and dead again, which is "
        "the state the loadPrograms global grew in"
    )
