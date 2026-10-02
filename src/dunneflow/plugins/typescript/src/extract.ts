/**
 * One TypeScript file's facts.
 *
 * `extractors/python/extract.py`, one language over, and deliberately shaped the same way
 * so the two can be read against each other. What moves is the subject; internal
 * computation is not. A loop is recorded as a **span** and never as a variable, an
 * operator or a value.
 *
 * **What this reader deliberately does not do, and each one is stated rather than absent:**
 *
 * - **It resolves nothing.** No type checker, no symbol table, no module resolution. Chunk
 *   9 is extraction only: every TypeScript call is left external by the host, which names
 *   the count rather than leaving a reader to infer it from a thin graph. The checker is
 *   what chunk 10's supplied edges are for, and `open` already has the whole file set so
 *   that it can be built there without changing the protocol.
 * - **An anonymous function is not a routine.** A declaration, a method, and a function or
 *   arrow *bound to a name* are routines; a callback passed inline is not, and its calls
 *   and boundaries belong to the nearest named routine that encloses it. Naming one would
 *   mean inventing a word for a reader to look for in a file that does not contain it
 *   (rule 30), and the alternative — thousands of `<anonymous>` rows — is rule 1's own
 *   subject. React's components are named, and `useEffect`'s callbacks are chunk 11's.
 * - **The DOM is not a boundary.** `detectors/typescript.yaml`'s header says why.
 * - **JSX conditional rendering is not a decision.** `{cond && <X/>}` and a ternary in
 *   JSX are left out, because `shape.judge()`'s test is *does something move inside it*
 *   and what moves is a rendered element — which this tool does not model. Recording them
 *   would put thousands of points on a worklist no reader can act on (rule 1).
 *
 * **What JSX *is*, since chunk 11: a component element is a call.** `<PageHero title={x}/>`
 * is the caller handing another routine of this program its arguments, which is the one
 * thing this tool exists to record — and in a React program it is most of the flow. The
 * tag names the callee, the props are its keyword arguments, and the checker names the far
 * end exactly as it does for `f(x)`. An intrinsic element — a bare lowercase tag, or a
 * hyphenated one — is **not** a call: it is React's own rule for telling a value from a
 * string, and it is the same judgement `detectors/typescript.yaml` already makes about the
 * DOM, which is the program's rendered output rather than something it calls.
 */

import ts from "typescript";
import { callSiteId, controlPointId, definitionId, hashSource } from "./ids.js";
import { dotted, isConstruction } from "./dotted.js";
import {
  matchCall, matchNetwork, matchSubscript,
  type BoundaryRule, type RuleSet, type TargetKind,
} from "./rules.js";
import { waysIn } from "./routes.js";
import { isGlobalFetch, packageBoundary } from "./pkg.js";
import type {
  ArmKind,
  BoundaryHit,
  CallArg,
  CallSite,
  ClassDef_,
  Comment,
  Constant,
  ControlArm,
  ControlKind,
  ControlPoint,
  DataStructure,
  Entrypoint,
  Field_,
  FileFacts,
  ImportRec,
  NetworkCall,
  Param,
  Routine,
  StringLiteral,
  StructureKind,
} from "./facts.js";

/** `ingest/literals.py`'s bound, applied where the wire is. The host declares it. */
const LITERAL_MIN = 3;
const LITERAL_MAX = 200_000;

const MODULE_SCOPE = "<module>";

/** What a promise chain adds after the call that did the work. See `target`. */
const PROMISE_TAIL = new Set(["then", "catch", "finally"]);

/**
 * Every node this reader records a call site at.
 *
 * Widened for JSX in chunk 11 and named rather than spelled out at each use, because the
 * edge pass has to hold exactly this set: a node the extractor minted a `site_id` at and
 * the checker can be asked about. All three are `ts.CallLikeExpression`s, which is the
 * compiler's own word for *something that resolves to a signature* — `getResolvedSignature`
 * takes the union, so a component element is answered by the same question as `f(x)`.
 */
export type CallNode = ts.CallExpression | ts.NewExpression | ts.JsxOpeningLikeElement;

/**
 * Whether a JSX tag names a **value** rather than an element of the page.
 *
 * React's own rule, and it is a rule about spelling rather than about types: the transform
 * passes a bare lowercase identifier through as the *string* `"div"`, and anything else as
 * the thing that name is bound to. A hyphenated tag is a custom element, which is also a
 * string. `<Foo.Bar/>`, `<this.X/>` and `<Foo/>` all name a value.
 *
 * So `<div>` is not a call and `<Container>` is. That is the same judgement
 * `detectors/typescript.yaml` makes when it refuses to report the DOM at all: an element
 * the browser draws is this program's output, and 721 of DunneCorp's 910 tags are that.
 */
export function namesAValue(
  tag: ts.JsxTagNameExpression,
): tag is Exclude<ts.JsxTagNameExpression, ts.JsxNamespacedName> {
  // `<svg:circle>`: a namespaced tag is XML, never a binding.
  if (ts.isJsxNamespacedName(tag)) return false;
  if (!ts.isIdentifier(tag)) return true;
  const first = tag.text[0] ?? "";
  return !(first >= "a" && first <= "z") && !tag.text.includes("-");
}

/**
 * A module name for a language that has none.
 *
 * `PLAN-v2.md`'s amendment: the stored path with separators turned into dots and the
 * suffix dropped. Coarse — DunneNote comes out as three package plates for 767 files — and
 * it is the same answer analysing the parent directory would give, so it is not *wrong*.
 * The better answer is a `FileFacts.package` read from the nearest `package.json`, which
 * is a chunk of its own with its own measurement and is deliberately off this path.
 */
export function moduleName(rel: string): string {
  const noSuffix = rel.replace(/\.(m|c)?[jt]sx?$/, "");
  return noSuffix.split("/").filter(Boolean).join(".");
}

interface Scope {
  routine: Routine;
  isAsync: boolean;
}

export class Extractor {
  routines: Routine[] = [];
  calls: CallSite[] = [];
  boundaries: BoundaryHit[] = [];
  structures: DataStructure[] = [];
  classes: ClassDef_[] = [];
  imports: ImportRec[] = [];
  constants: Constant[] = [];
  control: ControlPoint[] = [];
  controlArms: ControlArm[] = [];
  literals: StringLiteral[] = [];
  network: NetworkCall[] = [];
  literalsDropped = 0;
  /**
   * **Which node a routine was declared at**, so the edge pass never has to work it out a
   * second time.
   *
   * `line_start` is taken from a different node for each of the five shapes a routine is
   * written in — the declaration for a `function`, the *member* for a class field holding
   * an arrow, the whole `VariableStatement` for `const f = () => {}`. A second function
   * that re-derived it from a declaration the checker handed back would be a second answer
   * to *where does this routine begin*, and the two would disagree on exactly the shapes
   * nobody tests (rule 51). So the mapping is recorded as it is made, and the edge pass
   * walks a declaration's ancestors until one of them is a key here.
   *
   * Both the anchor and the function node are keys, because the checker points at either
   * depending on how the name was reached.
   */
  anchors = new Map<ts.Node, Routine>();
  /**
   * Every call site beside the node it was written at, for the edge pass and nothing else.
   *
   * Empty and unused during ordinary extraction, which is the point: the ids here are
   * minted by the **same** walk that mints the ones in `calls`, so a supplied edge and the
   * call site it names cannot come out of two different traversals with two different
   * ordinals (`callSiteId` has one).
   */
  callNodes: { site: CallSite; node: CallNode }[] = [];
  /**
   * The program's checker, where there is one. `undefined` when nothing has been opened.
   *
   * **It was held and never used until chunk 11c**, and the reason it is used now is worth
   * stating because it looks like the line chunk 9 drew being crossed. It is not: what a
   * call resolves to is still `edges.ts`' question and this walk never answers it. What
   * this asks is narrower and is a different fact — *which package declares the far end* —
   * because a boundary is a per-file fact and cannot be filled by a whole-program sweep
   * the way an edge can (`pkg.ts`). A name is still never matched against a routine here.
   */
  checker: ts.TypeChecker | undefined;

