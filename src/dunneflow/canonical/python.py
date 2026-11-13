"""The canonical form of one Python expression.

**The only place in this program that re-renders an expression**, and it exists because
two questions want two different answers about the same string.

`call_args.expr` and `constants.value` are recorded **as written** and never shortened
(rules 8 and 75, and chunk 3's decision): a reader who goes looking in the file for the
string a panel showed them has to find it, and `ast.unparse` returns something equivalent
rather than identical -- `d["k"]` comes back `d['k']`, a wrapped argument comes back on one
line. That is exactly the wrong answer for *display*.

It is exactly the right answer for a **comparison**, which asks a different question: are
these two the same expression. Lictores' pair has a `typer.echo` whose message was re-wrapped
across two lines with not one character of its content changed, and comparing what was
written puts it in *behaves differently* -- the band that promises what a routine **does**
moved, sitting beside one that says *edited only, and nothing it does changed*. A false
difference tells the reader something moved when it did not, which is rule 1.

So the store keeps what was written and the comparison asks this. Neither is a compromise.
"""

from __future__ import annotations

import ast


def canonical_expr(expr: str) -> str:
    """`expr` in a form two writings of the same expression share.

    **Returns its input unchanged when it cannot parse**, which is a real answer and not a
    failure: the comparison then asks about what was written, which is the honest question
    when there is nothing better to ask. Substituting anything else would be rule 49's
    defect -- a plausible value standing where a measurement belongs.

    Every one of the 49 arguments on Lictores that lands here is a splat fragment
    (`**kwargs`, `**_CANONICAL_JSON_KWARGS`). A splat is not an expression on its own, it
    is a call-site form, and comparing those as written is correct.

    The parenthesised retry is not a nicety. A multi-line expression is sliced out of the
    file with its continuation lines' **indentation intact**, so it reaches here as

        f"session {session!r} already holds the claim "
                    f"(grant {outgoing.grant_id}) - no change"

    which is an `IndentationError` on its own and an ordinary expression inside brackets.
    """
    for candidate in (expr, "(" + expr + ")"):
        try:
            return ast.unparse(ast.parse(candidate, mode="eval").body)
        except (SyntaxError, ValueError, RecursionError):
            continue
    return expr
