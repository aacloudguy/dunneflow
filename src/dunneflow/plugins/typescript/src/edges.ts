/**
 * Where each call goes, asked of the checker that already knows.
 *
 * This is the whole payoff of reading TypeScript with TypeScript. Chunk 9's map had 1,518
 * routines and **no internal edges at all**, and the honest thing it could say was that it
 * had none. Nothing here guesses: a call the checker did not resolve is left external, and
 * a bare name is never matched against a routine that happens to share it (rule 1, and
 * rule 5 — the two defects this replaces are exactly the ones Python's resolver spends
 * four hundred lines avoiding).
 *
 * **Two rungs and no third.**
 *
 * 1. `checker.getResolvedSignature(node)` — *which declaration does this call reach*. It is
 *    the question the compiler itself answers to type-check the call, so it is right about
 *    an overload set by construction: `PrismaClient.$transaction` declared three times
 *    resolves to the one the arguments fit, and chunk 9 already gave each of the three an
 *    identity of its own.
 * 2. Failing that, the symbol behind the callee expression, through `getAliasedSymbol` for
 *    an import, down to its declarations. **Exactly one** routine-like declaration is an
 *    edge; several is **no edge with the count recorded**, which is what `ambiguous` means
 *    and is exactly how Python already answers a name collision.
 *
 * There is no rung that matches a name, because that is the rung using a compiler is meant
 * to remove.
 *
 * **A declaration becomes a target by node identity, never by re-deriving a line.**
 * `Extractor.anchors` records which node each routine was declared at as the routine is
 * made, and the same walk fills it here — so a declaration is looked up by walking its
 * ancestors until one is a key. `line_start` is taken from a different node for each of the
 * five shapes a routine is written in, and a second function that worked it out again would
 * disagree with the first on exactly the shapes nobody tests (rule 51).
 *
 * **The caller side is the same walk too**, and that is not an economy. `site_id` is
 * `makeId("site", caller_id, expr, ordinal)`, and the ordinal counts identical expressions
 * within one caller — so a second traversal that visited nodes in any other order would
 * mint ids that name call sites the map does not have, with no symptom but a resolution
 * rate that is quietly nought.
 *
 * **A target outside the map is not an error and not a silence.** A call into
 * `node_modules`, into `lib.dom.d.ts` or into a `.svelte` file the walk never read is
 * reported with the file it landed in; the host looks it up, finds no routine, and records
 * it external — rule 26 by construction. The plugin does not pre-judge that, because the
 * plugin does not know what the host stored.
 */

import ts from "typescript";
import { walkFile, type CallNode } from "./extract.js";
import type { Routine, SuppliedEdge } from "./facts.js";
import { relPath, type Session } from "./program.js";
import type { RuleSet } from "./rules.js";

export interface EdgeHarvest {
  edges: SuppliedEdge[];
  /**
   * Call sites whose far end this reader could not name — **and the two reasons are two
   * numbers**, because they are two different facts and only one of them is a limitation
   * of this reader (design rule 21).
   *
   * `outside` is *the checker answered and the answer is not in this map*: a call into
   * `node_modules`, into `lib.dom.d.ts`, into a class constructor with no body. That is an
   * external call and the map is right about it. `unknown` is *the checker could not say*:
   * `obj[k]()`, a call through an `any`, a name the compilation does not hold. Flattening
   * the two would make a healthy map of a program that leans on libraries look exactly
   * like a reader that had stopped resolving.
   */
  outside: number;
  unknown: number;
  /** Files whose walk threw. Named rather than counted: it is a defect, not a filter. */
  failed: string[];
}

/**
 * The expression naming what is called: the callee, or a component element's tag.
 *
 * One function because rung 2 asks one question — *what is this name bound to* — and the
 * three node kinds spell the name in two fields. `getResolvedSignature` needs no such
 * thing: it takes the union whole, which is what `ts.CallLikeExpression` means.
 *
 * A `ts.Node` rather than a `ts.Expression`, because `<svg:circle>`'s namespaced tag is
 * neither — and `getSymbolAtLocation` asks about a node. Such a tag never reaches here:
 * `namesAValue` refused it a call site, so the width costs nothing and refuses nothing.
 */
