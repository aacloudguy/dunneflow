/**
 * Which dependency a call actually reaches — the boundary a name cannot find.
 *
 * `detectors/typescript.yaml`'s `boundaries` section matches the **dotted spelling** of an
 * expression, which is the only thing chunk 9 had and is a guess about how somebody named
 * a local variable. It works when a program writes `prisma.user.findMany` and fails
 * silently when it writes `client.user.findMany` — and it is rule 5, which is why every
 * Python rule in that file contains a dot.
 *
 * DunneCorp is the corpus that makes that visible, because three of its four most
 * interesting boundaries are written in a way no rule could match:
 *
 * ```
 * const resend = new Resend(apiKey);  await resend.emails.send({…})   // a local const
 * await getStripe().checkout.sessions.create({…})                     // a factory call
 * await doc.send(new UpdateCommand({…}))                              // a typed receiver
 * ```
 *
 * The checker has known the answer since chunk 10: it resolved every one of them to type
 * the call. So the question asked here is *which package declares the far end*, and the
 * answer is matched against a table of packages rather than of spellings.
 *
 * **A package rule outranks a name rule**, and that is the whole ordering. A name rule is a
 * guess about spelling; a package rule is what the compiler resolved. Where the checker has
 * spoken its answer is the fact, and the name rules stay as the fallback for the calls it
 * could not resolve — which is chunk 10's own argument, one fact type over.
 *
 * **It is one row either way** (rule 40): a call yields one boundary, from whichever lane
 * claimed it, never one from each.
 *
 * **`@types/foo` is `foo`.** A package that ships no types of its own has them in a
 * separate one, so `bcrypt.hash` resolves into `@types/bcrypt` and `console.log` into
 * `@types/node`. They are the same dependency and the prefix is stripped before matching —
 * measured on uigen, where `@types/bcrypt` is the only spelling `bcrypt` ever has.
 *
 * **The standard library is not a package**, and needs no special case: `libs.LIB_DIR` is a
 * path on no disk and contains no `node_modules`, so `Array.prototype.map` answers nothing
 * here and falls through to the name rules exactly as it did before.
 *
 * **This is not `edges.resolveOne` and the two must not be merged.** That one asks *which
 * routine of this program*, needs every declaration to see whether several competed, and
 * tells a checker that could not answer from one that answered elsewhere. This asks *which
 * dependency*, which is a property of the file a declaration sits in and not of the
 * overload chosen — so the first declaration is as good as the last, and a count of them
 * says nothing. One question each (rule 51 cuts the other way when the questions differ).
 */

import ts from "typescript";
import type { PackageRule, RuleSet } from "./rules.js";

const NODE_MODULES = "/node_modules/";
const TYPES_SCOPE = "@types/";

/**
 * The package a file belongs to, or `""` for a file of the program being read.
 *
 * The **last** `node_modules` in the path, because a dependency's own dependencies are
 * nested inside it and `a/node_modules/b/node_modules/c` is `c`.
 */
export function packageOf(file: string): string {
  const at = file.lastIndexOf(NODE_MODULES);
  if (at === -1) return "";
  const parts = file.slice(at + NODE_MODULES.length).split("/");
  const head = parts[0] ?? "";
  const name = head.startsWith("@") ? `${head}/${parts[1] ?? ""}` : head;
  return name.startsWith(TYPES_SCOPE) ? name.slice(TYPES_SCOPE.length) : name;
}

/** The declaration behind a call, by the checker's own two answers. */
function declarationOf(
  checker: ts.TypeChecker,
  node: ts.CallExpression | ts.NewExpression,
): ts.Declaration | undefined {
  const declared = checker.getResolvedSignature(node)?.declaration;
  if (declared !== undefined) return declared;
  let symbol = checker.getSymbolAtLocation(node.expression);
  if (symbol !== undefined && (symbol.flags & ts.SymbolFlags.Alias) !== 0) {
    try {
      symbol = checker.getAliasedSymbol(symbol);
    } catch {
      return undefined;
    }
  }
  return symbol?.declarations?.[0];
}

/** What a package rule says about one call, with the package it was matched on. */
export interface PackageHit {
  rule: PackageRule;
  pkg: string;
}

/**
 * The package rule for one call, or nothing.
 *
 * `undefined` is returned both where the checker could not say and where it said a package
 * nobody declared a rule for. The two are not told apart here on purpose: what follows is
 * the name rules, and they are the answer in both cases.
 */
export function packageBoundary(
  checker: ts.TypeChecker | undefined,
  node: ts.CallExpression | ts.NewExpression,
  rules: RuleSet,
): PackageHit | null {
  if (checker === undefined || rules.packages.length === 0) return null;
  const declared = declarationOf(checker, node);
  if (declared === undefined) return null;
  const pkg = packageOf(declared.getSourceFile().fileName);
  if (!pkg) return null;
  for (const rule of rules.packages) {
    // A scope is declared with its slash — `@aws-sdk/` — and a package without one, so the
    // two cannot be confused and `stripe` never matches `stripe-webhooks`.
    if (rule.name.endsWith("/") ? pkg.startsWith(rule.name) : pkg === rule.name) {
      return { rule, pkg };
    }
  }
  return null;
}
