/**
 * `detectors/typescript.yaml`, as the host sent it, matched the way the host matches it.
 *
 * **The file does not live here and must not.** It arrives in the `open` frame
 * (`detectors.rules_document`), because a plugin carrying its own copy is a second answer
 * that stops moving the moment somebody edits the YAML — and that file is in **this
 * language's** extraction stamp precisely so that an edit re-reads every TypeScript file.
 * (It said *the core key, re-reads every language* until chunk 11; chunk 5 split the
 * fingerprint and left the sentence behind, in three files at once.) What crosses the
 * wire is the document as written; what is here is `detectors.BoundaryRule.matches_call`,
 * transcribed, and it is transcribed rather than shared for the one reason rule 51 admits:
 * a process boundary is the place a rule cannot be moved to.
 *
 * So the transcription is kept to the four tests and nothing else, and `test_typescript.py`
 * puts the same dotted names through both implementations.
 */

export interface BoundaryRule {
  kind: string;
  direction: string;
  salience: string;
  exact: Set<string>;
  prefix: string[];
  method: Set<string>;
  subscript: Set<string>;
  contains: string[];
  targetArg: number | null;
  target: TargetKind;
  /** `when_arg`: the rule applies only for some values of one argument (`ArgCondition`). */
  whenArg: WhenArg | null;
  /** Said on whatever rule matches instead, when `whenArg` could not decide. */
  undecided: string;
  /** A fixed phrase after the evidence (`detectors.EVIDENCE_NOTE`). */
  note: string;
  /** Where the target argument is an object literal, the property to read it from. */
  targetField: string;
}

/**
 * `detectors.ArgCondition`, with two shapes only JavaScript needs. Node decides what
 * `net.connect` reaches by the *shape* of its first argument: a string is a Unix-domain
 * socket's path, a number is a TCP port, and an options object is either, by whether it
 * sets `path`. So `any_string` says a string literal decides yes, and `has_key` says an
 * object literal decides yes when it sets that property and no when it does not.
 * `typescript.yaml` is the only rules file that writes either, so no other reader is
 * handed a key it would ignore (rule 49).
 */
export interface WhenArg {
  index: number;
  in: Set<string>;
  notIn: Set<string>;
  anyString: boolean;
  hasKey: string;
}

/**
 * What to call the thing a boundary touches.
 *
 * `arg` is the original and the default: the argument at `target_arg`, as written, which
 * is right for `readFile(p)` and `console.log("…")` where the thing touched is named in
 * the call. The other two are for the shapes where it is not.
 *
 * `receiver_tail` is the dotted segment before the method — `db.booking.findMany(…)`
 * touches **booking**, and 130 of DunneCorp's rows were recording `{ where: { email } }`
 * instead, which is a piece of an expression rather than a thing the program touches.
 *
 * `package` is the dependency itself, for a rule matched on one: the thing touched *is*
 * Stripe, and the expression as written is already in `evidence`.
 */
export type TargetKind = "arg" | "receiver_tail" | "package";

/** A dependency this program reaches, and what reaching it means. See `pkg.ts`. */
export interface PackageRule {
  /** The package, or a scope with its trailing slash: `@aws-sdk/`. */
  name: string;
  kind: string;
  direction: string;
  salience: string;
  target: TargetKind;
}

export interface NetLibrary {
  prefix: string;
  protocol: string;
  isAsync: boolean;
}

/**
 * A framework that declares its ways in by **where a file sits**.
 *
 * No decorator, no registration call, no export name — Next.js routes on the path, so the
 * path is the declaration. What is declared here is which directories start a route tree,
 * which filenames are a page and which a handler, and which segments are not URL.
 */
export interface RouteRule {
  framework: string;
  kind: string;
  roots: string[];
  pages: Set<string>;
  handlers: Set<string>;
  verbs: Set<string>;
  stripGroups: boolean;
  evidence: string;
}

export interface RuleSet {
  boundaries: BoundaryRule[];
  subscriptIndex: Map<string, BoundaryRule>;
  netLibraries: NetLibrary[];
  netVerbs: Set<string>;
  netKwargs: Map<string, Set<string>>;
  routes: RouteRule[];
  packages: PackageRule[];
  /** Hooks whose first argument is work rather than a value. See `extract.hookRoutine`. */
  hookCallbacks: Set<string>;
  /** Directive prologues worth recording, in the order a file may write them. */
  directives: Set<string>;
}

function asArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((v) => String(v)) : [];
}

/**
 * An unknown `target:` is **refused**, not defaulted.
 *
 * **The default differs by table and that is deliberate.** A `boundaries` rule matched a
 * spelling and says what was passed, so `arg` is right; a `packages` rule matched a
 * dependency and the dependency *is* the thing touched, so `package` is. One default for
 * both would make every package row name its first argument, which for `send({to})` is
 * `{ to }` — a piece of an expression rather than a thing (it is what this chunk went to
 * the trouble of fixing for Prisma).
 *
 * A misspelt strategy that quietly fell back to `arg` would leave every row it governs
 * looking exactly like a rule nobody had thought about — rule 49, in a config file the
 * whole point of which is that somebody can edit it without reading this code.
 */
function asTarget(value: unknown, fallback: TargetKind = "arg"): TargetKind {
  if (value === undefined || value === null) return fallback;
  const word = String(value);
  if (word === "arg" || word === "receiver_tail" || word === "package") return word;
  throw new Error(
    `detectors/typescript.yaml declares target: ${word} — the strategies are arg, ` +
    `receiver_tail and package. A rule whose target nobody reads is a boundary row ` +
    `naming the wrong thing, every time, with nothing to say so.`,
  );
}

export function parseRules(doc: unknown): RuleSet {
  const data = (doc ?? {}) as Record<string, unknown>;
  const boundaries: BoundaryRule[] = [];
  const subscriptIndex = new Map<string, BoundaryRule>();

  for (const raw of (data["boundaries"] as Record<string, unknown>[]) ?? []) {
    const rule: BoundaryRule = {
      kind: String(raw["kind"]),
      direction: String(raw["direction"] ?? "BOTH"),
      salience: String(raw["salience"] ?? "normal"),
      exact: new Set(asArray(raw["exact"])),
      prefix: asArray(raw["prefix"]),
      method: new Set(asArray(raw["method"])),
      subscript: new Set(asArray(raw["subscript"])),
      contains: asArray(raw["contains"]),
      targetArg: raw["target_arg"] === undefined || raw["target_arg"] === null
        ? null
        : Number(raw["target_arg"]),
      target: asTarget(raw["target"]),
      whenArg: asWhenArg(raw["when_arg"]),
      undecided: String(raw["undecided"] ?? ""),
      note: String(raw["note"] ?? ""),
      targetField: String(raw["target_field"] ?? ""),
    };
    boundaries.push(rule);
    for (const s of rule.subscript) subscriptIndex.set(s, rule);
  }

  const network = (data["network"] as Record<string, unknown>) ?? {};
  const libs = (network["libraries"] as Record<string, Record<string, unknown>>) ?? {};
  const netLibraries: NetLibrary[] = Object.entries(libs)
    .map(([prefix, v]) => ({
      prefix,
      protocol: String(v["protocol"] ?? "?"),
      isAsync: Boolean(v["async"] ?? false),
    }))
    // Longest prefix wins, exactly as `load_rules` sorts them, so `axios.` and a bare
    // `fetch` can both be declared without one shadowing the other.
    .sort((a, b) => b.prefix.length - a.prefix.length);

  const netKwargs = new Map<string, Set<string>>();
  for (const [k, v] of Object.entries(
    (network["kwargs"] as Record<string, unknown>) ?? {},
  )) {
    netKwargs.set(k, new Set(asArray(v)));
  }

  const packages: PackageRule[] = Object.entries(
    (data["packages"] as Record<string, Record<string, unknown>>) ?? {},
  )
    .map(([name, v]) => ({
      name,
      kind: String(v["kind"]),
      direction: String(v["direction"] ?? "BOTH"),
      salience: String(v["salience"] ?? "normal"),
      target: asTarget(v["target"], "package"),
    }))
    // Longest first, so a package inside a declared scope can be given its own answer
    // without the scope shadowing it.
    .sort((a, b) => b.name.length - a.name.length);

  const routes: RouteRule[] = ((data["routes"] as Record<string, unknown>[]) ?? []).map(
    (raw) => ({
      framework: String(raw["framework"] ?? ""),
      kind: String(raw["kind"] ?? "HTTP_ROUTE"),
      // Longest first, so `src/app` is matched before `app` and a route tree under `src/`
      // cannot be read as two roots, one of them starting three segments in.
      roots: asArray(raw["roots"]).sort((a, b) => b.length - a.length),
      pages: new Set(asArray(raw["pages"])),
      handlers: new Set(asArray(raw["handlers"])),
      verbs: new Set(asArray(raw["verbs"])),
      stripGroups: raw["strip_groups"] !== false,
      evidence: String(raw["evidence"] ?? raw["framework"] ?? ""),
    }),
  );

  return {
    boundaries,
    subscriptIndex,
    netLibraries,
    netVerbs: new Set(asArray(network["verbs"])),
    netKwargs,
    routes,
    packages,
    hookCallbacks: new Set(asArray((data["hooks"] as Record<string, unknown>)?.["callbacks"])),
    // Only the words matter here; what each one *means* is the host's to print, and a
    // plugin that carried the sentence would be a second place it could be edited.
    directives: new Set(Object.keys(
      (data["directives"] as Record<string, unknown>) ?? {},
    )),
  };
}