function callee(node: CallNode): ts.Node {
  return ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)
    ? node.tagName
    : node.expression;
}

/** Where a routine lives, as the extractor recorded it. */
interface Target {
  file: string;
  line: number;
  name: string;
}

/**
 * The routine-like declarations behind a symbol, deduped.
 *
 * A symbol can have several declarations for reasons that are not ambiguity at all — an
 * interface and a `const` of the same name, a type and a value — so what is counted is the
 * declarations that reach **different routines**, not the declarations.
 */
function anchorsOf(
  decls: readonly ts.Declaration[],
  anchors: Map<ts.Node, Routine>,
): Routine[] {
  const out: Routine[] = [];
  for (const d of decls) {
    const hit = climb(d, anchors);
    if (hit !== null && !out.includes(hit)) out.push(hit);
  }
  return out;
}

/**
 * Whether a declaration could name a routine at all — the climb's one stopping condition.
 *
 * **Found by chunk 11c and it is a false edge, not a missing one.** `lib/rate-limit.ts`
 * writes `const { DynamoDBClient } = await import("@aws-sdk/client-dynamodb")` and then
 * `new DynamoDBClient({})`. The checker answers that call with the **binding element** —
 * which sits *inside* `getDocClient` — so an unguarded climb walks up out of it, finds the
 * first anchor above, and reports `getDocClient` calling `getDocClient`. Two of DunneCorp's
 * internal edges were that, and both named a routine that calls itself once, in a program
 * with no recursion in it.
 *
 * **And a type is not an implementation.** `run(action: () => Promise<R>)` calling
 * `action()` resolves — through rung 1 — to the `FunctionType` node in the parameter's own
 * annotation, which climbs to `run` and reports it calling itself. That was the last self
 * call left on DunneCorp after the three value shapes below, and it is the same defect a
 * third way: a shape somebody wrote down is not somewhere control can go.
 *
 * Three value shapes and one argument: each names a **value** rather than a declared
 * function.
 * A destructured binding and a parameter are values whatever encloses them — `run(action)`
 * calling `action()` is a call through something its caller supplied, and reporting it as
 * `run` calling `run` is the same false edge in its last shape. A `const` names a routine
 * only when what it is bound to is a function, which is the same test
 * `Extractor.variableStatement` applies when it decides to record one there, so the two
 * cannot disagree about what `const f = () => {}` is.
 *
 * Measured after: **58 of DunneCorp's 403 internal edges were a routine calling itself**,
 * and one remained until `isParameter` joined the list. `const [x, setX] = useState()` is
 * the commonest line in React, so a React map was 27% self-calls — the kind of number that
 * looks like a busy program rather than a broken reader (rule 49).
 */
function namesARoutine(node: ts.Node): boolean {
  // A type is not an implementation. Every kind here can appear **only** inside a type,
  // so a call that resolves to one goes wherever the value it was called through came
  // from — which is exactly what this map cannot say. An overload *signature* is a
  // `FunctionDeclaration` with no body and is deliberately not in this list, because
  // resolving an overload set to the declaration the arguments fit is chunk 10's own
  // feature and the shape it was tested on.
  if (ts.isFunctionTypeNode(node) || ts.isConstructorTypeNode(node)
      || ts.isCallSignatureDeclaration(node) || ts.isConstructSignatureDeclaration(node)
      || ts.isMethodSignature(node) || ts.isIndexSignatureDeclaration(node)
      || ts.isPropertySignature(node)) {
    return false;
  }
  if (ts.isParameter(node) || ts.isBindingElement(node)) return false;
  if (ts.isVariableDeclaration(node)) {
    const init = node.initializer;
    return init !== undefined
      && (ts.isArrowFunction(init) || ts.isFunctionExpression(init));
  }
  return true;
}

/**
 * The nearest routine this node sits in, by the anchors the extractor recorded.
 *
 * The climb is needed because a checker's declaration is frequently an inner node of the
 * thing the extractor anchored on — it points at an `ArrowFunction` and the routine was
 * anchored on the `VariableStatement` three levels up. It stops at the source file rather
 * than running out of parents, so a declaration that belongs to no routine answers
 * *nothing* rather than the file.
 *
 * **It has two stopping conditions and each catches what the other cannot.**
 * `namesARoutine` refuses a declaration that could not name a function at all; the
 * function-like test inside the loop refuses a declaration that sits **inside a function
 * this reader did not record**, where every anchor above belongs to something else. A
 * binding directly inside a named function needs the first and passes the second; an arrow
 * handed to `useCallback` needs the second and passes the first.
 */
