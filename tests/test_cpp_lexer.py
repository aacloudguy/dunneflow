"""Which bytes are code, and which line they came from — the C++ reader's footing.

Every later phase asks `Masked` and never the raw text, so a defect here is not a wrong
fact in one place: it desynchronises the mask and every brace, call and routine after it is
read out of a string or a comment. That is why this file is one test per trap rather than a
handful of round-trips, and why each says what getting it wrong would cost.

The traps are the language's, not this reader's. Three of them come from rules that exist
for other reasons entirely — the standard's translation phases, C++14's digit separators,
and raw strings' delimiter matching — and each is the kind of thing a scanner written from
intuition gets backwards.
"""

from __future__ import annotations

from dunneflow.extractors.cpp.lexer import Span, logical, mask


def code(src: str) -> str:
    """What survives as code, with everything else blanked but the offsets kept."""
    return mask(src).code_only()


# ------------------------------------------------------- splicing comes first --- #

def test_a_continuation_inside_a_line_comment_swallows_the_next_line():
    """The standard's own order, and the one place getting it backwards *invents* a fact.

    Line continuations go in translation phase 2; comments are recognised in phase 3. So a
    `//` comment ending in a backslash continues, and the line under it is not code at all.
    Recognise comments first and `Gone()` is read, attributed to whatever routine encloses
    it, and reported as flow the compiler never sees — a call in the map that is not in the
    program, which is the direction rule 1 exists to refuse.
    """
    out = code("// hides \\\nGone();\nReal();\n")
    assert "Gone()" not in out
    assert "Real()" in out


def test_every_physical_line_keeps_its_number_across_a_continuation():
    """A reader opens the file at the line this reports, so it must be where the token *is*.

    Written the other way first — a continued line folded into the one above and got no
    entry — on the argument that it is the logical line the compiler sees. It is also one
    lost line number per continuation, and the error **compounds**: every routine, call and
    boundary below the second continuation is reported two lines high. Caught by this
    fixture and by nothing else, because a map with every line slightly wrong still opens,
    still renders, and still looks right.
    """
    m = mask("a();\n// p \\\nq();\n// r \\\ns();\nz();\n")
    assert m.continuations == 2
    assert m.line_at(m.text.index("a()")) == 1
    assert m.line_at(m.text.index("z()")) == 6, "line numbers compounded across continuations"


def test_a_continuation_in_ordinary_code_is_one_statement_and_two_lines():
    m = mask("int x =\\\n  1;\nlast();\n")
    assert m.continuations == 1
    assert m.line_at(m.text.index("last()")) == 3


def test_a_crlf_continuation_splices_too():
    """`SOURCE_TEXT` normalises newlines before a reader sees them — and a rule that holds
    only for pre-normalised input is a rule with a hole in it, since this function is also
    what a test hands raw bytes to."""
    text, _, removed = logical("a =\\\r\n 1;\n")
    assert removed == 1
    assert "\\" not in text


# -------------------------------------------------------------- the literals --- #

def test_a_raw_string_ends_at_its_delimiter_and_not_at_a_backslash():
    r"""`R"(a\)b)"` closes at the `)"`, because a raw string processes no escapes.

    Unreal embeds shader source, JSON and regular expressions this way. Read as an ordinary
    literal, the first backslash escapes the character after it, the closing quote is
    missed, and **the rest of the file is read as string** — no routines, no calls, no
    boundaries, in a file that parsed perfectly yesterday.
    """
    out = code(r'auto s = R"(a\)b)" ; f();')
    assert "f()" in out, "the raw string swallowed the rest of the line"
    assert "a" not in out.replace("auto s", "")[:10]


def test_a_raw_string_with_a_named_delimiter_closes_on_that_name():
    out = code('auto s = R"json({"k": 1})json"; f();')
    assert "f()" in out
    assert '"k"' not in out


def test_an_r_that_does_not_open_a_token_is_not_a_raw_string():
    """`FOOR"x"` is an identifier and then a string, not a raw string.

    The check is on the character *before* the prefix rather than on the prefix's spelling,
    which is also what lets `u8R"(…)"` be one.
    """
    assert "k()" in code('FOOR"x"; k();')


def test_a_digit_separator_is_not_a_char_literal():
    """C++14 writes `1'000'000`, and a `'` taken for a quote swallows to the next one.

    Here that would mask `000` as a char literal and then read `000; char c = ` as code
    followed by a *second* quote — the mask inverts for the rest of the line.
    """
    out = code("int x = 1'000'000; char c = 'z'; g();")
    assert "1'000'000" in out, "a digit separator was read as a quote"
    assert "'z'" not in out, "a char literal was read as code"
    assert "g()" in out


def test_a_block_comment_does_not_nest():
    """`/* /* */` is closed. Counting depth reads the remainder of the file as comment."""
    out = code("a(); /* /* */ b();")
    assert "a()" in out and "b()" in out


def test_a_brace_inside_a_string_is_not_a_brace():
    """The whole reason this phase exists: `scopes.py` matches braces on `code_only()`."""
    out = code('const char* p = "it{s}"; h();')
    assert "{" not in out and "}" not in out
    assert "h()" in out


def test_an_unterminated_string_is_bounded_to_its_line():
    """Not the language's rule — the program is malformed either way — but it bounds the
    damage to the line that is wrong, where running to end-of-file reads every remaining
    brace as string and produces a map of nothing."""
    assert "Good()" in code('bad = "oops\nGood();')


# ------------------------------------------------------------ the offsets hold --- #

def test_blanking_keeps_offsets_so_a_match_indexes_back_into_the_text():
    """`code_only()` blanks rather than removes, so one offset table serves both (rule 51).

    A compacted copy would need a second mapping back to `text`, which is a second answer
    to the question `line_at` already answers.
    """
    src = 'void f() { /* note */ g("x"); }\n'
    m = mask(src)
    out = m.code_only()
    assert len(out) == len(m.text)
    assert m.text[out.index("g(")] == "g"


def test_newlines_survive_every_span_so_the_file_keeps_its_shape():
    """A multi-line comment must not collapse the lines under it into one."""
    out = code("a();\n/* one\n   two\n   three */\nb();\n")
    assert out.count("\n") == 5


def test_the_spans_are_named_rather_than_merged():
    """A comment, a string and a char are three facts, not one *not-code*.

    `literals.py` reads strings and `routines.py` reads the comment above a declaration, so
    flattening them would cost a routine its own documentation.
    """
    m = mask('// c\nauto s = "x"; char k = \'y\';\n')
    kinds = set(m.kind)
    assert {Span.LINE_COMMENT, Span.STRING, Span.CHAR, Span.CODE} <= kinds