/** `BoundaryRule.matches_call`, transcribed. The four tests and nothing else. */
export function matchesCall(rule: BoundaryRule, dotted: string): boolean {
  if (!dotted) return false;
  if (rule.exact.has(dotted)) return true;
  if (rule.prefix.some((p) => dotted.startsWith(p))) return true;
  if (rule.contains.some((c) => dotted.includes(c))) return true;
  if (rule.method.size) {
    const last = dotted.slice(dotted.lastIndexOf(".") + 1);
    // A bare name is a plain function call, not a method on something.
    if (dotted.includes(".") && rule.method.has(last)) return true;
  }
  return false;
}

function asWhenArg(raw: unknown): WhenArg | null {
  if (raw === undefined || raw === null) return null;
  const w = raw as Record<string, unknown>;
  return {
    // A condition with no position decides nothing, and is read as never (rule 49).
    index: typeof w["index"] === "number" ? w["index"] : -1,
    in: new Set(asArray(w["in"])),
    notIn: new Set(asArray(w["not_in"])),
    anyString: w["any_string"] === true,
    hasKey: String(w["has_key"] ?? ""),
  };
}

/** First matching rule wins, so order in the YAML is meaningful. */
export function matchCall(rules: RuleSet, dotted: string): BoundaryRule | null {
  for (const rule of rules.boundaries) {
    if (matchesCall(rule, dotted)) return rule;
  }
  return null;
}

/**
 * `matchCall` with each conditioned rule decided on its call's arguments, by `decide`
 * (yes, no, or `null` for undecided). One that cannot be decided does not match, and its
 * `undecided` sentence is the blind spot of the rule that does.
 */
export function matchCallWith(
  rules: RuleSet, dotted: string, decide: (w: WhenArg) => boolean | null,
): { rule: BoundaryRule | null; blind: string } {
  const blind: string[] = [];
  for (const rule of rules.boundaries) {
    if (!matchesCall(rule, dotted)) continue;
    if (rule.whenArg !== null) {
      const yes = decide(rule.whenArg);
      if (yes === null && rule.undecided) blind.push(rule.undecided);
      if (yes !== true) continue;
    }
    return { rule, blind: blind.join("; ") };
  }
  return { rule: null, blind: blind.join("; ") };
}

export function matchSubscript(rules: RuleSet, dotted: string): BoundaryRule | null {
  return rules.subscriptIndex.get(dotted) ?? null;
}

/**
 * `RuleSet.network_profile`, transcribed — including the clause that makes a bare key
 * exact. `requests.` and `httpx.AsyncClient` are namespace prefixes; `fetch` is a bare
 * name, and a prefix test makes it match `fetchImpl` and `fetchAll` (rule 5). Measured:
 * DunneNote reported exactly one network call and it was `fetchImpl`, a parameter holding
 * an implementation rather than the global.
 */
export function matchNetwork(rules: RuleSet, dotted: string): NetLibrary | null {
  if (!dotted) return null;
  for (const lib of rules.netLibraries) {
    if (dotted === lib.prefix) return lib;
    if (lib.prefix.includes(".") && dotted.startsWith(lib.prefix)) return lib;
  }
  return null;
}