  private scope: Scope[] = [];
  private classStack: string[] = [];
  private depth = 0;
  private moduleRoutine: Routine | null = null;
  private moduleClaimed = false;
  private callOrdinal = new Map<string, number>();
  private controlOrdinal = new Map<string, number>();
  private boundarySeen = new Set<string>();
  // A program may declare one qualified name twice, and TypeScript's commonest way of
  // doing it is not broken code at all: an **overload set** is several
  // `FunctionDeclaration` nodes with one name, and a class may carry a method and a field
  // arrow of the same name. Both keep an identity of their own rather than merging, so the
  // collision can be reported — `extractors/python/extract.py:_identity`, one language
  // over, and the store's `UNIQUE(routines.id)` is what finds it when it is missing.
  private seenQualnames = new Map<string, number>();
  /**
   * The file's own directive prologue, read once and carried onto every routine in it.
   *
   * A file-level `"use server"` marks **all** of its exports — that is what the directive
   * means — so a reader asking which routines are server actions must find them all, and
   * one row on a module scope that may never be claimed (rule 96) would answer for none.
   */
  private fileDirectives: string[] = [];
  private lines: number;

  constructor(
    readonly path: string,
    readonly module: string,
    readonly src: string,
    readonly sf: ts.SourceFile,
    readonly rules: RuleSet,
  ) {
    this.lines = src.split("\n").length;
  }

  // ------------------------------------------------------------------ lines --- //

  line(pos: number): number {
    return this.sf.getLineAndCharacterOfPosition(pos).line + 1;
  }

  startLine(node: ts.Node): number {
    return this.line(node.getStart(this.sf));
  }

  endLine(node: ts.Node): number {
    return this.line(node.getEnd());
  }

  /** As written, sliced from the file's own text and never re-rendered (rule 8). */
  text(node: ts.Node | undefined): string {
    if (node === undefined) return "";
    return this.src.slice(node.getStart(this.sf), node.getEnd());
  }

  // ------------------------------------------------------------------ owner --- //

  /**
   * The routine module-level code belongs to, **prepared and not claimed** — rule 96, and
   * `extractors/python/extract.py:module_scope` states the whole argument. A string has to
   * name an owner before anybody knows whether it is a fact, so asking there must not be
   * what puts a routine in the map.
   */
  /** A stable id for a qualified name, disambiguating any real duplicate. */
  identity(qualname: string): string {
    const n = this.seenQualnames.get(qualname) ?? 0;
    this.seenQualnames.set(qualname, n + 1);
    return definitionId(this.path, qualname, n + 1);
  }

  moduleScope(): Routine {
    if (this.moduleRoutine === null) {
      this.moduleRoutine = {
        id: definitionId(this.path, `${this.module}.${MODULE_SCOPE}`),
        name: MODULE_SCOPE,
        qualname: `${this.module}.${MODULE_SCOPE}`,
        module: this.module,
        file: this.path,
        line_start: 1,
        line_end: this.lines || 1,
        docstring: "Module-level code: runs at import, before anything is called.",
        body_hash: hashSource(this.src),
      };
      if (this.fileDirectives.length) {
        this.moduleRoutine.decorators = [...this.fileDirectives];
      }
    }
    return this.moduleRoutine;
  }

  owner(): Routine {
    const top = this.scope[this.scope.length - 1];
    if (top !== undefined) return top.routine;
    const scope = this.moduleScope();
    if (!this.moduleClaimed) {
      this.moduleClaimed = true;
      this.routines.push(scope);
    }
    return scope;
  }

  ownerId(): string {
    const top = this.scope[this.scope.length - 1];
    return top !== undefined ? top.routine.id : this.moduleScope().id;
  }

  inAsyncRoutine(): boolean {
    const top = this.scope[this.scope.length - 1];
    return top !== undefined ? top.isAsync : false;
  }

  // ----------------------------------------------------------------- facts --- //

  recordCall(
    callerId: string,
    expr: string,
    line: number,
    atBoundary: boolean,
    args: CallArg[],
    construction: boolean,
  ): CallSite {
    const key = `${callerId}\u0000${expr}`;
    const ordinal = this.callOrdinal.get(key) ?? 0;
    this.callOrdinal.set(key, ordinal + 1);
    const site: CallSite = {
      caller_id: callerId,
      callee_expr: expr,
      line,
      site_id: callSiteId(callerId, expr, ordinal),
    };
    // **Rule 2: a call that touches a boundary is never also an internal edge.** The
    // host's resolver suppresses it, and the flag is what it reads.
    if (atBoundary) site.at_boundary = true;
    if (construction) site.is_construction = true;
    if (args.length) site.args = args;
    this.calls.push(site);
    return site;
  }

  literal(text: string, line: number, kind: "PLAIN" | "INTERPOLATED"): void {
    if (text.length < LITERAL_MIN || text.length > LITERAL_MAX) {
      this.literalsDropped += 1;
      return;
    }
    const lit: StringLiteral = { routine_id: this.ownerId(), line, text };
    if (kind !== "PLAIN") lit.kind = kind;
    this.literals.push(lit);
  }

  // ------------------------------------------------------------------ walk --- //

  run(): void {
    this.fileDirectives = this.directivesOf(this.sf.statements);
    for (const stmt of this.sf.statements) this.visit(stmt);
  }

  visit(node: ts.Node): void {
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) {
      this.importDecl(node);
      // An import binds names and calls nothing; descending would only find its literals.
      return;
    }
    if (ts.isImportEqualsDeclaration(node)) {
      this.importEquals(node);
      return;
    }
    if (ts.isFunctionDeclaration(node)) {
      this.routine(node, node.name?.text ?? "default", node);
      return;
    }
    if (ts.isClassDeclaration(node) || ts.isClassExpression(node)) {
      this.classDecl(node);
      return;
    }
    if (ts.isInterfaceDeclaration(node)) {
      this.structure(node, node.name.text, "INTERFACE", this.interfaceFields(node),
                     this.heritage(node));
      return;
    }
    if (ts.isTypeAliasDeclaration(node)) {
      this.structure(node, node.name.text, "TYPE_ALIAS", [], []);
      return;
    }
    if (ts.isEnumDeclaration(node)) {
      this.structure(node, node.name.text, "ENUM", this.enumFields(node), []);
      return;
    }
    if (ts.isVariableStatement(node)) {
      this.variableStatement(node);
      return;
    }
    if (ts.isModuleDeclaration(node)) {
      // `namespace X { ... }` and `declare module "x" { ... }`. The body's statements are
      // this file's, and the namespace's name is deliberately not folded into qualnames:
      // that would be a second naming convention for the same file (rule 30).
      if (node.body && ts.isModuleBlock(node.body)) {
        for (const s of node.body.statements) this.visit(s);
      }
      return;
    }