function climb(node: ts.Node, anchors: Map<ts.Node, Routine>): Routine | null {
  if (!namesARoutine(node)) return null;
  let at: ts.Node | undefined = node;
  while (at !== undefined && !ts.isSourceFile(at)) {
    const hit = anchors.get(at);
    if (hit !== undefined) return hit;
    // **The climb stops at a function this reader did not record.** `const triggerRefresh
    // = useCallback(() => {…})` is an anonymous callback, which is deliberately not a
    // routine (see `extract.ts`' header) — so a declaration inside it belongs to it, and
    // the anchor above it is the *enclosing* component. Walking past one is how a React
    // provider came to call itself six times.
    if (ts.isFunctionLike(at)) return null;
    at = at.parent;
  }
  return null;
}

/**
 * Walk every file of every project, resolve every call, and say where each one goes.
 *
 * Two passes over the file set and not one, because a call in `a.ts` reaches a routine in
 * `b.ts` and the anchors of `b.ts` do not exist until `b.ts` has been walked. The first
 * pass is the extraction walk with a checker attached; the second is a lookup.
 */
export function collectEdges(session: Session, rules: RuleSet): EdgeHarvest {
  const anchors = new Map<ts.Node, Routine>();
  const where = new Map<Routine, Target>();
  const pending: {
    checker: ts.TypeChecker;
    calls: { site_id: string; caller_id: string; node: CallNode }[];
  }[] = [];
  const failed: string[] = [];

  for (const project of session.projects) {
    for (const abs of project.roots) {
      const sf = project.program.getSourceFile(abs);
      if (sf === undefined) {
        // In the root list and not in the program: the compiler could not read it. It is
        // named rather than counted, because one unreadable root is a fact about that file
        // and a number is a fact about nothing (design rule 1).
        failed.push(relPath(session.root, abs));
        continue;
      }
      const rel = relPath(session.root, abs);
      let ex;
      try {
        ex = walkFile(rel, sf.text, rules, sf, project.checker);
      } catch {
        failed.push(rel);
        continue;
      }
      for (const [node, routine] of ex.anchors) anchors.set(node, routine);
      for (const routine of ex.routines) {
        where.set(routine, {
          file: routine.file,
          line: routine.line_start,
          name: routine.name,
        });
      }
      pending.push({
        checker: project.checker,
        // **A call that touches a boundary is never also an internal edge** (rule 2), and
        // this reader already said which ones those are. The host suppresses them before
        // any resolver sees them, so an edge supplied for one would be work nobody reads
        // and a `supplied` figure that counts calls the map never resolved (rule 32).
        calls: ex.callNodes.filter((c) => c.site.at_boundary !== true).map((c) => ({
          site_id: c.site.site_id ?? "",
          caller_id: c.site.caller_id,
          node: c.node,
        })),
      });
    }
  }

  const edges: SuppliedEdge[] = [];
  let outside = 0;
  let unknown = 0;
  for (const group of pending) {
    for (const call of group.calls) {
      const answer = resolveOne(group.checker, call.node, anchors);
      /* **Where it stops, and why** (BACKLOG 36): sent with no target, in the words every
       * reader uses, so *About this map* can say it rather than counting a silence. */
      if (answer === "unknown") {
        unknown += 1;
        edges.push({
          site_id: call.site_id, caller_id: call.caller_id, reason: "untyped",
          how: "symbol; the checker could not say: a call through `any`, a computed name, "
            + "or a name the compilation does not hold",
        });
        continue;
      }
      if (typeof answer === "object" && "outside" in answer) {
        outside += 1;
        edges.push({
          site_id: call.site_id, caller_id: call.caller_id, reason: "outside",
          frontier: answer.outside, how: "symbol; declared outside this map",
        });
        continue;
      }
      if (typeof answer === "number") {
        // Several declarations competed. No edge, and the count is the honest reason —
        // never an arbitrary pick, which would be the one defect a checker cannot excuse.
        unknown += 1;
        edges.push({
          site_id: call.site_id,
          caller_id: call.caller_id,
          candidates: answer,
          how: "symbol",
        });
        continue;
      }
      const target = where.get(answer.routine);
      if (target === undefined) {
        unknown += 1;
        edges.push({
          site_id: call.site_id, caller_id: call.caller_id, reason: "unfollowed",
          how: "symbol; a routine this reader found and could not place",
        });
        continue;
      }
      edges.push({
        site_id: call.site_id,
        caller_id: call.caller_id,
        file: target.file,
        line: target.line,
        name: target.name,
        how: answer.how,
      });
    }
  }

  return { edges, outside, unknown, failed };
}

