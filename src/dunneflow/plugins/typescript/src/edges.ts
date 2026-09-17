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
import { walkFile } from "./extract.js";
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
 * The nearest routine this node sits in, by the anchors the extractor recorded.
 *
 * The climb is unconditional and stops at the first anchor, because a checker's declaration
 * is frequently an inner node of the thing the extractor anchored on — it points at an
 * `ArrowFunction` and the routine was anchored on the `VariableStatement` three levels up.
 * It stops at the source file rather than running out of parents, so a declaration that
 * belongs to no routine answers *nothing* rather than the file.
 */
function climb(node: ts.Node, anchors: Map<ts.Node, Routine>): Routine | null {
  let at: ts.Node | undefined = node;
  while (at !== undefined && !ts.isSourceFile(at)) {
    const hit = anchors.get(at);
    if (hit !== undefined) return hit;
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
    calls: { site_id: string; caller_id: string; node: ts.CallExpression | ts.NewExpression }[];
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
      if (answer === "unknown") {
        unknown += 1;
        continue;
      }
      if (answer === "outside") {
        outside += 1;
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
  node: ts.CallExpression | ts.NewExpression,
  anchors: Map<ts.Node, Routine>,
): { routine: Routine; how: string } | number | "outside" | "unknown" {
  let answered = false;

  const signature = checker.getResolvedSignature(node);
  const declared = signature?.declaration;
  if (declared !== undefined) {
    answered = true;
    const hit = climb(declared, anchors);
    if (hit !== null) return { routine: hit, how: "signature" };
    // The checker resolved it and the far end is not a routine this reader records. Fall
    // through rather than answer: the symbol may still reach a declaration that is one —
    // an overload's implementation, a re-export — and only when that fails too is this
    // call genuinely outside the map.
  }

  let symbol = checker.getSymbolAtLocation(node.expression);
  if (symbol !== undefined && (symbol.flags & ts.SymbolFlags.Alias) !== 0) {
    // An import binds a name to something declared elsewhere, and *elsewhere* is the whole
    // question. Unaliasing is the checker doing what `resolve/python/calls.py` spends its
    // import maps doing, and doing it with the module resolution the project actually uses.
    try {
      symbol = checker.getAliasedSymbol(symbol);
    } catch {
      return answered ? "outside" : "unknown";
    }
  }
  const decls = symbol?.declarations;
  if (decls === undefined || decls.length === 0) return answered ? "outside" : "unknown";

  const found = anchorsOf(decls, anchors);
  if (found.length === 1) {
    const one = found[0];
    if (one !== undefined) return { routine: one, how: "symbol" };
  }
  if (found.length > 1) return found.length;
  // A symbol with declarations, none of which is a routine in this map.
  return "outside";
}