    this.expressionsIn(node);
  }

  /** Everything that is not a declaration: calls, control, strings. */
  expressionsIn(node: ts.Node): void {
    if (this.controlPoint(node)) return;

    if (ts.isCallExpression(node) || ts.isNewExpression(node)) {
      this.callExpr(node);
      return;
    }
    if (ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) {
      this.jsxElement(node);
      return;
    }
    if (ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node)) {
      if (this.accessBoundary(node)) return;
    }
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      this.literal(node.text, this.startLine(node), "PLAIN");
    } else if (ts.isTemplateExpression(node)) {
      this.templateLiteral(node);
      return;
    }
    if (this.namedFunction(node)) return;

    node.forEachChild((child) => this.expressionsIn(child));
  }

  /**
   * A function or arrow **bound to a name**: a declaration, a class member, and
   * `const f = () => {}` — which is how most TypeScript functions are written. An
   * anonymous one is not a routine; see this file's header.
   *
   * **Two shapes it does not reach, and they were claimed here until chunk 11 pressed
   * one.** `{ f() {} }` and `x.f = function () {}` bind a name as plainly as a `const`
   * does and neither becomes a routine: an object literal is a `Constant` whose value is
   * the literal whole, and the method bodies' calls belong to the enclosing scope. The
   * sentence was in this docstring from the day the reader was written and nothing had
   * ever asked it for one — rule 37, in prose. Measured over the three TypeScript corpora
   * before it was written down: **20 object-literal methods and 84 property functions**
   * across DunneNote, DunneCorp and uigen, so it is a real gap of about a hundred rather
   * than a rounding error, and it is stated rather than quietly closed here — it would
   * move DunneNote's routine count, which is the figure chunk 11 holds fixed to prove it
   * changed nothing but JSX.
   */
  namedFunction(node: ts.Node): boolean {
    if (ts.isFunctionDeclaration(node)) {
      this.routine(node, node.name?.text ?? "default", node);
      return true;
    }
    if (ts.isClassDeclaration(node) || ts.isClassExpression(node)) {
      this.classDecl(node);
      return true;
    }
    if (ts.isVariableStatement(node)) {
      this.variableStatement(node);
      return true;
    }
    return false;
  }

  // ------------------------------------------------------------- one routine --- //

  routine(
    fn: ts.FunctionLikeDeclaration,
    name: string,
    node: ts.Node,
    className: string | null = null,
  ): void {
    const parent = this.scope[this.scope.length - 1];
    const prefix = parent !== undefined
      ? parent.routine.qualname
      : (className !== null ? `${this.module}.${className}` : this.module);
    const qualname = `${prefix}.${name}`;
    const isAsync = (ts.getCombinedModifierFlags(fn as ts.Declaration)
      & ts.ModifierFlags.Async) !== 0;

    const routine: Routine = {
      id: this.identity(qualname),
      name,
      qualname,
      module: this.module,
      file: this.path,
      line_start: this.startLine(node),
      line_end: this.endLine(node),
      body_hash: hashSource(this.text(fn.body ?? node)),
    };
    const params = this.params(fn);
    if (params.length) routine.params = params;
    const returns = fn.type ? this.text(fn.type) : null;
    if (returns) routine.returns = returns;
    if (isAsync) routine.is_async = true;
    if (className !== null) {
      routine.is_method = true;
      routine.class_name = className;
    }
    if (parent !== undefined) routine.is_nested = true;
    if (name.startsWith("_") || name.startsWith("#")) routine.visibility = "private";
    const doc = this.jsdoc(node);
    if (doc) routine.docstring = doc;
    const comments = this.leadingComments(node);
    if (comments.length) routine.comments = comments;
    const decorators = [...this.decorators(node), ...this.fileDirectives];
    // `async function act() { "use server"; … }` — Next.js allows the directive on one
    // function as well as on a file, and both are the same mark on the same kind of thing.
    if (fn.body !== undefined && ts.isBlock(fn.body)) {
      for (const own of this.directivesOf(fn.body.statements)) {
        if (!decorators.includes(own)) decorators.push(own);
      }
    }
    if (decorators.length) routine.decorators = decorators;

    this.routines.push(routine);
    this.anchors.set(node, routine);
    this.anchors.set(fn, routine);
    this.scope.push({ routine, isAsync });
    const savedDepth = this.depth;
    this.depth = 0;
    try {
      // The parameters' defaults are expressions of the *enclosing* routine at runtime and
      // of this one to a reader; taken here, where a reader would look for them.
      for (const p of fn.parameters) {
        if (p.initializer) this.expressionsIn(p.initializer);
      }
      if (fn.body) this.expressionsIn(fn.body);
    } finally {
      this.depth = savedDepth;
      this.scope.pop();
    }
  }

  params(fn: ts.FunctionLikeDeclaration): Param[] {
    return fn.parameters.map((p) => {
      const param: Param = { name: this.text(p.name) };
      if (p.type) param.type = this.text(p.type);
      if (p.initializer) param.default = this.text(p.initializer);
      // `...rest` is TypeScript's only variadic form, and there is no `**kwargs`.
      if (p.dotDotDotToken) param.kind = "vararg";
      return param;
    });
  }

  // ------------------------------------------------------------------ class --- //

  classDecl(node: ts.ClassDeclaration | ts.ClassExpression): void {
    const name = node.name?.text ?? "default";
    const qualname = `${this.module}.${name}`;
    const bases = this.heritage(node);

    this.classes.push({
      name, qualname, module: this.module, file: this.path,
      line: this.startLine(node),
      ...(bases.length ? { bases } : {}),
    });

    const fields: Field_[] = [];
    for (const member of node.members) {
      if (ts.isPropertyDeclaration(member) && member.name) {
        const field: Field_ = { name: this.text(member.name) };
        if (member.type) field.type = this.text(member.type);
        if (member.initializer) field.default = this.text(member.initializer);
        fields.push(field);
      }
    }
    const structure: DataStructure = {
      id: this.identity(`struct\u0000${qualname}`),
      name, kind: "CLASS", module: this.module, file: this.path,
      line: this.startLine(node),
    };
    if (fields.length) structure.fields = fields;
    if (bases.length) structure.bases = bases;
    const doc = this.jsdoc(node);
    if (doc) structure.docstring = doc;
    this.structures.push(structure);

    this.classStack.push(name);
    try {
      for (const member of node.members) {
        if (ts.isMethodDeclaration(member) || ts.isGetAccessor(member)
            || ts.isSetAccessor(member) || ts.isConstructorDeclaration(member)) {
          const mname = ts.isConstructorDeclaration(member)
            ? "constructor"
            : this.text(member.name);
          this.routine(member, mname, member, name);
        } else if (ts.isPropertyDeclaration(member) && member.initializer) {
          // `handler = () => {...}` is a method written as a field, and it is a routine.
          const init = member.initializer;
          if (ts.isArrowFunction(init) || ts.isFunctionExpression(init)) {
            this.routine(init, this.text(member.name), member, name);
          } else {
            this.expressionsIn(init);
          }
        }
      }
    } finally {
      this.classStack.pop();
    }
  }

  heritage(node: ts.ClassLikeDeclaration | ts.InterfaceDeclaration): string[] {
    const out: string[] = [];
    for (const clause of node.heritageClauses ?? []) {
      for (const t of clause.types) out.push(this.text(t));
    }
    return out;
  }

  // -------------------------------------------------------------- structure --- //

  structure(
    node: ts.Node,
    name: string,
    kind: StructureKind,
    fields: Field_[],
    bases: string[],
  ): void {
    const qualname = `${this.module}.${name}`;
    const structure: DataStructure = {
      id: this.identity(`struct\u0000${qualname}`),
      name, kind, module: this.module, file: this.path,
      line: this.startLine(node),
    };
    if (fields.length) structure.fields = fields;
    if (bases.length) structure.bases = bases;
    const doc = this.jsdoc(node);
    if (doc) structure.docstring = doc;
    this.structures.push(structure);
  }

  interfaceFields(node: ts.InterfaceDeclaration): Field_[] {
    const out: Field_[] = [];
    for (const member of node.members) {
      if ((ts.isPropertySignature(member) || ts.isMethodSignature(member)) && member.name) {
        const field: Field_ = { name: this.text(member.name) };
        if (member.type) field.type = this.text(member.type);
        out.push(field);
      }
    }
    return out;
  }

  enumFields(node: ts.EnumDeclaration): Field_[] {
    return node.members.map((m) => {
      const field: Field_ = { name: this.text(m.name) };
      if (m.initializer) field.default = this.text(m.initializer);
      return field;
    });
  }

  // ----------------------------------------------------------------- import --- //

  importDecl(node: ts.ImportDeclaration | ts.ExportDeclaration): void {
    const spec = node.moduleSpecifier;
    if (spec === undefined || !ts.isStringLiteral(spec)) return;
    const module = spec.text;
    const line = this.startLine(node);
    const clause = ts.isImportDeclaration(node) ? node.importClause : node.exportClause;

    if (clause === undefined) {
      // `import "./polyfill"` — a side-effecting import binds no name and is still a
      // dependency, which is the whole of what it says.
      this.imports.push({ module, name: "", alias: "", is_from: false, line });
      return;
    }
    if (ts.isImportClause(clause)) {
      if (clause.name) {
        this.imports.push({
          module, name: "default", alias: clause.name.text, is_from: true, line,
        });
      }
      const bindings = clause.namedBindings;
      if (bindings && ts.isNamespaceImport(bindings)) {
        // `import * as fs from "node:fs"` — the whole module under one name, which is
        // Python's `import x as y`, so `is_from` is false.
        this.imports.push({
          module, name: module, alias: bindings.name.text, is_from: false, line,
        });
      } else if (bindings && ts.isNamedImports(bindings)) {
        for (const el of bindings.elements) {
          const original = el.propertyName?.text ?? el.name.text;
          this.imports.push({
            module, name: original, alias: el.name.text, is_from: true, line,
          });
        }
      }
      return;
    }
    if (ts.isNamedExports(clause)) {
      for (const el of clause.elements) {
        const original = el.propertyName?.text ?? el.name.text;
        this.imports.push({
          module, name: original, alias: el.name.text, is_from: true, line,
        });
      }
    }
  }

  importEquals(node: ts.ImportEqualsDeclaration): void {
    const ref = node.moduleReference;
    if (ts.isExternalModuleReference(ref) && ref.expression
        && ts.isStringLiteral(ref.expression)) {
      this.imports.push({
        module: ref.expression.text, name: ref.expression.text,
        alias: node.name.text, is_from: false, line: this.startLine(node),
      });
    }
  }

  // --------------------------------------------------------------- variable --- //

  variableStatement(node: ts.VariableStatement): void {
    const isConst = (node.declarationList.flags & ts.NodeFlags.Const) !== 0;
    const atModuleScope = this.scope.length === 0;

    for (const decl of node.declarationList.declarations) {
      const init = decl.initializer;
      if (init !== undefined
          && (ts.isArrowFunction(init) || ts.isFunctionExpression(init))
          && ts.isIdentifier(decl.name)) {
        // `const handler = async () => {...}` — a routine written as a binding, which is
        // how most TypeScript functions are written.
        this.routine(init, decl.name.text, node);
        continue;
      }
      if (atModuleScope && init !== undefined && ts.isIdentifier(decl.name)) {
        const name = decl.name.text;
        const constant: Constant = {
          name,
          value: this.text(init),
          line: this.startLine(decl),
        };
        if (decl.type) constant.type = this.text(decl.type);
        if (isConst) constant.is_final = true;
        if (name.startsWith("_")) constant.private = true;
        const why = this.leadingComments(node);
        const first = why[0];
        if (first !== undefined) constant.comment = first.text;
        this.constants.push(constant);
      }
      if (init !== undefined) this.expressionsIn(init);
    }
  }

  // ------------------------------------------------------------------- call --- //

  callExpr(node: ts.CallExpression | ts.NewExpression): void {
    const expr = dotted(node.expression);
    const line = this.startLine(node);

    if (expr) {
      const owner = this.owner();
      // **The checker first, the spelling second** — `pkg.ts` says why. A package rule is
      // what the compiler resolved; a name rule is a guess about what somebody called a
      // local variable. Either way it is one boundary and never one from each (rule 40).
      const inPackage = packageBoundary(this.checker, node, this.rules);
      // The global `fetch` called through another name -- asked of the checker only where
      // neither the package nor the spelling has said anything (BACKLOG 4).
      const viaName = inPackage === null && matchCall(this.rules, expr) === null
        && isGlobalFetch(this.checker, node) ? "fetch" : "";
      const named = matchCall(this.rules, viaName || expr);
      const rule: BoundaryRule | null = inPackage !== null
        ? {
            kind: inPackage.rule.kind,
            direction: inPackage.rule.direction,
            salience: inPackage.rule.salience,
            exact: new Set(), prefix: [], method: new Set(), subscript: new Set(),
            contains: [], targetArg: 0, target: inPackage.rule.target,
          }
        : named;
      const site = this.recordCall(owner.id, expr, line, rule !== null,
                                   this.callArgs(node), isConstruction(node));
      this.callNodes.push({ site, node });
      if (rule !== null) {
        const hit: BoundaryHit = {
          routine_id: owner.id,
          kind: rule.kind as BoundaryHit["kind"],
          direction: rule.direction as BoundaryHit["direction"],
          target: this.target(node, expr, rule.target, rule.targetArg,
                              inPackage?.pkg ?? ""),
          line,
          evidence: expr,
        };
        if (rule.salience !== "normal") hit.salience = rule.salience;
        this.boundaries.push(hit);
      }
      this.maybeNetwork(node, expr, line, viaName || expr);
    }
    // **Outside the `expr` test, and that is the fix rather than the shape it started
    // in.** A `.map`/`.filter`/`.forEach` chain is a loop that is an expression, and
    // whether its receiver can be *named* is a different question: `["a","b"].map(fn)`
    // has no dotted form by clause 3, so no call is recorded — correctly — but the loop
    // is still there, and Python records `[f(x) for x in ["a", "b"]]` without hesitation.
    // Rule 3 governs what may be matched against a rule, never whether a span exists.
    this.maybeComprehension(node);

    if (ts.isCallExpression(node)) this.expressionsIn(node.expression);
    // A hook's callback is walked as a **routine** rather than as an expression of the
    // component, so what an effect touches is filed under the effect (rule 10).
    const claimed = this.hookRoutine(node, expr);
    (node.arguments ?? []).forEach((arg, idx) => {
      if (claimed && idx === 0) return;
      this.expressionsIn(arg);
    });
  }

  /**
   * `useEffect(() => {…})` — the callback is where a React component does the things this
   * tool records, and chunk 9 filed every one of them under the component that merely
   * declares the effect.
   *
   * **The name is stated, never invented** (rule 30), and the source spells it two ways.
   * Where the hook's call is bound to a name, that is the name — `const createFile =
   * useCallback(…)` is **createFile**, and it is also the only way that arrow becomes a
   * routine at all, since `variableStatement` looks for a function and finds a call.
   * Where it is not, the routine is the hook's own word, which is written at that line.
   *
   * Which hooks are data (`detectors/typescript.yaml`), so React Query or a house hook is
   * an edit there. An arrow that is not the first argument is not a callback in any of
   * them, and a hook handed a named function already has a routine.
   */
  hookRoutine(node: ts.CallExpression | ts.NewExpression, expr: string): boolean {
    if (!expr || !this.rules.hookCallbacks.has(expr)) return false;
    const fn = (node.arguments ?? [])[0];
    if (fn === undefined || !(ts.isArrowFunction(fn) || ts.isFunctionExpression(fn))) {
      return false;
    }
    const parent = node.parent as ts.Node | undefined;
    if (parent !== undefined && ts.isVariableDeclaration(parent)
        && ts.isIdentifier(parent.name)) {
      this.routine(fn, parent.name.text, fn);
      return true;
    }
    this.routine(fn, this.freeHookName(expr), fn);
    return true;
  }

  /**
   * `useEffect`, then `useEffect#2` — and the ordinal is in the **qualname**, not only in
   * the id.
   *
   * Found by running chunk 11d on uigen: two effects in one component are two routines
   * with one qualname, and `NAME_COLLISION` read that exactly as it is written to —
   * *defined 2 times, only the last one exists at run time* — at **BROKEN**, out of a
   * command that gates CI on BROKEN. The program is fine; the name was this reader's.
   *
   * So the two cases are kept apart rather than the detector being taught an exception. A
   * name the *program* chose twice is a collision and is the finding; a name **this reader
   * applies by convention** is expected to repeat, and it carries the ordinal that says
   * which one it is. The residue is the one `call_site_id` already states: an ordinal is a
   * position, and inserting an effect above another renames it.
   */
  freeHookName(word: string): string {
    const top = this.scope[this.scope.length - 1];
    const prefix = top !== undefined ? top.routine.qualname : this.module;
    let name = word;
    let n = 1;
    while (this.seenQualnames.has(`${prefix}.${name}`)) {
      n += 1;
      name = `${word}#${n}`;
    }
    return name;
  }

  /**
   * The directive prologue of a file or of a function body — `"use client"`, `"use server"`.
   *
   * A word written above the thing it marks, which is what a decorator is, so it is
   * recorded in `decorators` and needs no column of its own. Only the leading run of bare
   * string statements is a prologue: a string in the middle of a body is an expression
   * somebody wrote, and reading one as a directive would be the language's own rule
   * loosened for convenience.
   */
  directivesOf(statements: ts.NodeArray<ts.Statement>): string[] {
    const found: string[] = [];
    for (const stmt of statements) {
      if (!ts.isExpressionStatement(stmt)) break;
      const expr = stmt.expression;
      if (!ts.isStringLiteral(expr) && !ts.isNoSubstitutionTemplateLiteral(expr)) break;
      if (this.rules.directives.has(expr.text)) found.push(expr.text);
    }
    return found;
  }

  /**
   * `<PageHero title={x}>…</PageHero>` — a call, with its props for arguments.
   *
   * **Three things it deliberately does not do**, each of which was the obvious thing:
   *
   * - **It does not offer the tag to the boundary rules.** `matchCall` would put `<Link>`
   *   in front of every `method:` and `prefix:` list in the file, and a component named
   *   `Command` or `Image` matching one is rule 5 arriving through a door nobody was
   *   watching. A component is a routine of this program; a boundary is what leaves it.
   * - **Children are not arguments.** They are rendered output, and calling a page's whole
   *   body argument 0 would store the file twice, once as source and once as an `expr`
   *   (rule 8 cuts the other way here — the whole of a thing, but only where the thing is
   *   the argument).
   * - **It is not a construction.** `is_construction` says `new`, and JSX writes none.
   *
   * The closing tag is not a second call: `forEachChild` reaches it, and a `JsxClosingElement`
   * holds nothing but the name.
   */
  jsxElement(node: ts.JsxOpeningLikeElement): void {
    if (namesAValue(node.tagName)) {
      const expr = dotted(node.tagName);
      if (expr) {
        const owner = this.owner();
        const site = this.recordCall(owner.id, expr, this.startLine(node), false,
                                     this.jsxProps(node), false);
        this.callNodes.push({ site, node });
      }
    }
    // The props' own expressions are this routine's work whatever the tag is: a handler
    // written inline on a `<button>` calls what it calls.
    this.expressionsIn(node.attributes);
  }

  /**
   * A component's props, as keyword arguments — because that is what they are.
   *
   * `{...rest}` is `splat`, the same field TypeScript's `...args` and Python's `*args`
   * already use. A **boolean shorthand** — `<Field disabled/>` — carries the keyword and
   * an empty `expr`, because the program wrote no value there: React's transform supplies
   * `true`, and putting `true` in a column headed *as written* would be this reader
   * inventing the one word the file does not contain (rule 30).
   */
  jsxProps(node: ts.JsxOpeningLikeElement): CallArg[] {
    const out: CallArg[] = [];
    node.attributes.properties.forEach((attr, idx) => {
      if (ts.isJsxSpreadAttribute(attr)) {
        out.push({ idx, expr: this.text(attr.expression), splat: true });
        return;
      }
      const init = attr.initializer;
      const expr = init === undefined
        ? ""
        : (ts.isJsxExpression(init) ? this.text(init.expression) : this.text(init));
      out.push({ idx, expr, keyword: this.text(attr.name) });
    });
    return out;
  }

  callArgs(node: ts.CallExpression | ts.NewExpression): CallArg[] {
    const out: CallArg[] = [];
    (node.arguments ?? []).forEach((arg, idx) => {
      const rec: CallArg = { idx, expr: this.text(arg) };
      // `...rest` is TypeScript's spread, which is Python's `*args` at a call site.
      if (ts.isSpreadElement(arg)) rec.splat = true;
      out.push(rec);
    });
    return out;
  }

  /**
   * What is being touched, by the strategy the rule declares (`rules.TargetKind`).
   *
   * `arg` is the original: the literal where it is knowable, the expression where not.
   * `receiver_tail` is the segment before the method, which is where Prisma and every
   * client shaped like it names the thing — `db.booking.findMany(…)` touches **booking**,
   * where the argument is `{ where: { email } }` and names nothing at all. `package` is
   * the dependency, for a rule the checker matched: what a `stripe` call touches is
   * Stripe, and the expression is already in `evidence`.
   */
  target(
    node: ts.CallExpression | ts.NewExpression,
    expr: string,
    kind: TargetKind,
    idx: number | null,
    pkg: string,
  ): string {
    if (kind === "package") return pkg;
    if (kind === "receiver_tail") {
      const parts = expr.split(".");
      // **A promise's own methods are dropped first.** `db.user.update({…}).catch(…)`
      // folds to `db.user.update.catch` by clause 2 of the dotted contract, so the model
      // is two segments back rather than one — 1 of DunneCorp's 130 rows, which named
      // `update` where every other row named a table. The list is here rather than in the
      // YAML because it is a fact about the language and not about any library.
      while (parts.length > 1 && PROMISE_TAIL.has(parts[parts.length - 1] ?? "")) {
        parts.pop();
      }
      // `db.booking.findMany` -> booking; `db.$transaction` -> db. Two segments have no
      // tail beyond the root, and the root is then the most specific thing written.
      return parts.length >= 3
        ? (parts[parts.length - 2] ?? "")
        : (parts[0] ?? "");
    }
    if (idx === null) return "";
    const arg = (node.arguments ?? [])[idx];
    if (arg === undefined) return "";
    if (ts.isStringLiteral(arg) || ts.isNoSubstitutionTemplateLiteral(arg)) return arg.text;
    return this.text(arg);
  }

  /**
   * `process.env.PORT` — a property read, not a call, and the analogue of
   * `os.environ["X"]`. Both spellings arrive here: TypeScript writes the dotted form far
   * more often, and a rule declaring `subscript: [process.env]` serves both.
   */
  accessBoundary(node: ts.PropertyAccessExpression | ts.ElementAccessExpression): boolean {
    // **A property access that is being *called* belongs to the call rule, not to this
    // one.** `localStorage.setItem("seen", "1")` matches `exact: [localStorage.setItem]`
    // with the key as its target, and it also sits on `subscript: [localStorage]` — so
    // both fired and the map held two DATABASE rows for one act, one targeting `seen` and
    // one targeting `setItem`. Rule 40: two detectors recording one act is two numbers
    // about one thing. `process.env.PORT` is not called and so is still this rule's.
    const parent = node.parent as ts.Node | undefined;
    if (parent !== undefined
        && (ts.isCallExpression(parent) || ts.isNewExpression(parent))
        && parent.expression === node) {
      return false;
    }
    const base = dotted(node.expression);
    if (!base) return false;
    const rule = matchSubscript(this.rules, base);
    if (rule === null) return false;

    let target: string;
    if (ts.isPropertyAccessExpression(node)) {
      if (ts.isPrivateIdentifier(node.name)) return false;
      target = node.name.text;
    } else {
      const arg = node.argumentExpression;
      target = ts.isStringLiteral(arg) || ts.isNoSubstitutionTemplateLiteral(arg)
        ? arg.text
        : (this.text(arg) || "?");
    }
    const line = this.startLine(node);
    const key = `${base}\u0000${target}\u0000${line}`;
    if (this.boundarySeen.has(key)) return true;
    this.boundarySeen.add(key);

    const hit: BoundaryHit = {
      routine_id: this.owner().id,
      kind: rule.kind as BoundaryHit["kind"],
      direction: rule.direction as BoundaryHit["direction"],
      target,
      line,
      evidence: `${base}[...]`,
    };
    if (rule.salience !== "normal") hit.salience = rule.salience;
    this.boundaries.push(hit);
    return true;
  }

  maybeNetwork(node: ts.CallExpression | ts.NewExpression, expr: string, line: number,
               matchAs: string = expr): void {
    // `matchAs` is what the call is known to be, `expr` what it was written as. They differ
    // only for the global `fetch` reached through another name (BACKLOG 4).
    const lib = matchNetwork(this.rules, matchAs);
    if (lib === null) return;
    const last = expr.slice(expr.lastIndexOf(".") + 1).toLowerCase();
    const call: NetworkCall = {
      routine_id: this.owner().id,
      expr,
      protocol: lib.protocol,
      line,
    };
    if (this.rules.netVerbs.has(last)) call.verb = last.toUpperCase();
    const first = (node.arguments ?? [])[0];
    if (first !== undefined) {
      call.destination = ts.isStringLiteral(first) || ts.isNoSubstitutionTemplateLiteral(first)
        ? first.text
        : this.text(first);
    }
    if (lib.isAsync) call.is_async = true;
    if (this.isAwaited(node)) call.awaited = true;
    if (this.inAsyncRoutine()) call.in_async_routine = true;
    // The option bag, read **only where it is written literally** — an options object
    // assembled elsewhere is a value nobody here has evaluated.
    const bag = (node.arguments ?? [])[1];
    if (bag !== undefined && ts.isObjectLiteralExpression(bag)) {
      for (const [field, keys] of this.rules.netKwargs) {
        for (const prop of bag.properties) {
          if (!ts.isPropertyAssignment(prop) || !prop.name) continue;
          const key = ts.isIdentifier(prop.name) || ts.isStringLiteral(prop.name)
            ? prop.name.text
            : "";
          if (keys.has(key)) {
            (call as unknown as Record<string, unknown>)[field] =
              this.text(prop.initializer);
            break;
          }
        }
      }
    }
    this.network.push(call);
  }

  isAwaited(node: ts.Node): boolean {
    const parent = node.parent as ts.Node | undefined;
    return parent !== undefined && ts.isAwaitExpression(parent);
  }

  // --------------------------------------------------------------- control --- //

  nextControlOrdinal(routineId: string, kind: string, header: string): number {
    const key = `${routineId}\u0000${kind}\u0000${header}`;
    const n = this.controlOrdinal.get(key) ?? 0;
    this.controlOrdinal.set(key, n + 1);
    return n;
  }

  addPoint(
    node: ts.Node,
    kind: ControlKind,
    header: string,
    word: string,
    arms: number,
    exits = "",
    once: [number, number] = [0, 0],
  ): ControlPoint {
    const routineId = this.owner().id;
    const ordinal = this.nextControlOrdinal(routineId, kind, header);
    const point: ControlPoint = {
      point_id: controlPointId(routineId, kind, header, ordinal),
      routine_id: routineId,
      kind,
      line_start: this.startLine(node),
      line_end: this.endLine(node),
      depth: this.depth,
    };
    if (header) point.header = header;
    if (arms !== 1) point.arms = arms;
    if (exits) point.exits = exits;
    if (word) point.word = word;
    if (once[0]) {
      point.once_start = once[0];
      point.once_end = once[1];
    }
    this.control.push(point);
    return point;
  }

  addArm(point: ControlPoint, idx: number, kind: ArmKind, node: ts.Node, header = ""): void {
    const arm: ControlArm = {
      point_id: point.point_id,
      routine_id: point.routine_id,
      idx,
      kind,
      line_start: this.startLine(node),
      line_end: this.endLine(node),
    };
    if (header) arm.header = header;
    this.controlArms.push(arm);
  }

  inside(fn: () => void): void {
    this.depth += 1;
    try {
      fn();
    } finally {
      this.depth -= 1;
    }
  }

  /** Returns true when the node was a control point and has been walked. */
  controlPoint(node: ts.Node): boolean {
    if (ts.isIfStatement(node)) {
      // An `else if` is an `if` in the `elseStatement` of an `if`, exactly as Python's
      // `elif` is an `If` in an `orelse`. Flattened here for the same reason: the tree
      // shape says "2 arms" seven times where a reader sees one decision with seven ways
      // out. TypeScript's word for the rung is `else if`, two words, and `ArmKind` carries
      // it as written.
      if (this.isElseIfRung(node)) return false;
      this.ifLadder(node);
      return true;
    }
    if (ts.isSwitchStatement(node)) {
      this.switchStatement(node);
      return true;
    }
    if (ts.isTryStatement(node)) {
      this.tryStatement(node);
      return true;
    }
    if (ts.isForOfStatement(node) || ts.isForInStatement(node)) {
      this.forInOf(node);
      return true;
    }
    if (ts.isForStatement(node)) {
      this.forStatement(node);
      return true;
    }
    if (ts.isWhileStatement(node)) {
      this.whileStatement(node);
      return true;
    }
    if (ts.isDoStatement(node)) {
      this.doStatement(node);
      return true;
    }
    return false;
  }

  isElseIfRung(node: ts.IfStatement): boolean {
    const parent = node.parent as ts.Node | undefined;
    return parent !== undefined && ts.isIfStatement(parent) && parent.elseStatement === node;
  }

  ifLadder(node: ts.IfStatement): void {
    const rungs: ts.IfStatement[] = [];
    let cursor: ts.IfStatement | undefined = node;
    let tail: ts.Statement | undefined;
    while (cursor !== undefined) {
      rungs.push(cursor);
      const other: ts.Statement | undefined = cursor.elseStatement;
      if (other !== undefined && ts.isIfStatement(other)) {
        cursor = other;
      } else {
        tail = other;
        cursor = undefined;
      }
    }
    const header = this.text(node.expression);
    const exits = rungs.length === 1 && tail === undefined
      ? this.leavesWith(node.thenStatement)
      : "";
    const kind: ControlKind = exits ? "GUARD" : "DECISION";
    const arms = rungs.length + (tail !== undefined ? 1 : 0);
    const point = this.addPoint(node, kind, header, "if", arms, exits);

    rungs.forEach((rung, i) => {
      this.addArm(point, i, i === 0 ? "if" : "else if", rung.thenStatement,
                  this.text(rung.expression));
    });
    if (tail !== undefined) this.addArm(point, rungs.length, "else", tail);

    this.inside(() => {
      for (const rung of rungs) {
        this.expressionsIn(rung.expression);
        this.expressionsIn(rung.thenStatement);
      }
      if (tail !== undefined) this.expressionsIn(tail);
    });
  }

  /**
   * How a one-armed decision leaves. Recorded rather than inferred from the header,
   * because `if (!x) return` and `if (!x) throw` are the same sentence and opposite facts.
   */
  leavesWith(body: ts.Statement): string {
    const statements = ts.isBlock(body) ? [...body.statements] : [body];
    const last = statements[statements.length - 1];
    if (last === undefined) return "";
    if (ts.isReturnStatement(last)) return "return";
    if (ts.isThrowStatement(last)) return "throw";
    if (ts.isContinueStatement(last)) return "continue";
    if (ts.isBreakStatement(last)) return "break";
    return "";
  }

  switchStatement(node: ts.SwitchStatement): void {
    const header = this.text(node.expression);
    const clauses = node.caseBlock.clauses;
    const point = this.addPoint(node, "DECISION", header, "switch", clauses.length || 1);
    clauses.forEach((clause, i) => {
      const isDefault = ts.isDefaultClause(clause);
      this.addArm(point, i, isDefault ? "default" : "case", clause,
                  isDefault ? "" : this.text(clause.expression));
    });
    this.inside(() => {
      this.expressionsIn(node.expression);
      for (const clause of clauses) {
        for (const s of clause.statements) this.expressionsIn(s);
      }
    });
  }

  tryStatement(node: ts.TryStatement): void {
    const arms = 1 + (node.catchClause ? 1 : 0) + (node.finallyBlock ? 1 : 0);
    const point = this.addPoint(node, "HANDLER", "", "try", arms);
    let idx = 0;
    this.addArm(point, idx++, "try", node.tryBlock);
    if (node.catchClause) {
      // TypeScript's word is `catch`, and `ArmKind.EXCEPT` is Python's. Spelling one
      // language's arm with the other's word is the same defect as renaming it.
      this.addArm(point, idx++, "catch", node.catchClause,
                  node.catchClause.variableDeclaration
                    ? this.text(node.catchClause.variableDeclaration)
                    : "");
    }
    if (node.finallyBlock) this.addArm(point, idx, "finally", node.finallyBlock);

    this.inside(() => {
      this.expressionsIn(node.tryBlock);
      if (node.catchClause) this.expressionsIn(node.catchClause.block);
      if (node.finallyBlock) this.expressionsIn(node.finallyBlock);
    });
  }

  forInOf(node: ts.ForOfStatement | ts.ForInStatement): void {
    const word = ts.isForOfStatement(node) && node.awaitModifier ? "for await" : "for";
    const header = `${this.text(node.initializer)} ${ts.isForOfStatement(node) ? "of" : "in"} ${this.text(node.expression)}`;
    // **The lines this point evaluates once, before the first pass** — the iterable's
    // span minus every line a repeated part also occupies. `schema.ControlPoint` states
    // why the subtraction is the fact: a line cannot choose between the iterable and the
    // body, and leaving the range empty is the answer that cannot be wrong (rule 49).
    const once = this.onceRange(node.expression, node.statement);
    const point = this.addPoint(node, "LOOP", header, word, 1, "", once);
    this.addArm(point, 0, "for", node.statement);
    this.inside(() => {
      this.expressionsIn(node.expression);
      this.expressionsIn(node.statement);
    });
  }

  forStatement(node: ts.ForStatement): void {
    const parts = [
      this.text(node.initializer), this.text(node.condition), this.text(node.incrementor),
    ];
    const header = parts.join("; ");
    // The initialiser runs once; the test and the increment repeat.
    const once = node.initializer
      ? this.onceRange(node.initializer, node.statement)
      : ([0, 0] as [number, number]);
    const point = this.addPoint(node, "LOOP", header, "for", 1, "", once);
    this.addArm(point, 0, "for", node.statement);
    this.inside(() => {
      if (node.initializer) this.expressionsIn(node.initializer);
      if (node.condition) this.expressionsIn(node.condition);
      if (node.incrementor) this.expressionsIn(node.incrementor);
      this.expressionsIn(node.statement);
    });
  }

  whileStatement(node: ts.WhileStatement): void {
    // 0/0: a `while`'s test re-runs, so it evaluates nothing once.
    const point = this.addPoint(node, "LOOP", this.text(node.expression), "while", 1);
    this.addArm(point, 0, "while", node.statement);
    this.inside(() => {
      this.expressionsIn(node.expression);
      this.expressionsIn(node.statement);
    });
  }

  doStatement(node: ts.DoStatement): void {
    const point = this.addPoint(node, "LOOP", this.text(node.expression), "do", 1);
    this.addArm(point, 0, "do", node.statement);
    this.inside(() => {
      this.expressionsIn(node.statement);
      this.expressionsIn(node.expression);
    });
  }

  /**
   * A `.map` / `.filter` / `.forEach` chain: a loop that is an expression.
   *
   * Recorded only where the argument **is a function written here**. `xs.map(toName)`
   * passes a name and loops just as surely, but what it loops over is not in this
   * expression and calling it a span would put a line range around something that is one
   * token long (rule 1).
   */
  maybeComprehension(node: ts.CallExpression | ts.NewExpression): void {
    if (!ts.isCallExpression(node)) return;
    // Read off the **property access** rather than off the dotted string, so a receiver
    // with no name still has a method with one.
    if (!ts.isPropertyAccessExpression(node.expression)) return;
    const last = node.expression.name.text;
    if (!ITERATION_METHODS.has(last)) return;
    const first = (node.arguments ?? [])[0];
    if (first === undefined) return;
    if (!ts.isArrowFunction(first) && !ts.isFunctionExpression(first)) return;

    const receiver: ts.Node | undefined = node.expression.expression;
    const header = this.text(node.expression);
    const once = receiver ? this.onceRange(receiver, first) : ([0, 0] as [number, number]);
    // `word` is `""` for a comprehension in Python because it opens with a bracket. Here
    // it opens with the method's own name, which is the word the source wrote.
    this.addPoint(node, "COMPREHENSION", header, last, 1, "", once);
  }

  /**
   * The iterable's span minus every line the repeated part also occupies.
   *
   * Contiguous by construction: the body is strictly after the thing evaluated once, so
   * the subtraction only ever trims an end, and a one-line loop leaves it empty — which
   * is nothing excluded, the answer that cannot be wrong.
   */
  onceRange(evaluated: ts.Node, repeated: ts.Node): [number, number] {
    const start = this.startLine(evaluated);
    let end = this.endLine(evaluated);
    const bodyStart = this.startLine(repeated);
    if (bodyStart <= end) end = bodyStart - 1;
    return end >= start ? [start, end] : [0, 0];
  }

  // -------------------------------------------------------------- literals --- //

  templateLiteral(node: ts.TemplateExpression): void {
    // `${...}` is stood in for with `?`, exactly as an f-string's interpolation is, and the
    // result is marked INTERPOLATED so the host can tell a placeholder from a glob.
    let joined = node.head.text;
    for (const span of node.templateSpans) joined += "?" + span.literal.text;
    this.literal(joined, this.startLine(node), "INTERPOLATED");
    for (const span of node.templateSpans) this.expressionsIn(span.expression);
  }

  // -------------------------------------------------------------- comments --- //

  /** The JSDoc block immediately above, which is TypeScript's docstring. */
  jsdoc(node: ts.Node): string {
    const docs = (node as { jsDoc?: ts.JSDoc[] }).jsDoc;
    const first = docs?.[0];
    if (first === undefined) return "";
    const comment = first.comment;
    if (typeof comment === "string") return comment;
    if (Array.isArray(comment)) return comment.map((c) => c.text ?? "").join("");
    return "";
  }

  /**
   * The `//` comments above a declaration — the WHY, which the code never carries.
   *
   * A JSDoc block is **not** one of these: it is the routine's docstring and is recorded
   * there. Recording it twice would make one sentence two facts (rule 40).
   */
  leadingComments(node: ts.Node): Comment[] {
    const ranges = ts.getLeadingCommentRanges(this.src, node.getFullStart()) ?? [];
    const out: Comment[] = [];
    for (const range of ranges) {
      const raw = this.src.slice(range.pos, range.end);
      if (raw.startsWith("/**")) continue;
      const text = raw.startsWith("//")
        ? raw.slice(2).trim()
        : raw.replace(/^\/\*+/, "").replace(/\*+\/$/, "").trim();
      if (text) out.push({ text, line: this.line(range.pos), leading: true });
    }
    return out;
  }

  decorators(node: ts.Node): string[] {
    const mods = (node as { modifiers?: ts.NodeArray<ts.ModifierLike> }).modifiers;
    const out: string[] = [];
    for (const mod of mods ?? []) {
      if (ts.isDecorator(mod)) out.push(this.text(mod.expression));
    }
    return out;
  }
}