/**
 * One call site: a routine, a candidate count, or one of two kinds of *no*.
 *
 * `"unknown"` is *the checker could not say* — `obj[k]()`, a call through an `any`, a name
 * the compilation does not hold. `"outside"` is *it said, and the answer is not a routine
 * this reader records* — `node_modules`, a `.d.ts`, a declaration with no body. A number is
 * *it said several*. All four are different facts and none is collapsed into another
 * (rule 49: a plausible single answer is what hides the three real ones).
 */
function resolveOne(
  checker: ts.TypeChecker,
  node: CallNode,
  anchors: Map<ts.Node, Routine>,
): { routine: Routine; how: string } | number | { outside: string } | "unknown" {
  let answered = false;
  let far: ts.Declaration | undefined;

  const signature = checker.getResolvedSignature(node);
  const declared = signature?.declaration;
  if (declared !== undefined) {
    answered = true;
    far = declared;
    const hit = climb(declared, anchors);
    if (hit !== null) return { routine: hit, how: "signature" };
    // The checker resolved it and the far end is not a routine this reader records. Fall
    // through rather than answer: the symbol may still reach a declaration that is one —
    // an overload's implementation, a re-export — and only when that fails too is this
    // call genuinely outside the map.
  }

  let symbol = checker.getSymbolAtLocation(callee(node));
  if (symbol !== undefined && (symbol.flags & ts.SymbolFlags.Alias) !== 0) {
    // An import binds a name to something declared elsewhere, and *elsewhere* is the whole
    // question. Unaliasing is the checker doing what `resolve/python/calls.py` spends its
    // import maps doing, and doing it with the module resolution the project actually uses.
    try {
      symbol = checker.getAliasedSymbol(symbol);
    } catch {
      return answered ? { outside: farEnd(far, callee(node)) } : "unknown";
    }
  }
  const decls = symbol?.declarations;
  if (decls === undefined || decls.length === 0) {
    return answered ? { outside: farEnd(far, callee(node)) } : "unknown";
  }

  const found = anchorsOf(decls, anchors);
  if (found.length === 1) {
    const one = found[0];
    if (one !== undefined) return { routine: one, how: "symbol" };
  }
  if (found.length > 1) return found.length;
  // A symbol with declarations, none of which is a routine in this map.
  return { outside: farEnd(far ?? decls[0], callee(node)) };
}

/**
 * The far end, as a reader can look it up: the package a declaration ships in
 * (`react.useState`, `@tauri-apps/api.invoke`), the library file the language declares it in
 * (`lib.es5.d.ts.map` for `xs.map(f)`), or the declaration file in this tree, then the name
 * called.
 */
function farEnd(decl: ts.Declaration | undefined, name: ts.Node): string {
  const called = ts.isPropertyAccessExpression(name) ? name.name.text
    : ts.isIdentifier(name) ? name.text : name.getText();
  if (decl === undefined) return called;
  const file = decl.getSourceFile().fileName.replace(/\\/g, "/");
  const nm = file.lastIndexOf("/node_modules/");
  let home: string;
  if (nm >= 0) {
    const rest = file.slice(nm + "/node_modules/".length).split("/");
    home = rest[0]?.startsWith("@") ? `${rest[0]}/${rest[1] ?? ""}` : (rest[0] ?? "");
    if (home === "@types/node" || home.startsWith("@types/")) home = home.slice("@types/".length);
  } else {
    home = file.slice(file.lastIndexOf("/") + 1);
  }
  return `${home}.${called}`;
}
