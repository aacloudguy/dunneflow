/**
 * `ingest/dotted.py`, kept for TypeScript. The contract is the host's; this is one
 * reader's obedience to it, and `tests/fixtures/dotted/cases.json` is what says so.
 *
 * Every `exact`, `prefix`, `method` and `contains` in `detectors/typescript.yaml` is
 * matched against what this returns. A reader that spells an expression differently does
 * not fail — it makes every rule miss, so the map comes back with no boundaries at all,
 * looking exactly like a program that touches nothing.
 *
 * The eight clauses, and where each one lives below:
 *
 *  1. a source-order identifier chain, dot-joined — `chain`
 *  2. a call in the middle folds to its callee — the `CallExpression` arm
 *  3. no name anywhere in the chain gives `""`, and `""` is never matched — every arm
 *     returns `""` and `chain` propagates it
 *  4. no resolution, no alias expansion — nothing here looks anything up
 *  5. nullability is not identity — the `NonNullExpression` arm, and `?.` is already
 *     invisible because TypeScript models it as an ordinary property access carrying a
 *     `questionDotToken`
 *  6. type arguments are not part of the name — free, because `foo<T>()` puts them on the
 *     **call** and this reads the call's `expression`
 *  7. `new Foo()` is `Foo`, and `is_construction` rides beside it — `isConstruction`
 *  8. the receiver word as written — `this` is returned as `this`, never expanded
 */

import ts from "typescript";

/**
 * The dotted form of an expression, or `""` where it cannot be named.
 *
 * `""` is an answer and not a failure: it means naming the chain would require deciding
 * what something is, and deciding that is resolution (clause 3). It is never matched
 * against a rule.
 */
export function dotted(node: ts.Expression | undefined): string {
  if (node === undefined) return "";

  if (ts.isIdentifier(node)) return node.text;
  if (node.kind === ts.SyntaxKind.ThisKeyword) return "this";
  if (node.kind === ts.SyntaxKind.SuperKeyword) return "super";

  // `a!.b` — nullability is not identity (clause 5).
  if (ts.isNonNullExpression(node)) return dotted(node.expression);
  if (ts.isParenthesizedExpression(node)) return dotted(node.expression);
  // `x as T`, `x satisfies T`, `<T>x` — a type assertion changes no name.
  if (ts.isAsExpression(node) || ts.isSatisfiesExpression(node)) return dotted(node.expression);
  if (ts.isTypeAssertionExpression(node)) return dotted(node.expression);
  if (ts.isExpressionWithTypeArguments(node)) return dotted(node.expression);

  // `a.b`, and `a?.b` — TypeScript models the optional form as this same node carrying a
  // `questionDotToken`, so clause 5 costs nothing here.
  if (ts.isPropertyAccessExpression(node)) {
    const base = dotted(node.expression);
    if (!base) return "";
    // A private name (`this.#x`) has no dotted spelling a rule could be written against.
    if (ts.isPrivateIdentifier(node.name)) return "";
    return `${base}.${node.name.text}`;
  }

  // `a["b"]` — clause 3, and *anywhere* in the chain rather than only at its root:
  // `reg.handlers["x"].run()` cannot be named without deciding what `handlers["x"]` is.
  if (ts.isElementAccessExpression(node)) return "";

  // Clause 2: a call in the middle folds to its callee, repeatedly.
  // `createClient(x).query()` is `createClient.query`.
  if (ts.isCallExpression(node)) return dotted(node.expression);
  if (ts.isNewExpression(node)) return dotted(node.expression);

  // A literal, an object, an arrow, an await, an arithmetic expression. None of them
  // names anything, and inventing a word for one would put it in front of every rule.
  return "";
}

/** Clause 7. `new Foo()` and `Foo()` call one name and do two different things. */
export function isConstruction(node: ts.Node): boolean {
  return ts.isNewExpression(node);
}
