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

/**
 * Is this call the global `fetch` reached through another name? (BACKLOG 4.)
 *
 * `const f = fetch; f(url)`, `const get = window.fetch`, `const go = fetch.bind(globalThis)`:
 * the request is made, and the spelling rule sees `f`, which is not a boundary by any name
 * it knows. The checker can follow the binding, so it is asked -- as `packageBoundary`
 * asks it about a package -- and only where the spelling has already said nothing.
 *
 * **By value, never by type.** A parameter typed `typeof fetch` has fetch's signature and
 * holds whatever its caller passed: DunneNote's `fetchImpl` is exactly that, in a corpus
 * whose stated ground truth is that no program file calls `fetch` at all (rule 5). So the
 * callee has to be a `const` whose initialiser *is* the global -- written as `fetch`,
 * `window.fetch` or `globalThis.fetch`, or a `.bind` of one -- and the global is confirmed
 * by its declaration being the standard library's, not a routine of this program that
 * happens to share the name.
 *
 * **Proved on a fixture and on no real corpus.** Searched for one on 2026-09-18: one hit
 * in the whole Developer tree, in a test file. Built on Tom's call (2026-10-02), pressed in
 * `tests/test_typescript.py`, and re-run on `gstack`, the only real `fetch` population to
 * hand, to show it changes nothing there.
 */
export function isGlobalFetch(
  checker: ts.TypeChecker | undefined,
  node: ts.CallExpression | ts.NewExpression,
): boolean {
  if (checker === undefined || !ts.isIdentifier(node.expression)) return false;
  const held = checker.getSymbolAtLocation(node.expression)?.valueDeclaration;
  if (held === undefined || !ts.isVariableDeclaration(held) || held.initializer === undefined
      || !ts.isVariableDeclarationList(held.parent)
      || (held.parent.flags & ts.NodeFlags.Const) === 0) {
    return false;
  }
  let init: ts.Expression = held.initializer;
  if (ts.isCallExpression(init) && ts.isPropertyAccessExpression(init.expression)
      && init.expression.name.text === "bind") {
    init = init.expression.expression;
  }
  const named = ts.isIdentifier(init) ? init
    : ts.isPropertyAccessExpression(init) ? init.name : undefined;
  if (named === undefined || named.text !== "fetch") return false;
  const declared = checker.getSymbolAtLocation(named)?.declarations?.[0];
  if (declared === undefined) return false;
  const file = declared.getSourceFile();
  if (!file.isDeclarationFile) return false;
  const pkg = packageOf(file.fileName);
  return pkg === "" ? /\/lib\.[^/]*\.d\.ts$/.test(file.fileName)
    : pkg === "node" || pkg === "undici-types";
}
