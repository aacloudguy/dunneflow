"""The directives, and the braces a matcher must never be shown.

Two subjects. What `#include` and `#define` *say*, and what every directive line has to be
hidden from — because a macro body is text, is under no obligation to balance, and Unreal
ships the shape that proves it.
"""

from __future__ import annotations

from dunneflow.extractors.cpp.lexer import mask
from dunneflow.extractors.cpp.preprocessor import scan


def pre(src: str):
    return scan(mask(src))


# -------------------------------------------------------------- what they say --- #

def test_both_spellings_of_include_are_read_and_told_apart():
    """`is_from` carries quoted-against-angled, which is the only dependency fact here.

    **Read off the wrong view this test fails in one direction only**, and that is how it
    was found: a directive is located on `code_only()`, where strings are blanked so a `#`
    inside a raw string cannot pose as one — and read off that same view the *path* is a run
    of spaces. `<vector>` came back and `"Misc/Guid.h"` did not, which in a project-relative
    codebase like Unreal is very nearly all of them.
    """
    p = pre('#include "Misc/Guid.h"\n#include <vector>\n')
    assert [(i.module, i.is_from) for i in p.includes] == [
        ("Misc/Guid.h", True), ("vector", False)]


def test_an_include_is_recorded_as_written_and_never_resolved():
    """This reader never opens a file it was not independently asked to walk."""
    p = pre('#include "../../Runtime/Core/Public/Misc/Guid.h"\n')
    assert p.includes[0].module == "../../Runtime/Core/Public/Misc/Guid.h"


def test_a_trailing_comment_is_not_part_of_the_path_or_the_value():
    assert pre('#include "A/B.h"  // why\n').includes[0].module == "A/B.h"
    assert pre("#define MAX_USERS 100 // the cap\n").defines[0].value == "100"


def test_an_object_like_macro_is_a_constant_and_a_function_like_one_is_not():
    """`(` *immediately* after the name is the language's own test, not a heuristic.

    `#define F (a)` is object-like with the value `(a)`; `#define F(a)` is a macro with a
    parameter. The only thing telling them apart is the space, and calling the second a
    constant would put an expression in a column readers compare for equality.
    """
    p = pre("#define MAX_USERS 100\n#define MAX(a,b) ((a)>(b))\n#define F (a)\n")
    assert [(c.name, c.value) for c in p.defines] == [("MAX_USERS", "100"), ("F", "(a)")]


def test_a_valueless_define_is_not_a_constant():
    """The header-guard idiom, a few hundred per corpus. A constant whose value is the
    empty string is a row that says nothing."""
    assert pre("#define GUID_H_\n").defines == []


def test_a_hash_inside_a_raw_string_is_not_a_directive():
    """Which is the whole reason the directive is *found* on the masked stream."""
    p = pre('auto s = R"(\n#include <evil>\n)";\n#include "real.h"\n')
    assert [i.module for i in p.includes] == ["real.h"]


def test_whitespace_may_sit_either_side_of_the_hash():
    assert pre("#  include  <set>\n").includes[0].module == "set"


def test_a_directive_word_this_build_does_not_model_is_counted_by_name():
    """`#pragma` and `#undef` are here by design; anything else is worth knowing about
    (design rule 1 — a filter nobody can see)."""
    p = pre("#pragma once\n#undef X\n#pragma pack(1)\n")
    assert p.unread == {"pragma": 2, "undef": 1}


# ------------------------------------- what the brace matcher must not be shown --- #

def test_a_macro_body_never_contributes_a_brace():
    """The shape that costs, and Unreal ships it.

        #define BEGIN_NS(x) namespace x {
        #define END_NS }

    Counted, those are an open and a close belonging to no scope, and **the brace tree
    below them is wrong for the rest of the file** — every routine attributed to the wrong
    class or to none. A brace that is not there loses a scope; a brace that is there
    wrongly moves every scope after it, so the reader is shown neither.
    """
    p = pre("#define BEGIN_NS(x) namespace x {\n#define END_NS }\nvoid f(){}\n")
    assert "{" in p.code and "}" in p.code
    assert p.code.count("{") == 1 and p.code.count("}") == 1, (
        "a macro body's braces reached the stream the matcher reads"
    )


def test_the_blanked_stream_keeps_its_offsets_and_its_lines():
    """Same length and same newlines, so one line table serves every view (rule 51)."""
    src = '#include "a.h"\nvoid f(){}\n'
    m = mask(src)
    p = scan(m)
    assert len(p.code) == len(m.text)
    assert m.line_at(p.code.index("void f")) == 2


# ---------------------------------------------------- what is dead and what is not --- #

def test_if_zero_is_the_one_condition_that_is_skipped():
    p = pre("#if 0\nvoid gone(){}\n#endif\nvoid here(){}\n")
    assert "gone" not in p.code and "here" in p.code
    assert p.dead_regions == 1


def test_a_nested_conditional_inside_if_zero_does_not_revive_it():
    """The bug that ends a skipped region one `#endif` early and reads the rest of the
    file's declarations as live when they are not."""
    p = pre("#if 0\n#ifdef X\nvoid a(){}\n#endif\nvoid b(){}\n#endif\nvoid c(){}\n")
    for gone in ("a(", "b("):
        assert gone not in p.code
    assert "c(" in p.code


def test_the_other_arm_of_if_zero_is_live():
    """`#if 0 … #else … #endif` is the commonest way to comment one of two implementations
    out, and the one that is left is the program."""
    p = pre("#if 0\nvoid dead(){}\n#else\nvoid live(){}\n#endif\n")
    assert "dead" not in p.code and "live" in p.code


def test_an_ordinary_ifdef_is_read_as_live_on_both_arms():
    """Deciding one needs a build configuration nobody handed this reader, and on the demo
    corpus there is none to hand. Guessing which arm a compiler takes is the plausible
    value rule 49 forbids; recording both is honest and the duplicate qualname is kept as
    two identities rather than one silently replacing the other.
    """
    p = pre("#ifdef WIN\nvoid w(){}\n#else\nvoid u(){}\n#endif\n")
    assert "w(" in p.code and "u(" in p.code
    assert p.dead_regions == 0 and p.conditionals == 1


def test_if_zero_and_something_else_is_an_expression_and_is_not_evaluated():
    """`#if 0 && FOO` is arithmetic, and evaluating it is what this module refuses to do.

    Read as always-false it would be *right* here and wrong the moment somebody writes
    `#if 0 || DEBUG`, which is the same shape and the opposite answer.
    """
    p = pre("#if 0 && FOO\nvoid maybe(){}\n#endif\n")
    assert "maybe" in p.code
    assert p.dead_regions == 0