/** The array methods that are a loop written as an expression. */
const ITERATION_METHODS = new Set([
  "map", "filter", "forEach", "reduce", "reduceRight", "flatMap",
  "some", "every", "find", "findIndex", "findLast", "findLastIndex", "sort",
]);

/** The file's own prose: a leading block comment before anything else. */
function moduleDoc(sf: ts.SourceFile, src: string): string {
  const first = sf.statements[0];
  const ranges = ts.getLeadingCommentRanges(src, first ? first.getFullStart() : 0) ?? [];
  const head = ranges[0];
  if (head === undefined) return "";
  const raw = src.slice(head.pos, head.end);
  if (!raw.startsWith("/*")) return "";
  return raw
    .replace(/^\/\*+/, "")
    .replace(/\*+\/$/, "")
    .split("\n")
    .map((l) => l.replace(/^\s*\*ic?\s?/, "").replace(/^\s*\*\s?/, ""))
    .join("\n")
    .trim();
}

/**
 * **The one place a `ts.SourceFile` is made**, and both passes go through it (rule 51).
 *
 * Two parses of one file with different options are two ASTs, and an edge pass walking the
 * second would mint `site_id`s against nodes the extraction never saw — ids that look
 * exactly like ids and match nothing. It is also what makes the checker answerable at all:
 * `getResolvedSignature` answers only for nodes belonging to its own program, so the
 * program's compiler host calls **this** function and the extractor is handed what it
 * built.
 */
export function makeSourceFile(rel: string, source: string): ts.SourceFile {
  const isTsx = rel.endsWith(".tsx") || rel.endsWith(".jsx");
  return ts.createSourceFile(
    rel,
    source,
    { languageVersion: ts.ScriptTarget.Latest, jsDocParsingMode: ts.JSDocParsingMode.ParseAll },
    /* setParentNodes */ true,
    isTsx ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
}

/**
 * One walk of one file, with the extractor left standing so a caller can read more off it.
 *
 * `extractFile` wants the facts; `edges.ts` wants `anchors` and `callNodes`, which are the
 * same walk's by-products. Two walks would be two sets of ordinals.
 */
export function walkFile(
  rel: string,
  source: string,
  rules: RuleSet,
  sf?: ts.SourceFile,
  checker?: ts.TypeChecker,
): Extractor {
  const module = moduleName(rel);
  const ex = new Extractor(rel, module, source, sf ?? makeSourceFile(rel, source), rules);
  ex.checker = checker;
  ex.run();
  return ex;
}

export function extractFile(
  rel: string,
  source: string,
  rules: RuleSet,
  sf?: ts.SourceFile,
  checker?: ts.TypeChecker,
): FileFacts {
  const facts: FileFacts = {
    path: rel,
    lang: "typescript",
    module: moduleName(rel),
    content_hash: hashSource(source),
  };

  const ex = walkFile(rel, source, rules, sf, checker);
  const doc = moduleDoc(ex.sf, source);
  if (doc) facts.doc = doc;

  // **Where the file sits is a declaration**, and the only one a Next.js page makes. Taken
  // after the walk because it needs the routines it recorded: a page's way in points at the
  // component the file default-exports, and a handler's at the function it exported under
  // that verb (`routes.ts`).
  const ways: Entrypoint[] = waysIn(rel, ex.sf, rules, ex.routines, ex.anchors);
  if (ways.length) facts.entrypoints = ways;

  if (ex.routines.length) facts.routines = ex.routines;
  if (ex.calls.length) facts.calls = ex.calls;
  if (ex.boundaries.length) facts.boundaries = ex.boundaries;
  if (ex.structures.length) facts.structures = ex.structures;
  if (ex.classes.length) facts.classes = ex.classes;
  if (ex.imports.length) facts.imports = ex.imports;
  if (ex.constants.length) facts.constants = ex.constants;
  if (ex.control.length) facts.control = ex.control;
  if (ex.controlArms.length) facts.control_arms = ex.controlArms;
  if (ex.literals.length) facts.literals = ex.literals;
  if (ex.network.length) facts.network = ex.network;
  if (ex.literalsDropped) facts.literals_dropped = ex.literalsDropped;
  // Prepared, and claimed by the host only if one of those strings turns out to be a
  // fact (rule 96).
  facts.module_scope = ex.moduleScope();
  return facts;
}
